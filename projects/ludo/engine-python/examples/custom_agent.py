"""How another project consumes `ludo_engine`.

    uv run --directory projects/ludo/engine-python python examples/custom_agent.py

This is the template each agent stack will follow. A stack replaces the
`choose` body with an LLM call; everything around it stays the same.

Note what is NOT here: no subclassing, no registration, no framework. The
engine asks one question and this file answers it.
"""

from ludo_engine import COLORS, Game, GameConfig, HOME, ListSink, RandomBot, to_square

# Not everything lives in the public API. These are internals of the `board`
# module — importing them directly is allowed, but it's a signal that either
# you're reaching too deep or they deserve promoting to `__all__`.
from ludo_engine.board import LAST_CIRCUIT, is_safe


def would_capture(view, color, move) -> bool:
    """Does this move land on a lone opponent?"""
    if move.to > LAST_CIRCUIT:
        return False
    target = to_square(color, move.to)
    if target is None or is_safe(target):
        return False
    return any(
        any(to_square(other, p) == target for p in positions)
        for other, positions in view.board().items()
        if other != color
    )


class GreedyBot:
    """A hand-written heuristic: capture, then finish, then leave base, then advance.

    Satisfies the engine's `Decider` contract purely by having a `choose`
    method of the right shape — no import of `Decider`, no inheritance.
    """

    name = "greedy-bot"

    def choose(self, ctx):
        # ctx.legal_moves is already validated by the engine. Anything in this
        # list is legal; anything outside it will be rejected.
        for move in ctx.legal_moves:
            if would_capture(ctx.state, ctx.color, move):
                return move

        for move in ctx.legal_moves:
            if move.to == HOME:
                return move

        for move in ctx.legal_moves:
            if move.frm < 0:                       # leaving base
                return move

        return max(ctx.legal_moves, key=lambda m: m.to)


def main() -> None:
    sink = ListSink()

    # Greedy plays red; random bots take the other three seats.
    deciders = {c: RandomBot(seed=i) for i, c in enumerate(COLORS)}
    deciders["red"] = GreedyBot()

    outcome = Game(GameConfig(seed=2026, max_turns=600), sink).play(deciders)

    print(f"reason={outcome.reason}  turns={outcome.turns_played}  "
          f"events={len(sink.events)}")
    for s in outcome.standings:
        marker = "  <- heuristic" if s["player"] == "red" else ""
        print(f"  {s['rank']}. {s['player']:<7} home={s['tokens_home']} "
              f"progress={s['progress']:>3} captures={s['captures_made']}{marker}")

    # The event stream is the only output. A UI or evaluator reads exactly this.
    kinds = {}
    for event in sink.events:
        kinds[event["type"]] = kinds.get(event["type"], 0) + 1
    print("\nevent types emitted:")
    for kind, count in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>5}  {kind}")


if __name__ == "__main__":
    main()
