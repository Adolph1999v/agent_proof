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

const verificationSteps = [
  ["01", "Brief", "Task, repo, and patch"],
  ["02", "Challenge", "Independent checks"],
  ["03", "Evidence", "Human decision"],
] as const;

const proofContract = [
  ["Intent", "The patch solves the requested task."],
  ["Behavior", "The patch survives tests it did not write."],
  ["Evidence", "The verdict can be reproduced and reviewed."],
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
      <div className="ambient-field" aria-hidden="true" />

      <header className="topbar">
        <a className="brand" href="#workspace" aria-label="AgentProof workspace">
          <span className="brand-mark" aria-hidden="true">
            <i />
            AP
          </span>
          <span>
            AgentProof
            <small>Local verification workspace</small>
          </span>
        </a>

        <nav className="topnav" aria-label="Workspace sections">
          <span className="topnav-item topnav-item-active">Verifier</span>
          <span className="topnav-item">Model lab</span>
        </nav>

        <div className="topbar-controls">
          <span className="local-mode">
            <i aria-hidden="true" />
            Local-first
          </span>
          <span className={`connection connection-${state.status}`}>
            <span className="connection-dot" aria-hidden="true" />
            {connectionLabel}
          </span>
        </div>
      </header>

      <div className="workspace" id="workspace">
        <section className="page-heading" aria-labelledby="page-title">
          <div className="heading-copy">
            <p className="kicker">Independent patch verification</p>
            <h1 id="page-title">
              Review an agent-generated <em>change.</em>
            </h1>
            <p>
              Turn an AI completion claim into evidence a person can inspect, reproduce, and
              approve with confidence.
            </p>
          </div>

          <aside className="briefing-card" aria-label="Verdict protocol">
            <div className="briefing-topline">
              <span>Verdict protocol</span>
              <span className="protocol-live">Ready</span>
            </div>
            <p>Every verdict needs more than a green test suite.</p>
            <div className="protocol-points">
              <span>Intent</span>
              <i aria-hidden="true" />
              <span>Challenge</span>
              <i aria-hidden="true" />
              <span>Evidence</span>
            </div>
          </aside>
        </section>

        <section className="workspace-stage" aria-labelledby="review-heading">
          <aside className="stage-rail" aria-label="Verification stages">
            <p className="rail-label">Runbook</p>
            <ol>
              {verificationSteps.map(([number, title, body], index) => (
                <li className={index === 0 ? "stage-active" : ""} key={number}>
                  <span>{number}</span>
                  <div>
                    <strong>{title}</strong>
                    <small>{body}</small>
                  </div>
                </li>
              ))}
            </ol>
            <p className="rail-footnote">Phase 1<br />Foundation</p>
          </aside>

          <section className="review-card">
            <div className="review-card-topline">
              <span className="section-id">Verification request</span>
              <span className="draft-state">Draft · local only</span>
            </div>

            <div className="review-heading">
              <div>
                <p className="card-kicker">Step 01</p>
                <h2 id="review-heading">Build a verification brief</h2>
              </div>
              <p>
                Give the verifier the same context as the coding agent—then let it look for what
                was missed.
              </p>
            </div>

            <form>
              <div className="field-grid">
                <label htmlFor="repository">
                  <span>Repository path</span>
                  <input
                    id="repository"
                    name="repository"
                    placeholder="/path/to/repository"
                    type="text"
                  />
                </label>

                <label htmlFor="trace">
                  <span>
                    Agent trace <em>Optional</em>
                  </span>
                  <input
                    id="trace"
                    name="trace"
                    placeholder="Select the agent's execution trace"
                    type="text"
                  />
                </label>
              </div>

              <label htmlFor="task">
                <span>Original task or issue</span>
                <textarea
                  id="task"
                  name="task"
                  placeholder="Describe what the coding agent was asked to change…"
                  rows={4}
                />
              </label>

              <label htmlFor="patch">
                <span>Candidate patch</span>
                <textarea
                  className="code-input"
                  id="patch"
                  name="patch"
                  placeholder="Paste a unified diff or select a local commit…"
                  rows={8}
                />
              </label>

              <div className="form-footer">
                <button type="button" disabled>
                  <span>Start verification</span>
                  <i aria-hidden="true">↗</i>
                </button>
                <p>Execution unlocks in Phase 2. Nothing is sent away from this machine.</p>
              </div>
            </form>
          </section>

          <aside className="outcome-card" aria-labelledby="outcome-heading">
            <div className="outcome-topline">
              <span>Live state</span>
              <span className="not-started">Not started</span>
            </div>

            <div className="signal-orb" aria-hidden="true">
              <span />
              <i />
            </div>

            <h2 id="outcome-heading">Waiting for a request</h2>
            <p>
              AgentProof will challenge the patch, not simply summarize it. The final call remains
              with a human.
            </p>

            <div className="evidence-list">
              {proofContract.map(([title, body]) => (
                <div key={title}>
                  <strong>{title}</strong>
                  <span>{body}</span>
                </div>
              ))}
            </div>

            <div className="api-readout">
              <span>Local API</span>
              <strong className={`status-${state.status}`}>{connectionLabel}</strong>
            </div>
          </aside>
        </section>

        <section className="evaluation" aria-labelledby="evaluation-heading">
          <div className="evaluation-heading">
            <div>
              <p className="card-kicker">Model selection</p>
              <h2 id="evaluation-heading">Evaluation, made explicit.</h2>
            </div>
            <p>
              All candidates receive identical patches, prompts, context limits, and deterministic
              settings. Correctness is the gate; speed and resource use break ties.
            </p>
          </div>

          {state.status === "ready" ? (
            <div className="evaluation-grid">
              <div className="candidate-list" aria-label="Model candidates">
                <div className="list-header">
                  <span>Candidate models</span>
                  <span>Benchmark queue</span>
                </div>
                {state.rubric.candidates.map((candidate, index) => (
                  <div className="candidate-row" key={candidate}>
                    <span>0{index + 1}</span>
                    <strong>{candidate}</strong>
                    <i>Queued</i>
                  </div>
                ))}
              </div>

              <div className="rubric-list">
                <div className="list-header">
                  <span>Weighted score</span>
                  <span>{state.rubric.total_weight} points</span>
                </div>
                {state.rubric.categories.map((category) => (
                  <div className="rubric-row" key={category.key}>
                    <span>{category.label}</span>
                    <div>
                      <i aria-hidden="true">
                        <b style={{ width: `${category.weight}%` }} />
                      </i>
                      <strong>{category.weight}%</strong>
                    </div>
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
