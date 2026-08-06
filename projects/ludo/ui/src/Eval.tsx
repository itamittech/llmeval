// The eval report for a whole recorded game — the second artifact the
// pipeline produces (games/<name>.eval.json, schema-validated by the eval
// harness before it was committed). Pure like Player: parsed result in,
// markup out, no IO below this line.
//
// Same rule as the transcript player: `stack` and agent labels are DISPLAYED,
// never branched on. Everything shown is read from the result verbatim.

const COLORS = ["red", "green", "yellow", "blue"] as const;

export type EvalResult = {
  game: { file: string; stack: string | null; seed: number | null;
          turns_played: number; reason: string };
  players: Record<string, {
    rank: number;
    position: { tokens_home: number; progress: number; tokens_in_base: number; score: number };
    play: { captures_made: number; captures_suffered: number; turns_forfeited: number };
    efficiency: { llm_calls: number; tokens_in: number; tokens_out: number;
                  reasoning_chars: number };
    negotiation: { messages_sent: number; table_notes: number; memory_writes: number };
  }>;
  judge: null | {
    model: string; runs: number; discarded_unsourced: number;
    agreement_with_outcome: number | null;
    scores: Record<string, Record<string, { mean: number | null }>>;
  };
  totals: { events: number; llm_calls: number; tokens_in: number; tokens_out: number };
};

export function parseEvalResult(raw: string): EvalResult {
  return JSON.parse(raw) as EvalResult;
}

export function EvalPanel({ result }: { result: EvalResult }) {
  const byRank = [...COLORS].sort(
    (a, b) => result.players[a].rank - result.players[b].rank);
  return (
    <section className="eval" aria-label="eval report">
      <h2>Eval report — whole game</h2>
      <p className="muted">
        Deterministic scoring of {result.game.file} (stack {result.game.stack ?? "none"},{" "}
        {result.game.turns_played} turns, {result.game.reason}). Computed from the
        transcript alone; rank is the engine&apos;s own standings, never reordered.
      </p>
      <table className="standings">
        <thead>
          <tr><th>#</th><th>player</th><th>score</th><th>home</th><th>progress</th>
            <th>capt.</th><th>forfeits</th><th>calls</th><th>tokens</th><th>msgs</th></tr>
        </thead>
        <tbody>
          {byRank.map((color) => {
            const p = result.players[color];
            return (
              <tr key={color}>
                <td>{p.rank}</td>
                <td>{color}</td>
                <td>{p.position.score}</td>
                <td>{p.position.tokens_home}</td>
                <td>{p.position.progress}</td>
                <td>{p.play.captures_made}/{p.play.captures_suffered}</td>
                <td>{p.play.turns_forfeited}</td>
                <td>{p.efficiency.llm_calls}</td>
                <td>{p.efficiency.tokens_in + p.efficiency.tokens_out}</td>
                <td>{p.negotiation.messages_sent + p.negotiation.table_notes}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {result.judge === null ? (
        <p className="muted">
          No judge has scored this game. The judge machinery — anonymisation,
          the seven-dimension rubric, citation enforcement — is built and waits
          on the judge model id; when it runs, its scores land here.
        </p>
      ) : (
        <div>
          <p className="muted">
            Judge {result.judge.model} × {result.judge.runs} runs
            ({result.judge.discarded_unsourced} unsourced scores discarded
            {result.judge.agreement_with_outcome !== null
              && `, agreement with outcome ${result.judge.agreement_with_outcome}`}).
          </p>
          <table className="standings">
            <tbody>
              {byRank.map((color) => (
                <tr key={color}>
                  <td>{color}</td>
                  <td className="muted">
                    {Object.entries(result.judge!.scores[color] ?? {})
                      .filter(([, cell]) => cell.mean !== null)
                      .map(([dim, cell]) => `${dim.split("_")[0]} ${cell.mean}`)
                      .join("  ") || "no sourced scores"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
