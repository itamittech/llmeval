import type { EvalResult } from "./types";

function pct(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

/**
 * The eval panel: the committed `.eval.json` beside each race, rendered.
 *
 * Two columns are the point. **Precision** asks whether a unit was spent on an
 * objectively hard stage; **fit** asks whether it was spent on a family that
 * lane is actually bad at. They come apart, and the winner is usually the lane
 * with the better fit — so showing only one would call the winning strategy a
 * mistake.
 */
export function Eval({ result }: { result: EvalResult }) {
  return (
    <section className="eval" aria-label="evaluation">
      <h2>Scored</h2>
      <p className="hint">
        Deterministic, no judge — the tier the runners never saw is in the transcript,
        so the decision can be marked as well as the answer.
      </p>
      <table>
        <thead>
          <tr>
            <th>lane</th><th>cleared</th><th>solo</th><th>precision</th><th>fit</th>
          </tr>
        </thead>
        <tbody>
          {result.lanes.map((lane) => (
            <tr key={lane.player} data-lane={lane.player}>
              <td>{lane.player}</td>
              <td>{lane.stages_cleared}</td>
              <td>{pct(lane.solo_accuracy)}</td>
              <td>{pct(lane.escalation_precision)}</td>
              <td>{pct(lane.escalation_fit)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={`check ${result.self_check.ok ? "ok" : "bad"}`}>
        self-check: {result.self_check.ok ? "ok" : "FAILED"} — {result.self_check.detail}
      </p>
    </section>
  );
}
