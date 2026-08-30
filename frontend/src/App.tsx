import { type FormEvent, useCallback, useEffect, useState } from "react";

import DirectoryPicker from "./DirectoryPicker";

type Health = {
  status: "ok";
  service: string;
  version: string;
};

type CommandEvidence = {
  command: string[];
  status: "passed" | "failed" | "timed_out" | "not_run";
  exit_code: number | null;
  duration_ms: number | null;
  output_preview: string | null;
};

type VerificationReport = {
  run_id: string;
  verdict: "UNSAFE" | "INCONCLUSIVE";
  summary: string;
  repository_id: string | null;
  baseline_id: string | null;
  baseline_manifest_digest: string | null;
  change_source: "manual_patch" | "approved_baseline";
  patch_normalized: boolean;
  protected_inputs_changed: string[];
  changed_files: Array<{
    path: string;
    added_lines: number;
    deleted_lines: number;
    protected: boolean;
  }>;
  patch_check: CommandEvidence;
  test_execution: CommandEvidence;
  evidence_path: string;
};

type IndependentChallengeReport = {
  challenge_id: string;
  source_run_id: string;
  verdict: "VERIFIED" | "UNSAFE" | "INCONCLUSIVE";
  summary: string;
  proposal: {
    behavior_mode: "change" | "preserve";
    summary: string;
    invariants: string[];
    test_sha256: string;
    test_path: string;
  };
  model: {
    provider: string;
    model: string;
    duration_ms: number;
    prompt_tokens: number;
    completion_tokens: number;
  };
  baseline_execution: CommandEvidence;
  candidate_execution: CommandEvidence;
  evidence_path: string;
  trajectory_path: string;
};

type ProjectChange = {
  path: string;
  status: "added" | "modified" | "deleted" | "renamed";
  previous_path: string | null;
};

type BaselineSummary = {
  baseline_id: string;
  created_at: string;
  parent_baseline_id: string | null;
  file_count: number;
};

type ProjectInspection = {
  repository_id: string;
  name: string;
  current_path: string;
  path_changed: boolean;
  identity_kind: "git" | "folder";
  current_digest: string;
  current_file_count: number;
  baseline_count: number;
  latest_baseline: BaselineSummary | null;
  changes: ProjectChange[];
  current_state_audit: {
    status: "passed" | "failed" | "timed_out" | "not_supported";
    summary: string;
  } | null;
};

type LoadState =
  | { status: "loading" }
  | { status: "ready"; health: Health }
  | { status: "error"; message: string };

type VerificationState =
  | { status: "idle" }
  | { status: "running" }
  | { status: "ready"; report: VerificationReport }
  | { status: "error"; message: string };

type ProjectState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; project: ProjectInspection }
  | { status: "error"; message: string };

type ChallengeState =
  | { status: "idle" }
  | { status: "running" }
  | { status: "ready"; report: IndependentChallengeReport }
  | { status: "error"; message: string };

const proofContract = [
  ["Intent", "The patch solves the requested task."],
  ["Behavior", "The patch survives tests it did not write."],
  ["Evidence", "The verdict can be reproduced and reviewed."],
] as const;

async function loadFoundation(): Promise<{ health: Health }> {
  const healthResponse = await fetch("/api/health");
  if (!healthResponse.ok) {
    throw new Error("The local backend did not return a successful response.");
  }

  return {
    health: (await healthResponse.json()) as Health,
  };
}

function readableCheckStatus(status: CommandEvidence["status"]): string {
  return {
    passed: "Passed",
    failed: "Failed",
    timed_out: "Timed out",
    not_run: "Not run",
  }[status];
}

