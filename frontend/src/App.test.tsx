import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const health = { status: "ok", service: "agentproof", version: "0.3.0" };

const unsafeReport = {
  run_id: "run-20260829T180000Z-1234abcd",
  verdict: "UNSAFE",
  summary: "The immutable baseline test suite failed after the patch was applied.",
  repository_id: null,
  baseline_id: null,
  change_source: "approved_baseline",
  patch_normalized: false,
  protected_inputs_changed: [],
  changed_files: [
    { path: "calculator.py", added_lines: 1, deleted_lines: 1, protected: false },
  ],
  patch_check: {
    command: ["git", "apply", "--check"],
    status: "passed",
    exit_code: 0,
    duration_ms: 8,
    output_preview: "",
  },
  test_execution: {
    command: ["python", "-m", "pytest", "-q"],
    status: "failed",
    exit_code: 1,
    duration_ms: 87,
    output_preview: "1 failed",
  },
  evidence_path: "artifacts/runs/run-20260829T180000Z-1234abcd/report.json",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AgentProof foundation", () => {
  it("shows the focused verifier and backend state", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      screen.getByRole("heading", { name: /review an agent-generated change/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /verify detected changes/i })).toBeDisabled();

    await waitFor(() => {
      expect(screen.getAllByText("Backend connected · v0.3.0")).toHaveLength(2);
    });

    expect(screen.queryByText("Model lab")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/agent trace/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /explicit patch/i })).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("reports a backend failure without pretending verification is available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Connection refused")));

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Connection refused");
    expect(screen.getByRole("button", { name: /verify detected changes/i })).toBeDisabled();
  });

  it("fills the project path through the local folder picker", async () => {
    const directoryListing = {
      current_path: "/Users/reviewer/agent-proof-demo",
      parent_path: "/Users/reviewer",
      directories: [],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(directoryListing), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await screen.findAllByText("Backend connected · v0.3.0");
    fireEvent.click(screen.getByRole("button", { name: "Browse" }));
    expect(
      await screen.findByRole("heading", { name: "Choose a project folder" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use this folder" }));

    expect(screen.getByLabelText("Project folder")).toHaveValue(
      "/Users/reviewer/agent-proof-demo",
    );
    expect(screen.getByRole("button", { name: "Inspect project" })).toBeEnabled();
  });

  it("submits the user-approved inputs and renders an unsafe deterministic verdict", async () => {
    const inspection = {
      repository_id: "project-1234567890abcdef1234567890abcdef",
      name: "calculator",
      current_path: "/tmp/calculator",
      path_changed: false,
      identity_kind: "git",
      current_digest: "b".repeat(64),
      current_file_count: 3,
      baseline_count: 1,
      latest_baseline: {
        baseline_id: "baseline-20260830T000000Z-1234abcd",
        created_at: "2026-08-30T00:00:00Z",
        parent_baseline_id: null,
        file_count: 3,
      },
      changes: [{ path: "calculator.py", status: "modified", previous_path: null }],
      current_state_audit: null,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(inspection), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(unsafeReport), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await screen.findAllByText("Backend connected · v0.3.0");
    fireEvent.change(screen.getByLabelText(/project folder/i), {
      target: { value: "/tmp/calculator" },
    });
    fireEvent.change(screen.getByLabelText(/original task or issue/i), {
      target: { value: "Keep the calculator correct." },
    });
    fireEvent.click(screen.getByRole("button", { name: /inspect project/i }));
    expect(await screen.findByText("1 unverified change(s)")).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: /verify detected changes/i });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByRole("heading", { name: "Unsafe change detected" })).toBeInTheDocument();
    expect(screen.getByText("The immutable baseline test suite failed after the patch was applied.")).toBeInTheDocument();
    expect(screen.getByText("Patch preflight")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/verifications/automatic",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("inspects a project and approves its first isolated baseline", async () => {
    const inspection = {
      repository_id: "project-1234567890abcdef1234567890abcdef",
      name: "calculator",
      current_path: "/tmp/calculator",
      path_changed: false,
      identity_kind: "git",
      current_digest: "a".repeat(64),
      current_file_count: 3,
      baseline_count: 0,
      latest_baseline: null,
      changes: [],
      current_state_audit: {
        status: "passed",
        summary: "Current pytest checks pass; no earlier baseline was required.",
      },
    };
    const approved = {
      baseline: {
        baseline_id: "baseline-20260830T000000Z-1234abcd",
        repository_id: inspection.repository_id,
      },
      project: {
        ...inspection,
        baseline_count: 1,
        latest_baseline: {
          baseline_id: "baseline-20260830T000000Z-1234abcd",
          created_at: "2026-08-30T00:00:00Z",
          parent_baseline_id: null,
          file_count: 3,
        },
        current_state_audit: null,
      },
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(inspection), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(approved), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await screen.findAllByText("Backend connected · v0.3.0");
    fireEvent.change(screen.getByLabelText(/project folder/i), {
      target: { value: "/tmp/calculator" },
    });
    fireEvent.change(screen.getByLabelText(/original task or issue/i), {
      target: { value: "Accept the current state as the first baseline." },
    });
    fireEvent.click(screen.getByRole("button", { name: /inspect project/i }));

    expect(await screen.findByText("Current checks pass")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /approve first baseline/i }));

    expect(await screen.findByText("1 baseline(s)")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/projects/baselines",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
