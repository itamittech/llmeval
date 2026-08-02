"""Dicts, sets, comprehensions, and truthiness.

Run:  python 05_dicts_sets_truthiness.py

Everything here appears in Game._emit_start() and Game._decide().
"""


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# ---------------------------------------------------------------------------
section("1. Dict access: [] raises, .get() doesn't")

config = {"seed": 7, "max_turns": 200}

print("config['seed']            ->", config["seed"])
try:
    config["stack"]
except KeyError as exc:
    print("config['stack']           -> KeyError:", exc)

print("config.get('stack')       ->", config.get("stack"))
print("config.get('stack', 'no') ->", config.get("stack", "no"), "  <-- default")

print("\nThe engine uses .get() when a key is genuinely optional:")
print("    meta = dict(self.config.players.get(color, {}))")
print("...so a colour with no configured metadata yields {} instead of crashing.")


# ---------------------------------------------------------------------------
section("2. setdefault: fill a key only if it's missing")

meta = {"model": "some-model"}
meta.setdefault("agent", "unknown")     # missing -> inserted
meta.setdefault("model", "OVERWRITE")   # present -> left alone
print("meta =", meta)
print("\n'model' was NOT overwritten. setdefault never clobbers.")
print("The engine uses it so explicit config always beats the fallback.")


# ---------------------------------------------------------------------------
section("3. ** unpacking: merge dicts into a new one")

base = {"color": "red"}
extra = {"agent": "bot", "access": "bedrock"}

merged = {**base, **extra}
print("{**base, **extra} ->", merged)

print("\nLater keys win:")
print("{**{'a': 1}, **{'a': 2}} ->", {**{"a": 1}, **{"a": 2}})

print("\nThe engine builds each player entry as:")
print("    players.append({'color': color, **meta})")
print("...one dict with 'color' first, then everything from meta.")


# ---------------------------------------------------------------------------
section("4. Comprehensions: build a collection in one expression")

COLORS = ("red", "green", "yellow", "blue")

squares = [n * n for n in range(6)]
print("list :", squares)

bots = {c: f"bot-{i}" for i, c in enumerate(COLORS)}
print("dict :", bots)

evens = {n for n in range(10) if n % 2 == 0}
print("set  :", evens, "  (note: unordered)")

print("\nenumerate() gives you index AND value:")
for i, c in enumerate(COLORS):
    print(f"   {i} -> {c}")

print("\nThe engine's CLI builds its four bots with exactly this pattern:")
print("    {c: RandomBot(seed * 100 + i) for i, c in enumerate(COLORS)}")


# ---------------------------------------------------------------------------
section("5. Sets: fast membership, but only for hashable things")

moves = [(0, 3, 5), (1, -1, 0), (2, 10, 12)]
allowed = set(moves)

print("allowed =", allowed)
print("(1, -1, 0) in allowed ->", (1, -1, 0) in allowed)
print("(9, 9, 9)  in allowed ->", (9, 9, 9) in allowed)

print("\n`in` on a set is O(1); on a list it scans. With 4 items that's")
print("irrelevant — the real reason the engine uses a set is that it")
print("expresses 'is this one of the moves I authorised?' exactly.")

print("\nUnhashable things cannot go in a set:")
try:
    {[1, 2, 3]}
except TypeError as exc:
    print("   {[1, 2, 3]} -> TypeError:", exc)
print("Lists are mutable, so their hash could change. Python forbids it.")


# ---------------------------------------------------------------------------
section("6. Truthiness: empty things are False")

for value in ([], [1], {}, {"a": 1}, "", "x", 0, 1, None):
    print(f"   bool({value!r:10}) = {bool(value)}")

print("\nSo `if not moves:` means 'if the list is empty'.")
print("And `return bool(captures)` turns a list into a plain True/False.")

print("\nCareful — use `is None` for None, not truthiness:")
count = 0
print(f"   count = 0   ->  `if not count` is {not count}  (misleading!)")
print(f"               ->  `if count is None` is {count is None}  (correct)")
print("\nThe engine writes `if move is None:` because a Move could in principle")
print("be falsy, but only an actual failure returns None.")

print("\nDone. Next: 06_type_hints_and_errors.py")
