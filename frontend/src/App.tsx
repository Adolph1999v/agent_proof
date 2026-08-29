import { useEffect, useState } from "react";

type Health = {
  status: "ok";
  service: string;
  version: string;
};

type ScoreCategory = {
  key: string;
  label: string;
  weight: number;
};

type Rubric = {
  candidates: string[];
  categories: ScoreCategory[];
  total_weight: number;
  correctness_is_gate: boolean;
};

type LoadState =
  | { status: "loading" }
  | { status: "ready"; health: Health; rubric: Rubric }
  | { status: "error"; message: string };

const proofContract = [
  ["01", "Preserve intent", "Compare the patch against the original task."],
  ["02", "Challenge behavior", "Generate checks the patch author did not control."],
  ["03", "Return evidence", "Show commands, outputs, and a reproducible verdict."],
] as const;

async function loadFoundation(): Promise<{ health: Health; rubric: Rubric }> {
  const [healthResponse, rubricResponse] = await Promise.all([
    fetch("/api/health"),
    fetch("/api/model-evaluation/rubric"),
  ]);

  if (!healthResponse.ok || !rubricResponse.ok) {
    throw new Error("The local backend did not return a successful response.");
  }

  return {
    health: (await healthResponse.json()) as Health,
    rubric: (await rubricResponse.json()) as Rubric,
  };
}

export default function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let active = true;

    loadFoundation()
      .then((result) => {
        if (active) setState({ status: "ready", ...result });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const message = error instanceof Error ? error.message : "Unknown backend error";
        setState({ status: "error", message });
      });

    return () => {
      active = false;
    };
  }, []);

  const connectionLabel =
    state.status === "ready"
      ? `Backend connected · v${state.health.version}`
      : state.status === "error"
        ? "Backend unavailable"
        : "Connecting to backend";

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#workspace" aria-label="AgentProof workspace">
          <span className="brand-mark" aria-hidden="true">
            AP
          </span>
          <span>
            AgentProof
            <small>Local verification workspace</small>
          </span>
        </a>
        <span className={`connection connection-${state.status}`}>
          <span className="connection-dot" aria-hidden="true" />
          {connectionLabel}
        </span>
      </header>

      <div className="workspace" id="workspace">
        <section className="page-heading" aria-labelledby="page-title">
          <div>
            <p className="kicker">New verification</p>
            <h1 id="page-title">Review an agent-generated change</h1>
            <p>
              Provide the original task, repository, and candidate patch. AgentProof will try to
              disprove the completion claim before a human approves it.
            </p>
          </div>
          <span className="phase-badge">Phase 1 · Foundation</span>
        </section>

        <div className="content-grid">
          <section className="review-card" aria-labelledby="review-heading">
            <div className="card-heading">
              <div>
                <p className="card-kicker">Verification inputs</p>
                <h2 id="review-heading">Candidate change</h2>
              </div>
              <span>Inputs stay local</span>
            </div>

            <form>
              <label htmlFor="repository">
                Repository path
                <input
                  id="repository"
                  name="repository"
                  placeholder="/path/to/repository"
                  type="text"
                />
              </label>

              <label htmlFor="task">
                Original task or issue
                <textarea
                  id="task"
                  name="task"
                  placeholder="Describe what the coding agent was asked to change…"
                  rows={4}
                />
              </label>

              <label htmlFor="patch">
                Candidate patch
                <textarea
                  className="code-input"
                  id="patch"
                  name="patch"
                  placeholder="Paste a unified diff or select a local commit…"
                  rows={8}
                />
              </label>

              <label htmlFor="trace">
                Agent trace <span>Optional</span>
                <input
                  id="trace"
                  name="trace"
                  placeholder="Paste or select the agent's execution trace"
                  type="text"
                />
              </label>

              <div className="form-footer">
                <button type="button" disabled>
                  Start verification
                </button>
                <p>Verification execution becomes available in Phase 2.</p>
              </div>
            </form>
          </section>

          <aside className="side-rail" aria-label="Verification context">
            <section className="status-card" aria-labelledby="status-heading">
              <div className="card-heading compact">
                <div>
                  <p className="card-kicker">Environment</p>
                  <h2 id="status-heading">System status</h2>
                </div>
              </div>
              <dl>
                <div>
                  <dt>API</dt>
                  <dd className={`status-value status-${state.status}`}>{connectionLabel}</dd>
                </div>
                <div>
                  <dt>Verification engine</dt>
                  <dd>Phase 2</dd>
                </div>
                <div>
                  <dt>Approval policy</dt>
                  <dd>Human required</dd>
                </div>
              </dl>
            </section>

            <section className="contract-card" aria-labelledby="contract-heading">
              <div className="card-heading compact">
                <div>
                  <p className="card-kicker">Proof contract</p>
                  <h2 id="contract-heading">What a verdict must show</h2>
                </div>
              </div>
              <ol>
                {proofContract.map(([number, title, body]) => (
                  <li key={number}>
                    <span>{number}</span>
                    <div>
                      <strong>{title}</strong>
                      <p>{body}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          </aside>
        </div>

        <section className="evaluation" aria-labelledby="evaluation-heading">
          <div className="section-heading">
            <div>
              <p className="card-kicker">Model selection</p>
              <h2 id="evaluation-heading">Evaluation contract</h2>
            </div>
            <p>
              Identical patches, prompts, limits, and deterministic settings. Correctness is the
              gate; speed and resource use break ties.
            </p>
          </div>

          {state.status === "ready" ? (
            <div className="evaluation-grid">
              <div className="candidate-list" aria-label="Model candidates">
                <p className="list-label">Candidate models</p>
                {state.rubric.candidates.map((candidate, index) => (
                  <div key={candidate}>
                    <span>0{index + 1}</span>
                    <strong>{candidate}</strong>
                  </div>
                ))}
              </div>
              <div className="rubric-list">
                <p className="list-label">Weighted score</p>
                {state.rubric.categories.map((category) => (
                  <div className="rubric-row" key={category.key}>
                    <span>{category.label}</span>
                    <strong>{category.weight}%</strong>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="state-card" role={state.status === "error" ? "alert" : "status"}>
              {state.status === "error" ? state.message : "Loading the evaluation contract…"}
            </div>
          )}
        </section>
      </div>

      <footer>
        <span>AgentProof · Local-first patch verification</span>
        <span>Reproducible evidence · Human approval</span>
      </footer>
    </main>
  );
}
