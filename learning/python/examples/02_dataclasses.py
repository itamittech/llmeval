"""Dataclasses: the boilerplate remover — and its one famous trap.

Run:  python 02_dataclasses.py

Covers GameConfig, Outcome, Move, Snapshot from the engine.
"""

from dataclasses import dataclass, field


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# ---------------------------------------------------------------------------
section("1. The boilerplate a dataclass writes for you")

class MoveByHand:
    def __init__(self, token, frm, to):
        self.token = token
        self.frm = frm
        self.to = to

    def __repr__(self):
        return f"MoveByHand(token={self.token}, frm={self.frm}, to={self.to})"

    def __eq__(self, other):
        return (self.token, self.frm, self.to) == (other.token, other.frm, other.to)


@dataclass
class Move:
    token: int
    frm: int
    to: int


print("by hand: ", MoveByHand(0, 3, 5))
print("dataclass:", Move(0, 3, 5))
print("equality: ", Move(0, 3, 5) == Move(0, 3, 5))
print("\nSame behaviour. The @dataclass version is 4 lines instead of 12.")
print("`token: int` is a type ANNOTATION — that's how @dataclass finds the fields.")


# ---------------------------------------------------------------------------
section("2. THE TRAP: a mutable default is shared by every instance")

@dataclass
class Broken:
    name: str = "x"
    players: dict = None      # pretend this was `= {}` — see below


# Python evaluates default values ONCE, when the function is defined.
# So `def f(items=[])` gives EVERY call the SAME list.
def add_bad(item, items=[]):
    items.append(item)
    return items


print("add_bad('a') ->", add_bad("a"))
print("add_bad('b') ->", add_bad("b"), "  <-- 'a' is still there!")
print("add_bad('c') ->", add_bad("c"), "  <-- they all share one list")
print("\nThe list was created once, at def time. Every call mutates that one list.")

print("\n@dataclass refuses to let you make this mistake:")
try:
    @dataclass
    class AlsoBroken:
        players: dict = {}
except ValueError as exc:
    print("   ValueError:", exc)


# ---------------------------------------------------------------------------
section("3. The fix: field(default_factory=...)")

@dataclass
class GameConfig:
    seed: int = 1
    max_turns: int = 200
    # default_factory is a FUNCTION. It is called fresh for each instance.
    players: dict = field(default_factory=dict)


c1 = GameConfig()
c2 = GameConfig()
c1.players["red"] = {"agent": "bot"}
print("c1.players =", c1.players)
print("c2.players =", c2.players, "  <-- unaffected. Separate dicts.")
print("\nThis is why the engine writes:")
print("    players: dict[Color, dict] = field(default_factory=dict)")


# ---------------------------------------------------------------------------
section("4. frozen=True — immutable, and therefore hashable")

@dataclass(frozen=True)
class FrozenMove:
    token: int
    frm: int
    to: int


m = FrozenMove(0, 3, 5)
print("m =", m)
try:
    m.token = 99
except Exception as exc:
    print("m.token = 99  ->", type(exc).__name__ + ":", exc)

print("\nWhy it matters: only hashable objects can go in a set.")
legal = {FrozenMove(0, 3, 5), FrozenMove(1, 0, 6)}
print("FrozenMove(0, 3, 5) in legal ->", FrozenMove(0, 3, 5) in legal)
print("FrozenMove(2, 0, 6) in legal ->", FrozenMove(2, 0, 6) in legal)

print("\nA MUTABLE dataclass cannot be put in a set:")
try:
    {Move(0, 3, 5)}
except TypeError as exc:
    print("   TypeError:", exc)

print("\nGame._decide() does `allowed = set(moves)` then `if move in allowed`.")
print("That single line is why Move is declared frozen.")


# ---------------------------------------------------------------------------
section("5. frozen is SHALLOW — the trap behind the engine's snapshot")

@dataclass(frozen=True)
class Snapshot:
    tokens: dict


live = {"red": [1, 2, 3]}
snap = Snapshot(tokens=live)       # storing a REFERENCE, not a copy

live["red"].append(999)            # mutate the original
print("snap.tokens =", snap.tokens, "  <-- the 'frozen' snapshot changed!")
print("\nfrozen=True stops you REBINDING the field. It does not deep-freeze")
print("what the field points at. A dict inside a frozen dataclass is still a dict.")

safe = Snapshot(tokens={k: list(v) for k, v in live.items()})   # copy on the way in
live["red"].append(1000)
print("\nwith an explicit copy:", safe.tokens, "  <-- unaffected")
print("\nThis is exactly why GameState.snapshot() copies every list.")
print("Get it wrong and the three-sixes rollback silently does nothing.")

print("\nDone. Next: 03_protocols_duck_typing.py")
