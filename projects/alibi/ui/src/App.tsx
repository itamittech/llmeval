// The ALIBI transcript player. Spectators see everything (answered question 6
// carried into game two): every hand, every shown exhibit, every query — but
// the SOLUTION and which documents lied stay sealed until the transcript's own
// game_ended, so scrubbing the timeline replays the mystery honestly.
//
// ADR-0007's rules apply unchanged: fixtures in projects/alibi/games/ drive
// everything, and `stack` is displayed, never branched on.

import { useMemo, useState } from "react";

import { Evaluation } from "./Eval";
import {
  eventsOfType, gameEnded, gameStarted, parseTranscript,
  type EvalResult, type GameEvent,
} from "./types";

const transcriptModules = import.meta.glob("../../games/*.jsonl", {
  query: "?raw", import: "default", eager: true,
}) as Record<string, string>;

const evalModules = import.meta.glob("../../games/*.eval.json", {
  eager: true,
}) as Record<string, { default: EvalResult }>;

function fixtures(): Map<string, { events: GameEvent[]; eval?: EvalResult }> {
  const found = new Map<string, { events: GameEvent[]; eval?: EvalResult }>();
  for (const [path, raw] of Object.entries(transcriptModules)) {
    const name = path.split("/").pop()!;
    const evalEntry = Object.entries(evalModules)
      .find(([p]) => p.endsWith(`${name}.eval.json`));
    found.set(name, { events: parseTranscript(raw), eval: evalEntry?.[1].default });
  }
  return found;
}

export default function App() {
  const games = useMemo(fixtures, []);
  const names = [...games.keys()].sort();
  const [selected, setSelected] = useState(names[0] ?? "");
  const game = games.get(selected);
  const [position, setPosition] = useState(game ? game.events.length : 0);

  if (!game) {
    return <main className="empty">No committed games found in projects/alibi/games/.</main>;
  }
  return (
    <main>
      <header className="chrome">
        <h1>ALIBI</h1>
        <select
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            setPosition(games.get(e.target.value)!.events.length);
          }}
        >
          {names.map((name) => <option key={name}>{name}</option>)}
        </select>
        <input
          type="range"
          min={1}
          max={game.events.length}
          value={Math.min(position, game.events.length)}
          onChange={(e) => setPosition(Number(e.target.value))}
        />
        <span className="muted">{Math.min(position, game.events.length)} / {game.events.length} events</span>
      </header>
      <Player events={game.events} position={Math.min(position, game.events.length)} evaluation={game.eval} />
    </main>
  );
}

export function Player({ events, position, evaluation }: {
  events: GameEvent[]; position: number; evaluation?: EvalResult;
}) {
  const visible = events.slice(0, position);
  const started = gameStarted(events);
  const ended = gameEnded(visible);
  const solved = ended?.payload.reason === "solved";

  return (
    <div className="player">
      <CasePanel started={started} visible={visible} ended={ended} />
      <Feed visible={visible} />
      <aside>
        <ArchivePanel visible={visible} ended={ended} />
        {ended && (
          <section className="panel">
            <h2>{solved ? "Case closed" : ended.payload.reason === "turn_cap" ? "Time called" : "Everyone out"}</h2>
            <p>
              The truth: <strong>{ended.payload.solution.who}</strong> with{" "}
              <strong>{ended.payload.solution.how}</strong> in{" "}
              <strong>{ended.payload.solution.where}</strong>.
            </p>
            <ol className="standings">
              {ended.payload.standings.map((row: any) => (
                <li key={row.player}>
                  <span className={`badge ${row.player}`}>{row.player}</span>
                  {row.solved ? " solved the case" : row.eliminated ? " accused wrongly" : ""}
                  {" — final belief "}{row.belief_dimensions_correct}/3
                </li>
              ))}
            </ol>
          </section>
        )}
        {ended && evaluation && <Evaluation result={evaluation} />}
      </aside>
    </div>
  );
}

