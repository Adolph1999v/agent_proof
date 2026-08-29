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

const workflow = [
  ["01", "Understand intent", "Extract the behavior the patch must preserve."],
  ["02", "Freeze evidence", "Keep original tests outside the patch's control."],
  ["03", "Challenge the patch", "Generate and execute independent adversarial checks."],
  ["04", "Prove the verdict", "Return reproducible evidence for human review."],
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

  return (
    <main>
      <nav className="nav shell" aria-label="Primary navigation">
        <a className="brand" href="#top" aria-label="AgentProof home">
          <span className="brand-mark">AP</span>
          <span>AgentProof</span>
        </a>
        <span className={`connection connection-${state.status}`}>
          <span className="connection-dot" aria-hidden="true" />
          {state.status === "ready"
            ? `Backend connected · v${state.health.version}`
            : state.status === "error"
              ? "Backend unavailable"
              : "Checking local backend"}
        </span>
      </nav>

      <section className="hero shell" id="top">
        <div className="eyebrow">Independent verification for agent-written code</div>
        <h1>
          Do not trust <em>“done.”</em>
          <br />
          Make the patch prove it.
        </h1>
        <p className="hero-copy">
          AgentProof checks whether an AI-generated change preserved the task, the tests, and the
          truth behind its completion claims—before a human approves the merge.
        </p>
        <div className="hero-actions">
          <button type="button" disabled>
            Verify a patch <span>Phase 2</span>
          </button>
          <a href="#evaluation">See evaluation contract</a>
        </div>
      </section>

      <section className="workflow shell" aria-labelledby="workflow-heading">
        <div className="section-heading">
          <span>Verification workflow</span>
          <h2 id="workflow-heading">A second opinion that has to show its work.</h2>
        </div>
        <div className="workflow-grid">
          {workflow.map(([number, title, body]) => (
            <article key={number}>
              <span className="step-number">{number}</span>
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="evaluation shell" id="evaluation" aria-labelledby="evaluation-heading">
        <div className="section-heading">
          <span>Model selection</span>
          <h2 id="evaluation-heading">Correctness wins. Speed breaks ties.</h2>
          <p>
            Every candidate receives identical authentic patches, prompts, limits, and deterministic
            settings. A serious false-safe result is disqualifying.
          </p>
        </div>

        {state.status === "ready" ? (
          <div className="evaluation-panel">
            <div className="candidate-list" aria-label="Model candidates">
              {state.rubric.candidates.map((candidate, index) => (
                <div key={candidate}>
                  <span>0{index + 1}</span>
                  <strong>{candidate}</strong>
                </div>
              ))}
            </div>
            <div className="rubric-list">
              {state.rubric.categories.map((category) => (
                <div className="rubric-row" key={category.key}>
                  <div>
                    <span>{category.label}</span>
                    <strong>{category.weight}%</strong>
                  </div>
                  <div className="meter" aria-hidden="true">
                    <span style={{ width: `${category.weight}%` }} />
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

      <footer className="shell">
        <span>Phase 1 · Reproducible foundation</span>
        <span>Local-first · Human-approved · Evidence-backed</span>
      </footer>
    </main>
  );
}
