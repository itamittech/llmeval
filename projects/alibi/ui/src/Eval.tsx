// The eval panel: the committed .eval.json beside each game, rendered.
// Everything shown here is deterministic — ground truth exists, so these are
// measurements, not judgements (projects/alibi/eval).

import type { EvalResult } from "./types";

export function Evaluation({ result }: { result: EvalResult }) {
  return (
    <section className="panel eval">
      <h2>Scored</h2>
      {!result.checks.standings_match && (
        <p className="warning">Scorer and engine disagree — do not trust this result.</p>
      )}
      <table>
        <thead>
          <tr>
            <th>detective</th><th>rank</th><th>brier</th><th>herrings read</th><th>calls</th>
          </tr>
        </thead>
        <tbody>
          {result.detectives.map((d) => (
            <tr key={d.player}>
              <td><span className={`badge ${d.player}`}>{d.player}</span></td>
              <td>{d.rank}{d.solved ? " ★" : ""}</td>
              <td>{d.beliefs.mean_brier ?? "—"}</td>
              <td>{d.red_herrings_read}</td>
              <td>{d.tokens.calls}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">
        Brier: 0 is clairvoyant, 0.25 is a hedged coin flip, 1 is confidently wrong.
        Herrings read is exposure, not belief — the belief trajectory says who was fooled.
      </p>
    </section>
  );
}