function readableElapsed(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export default function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [repositoryPath, setRepositoryPath] = useState("");
  const [directoryPickerOpen, setDirectoryPickerOpen] = useState(false);
  const [task, setTask] = useState("");
  const [projectState, setProjectState] = useState<ProjectState>({ status: "idle" });
  const [verification, setVerification] = useState<VerificationState>({ status: "idle" });
  const [challenge, setChallenge] = useState<ChallengeState>({ status: "idle" });
  const [challengeElapsedSeconds, setChallengeElapsedSeconds] = useState(0);
  const [modelUrl, setModelUrl] = useState("http://127.0.0.1:1234/v1");
  const [modelName, setModelName] = useState("agentproof-qwen3.6-27b");

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

  useEffect(() => {
    if (challenge.status !== "running") {
      setChallengeElapsedSeconds(0);
      return;
    }
    const startedAt = Date.now();
    const updateElapsed = () => {
      setChallengeElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    };
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [challenge.status]);

  const connectionLabel =
    state.status === "ready"
      ? `Backend connected · v${state.health.version}`
      : state.status === "error"
        ? "Backend unavailable"
        : "Connecting to backend";
  const inspectedProject = projectState.status === "ready" ? projectState.project : null;
  const canStartVerification = Boolean(
    repositoryPath.trim() &&
      task.trim() &&
      inspectedProject?.latest_baseline &&
      inspectedProject.changes.length,
  );
  const report = verification.status === "ready" ? verification.report : null;
  const challengeReport = challenge.status === "ready" ? challenge.report : null;
  const taskLooksVague = Boolean(task.trim() && task.trim().split(/\s+/).length < 5);
  const activeVerdict = challengeReport?.verdict ?? report?.verdict;
  const failureEvidence = challengeReport
    ? challengeReport.candidate_execution.status === "failed"
      ? challengeReport.candidate_execution.output_preview
      : challengeReport.baseline_execution.status === "failed"
        ? challengeReport.baseline_execution.output_preview
        : null
    : report
      ? report.patch_check.status === "failed"
        ? report.patch_check.output_preview
        : report.test_execution.status === "failed" || report.test_execution.status === "timed_out"
          ? report.test_execution.output_preview
          : null
      : null;
  const detectedStateLabel = inspectedProject?.latest_baseline
    ? inspectedProject.changes.length
      ? challengeReport?.verdict === "VERIFIED"
        ? `${inspectedProject.changes.length} verified change(s) · approval needed`
        : challengeReport?.verdict === "UNSAFE" || report?.verdict === "UNSAFE"
          ? `${inspectedProject.changes.length} unsafe change(s)`
          : challengeReport?.verdict === "INCONCLUSIVE"
            ? `${inspectedProject.changes.length} change(s) · inconclusive`
            : challenge.status === "running"
              ? `${inspectedProject.changes.length} change(s) · challenging`
              : challenge.status === "error"
                ? `${inspectedProject.changes.length} change(s) · challenge failed`
                : report?.test_execution.status === "passed"
                  ? `${inspectedProject.changes.length} change(s) · tests passed`
                  : verification.status === "running"
                    ? `${inspectedProject.changes.length} change(s) · checking`
                    : `${inspectedProject.changes.length} unverified change(s)`
      : "Matches approved baseline"
    : inspectedProject?.current_state_audit?.status === "passed"
      ? "Current checks pass"
      : "Current state inspected";
  const detectedStateDetail = inspectedProject?.changes.length
    ? challengeReport?.verdict === "VERIFIED"
      ? "Independent evidence passed. Approve this state to make it the next baseline."
      : challengeReport?.verdict === "UNSAFE"
        ? "Independent evidence found a regression; this state cannot be approved."
        : challengeReport?.verdict === "INCONCLUSIVE"
          ? "Independent evidence could not distinguish the baseline from the candidate."
          : challenge.status === "running"
            ? `The local model is producing a bounded challenge (${readableElapsed(challengeElapsedSeconds)}).`
            : challenge.status === "error"
              ? "The challenge did not complete; the detected changes remain unapproved."
              : report?.test_execution.status === "passed"
                ? "Unchanged approved tests passed; an independent challenge is still required."
                : inspectedProject.changes
                    .slice(0, 3)
                    .map((change) => `${change.status}: ${change.path}`)
                    .join(" · ")
    : inspectedProject?.latest_baseline
      ? "The current project is identical to the latest approved baseline."
      : inspectedProject?.current_state_audit?.summary ?? "No approved comparison exists yet";

  async function startVerification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canStartVerification || verification.status === "running") return;

    setVerification({ status: "running" });
    setChallenge({ status: "idle" });
    try {
      const response = await fetch("/api/verifications/automatic", {
        body: JSON.stringify({
          repository_path: repositoryPath,
          task,
          trace: null,
        }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const payload = (await response.json()) as VerificationReport | { detail?: string };
      if (!response.ok) {
        throw new Error("detail" in payload ? payload.detail : "Unable to start verification.");
      }
      setVerification({ status: "ready", report: payload as VerificationReport });
    } catch (error: unknown) {
      setVerification({
        status: "error",
        message: error instanceof Error ? error.message : "Unable to start verification.",
      });
    }
  }

  const updateRepositoryPath = useCallback((path: string) => {
    setRepositoryPath(path);
    setProjectState({ status: "idle" });
    setVerification({ status: "idle" });
    setChallenge({ status: "idle" });
  }, []);

  const closeDirectoryPicker = useCallback(() => setDirectoryPickerOpen(false), []);
  const selectDirectory = useCallback(
    (path: string) => {
      updateRepositoryPath(path);
      setDirectoryPickerOpen(false);
    },
    [updateRepositoryPath],
  );

  async function inspectProject() {
    if (!repositoryPath.trim() || projectState.status === "loading") return;
    setProjectState({ status: "loading" });
    setVerification({ status: "idle" });
    setChallenge({ status: "idle" });
    try {
      const response = await fetch("/api/projects/inspect", {
        body: JSON.stringify({ repository_path: repositoryPath }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const payload = (await response.json()) as ProjectInspection | { detail?: string };
      if (!response.ok) {
        throw new Error("detail" in payload ? payload.detail : "Unable to inspect this project.");
      }
      setProjectState({ status: "ready", project: payload as ProjectInspection });
    } catch (error: unknown) {
      setProjectState({
        status: "error",
        message: error instanceof Error ? error.message : "Unable to inspect this project.",
      });
    }
  }

  async function approveBaseline() {
    if (!inspectedProject || !task.trim()) return;
    setProjectState({ status: "loading" });
    try {
      const response = await fetch("/api/projects/baselines", {
        body: JSON.stringify({
          repository_path: repositoryPath,
          expected_current_digest: inspectedProject.current_digest,
          task,
          evidence_run_id: report?.run_id ?? null,
        }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const payload = (await response.json()) as
        | { project: ProjectInspection }
        | { detail?: string };
      if (!response.ok || !("project" in payload)) {
        throw new Error("detail" in payload ? payload.detail : "Unable to approve this baseline.");
      }
      setProjectState({ status: "ready", project: payload.project });
      setVerification({ status: "idle" });
      setChallenge({ status: "idle" });
    } catch (error: unknown) {
      setProjectState({
        status: "error",
        message: error instanceof Error ? error.message : "Unable to approve this baseline.",
      });
    }
  }

  async function runIndependentChallenge() {
    if (
      !report ||
      report.verdict !== "INCONCLUSIVE" ||
      !modelUrl.trim() ||
      !modelName.trim() ||
      challenge.status === "running"
    ) return;

    setChallenge({ status: "running" });
    try {
      const response = await fetch("/api/challenges", {
        body: JSON.stringify({
          run_id: report.run_id,
          task,
          model_url: modelUrl,
          model_name: modelName,
        }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const payload = (await response.json()) as IndependentChallengeReport | { detail?: string };
      if (!response.ok) {
        throw new Error("detail" in payload ? payload.detail : "Unable to run the challenge.");
      }
      setChallenge({ status: "ready", report: payload as IndependentChallengeReport });
    } catch (error: unknown) {
      setChallenge({
        status: "error",
        message: error instanceof Error ? error.message : "Unable to run the challenge.",
      });
    }
  }

  return (
    <main className="app-shell">
      <div className="ambient-field" aria-hidden="true" />
      <DirectoryPicker
        initialPath={repositoryPath}
        onCancel={closeDirectoryPicker}
        onSelect={selectDirectory}
        open={directoryPickerOpen}
      />

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
            <p className="kicker">Independent change verification</p>
            <h1 id="page-title">
              Review an agent-generated <em>change.</em>
            </h1>
            <p>
              Turn an AI completion claim into evidence a person can inspect, reproduce, and
              approve with confidence.
            </p>
          </div>

        </section>

        <section className="workspace-stage" aria-labelledby="review-heading">
          <section className="review-card">
            <div className="review-card-topline">
              <span className="section-id">Verification request</span>
              <span className="draft-state">Draft · local only</span>
            </div>

            <div className="review-heading">
              <div>
                <p className="card-kicker">Step 01</p>
                <h2 id="review-heading">Describe what should be verified</h2>
              </div>
              <p>
                Point AgentProof at the project and describe the task. Change discovery happens
                locally and automatically.
              </p>
            </div>

            <form onSubmit={startVerification}>
              {state.status === "error" ? (
                <p className="project-error" role="alert">{state.message}</p>
              ) : null}
              <div className="path-field">
                <label htmlFor="repository">Project folder</label>
                <div className="path-input-row">
                  <input
                    id="repository"
                    name="repository"
                    onChange={(event) => updateRepositoryPath(event.target.value)}
                    placeholder="Choose the project to verify"
                    type="text"
                    value={repositoryPath}
                  />
                  <button
                    className="browse-folders"
                    onClick={() => setDirectoryPickerOpen(true)}
                    type="button"
                  >
                    Browse
                  </button>
                </div>
              </div>

              <label htmlFor="task">
                <span>Original task or issue</span>
                <textarea
                  id="task"
                  name="task"
                  onChange={(event) => setTask(event.target.value)}
                  placeholder="Describe what the coding agent was asked to change…"
                  rows={4}
                  value={task}
                />
              </label>
              {taskLooksVague ? (
                <p className="task-guidance">
                  Describe the feature and expected behavior more specifically for a faster, more
                  relevant independent challenge.
                </p>
              ) : null}

              <section className="project-discovery" aria-label="Automatic change discovery">
                  <div className="discovery-action">
                    <div>
                      <strong>Automatic change discovery</strong>
                      <span>Identify this project, audit its current state, and find changes.</span>
                    </div>
                    <button
                      disabled={!repositoryPath.trim() || projectState.status === "loading"}
                      onClick={inspectProject}
                      type="button"
                    >
                      {projectState.status === "loading" ? "Inspecting…" : "Inspect project"}
                    </button>
                  </div>

                  {projectState.status === "error" ? (
                    <p className="project-error" role="alert">{projectState.message}</p>
                  ) : null}

                  {inspectedProject ? (
                    <div className="project-summary">
                      <div className="project-identity">
                        <span>Recognized project</span>
                        <strong>{inspectedProject.name}</strong>
                        <code>{inspectedProject.repository_id.slice(0, 20)}…</code>
                      </div>
                      <div>
                        <span>Approved history</span>
                        <strong>
                          {inspectedProject.latest_baseline
                            ? `${inspectedProject.baseline_count} baseline(s)`
                            : "First baseline needed"}
                        </strong>
                        <small>
                          {inspectedProject.path_changed
                            ? "Known project found at a new path"
                            : `${inspectedProject.current_file_count} files inventoried`}
                        </small>
                      </div>
                      <div>
                        <span>Detected state</span>
                        <strong>{detectedStateLabel}</strong>
                        <small>{detectedStateDetail}</small>
                      </div>
                      {(!inspectedProject.latest_baseline ||
                        (challengeReport?.verdict === "VERIFIED" &&
                          report?.change_source === "approved_baseline")) ? (
                        <button
                          className="approve-baseline"
                          disabled={
                            !task.trim() ||
                            inspectedProject.current_state_audit?.status === "failed" ||
                            inspectedProject.current_state_audit?.status === "timed_out"
                          }
                          onClick={approveBaseline}
                          type="button"
                        >
                          {inspectedProject.latest_baseline
                            ? "Approve as next baseline"
                            : "Approve first baseline"}
                        </button>
                      ) : null}
                    </div>
                  ) : null}
              </section>

              <div className="form-footer">
                <button disabled={!canStartVerification || verification.status === "running"} type="submit">
                  <span>
                    {verification.status === "running" ? "Verifying…" : "Verify detected changes"}
                  </span>
                  <i aria-hidden="true">↗</i>
                </button>
                <p>
                  No patch knowledge required. AgentProof compares the correct approved baseline.
                </p>
              </div>
            </form>

            {report?.verdict === "INCONCLUSIVE" && report.test_execution.status === "passed" ? (
              <section className="challenge-panel" aria-labelledby="challenge-heading">
                <div className="challenge-heading">
                  <div>
                    <p className="card-kicker">Step 02</p>
                    <h3 id="challenge-heading">Run an independent challenge</h3>
                  </div>
                  <span>One local model at a time</span>
                </div>

                <div className="field-grid">
                  <label htmlFor="model-url">
                    <span>Local model endpoint</span>
                    <input
                      id="model-url"
                      onChange={(event) => setModelUrl(event.target.value)}
                      spellCheck="false"
                      value={modelUrl}
                    />
                  </label>
                  <label htmlFor="model-name">
                    <span>Loaded model name</span>
                    <input
                      id="model-name"
                      onChange={(event) => setModelName(event.target.value)}
                      spellCheck="false"
                      value={modelName}
                    />
                  </label>
                </div>
                <p className="model-context-note">
                  Qwen3.6 27B on a 48GB Mac: load a 48K context window. AgentProof still bounds
                  repository input so output and system memory retain headroom.
                </p>

                {challenge.status === "error" ? (
                  <p className="challenge-error" role="alert">{challenge.message}</p>
                ) : null}

                {challengeReport ? (
                  <div className="challenge-evidence">
                    <div>
                      <span>Generated invariant</span>
                      <strong>{challengeReport.proposal.invariants[0]}</strong>
                    </div>
                    <div>
                      <span>Baseline / candidate</span>
                      <strong>
                        {readableCheckStatus(challengeReport.baseline_execution.status)} / {" "}
                        {readableCheckStatus(challengeReport.candidate_execution.status)}
                      </strong>
                    </div>
                    <div>
                      <span>Model usage</span>
                      <strong>
                        {challengeReport.model.prompt_tokens + challengeReport.model.completion_tokens}
                        {" tokens"}
                      </strong>
                    </div>
                  </div>
                ) : null}

                <div className="challenge-action">
                  <button
                    disabled={
                      !modelUrl.trim() || !modelName.trim() || challenge.status === "running"
                    }
                    onClick={runIndependentChallenge}
                    type="button"
                  >
                    {challenge.status === "running"
                      ? `Generating and testing · ${readableElapsed(challengeElapsedSeconds)}`
                      : "Run local challenge"}
                  </button>
                  <p>
                    {challenge.status === "running"
                      ? "Large local models can take a few minutes. Keep this page open while AgentProof waits."
                      : "The model proposes the test. AgentProof executes it and owns the verdict."}
                  </p>
                </div>
              </section>
            ) : null}
          </section>

          <aside className="outcome-card" aria-labelledby="outcome-heading">
            <div className="outcome-topline">
              <span>Live state</span>
              <span className={`not-started ${activeVerdict ? `verdict-${activeVerdict.toLowerCase()}` : ""}`}>
                {challenge.status === "running"
                  ? "Challenging"
                  : verification.status === "running"
                    ? "Running"
                    : activeVerdict ?? "Not started"}
              </span>
            </div>

            <div className="signal-orb" aria-hidden="true">
              <span />
              <i />
            </div>

            <h2 id="outcome-heading">
              {challenge.status === "running"
                ? "Writing an independent test"
                : verification.status === "running"
                ? "Building disposable evidence"
                : activeVerdict === "VERIFIED"
                  ? "Verified by an independent challenge"
                  : activeVerdict === "UNSAFE"
                  ? "Unsafe change detected"
                  : challengeReport
                    ? "Challenge remains inconclusive"
                    : report
                    ? "Needs an independent challenge"
                    : "Waiting for a request"}
            </h2>
            <p>
              {challenge.status === "running"
                ? `The local model is analyzing bounded application context and preparing one test (${readableElapsed(challengeElapsedSeconds)}).`
                : challenge.status === "error"
                ? challenge.message
                : verification.status === "error"
                ? verification.message
                : challengeReport
                  ? challengeReport.summary
                  : report
                  ? report.summary
                  : "AgentProof will challenge the patch, not simply summarize it. The final call remains with a human."}
            </p>

            <div className="evidence-list">
              {(challengeReport
                ? [
                    ["Local model", challengeReport.model.model],
                    [
                      "Baseline challenge",
                      readableCheckStatus(challengeReport.baseline_execution.status),
                    ],
                    [
                      "Candidate challenge",
                      readableCheckStatus(challengeReport.candidate_execution.status),
                    ],
                  ]
                : report
                ? [
                    [
                      "Patch preflight",
                      report.patch_check.status === "passed" && report.patch_normalized
                        ? "Passed · terminal newline restored"
                        : readableCheckStatus(report.patch_check.status),
                    ],
                    [
                      "Test isolation",
                      report.protected_inputs_changed.length
                        ? `${report.protected_inputs_changed.length} candidate test/config change(s) quarantined; unchanged tests retained`
                        : "Frozen baseline tests remained unchanged",
                    ],
                    [
                      "Unchanged baseline tests",
                      readableCheckStatus(report.test_execution.status),
                    ],
                  ]
                : proofContract
              ).map(([title, body]) => (
                <div key={title}>
                  <strong>{title}</strong>
                  <span>{body}</span>
                </div>
              ))}
            </div>

            {failureEvidence ? (
              <details className="failure-evidence" open>
                <summary>Command evidence</summary>
                <pre>{failureEvidence}</pre>
              </details>
            ) : null}

            <div className="api-readout">
              <span>Local API</span>
              <strong className={`status-${state.status}`}>{connectionLabel}</strong>
            </div>
            {challengeReport || report ? (
              <p className="evidence-path">
                Evidence: {challengeReport?.evidence_path ?? report?.evidence_path}
              </p>
            ) : null}
          </aside>
        </section>

      </div>

      <footer>
        <span>AgentProof · Local-first change verification</span>
        <span>Reproducible evidence · Human approval</span>
      </footer>
    </main>
  );
}