function CasePanel({ started, visible, ended }: {
  started: GameEvent; visible: GameEvent[]; ended?: GameEvent;
}) {
  const p = started.payload;
  const dealt = eventsOfType(visible, "case_dealt")[0];
  return (
    <section className="panel case">
      <h2>The case</h2>
      <p className="muted">
        The Nilgiri Sapphire, the Grand Meridian centenary gala. Seed {p.seed},{" "}
        {/* stack is DISPLAYED here and branched on nowhere — ADR-0007 rule 4 */}
        stack {p.stack}{p.profile ? `, profile ${p.profile}` : ""}, cap {p.max_turns} turns.
      </p>
      <table>
        <tbody>
          {p.players.map((player: any) => (
            <tr key={player.color}>
              <td><span className={`badge ${player.color}`}>{player.color}</span></td>
              <td>{player.model ?? player.agent}{player.seat != null ? ` (seat ${player.seat})` : ""}</td>
              <td className="hand">
                {dealt ? dealt.payload.hands[player.color].join(", ") : "dealing…"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">
        Exhibits are spectator-visible; the detectives see only their own.
        {!ended && " The sealed triple stays sealed until the game ends."}
      </p>
    </section>
  );
}

function ArchivePanel({ visible, ended }: { visible: GameEvent[]; ended?: GameEvent }) {
  const generated = eventsOfType(visible, "archive_generated")[0];
  if (!generated) return null;
  const herrings: string[] = ended ? ended.payload.red_herrings : [];
  return (
    <section className="panel archive">
      <h2>The archive</h2>
      <p className="muted small">
        Testimony, not truth. {ended
          ? "The documents that lied are marked now the case is over."
          : "Some of these are lying; nobody is told which until the end."}
      </p>
      <ul>
        {generated.payload.documents.map((doc: any) => (
          <li key={doc.id} className={herrings.includes(doc.id) ? "herring" : ""}>
            <code>{doc.id}</code> <em>({doc.kind})</em> {doc.text}
            {herrings.includes(doc.id) && <strong> — red herring</strong>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Feed({ visible }: { visible: GameEvent[] }) {
  return (
    <section className="panel feed">
      <h2>The investigation</h2>
      <ol>
        {visible.map((event) => {
          const line = describe(event);
          return line ? <li key={event.seq} className={event.type}>{line}</li> : null;
        })}
      </ol>
    </section>
  );
}

function describe(event: GameEvent): React.ReactNode {
  const p = event.payload;
  switch (event.type) {
    case "turn_started":
      return <><span className={`badge ${p.player}`}>{p.player}</span> takes turn {event.turn}</>;
    case "archive_searched":
      return <><span className={`badge ${p.player}`}>{p.player}</span> asks the archivist:{" "}
        <q>{p.query}</q> → {p.results.length ? p.results.join(", ") : "nothing"}</>;
    case "suggestion_made":
      return <><span className={`badge ${p.player}`}>{p.player}</span> suggests{" "}
        <strong>{p.who} / {p.how} / {p.where}</strong>
        {p.note && <> — table note: <q className="claim">{p.note}</q></>}</>;
    case "refutation_made":
      return p.refuter
        ? <><span className={`badge ${p.refuter}`}>{p.refuter}</span> privately shows{" "}
            <span className={`badge ${p.suggester}`}>{p.suggester}</span>:{" "}
            <strong>{p.element}</strong>{p.chosen_by === "engine" ? " (engine's choice)" : ""}</>
        : <>nobody can refute — the table goes quiet</>;
    case "accusation_made":
      return <><span className={`badge ${p.player}`}>{p.player}</span> ACCUSES:{" "}
        <strong>{p.who} / {p.how} / {p.where}</strong> — {p.correct ? "correct" : "wrong"}</>;
    case "detective_eliminated":
      return <><span className={`badge ${p.player}`}>{p.player}</span> is out of the race</>;
    case "belief_declared":
      return <><span className={`badge ${p.player}`}>{p.player}</span> files a belief:{" "}
        {p.who} ({p.confidence.who}), {p.how} ({p.confidence.how}), {p.where} ({p.confidence.where})</>;
    case "agent_reasoning":
      return <><span className={`badge ${p.player}`}>{p.player}</span> <em className="claim">thinks: {p.text}</em></>;
    case "memory_write":
      return <><span className={`badge ${p.player}`}>{p.player}</span> notes ({p.kind}
        {p.about ? `, re ${p.about}` : ""}): <span className="claim">{p.text}</span></>;
    case "guardrail_triggered":
      return <><span className={`badge ${p.player}`}>{p.player}</span> blocked by guardrail{" "}
        <code>{p.rule}</code>: {p.detail}</>;
    case "invalid_action":
      return <><span className={`badge ${p.player}`}>{p.player}</span> invalid {p.phase}: {p.reason}</>;
    default:
      return null;
  }
}
