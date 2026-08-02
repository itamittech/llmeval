"""Classes, `self`, and instance state.

Run:  python 01_classes_and_self.py

The `Game` class in the engine is built entirely from what's here.
"""


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# ---------------------------------------------------------------------------
section("1. A class is a factory for objects that hold their own data")

class Counter:
    # __init__ runs when you write Counter(). It is NOT a constructor that
    # returns something — it receives an already-created empty object as
    # `self` and fills it in.
    def __init__(self, start):
        self.value = start          # `self.value` creates the attribute

    def bump(self):
        self.value += 1


a = Counter(0)
b = Counter(100)
a.bump()
a.bump()
b.bump()
print(f"a.value = {a.value}      b.value = {b.value}")
print("Two objects, two independent `value` attributes.")


# ---------------------------------------------------------------------------
section("2. `self` is just the first parameter — Python passes it for you")

class Greeter:
    def __init__(self, name):
        self.name = name

    def hello(self):
        return f"hello from {self.name}"


g = Greeter("red")
print("g.hello()            ->", g.hello())
print("Greeter.hello(g)     ->", Greeter.hello(g))
print("Identical. `g.hello()` is shorthand for passing g as `self`.")
print("\nThis is why every method in Game starts with `self`:")
print("    def _play_turn(self, color, decider): ...")


# ---------------------------------------------------------------------------
section("3. A leading underscore means 'internal' — by convention only")

class Engine:
    def __init__(self):
        self.turn = 0          # public: others may read this
        self._rotation = -1    # internal: please don't touch

    def next_turn(self):
        self.turn += 1
        self._rotation = (self._rotation + 1) % 4
        return self._rotation


e = Engine()
for _ in range(5):
    e.next_turn()
print(f"after 5 turns:  turn={e.turn}  _rotation={e._rotation}")
print("Nothing STOPS you reading e._rotation:", e._rotation)
print("Python has no `private` keyword. The underscore is a message to humans.")
print("\nThe engine uses this: `self.turn` is public, `self._rotation` is not.")


# ---------------------------------------------------------------------------
section("4. The modulo trick that rotates players forever")

COLORS = ("red", "green", "yellow", "blue")

rotation = -1
order = []
for _ in range(9):
    rotation = (rotation + 1) % len(COLORS)   # % wraps 4 back to 0
    order.append(COLORS[rotation])
print(" -> ".join(order))
print("Starting at -1 means the first (+1) % 4 gives 0, so red goes first.")
print("This is exactly Game._next_player().")


# ---------------------------------------------------------------------------
section("5. @property — a method that looks like an attribute")

class Result:
    def __init__(self, standings):
        self.standings = standings

    @property
    def winner(self):
        return self.standings[0]["player"]


r = Result([{"player": "green", "rank": 1}, {"player": "red", "rank": 2}])
print("r.winner ->", r.winner, "   (no parentheses!)")
print("Computed on access, but reads like data. Outcome.winner does this.")

try:
    r.winner = "blue"
except AttributeError as exc:
    print("\nAssigning to it fails:", exc)
    print("A @property with no setter is read-only.")

print("\nDone. Next: 02_dataclasses.py")
