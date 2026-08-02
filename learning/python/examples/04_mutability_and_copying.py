"""Mutability, references, and copying — the bug class that hides longest.

Run:  python 04_mutability_and_copying.py

This is the reasoning behind GameState.snapshot() / restore().
"""

import copy


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# ---------------------------------------------------------------------------
section("1. Assignment never copies. It binds another name to one object.")

a = [1, 2, 3]
b = a                # NOT a copy
b.append(4)
print("a =", a)
print("b =", b)
print("a is b ->", a is b, "  (the same object, two names)")

print("\nWith an immutable type the problem cannot arise:")
x = 5
y = x
y += 1
print(f"x = {x}, y = {y}   (ints can't be mutated, so y got a NEW int)")


# ---------------------------------------------------------------------------
section("2. Mutable vs immutable, at a glance")

print("mutable   : list  dict  set  most classes")
print("immutable : int  float  str  bool  tuple  frozenset  frozen dataclass")
print()
t = (1, 2, 3)
try:
    t[0] = 99
except TypeError as exc:
    print("tuple[0] = 99 ->", exc)


# ---------------------------------------------------------------------------
section("3. A shallow copy copies the OUTER container only")

original = {"red": [1, 2], "blue": [3, 4]}

shallow = dict(original)              # new dict, SAME inner lists
shallow["red"].append(999)
print("after mutating shallow['red']:")
print("  original =", original, "  <-- damaged")

original = {"red": [1, 2], "blue": [3, 4]}
deep = {k: list(v) for k, v in original.items()}   # new dict AND new lists
deep["red"].append(999)
print("\nafter mutating a properly copied dict:")
print("  original =", original, "  <-- safe")
print("  copy     =", deep)


# ---------------------------------------------------------------------------
section("4. Three ways to copy, and when each is enough")

nested = {"red": [1, 2]}

print("dict(nested)              -> outer only  (inner lists shared)")
print("{k: list(v) for k,v ...}  -> outer + one level  <-- engine uses this")
print("copy.deepcopy(nested)     -> everything, recursively (slower)")

d = copy.deepcopy(nested)
d["red"].append(7)
print("\ndeepcopy leaves the original alone:", nested)

print("""
The engine uses the middle option deliberately. GameState holds
dict[str, list[int]] — exactly two levels — so a comprehension that
rebuilds the lists is both sufficient and much cheaper than deepcopy.
""")


# ---------------------------------------------------------------------------
section("5. The actual bug this prevents")

class BrokenState:
    def __init__(self):
        self.tokens = {"red": [-1, -1, -1, -1]}

    def snapshot(self):
        return self.tokens               # BUG: hands out a live reference

    def restore(self, snap):
        self.tokens = snap


class GoodState:
    def __init__(self):
        self.tokens = {"red": [-1, -1, -1, -1]}

    def snapshot(self):
        return {k: list(v) for k, v in self.tokens.items()}     # copy out

    def restore(self, snap):
        self.tokens = {k: list(v) for k, v in snap.items()}     # copy in


for cls in (BrokenState, GoodState):
    s = cls()
    before = s.snapshot()          # "save the board at turn start"
    s.tokens["red"][0] = 5         # the player moves a token
    s.tokens["red"][1] = 9         # and another
    s.restore(before)              # three sixes! cancel the whole turn
    status = "OK" if s.tokens["red"] == [-1, -1, -1, -1] else "FAILED TO REVERT"
    print(f"{cls.__name__:12} after restore: {s.tokens['red']}   {status}")

print("""
BrokenState's snapshot IS the live dict, so mutating the board also mutates
the snapshot. restore() then 'reverts' to the already-modified state.

Note the trap: the rule code (`if sixes == 3: restore()`) looks perfectly
correct, and a test asserting `restore was called` would pass. Only a test
that checks the BOARD catches it — which is what test_game.py does.
""")

print("Done. Next: 05_dicts_sets_truthiness.py")
