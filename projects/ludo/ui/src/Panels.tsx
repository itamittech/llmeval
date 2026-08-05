// Everything beside the board: header, standings, spend, and the agent feed.
//
// The `stack` field is DISPLAYED here and branched on nowhere — that word is
// ADR-0007's rule 4, and tests/stack-independence.test.tsx holds this file to
// it by re-rendering a mutated transcript and diffing the markup.
//
// Feed items are labelled as what a player SAID. Agents lie deliberately;
// nothing here presents a message as a fact about the game.

import { progress, standings, tokensHome, type FeedItem, type GameView } from "./projector";
import { COLORS, type Color } from "./types";

const DOT: Record<Color, string> = {
  red: "#d64545", green: "#3f9c5a", yellow: "#d6a534", blue: "#3f6fbf",
};

function Dot({ color }: { color: Color }) {
  return <span className="dot" style={{ background: DOT[color] }} aria-hidden="true" />;
}

export function Header({ view }: { view: GameView }) {
  const ended = view.gameEnded;
  return (
    <header className="header">
      <div>
        <span className="stack-label">stack: {view.stack}</span>
        {view.seed !== null && <span> · seed {view.seed}</span>}
        {view.profile && <span> · profile {view.profile}</span>}
        {view.maxTurns !== null && <span> · turn {view.turn} / {view.maxTurns}</span>}
      </div>
      <div>
        {ended
          ? <strong>game over: {String(ended.reason)} after {String(ended.turns_played)} turns</strong>
          : view.currentPlayer
            ? <span><Dot color={view.currentPlayer} /> {view.currentPlayer} to play
                {view.lastRoll && view.lastRoll.player === view.currentPlayer
                  && <span> — rolled <strong>{view.lastRoll.value}</strong></span>}
              </span>
            : <span>waiting to start</span>}
      </div>
    </header>
  );
}

export function Standings({ view }: { view: GameView }) {
  return (
    <table className="standings">
      <thead>
        <tr><th>#</th><th>player</th><th>home</th><th>progress</th><th>capt.</th><th>lost</th><th>forfeits</th></tr>
      </thead>
      <tbody>
        {standings(view).map((color, i) => (
          <tr key={color}>
            <td>{i + 1}</td>
            <td><Dot color={color} /> {color}
              {view.players.find((p) => p.color === color)?.agent
                && <span className="muted"> · {view.players.find((p) => p.color === color)?.agent}</span>}
            </td>
            <td>{tokensHome(view, color)}</td>
            <td>{progress(view, color)}</td>
            <td>{view.stats[color].made}</td>
            <td>{view.stats[color].suffered}</td>
            <td>{view.stats[color].forfeits}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Spend({ view }: { view: GameView }) {
  const total = COLORS.reduce((sum, c) => {
    const s = view.spend[c];
    return sum + s.input + s.output + s.cacheRead + s.cacheWrite;
  }, 0);
  if (total === 0) {
    return <p className="muted">No model calls in this transcript — an engine-only game.</p>;
  }
  return (
    <table className="standings">
      <thead><tr><th>player</th><th>calls</th><th>in</th><th>out</th><th>cache r/w</th></tr></thead>
      <tbody>
        {COLORS.map((c) => (
          <tr key={c}>
            <td><Dot color={c} /> {c}</td>
            <td>{view.spend[c].calls}</td>
            <td>{view.spend[c].input}</td>
            <td>{view.spend[c].output}</td>
            <td>{view.spend[c].cacheRead}/{view.spend[c].cacheWrite}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FeedRow({ item }: { item: FeedItem }) {
  return (
    <li className={`feed-${item.kind.replace(" ", "-")}`}>
      <span className="muted">t{item.turn}</span> <Dot color={item.player} />
      <strong> {item.player}</strong> <em>{item.kind}</em>
      {item.extra && <span className="muted"> ({item.extra})</span>}: {item.text}
    </li>
  );
}

export function Feed({ view }: { view: GameView }) {
  if (view.feed.length === 0) {
    return <p className="muted">No agent events yet. What players say here are claims, not facts.</p>;
  }
  const recent = view.feed.slice(-40);
  return (
    <ul className="feed" aria-label="agent activity — claims, not facts">
      {recent.map((item) => <FeedRow key={item.seq} item={item} />)}
    </ul>
  );
}
