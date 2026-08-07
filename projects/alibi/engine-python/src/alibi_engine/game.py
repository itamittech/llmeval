"""The turn loop — ALIBI's referee.

Drives a case to a correct accusation, four wrong ones, or the turn cap,
emitting the shared event stream as it goes. Knows nothing about agents beyond
the `Detective` protocol.

Two structural rules a reader should see enforced here rather than trusted:

- **Privacy by construction.** Each detective gets a `DetectiveView` built
  from its own slice of state. Other hands and other shown exhibits are not
  hidden behind an access check — they are simply not in the object.
- **The table is facts.** Refutation is engine-mediated: the engine finds the
  refuter, validates the shown exhibit, and records it. No detective can fake
  a refutation, so every lie in the game stays a claim, never a forged fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .archive import Archive, generate
from .case import ALL_ELEMENTS, COLORS, DIMENSIONS, ELEMENTS, Case, Color, deal
from .deciders import (
    Belief, Detective, DetectiveView, Reflector, SearchBudget, ShowContext,
    Suggestion, SuggestionRecord, Triple, TurnContext, TurnEnd,
)
from .events import EventSink
from .rng import Rng

ENGINE_VERSION = "0.1.0"

#: Chances a detective gets per phase to produce a valid action.
PHASE_ATTEMPTS = 2


@dataclass
class GameConfig:
    seed: int = 1
    max_turns: int = 40
    max_searches_per_turn: int = 2
    ruleset: str = "baseline"
    stack: str = "none"
    #: Per-colour metadata for game_started (agent name, model, access).
    players: dict[Color, dict] = field(default_factory=dict)
    #: Provenance the harness supplies (schema-defined); omitted when None,
    #: which is what keeps conformance vectors byte-stable.
    profile: str | None = None
    prompt_set: dict | None = None
    framework: dict | None = None
    archivist: dict | None = None


@dataclass
class Outcome:
    reason: str
    turns_played: int
    solution: dict
    standings: list[dict]

    @property
    def winner(self) -> Color | None:
        top = self.standings[0]
        return top["player"] if top["solved"] else None


@dataclass
class _PlayerState:
    hand: tuple[str, ...]
    shown: dict[str, Color] = field(default_factory=dict)
    eliminated: bool = False
    last_belief: Belief | None = None
    suggestions_made: int = 0
    refutations_given: int = 0
    searches_made: int = 0


class Game:
    def __init__(self, config: GameConfig, sink: EventSink) -> None:
        self.config = config
        self.sink = sink
        # One RNG, one draw order: the deal consumes first, the archive next.
        rng = Rng(config.seed)
        self.case: Case = deal(rng)
        self.archive: Archive = generate(self.case, rng)
        self.players = {c: _PlayerState(hand=self.case.hands[c]) for c in COLORS}
        self.log: list[SuggestionRecord] = []
        self.turn = 0
        self._rotation = -1
        self._solved_by: Color | None = None
        self._turn_events: list[dict] = []

    # -- public ----------------------------------------------------------

    def play(self, detectives: dict[Color, Detective]) -> Outcome:
        self._emit_start(detectives)
        self._emit("case_dealt", {"hands": {c: list(self.players[c].hand) for c in COLORS}})
        self._emit("archive_generated", {"documents": [d.payload() for d in self.archive.documents]})

        while (self.turn < self.config.max_turns and self._solved_by is None
               and any(not p.eliminated for p in self.players.values())):
            color = self._next_player()
            self.turn += 1
            self._play_turn(color, detectives[color])

        if self._solved_by is not None:
            reason = "solved"
        elif all(p.eliminated for p in self.players.values()):
            reason = "all_eliminated"
        else:
            reason = "turn_cap"

        standings = self._standings()
        self._emit("game_ended", {
            "reason": reason,
            "turns_played": self.turn,
            "solution": dict(self.case.solution),
            "red_herrings": self.archive.red_herrings(),
            "standings": standings,
        })
        return Outcome(reason, self.turn, dict(self.case.solution), standings)

    # -- turn ------------------------------------------------------------

    def _play_turn(self, color: Color, detective: Detective) -> None:
        self._turn_events = []
        self._emit("turn_started", {"player": color})
        budget = self._budget(color)

        suggestion = self._phase_suggest(color, detective, budget)
        refutation: tuple[Color, str] | None = None
        no_refutation: Suggestion | None = None

        if suggestion is not None:
            self.players[color].suggestions_made += 1
            self._emit("suggestion_made", {
                "player": color, "who": suggestion.who, "how": suggestion.how,
                "where": suggestion.where,
                "note": suggestion.note if isinstance(suggestion.note, str) else None,
            })
            refutation, no_refutation = self._resolve_refutation(color, detective, suggestion, budget)

        reason = self._phase_accuse(color, detective, budget, refutation, no_refutation)

        if reason is None:
            reason = "played" if suggestion is not None else "passed"
            self._phase_conclude(color, detective, budget)

        self._emit("turn_ended", {"player": color, "reason": reason})

        if isinstance(detective, Reflector):
            detective.reflect(TurnEnd(
                self._view(color), color, self.turn, reason, tuple(self._turn_events),
            ))

    def _phase_suggest(self, color: Color, detective: Detective,
                       budget: SearchBudget) -> Suggestion | None:
        for attempt in range(1, PHASE_ATTEMPTS + 1):
            ctx = TurnContext(self._view(color), color, self.turn, budget, attempt)
            try:
                suggestion = detective.suggest(ctx)
            except Exception as exc:  # a broken agent passes; it does not crash the game
                self._invalid(color, "suggest", f"decider error: {type(exc).__name__}", attempt)
                continue
            if suggestion is None or self._valid_triple(suggestion):
                return suggestion
            self._invalid(color, "suggest", "unknown element or wrong dimension", attempt)
        return None

    def _resolve_refutation(
        self, suggester: Color, suggester_det: Detective, suggestion: Suggestion,
        budget: SearchBudget,
    ) -> tuple[tuple[Color, str] | None, Suggestion | None]:
        named = set(suggestion.named())
        refuter = next(
            (c for c in self._clockwise_from(suggester)
             if named & set(self.players[c].hand)),
            None,
        )

        if refuter is None:
            self._emit("refutation_made", {
                "suggester": suggester, "refuter": None, "element": None,
            })
            self.log.append(SuggestionRecord(
                self.turn, suggester, suggestion.who, suggestion.how,
                suggestion.where, suggestion.note, None,
            ))
            return None, suggestion

        options = tuple(e for e in self.players[refuter].hand if e in named)
        element, chosen_by = self._phase_show(refuter, suggester, suggestion, options)

        self.players[suggester].shown[element] = refuter
        self.players[refuter].refutations_given += 1
        self._emit("refutation_made", {
            "suggester": suggester, "refuter": refuter,
            "element": element, "chosen_by": chosen_by,
        })
        self.log.append(SuggestionRecord(
            self.turn, suggester, suggestion.who, suggestion.how,
            suggestion.where, suggestion.note, refuter,
        ))
        return (refuter, element), None

    def _phase_show(self, refuter: Color, suggester: Color,
                    suggestion: Suggestion, options: tuple[str, ...]) -> tuple[str, str]:
        """Refutation is compulsory, so unlike a LUDO move it cannot be
        forfeited: an invalid choice falls back to the canonical first option,
        chosen by the engine and visibly recorded as such."""
        detective = self._detectives[refuter]
        ctx = ShowContext(self._view(refuter), refuter, self.turn, suggester,
                          suggestion, options)
        try:
            element = detective.show(ctx)
        except Exception as exc:
            self._invalid(refuter, "show", f"decider error: {type(exc).__name__}", 1)
            return options[0], "engine"
        if element in options:
            return element, "detective"
        self._invalid(refuter, "show", "not a held, named element", 1)
        return options[0], "engine"

    def _phase_accuse(self, color: Color, detective: Detective, budget: SearchBudget,
                      refutation: tuple[Color, str] | None,
                      no_refutation: Suggestion | None) -> str | None:
        """Returns the turn-ending reason if the accusation ended it, else None."""
        triple: Triple | None = None
        for attempt in range(1, PHASE_ATTEMPTS + 1):
            ctx = TurnContext(self._view(color), color, self.turn, budget, attempt,
                              refutation=refutation, no_refutation=no_refutation)
            try:
                candidate = detective.accuse(ctx)
            except Exception as exc:
                self._invalid(color, "accuse", f"decider error: {type(exc).__name__}", attempt)
                continue
            if candidate is None:
                return None
            if self._valid_triple(candidate):
                triple = candidate
                break
            self._invalid(color, "accuse", "unknown element or wrong dimension", attempt)

        if triple is None:
            return None

        correct = (triple.who, triple.how, triple.where) == tuple(
            self.case.solution[d] for d in DIMENSIONS
        )
        self._emit("accusation_made", {
            "player": color, "who": triple.who, "how": triple.how,
            "where": triple.where, "correct": correct,
        })
        if correct:
            self._solved_by = color
            return "solved"
        self.players[color].eliminated = True
        self._emit("detective_eliminated", {"player": color})
        return "eliminated"

    def _phase_conclude(self, color: Color, detective: Detective,
                        budget: SearchBudget) -> None:
        for attempt in range(1, PHASE_ATTEMPTS + 1):
            ctx = TurnContext(self._view(color), color, self.turn, budget, attempt)
            try:
                belief = detective.conclude(ctx)
            except Exception as exc:
                self._invalid(color, "conclude", f"decider error: {type(exc).__name__}", attempt)
                continue
            if self._valid_belief(belief):
                self.players[color].last_belief = belief
                self._emit("belief_declared", {
                    "player": color, "who": belief.who, "how": belief.how,
                    "where": belief.where,
                    "confidence": {d: belief.confidence[d] for d in DIMENSIONS},
                })
                return
            self._invalid(color, "conclude", "invalid belief", attempt)

    # -- plumbing --------------------------------------------------------

    def _budget(self, color: Color) -> SearchBudget:
        def on_search(query: str, results) -> None:
            if results is None:
                self._invalid(color, "search", "search quota exhausted", 1)
                return
            self.players[color].searches_made += 1
            self._emit("archive_searched", {
                "player": color, "query": query,
                "results": [d.id for d in results],
                "quota_left": budget.quota_left,
            })

        budget = SearchBudget(self.archive, self.config.max_searches_per_turn, on_search)
        return budget

    def _view(self, color: Color) -> DetectiveView:
        p = self.players[color]
        return DetectiveView(
            color, p.hand, p.shown,
            tuple(c for c in COLORS if self.players[c].eliminated),
            tuple(self.log),
        )

    def _clockwise_from(self, color: Color) -> list[Color]:
        i = COLORS.index(color)
        return [COLORS[(i + k) % len(COLORS)] for k in range(1, len(COLORS))]

    def _next_player(self) -> Color:
        while True:
            self._rotation = (self._rotation + 1) % len(COLORS)
            color = COLORS[self._rotation]
            if not self.players[color].eliminated:
                return color

    def _valid_triple(self, t) -> bool:
        return (getattr(t, "who", None) in ELEMENTS["who"]
                and getattr(t, "how", None) in ELEMENTS["how"]
                and getattr(t, "where", None) in ELEMENTS["where"])

    def _valid_belief(self, b) -> bool:
        if not self._valid_triple(b):
            return False
        conf = getattr(b, "confidence", None)
        if not isinstance(conf, dict):
            return False
        return all(
            isinstance(conf.get(d), (int, float)) and 0 <= conf[d] <= 1
            for d in DIMENSIONS
        )

    def _invalid(self, color: Color, phase: str, reason: str, attempt: int) -> None:
        self._emit("invalid_action", {
            "player": color, "phase": phase, "reason": reason, "attempt": attempt,
        })

    def _standings(self) -> list[dict]:
        def belief_correct(color: Color) -> int:
            belief = self.players[color].last_belief
            if belief is None:
                return 0
            return sum(
                getattr(belief, d) == self.case.solution[d] for d in DIMENSIONS
            )

        def key(color: Color):
            p = self.players[color]
            solved = color == self._solved_by
            # Solver first; then the still-standing over the eliminated; then
            # sharper final beliefs; then fewer searches (same knowledge,
            # bought cheaper); canonical colour order settles dead heats.
            return (not solved, p.eliminated, -belief_correct(color),
                    p.searches_made, COLORS.index(color))

        ranked = sorted(COLORS, key=key)
        return [
            {
                "player": c,
                "rank": i + 1,
                "solved": c == self._solved_by,
                "eliminated": self.players[c].eliminated,
                "belief_dimensions_correct": belief_correct(c),
                "suggestions_made": self.players[c].suggestions_made,
                "refutations_given": self.players[c].refutations_given,
                "searches_made": self.players[c].searches_made,
            }
            for i, c in enumerate(ranked)
        ]

    # -- emission --------------------------------------------------------

    def _emit(self, type_: str, payload: dict) -> None:
        self._turn_events.append({"type": type_, "payload": payload})
        self.sink.emit(type_, payload, turn=self.turn)

    def _emit_start(self, detectives: dict[Color, Detective]) -> None:
        self._detectives = detectives
        players = []
        for color in COLORS:
            meta = dict(self.config.players.get(color, {}))
            meta.setdefault("agent", getattr(detectives.get(color), "name", "unknown"))
            players.append({"color": color, **meta})

        payload = {
            "seed": self.config.seed,
            "max_turns": self.config.max_turns,
            "max_searches_per_turn": self.config.max_searches_per_turn,
            "ruleset": self.config.ruleset,
            "stack": self.config.stack,
            "engine": {"language": "python", "version": ENGINE_VERSION},
            "case": {
                "suspects": len(ELEMENTS["who"]),
                "methods": len(ELEMENTS["how"]),
                "places": len(ELEMENTS["where"]),
                "archive_documents": len(self.archive.documents),
            },
            "players": players,
        }
        for key in ("profile", "prompt_set", "framework", "archivist"):
            value = getattr(self.config, key)
            if value is not None:
                payload[key] = value
        self._emit("game_started", payload)
