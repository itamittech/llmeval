"""Type hints, None, and exception handling.

Run:  python 06_type_hints_and_errors.py

Covers the signatures and the try/except in Game._decide().
"""

from __future__ import annotations


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# ---------------------------------------------------------------------------
section("1. Reading a type hint")

def play(deciders: dict[str, object], max_turns: int = 200) -> list[dict]:
    """
    deciders: dict[str, object]   a dict, str keys, object values
    max_turns: int = 200          an int, defaulting to 200
    -> list[dict]                 returns a list of dicts
    """
    return [{"turns": max_turns, "players": len(deciders)}]


print(play({"red": None, "blue": None}))
print("\n    def play(self, deciders: dict[Color, Decider]) -> Outcome:")
print("       'takes a dict of colour -> decider, returns an Outcome'")


# ---------------------------------------------------------------------------
section("2. `X | None` means 'an X, or nothing'")

def find(items: list[int], target: int) -> int | None:
    for i, item in enumerate(items):
        if item == target:
            return i
    return None                       # explicit 'not found'


print("find([10,20,30], 20) ->", find([10, 20, 30], 20))
print("find([10,20,30], 99) ->", find([10, 20, 30], 99))

print("\n`-> Move | None` on Game._decide() is a contract:")
print("   'a Move if the agent produced a legal one, otherwise None'")
print("...which is exactly why the caller writes `if move is None:`")


# ---------------------------------------------------------------------------
section("3. Hints are NOT enforced. Python will not stop you.")

def add(a: int, b: int) -> int:
    return a + b


print("add(1, 2)          ->", add(1, 2))
print("add('x', 'y')      ->", add("x", "y"), "  <-- no error!")
print("\nAnnotations are for humans, editors, and type checkers (mypy/pyright).")
print("The interpreter ignores them. Never rely on them for validation —")
print("which is why the engine re-checks every move against its legal set.")


# ---------------------------------------------------------------------------
section("4. `from __future__ import annotations`")

print("""At the top of most engine modules. It makes Python store annotations
as plain strings instead of evaluating them at import time.

Two practical wins:
  - you can reference a class before it is defined (forward references)
  - no import cost for types used only in signatures

You will see it in nearly every modern Python file. Just accept it.""")


# ---------------------------------------------------------------------------
section("5. try / except — catching a misbehaving agent")

class BrokenAgent:
    def choose(self, ctx):
        raise RuntimeError("model timed out")


def ask(agent):
    try:
        return agent.choose(None)
    except Exception as exc:
        #  `exc` is the exception OBJECT
        #  type(exc)          -> the class, e.g. <class 'RuntimeError'>
        #  type(exc).__name__ -> the class NAME as a string: 'RuntimeError'
        print(f"   caught {type(exc).__name__}: {exc}")
        return None


print("ask(BrokenAgent()) ->", ask(BrokenAgent()))

print("""
The engine records `type(exc).__name__` rather than str(exc) in its event
stream. The class name is a short, stable category ('RuntimeError'); the
message is long, model-dependent, and can leak prompt text into a
transcript that gets committed to a public repo.""")


# ---------------------------------------------------------------------------
section("6. getattr — read an attribute that might not exist")

class Named:
    name = "random-bot"


class Anonymous:
    pass


for obj in (Named(), Anonymous(), None):
    label = getattr(obj, "name", "unknown")
    print(f"   getattr({type(obj).__name__:10}, 'name', 'unknown') -> {label!r}")

print("\nWorks on None too, which is why the engine can write:")
print("    getattr(deciders.get(color), 'name', 'unknown')")
print("...covering both 'no decider for this colour' and 'decider has no name'")
print("in a single expression, with no if-statement.")

print("\nDone — that's every Python concept used in the Game class.")
print("Now read 01-walkthrough-game.md with the real code side by side.")
