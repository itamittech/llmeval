import { useMemo, useState } from "react";

import { Eval } from "./Eval";
import { COLORS, replay, type EvalResult, type GameEvent, type RaceState } from "./types";

const fixtures = import.meta.glob("../../games/*.jsonl", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

const results = import.meta.glob("../../games/*.eval.json", {
  eager: true,
  import: "default",
}) as Record<string, EvalResult>;

function nameOf(path: string): string {
  return path.split("/").pop() ?? path;
}

export function App() {
  const names = useMemo(() => Object.keys(fixtures).map(nameOf).sort(), []);
  const [name, setName] = useState(names[0] ?? "");
  const [cursor, setCursor] = useState(Number.MAX_SAFE_INTEGER);

  const events = useMemo<GameEvent[]>(() => {
    const path = Object.keys(fixtures).find((p) => nameOf(p) === name);
    if (!path) return [];
    return fixtures[path]
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => JSON.parse(line) as GameEvent);
  }, [name]);

  const result = useMemo(() => {
    const path = Object.keys(results).find((p) => nameOf(p) === `${name}.eval.json`);
    return path ? results[path] : undefined;
  }, [name]);

  const last = events.length ? events[events.length - 1].seq : 0;
  const at = Math.min(cursor, last);
  const state = useMemo(() => replay(events, at), [events, at]);

  if (!events.length) {
    return <main className="app">No committed races found in projects/relay/games.</main>;
  }

  return (
    <main className="app">
      <header>
        <h1>RELAY</h1>
        <p className="tagline">
          Four small models race. Any of them may hand a stage to the anchor — and the
          pool they spend from is shared.
        </p>
        <div className="controls">
          <select value={name} onChange={(e) => { setName(e.target.value); setCursor(Number.MAX_SAFE_INTEGER); }}>
            {names.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
          <input
            type="range"
            min={0}
            max={last}
            value={at}
            aria-label="scrub the race"
            onChange={(e) => setCursor(Number(e.target.value))}
          />
          <span className="counter">
            turn {state.turn}/{state.maxTurns} · event {at}/{last}
          </span>
        </div>
      </header>

      <Commons state={state} />
      <Track state={state} />
      <div className="columns">
        <Feed state={state} />
        <aside>
          <Seal state={state} />
          {result ? <Eval result={result} /> : null}
        </aside>
      </div>
    </main>
  );
}

function Commons({ state }: { state: RaceState }) {
  const spent = state.quotaStart - state.quota;
  const pct = state.quotaStart ? (state.quota / state.quotaStart) * 100 : 0;
  return (
    <section className="commons" aria-label="shared quota">
      <h2>The commons</h2>
      <div className="meter">
        <div className="meter-fill" style={{ width: `${pct}%` }} />
      </div>
      <p>
        <strong>{state.quota}</strong> of {state.quotaStart} escalations left
        {state.quota === 0 ? " — the pool is dry" : ""} · {spent} spent
      </p>
    </section>
  );
}

function Track({ state }: { state: RaceState }) {
  return (
    <section className="track" aria-label="the track">
      {COLORS.map((color) => {
        const lane = state.lanes[color];
        return (
          <div className="lane" key={color} data-lane={color}>
            <span className="lane-name">{color}</span>
            <div className="lane-track">
              {state.stages.map((stage, i) => (
                <span
                  key={stage.id}
                  className={`pip ${i < lane.position ? "cleared" : ""} ${i === lane.position && !lane.finished ? "here" : ""}`}
                  title={stage.family}
                />
              ))}
            </div>
            <span className="lane-stats">
              {lane.ticks} ticks · {lane.escalations} esc
              {lane.finished ? " · finished" : ""}
            </span>
          </div>
        );
      })}
    </section>
  );
}

function Feed({ state }: { state: RaceState }) {
  const recent = state.feed.slice(-40).reverse();
  return (
    <section className="feed" aria-label="what happened">
      <h2>The race</h2>
      {recent.map((item) => (
        <p key={`${item.seq}-${item.kind}`} className={`item ${item.kind}`} data-lane={item.player}>
          <span className="turn">t{item.turn}</span>
          <span className="who">{item.player}</span>
          {item.kind === "note" ? <em>“{item.text}”</em> : <span>{item.text}</span>}
          {item.kind === "attempt" && item.escalated ? <span className="tag">anchor</span> : null}
          {/* A pass is not a miss. Tagging it "missed" would read as a wrong
              answer, when the runner declined to give one. */}
          {item.kind === "attempt" && item.answered ? (
            <span className={`tag ${item.correct ? "ok" : "bad"}`}>
              {item.correct ? "cleared" : "missed"}
            </span>
          ) : null}
        </p>
      ))}
    </section>
  );
}

/**
 * The seal, rendered.
 *
 * Before `game_ended` this panel says what it does not know. That is not
 * decoration: a viewer who could see the tiers would know something every
 * runner was forbidden to know, and the replay would stop being an honest
 * account of the race.
 */
function Seal({ state }: { state: RaceState }) {
  if (!state.trackKey) {
    return (
      <section className="seal sealed" aria-label="the sealed track">
        <h2>Sealed</h2>
        <p>
          Every stage has a difficulty tier. Nobody in the race is told it — judging that
          for yourself is the whole game — so it stays sealed here too, until the finish.
        </p>
        <p className="hint">Scrub to the end to open it.</p>
      </section>
    );
  }
  return (
    <section className="seal open" aria-label="the opened track">
      <h2>The key</h2>
      <p className="hint">Revealed at the finish, and never before.</p>
      <table>
        <thead>
          <tr><th>stage</th><th>tier</th><th>answer</th></tr>
        </thead>
        <tbody>
          {state.trackKey.map((entry) => (
            <tr key={entry.id} className={`tier-${entry.tier}`}>
              <td>{entry.id}</td>
              <td>{entry.tier}</td>
              <td>{entry.answer}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
