"""Protocols and duck typing — how an LLM agent plugs into the engine.

Run:  python 03_protocols_duck_typing.py

This is the single most important idea in the engine's design.
"""

from typing import Protocol


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# ---------------------------------------------------------------------------
section("1. Duck typing: Python cares what an object DOES, not what it IS")

class Dog:
    def speak(self):
        return "woof"


class Robot:
    def speak(self):
        return "beep"


class Rock:
    pass


def make_it_speak(thing):
    return thing.speak()


for obj in (Dog(), Robot()):
    print(f"{type(obj).__name__:8} -> {make_it_speak(obj)}")

print("\nNeither class inherits from anything. They just both have .speak().")
try:
    make_it_speak(Rock())
except AttributeError as exc:
    print("Rock()   -> AttributeError:", exc)
print("The failure happens at RUNTIME, when the method is actually called.")


# ---------------------------------------------------------------------------
section("2. A Protocol makes the expectation explicit and checkable")

class Speaker(Protocol):
    def speak(self) -> str: ...
    #                       ^^^ literally the `...` object, a placeholder body.
    #                       A Protocol declares shape; it holds no logic.


def announce(speaker: Speaker) -> None:
    print("  ", speaker.speak())


print("Dog and Robot satisfy Speaker WITHOUT inheriting from it:")
announce(Dog())
announce(Robot())

print("\nThis is 'structural typing' — matching by shape.")
print("A type checker (mypy/pyright) verifies it before you run.")
print("At runtime, Python still just calls the method and hopes.")


# ---------------------------------------------------------------------------
section("3. Contrast: inheritance forces a compile-time relationship")

from abc import ABC, abstractmethod


class SpeakerBase(ABC):
    @abstractmethod
    def speak(self) -> str: ...


class Cat(SpeakerBase):          # MUST name the base class
    def speak(self):
        return "meow"


print("Cat inherits SpeakerBase ->", Cat().speak())

try:
    class Mute(SpeakerBase):
        pass
    Mute()
except TypeError as exc:
    print("A subclass that forgets speak() cannot be created:")
    print("   TypeError:", exc)

print("\nABC  = 'you must declare that you implement this' (like Java implements)")
print("Protocol = 'if you have the right methods, you qualify'")


# ---------------------------------------------------------------------------
section("4. Why the engine chose Protocol")

class Move:
    def __init__(self, token):
        self.token = token

    def __repr__(self):
        return f"Move({self.token})"


class Decider(Protocol):
    def choose(self, legal_moves: list) -> Move: ...


# An agent. Note what is NOT here: no import of Decider, no inheritance.
class MyLLMAgent:
    name = "my-agent"

    def choose(self, legal_moves):
        return legal_moves[0]


def run_turn(decider: Decider, legal_moves: list) -> Move:
    return decider.choose(legal_moves)


print("run_turn(MyLLMAgent(), ...) ->", run_turn(MyLLMAgent(), [Move(0), Move(1)]))

print("""
The engine lives in one package. The Strands agent and the LangGraph agent
live in SEPARATE packages with deliberately separate dependency trees.

With Protocol, neither agent package has to import the engine to satisfy
its contract — they just need a `choose` method. So the engine stays free
of every agent framework, which is the whole point of ADR-0002.

With inheritance, each agent would need `class X(Decider)` — a hard
compile-time dependency on the engine, in both directions of the build.
""")


# ---------------------------------------------------------------------------
section("5. Python does NOT enforce annotations at runtime")

print("run_turn(Dog(), ...) — Dog has speak(), not choose():")
try:
    run_turn(Dog(), [Move(0)])
except AttributeError as exc:
    print("   AttributeError:", exc)

print("\nThe `decider: Decider` annotation did not block the call.")
print("Annotations are documentation + tooling. They are not runtime checks.")
print("This is why the engine VALIDATES the returned move rather than trusting it.")

print("\nDone. Next: 04_mutability_and_copying.py")
