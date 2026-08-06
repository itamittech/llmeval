// The transcript player. `Player` is the whole rendered game — pure function
// of (events, position) — and `App` wraps it with loading and playback.
// Tests render `Player` directly; nothing below it does IO.

import { useEffect, useMemo, useRef, useState } from "react";

import { Board } from "./Board";
import { EvalPanel, parseEvalResult, type EvalResult } from "./Eval";
import { Feed, Header, Spend, Standings } from "./Panels";
import { project } from "./projector";
import { parseTranscript, type GameEvent } from "./types";

import scriptedRaw from "../../games/scripted-strands-seed7.jsonl?raw";
import sampleRaw from "../../games/sample-seed7.jsonl?raw";
import scriptedEvalRaw from "../../games/scripted-strands-seed7.eval.json?raw";
import sampleEvalRaw from "../../games/sample-seed7.eval.json?raw";

// Each bundled game ships with its committed eval result — the pipeline's
// second artifact. An uploaded transcript has none (run `just score` on it).
const BUNDLED: Record<string, { transcript: string; evalRaw?: string }> = {
  "scripted-strands-seed7 — agents negotiating (43 events)":
    { transcript: scriptedRaw, evalRaw: scriptedEvalRaw },
  "sample-seed7 — engine-only random bots (1803 events)":
    { transcript: sampleRaw, evalRaw: sampleEvalRaw },
};

export function Player({ events, position }: { events: GameEvent[]; position: number }) {
  const view = useMemo(() => project(events, position), [events, position]);
  return (
    <div className="player">
      <Header view={view} />
      <div className="columns">
        <Board view={view} />
        <div className="side">
          <h2>Standings</h2>
          <Standings view={view} />
          <h2>Model spend</h2>
          <Spend view={view} />
          <h2>Table talk &amp; minds</h2>
          <Feed view={view} />
        </div>
      </div>
    </div>
  );
}

export function App() {
  const [name, setName] = useState(Object.keys(BUNDLED)[0]);
  const [events, setEvents] = useState<GameEvent[]>(
    () => parseTranscript(BUNDLED[name].transcript));
  const [evalResult, setEvalResult] = useState<EvalResult | null>(() => {
    const raw = BUNDLED[name].evalRaw;
    return raw ? parseEvalResult(raw) : null;
  });
  const [position, setPosition] = useState(events.length);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(8);
  const timer = useRef<number | null>(null);

  const load = (label: string, raw: string, evalRaw?: string) => {
    const parsed = parseTranscript(raw);
    setName(label);
    setEvents(parsed);
    setEvalResult(evalRaw ? parseEvalResult(evalRaw) : null);
    setPosition(0);
    setPlaying(true);
  };

  useEffect(() => {
    if (!playing) return;
    timer.current = window.setInterval(() => {
      setPosition((i) => {
        if (i >= events.length) { setPlaying(false); return i; }
        return i + 1;
      });
    }, 1000 / speed);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [playing, speed, events]);

  return (
    <main>
      <h1>LUDO transcript player</h1>
      <p className="muted">
        Replays a recorded event stream — the only thing any stack emits and the
        only thing this page reads. Offline, no keys, no backend.
      </p>
      <div className="controls">
        <select value={name} onChange={(e) => load(e.target.value,
            BUNDLED[e.target.value].transcript, BUNDLED[e.target.value].evalRaw)}>
          {Object.keys(BUNDLED).map((label) => <option key={label}>{label}</option>)}
        </select>
        <input type="file" accept=".jsonl" aria-label="open a transcript"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            file.text().then((raw) => load(file.name, raw));
          }} />
        <button onClick={() => setPosition((i) => Math.max(0, i - 1))}>◀ step</button>
        <button onClick={() => setPlaying((p) => !p)}>{playing ? "pause" : "play"}</button>
        <button onClick={() => setPosition((i) => Math.min(events.length, i + 1))}>step ▶</button>
        <label>speed <input type="range" min={1} max={60} value={speed}
          onChange={(e) => setSpeed(Number(e.target.value))} /> {speed}/s</label>
        <label className="seek">seek <input type="range" min={0} max={events.length}
          value={position} onChange={(e) => { setPlaying(false); setPosition(Number(e.target.value)); }} />
          {position}/{events.length}</label>
      </div>
      <Player events={events} position={position} />
      {evalResult && <EvalPanel result={evalResult} />}
    </main>
  );
}
