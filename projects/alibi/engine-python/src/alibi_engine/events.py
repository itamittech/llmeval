"""Event emission.

The engine's only output. Conforms to shared/schemas/alibi-event.schema.json —
the integration contract for the UI and the eval harness (ADR-0003, second
game). Engine events carry no timestamps: two runs of the same seed must
produce byte-identical transcripts so they can be diffed mechanically.

Identical machinery to LUDO's events module by design: the sink is part of the
per-project shape a reader should recognise on sight.
"""

from __future__ import annotations

import json
from typing import Any, TextIO


class EventSink:
    """Assigns sequence numbers and hands events to a destination."""

    def __init__(self) -> None:
        self._seq = 0

    def emit(self, type_: str, payload: dict[str, Any], turn: int = 0) -> dict[str, Any]:
        event = {"seq": self._seq, "turn": turn, "type": type_, "payload": payload}
        self._seq += 1
        self._write(event)
        return event

    def _write(self, event: dict[str, Any]) -> None:
        raise NotImplementedError


class ListSink(EventSink):
    """Collects events in memory. Used by tests and short runs."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, Any]] = []

    def _write(self, event: dict[str, Any]) -> None:
        self.events.append(event)


class JsonlSink(EventSink):
    """Streams events to a JSON Lines file as the game plays."""

    def __init__(self, stream: TextIO) -> None:
        super().__init__()
        self._stream = stream

    def _write(self, event: dict[str, Any]) -> None:
        self._stream.write(json.dumps(event, separators=(",", ":")) + "\n")


class TeeSink(EventSink):
    """Fans out to several sinks while keeping one shared sequence."""

    def __init__(self, *sinks: EventSink) -> None:
        super().__init__()
        self._sinks = sinks

    def _write(self, event: dict[str, Any]) -> None:
        for sink in self._sinks:
            sink._write(event)


def canonical(event: dict[str, Any]) -> str:
    """Stable serialisation, for digests and cross-engine conformance."""
    return json.dumps(event, sort_keys=True, separators=(",", ":"))
