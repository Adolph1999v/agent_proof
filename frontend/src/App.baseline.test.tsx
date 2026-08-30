import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const health = { status: "ok", service: "agentproof", version: "0.3.0" };
const rubric = {
  candidates: ["Qwen3.6 27B Q6", "Qwen3-Coder 30B", "Qwen2.5-Coder 7B"],
  categories: [],
  total_weight: 100,
  correctness_is_gate: true,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("approved baseline comparison", () => {
  it("clearly reports when the current project matches its latest baseline", async () => {
    const inspection = {
      repository_id: "project-1234567890abcdef1234567890abcdef",
      name: "agent_proof",
      current_path: "/tmp/agent_proof",
      path_changed: false,
      identity_kind: "git",
      current_digest: "a".repeat(64),
      current_file_count: 45,
      baseline_count: 1,
      latest_baseline: {
        baseline_id: "baseline-20260830T000000Z-1234abcd",
        created_at: "2026-08-30T00:00:00Z",
        parent_baseline_id: null,
        file_count: 45,
      },
      changes: [],
      current_state_audit: {
        status: "passed",
        summary: "Current pytest checks pass in the disposable audit workspace.",
      },
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(rubric), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(inspection), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await screen.findByText("Qwen3.6 27B Q6");
    fireEvent.change(screen.getByLabelText(/project path/i), {
      target: { value: "/tmp/agent_proof" },
    });
    fireEvent.click(screen.getByRole("button", { name: /inspect project/i }));

    expect(await screen.findByText("Matches approved baseline")).toBeInTheDocument();
    expect(
      screen.getByText("The current project is identical to the latest approved baseline."),
    ).toBeInTheDocument();
  });

  it("keeps detected changes visible while updating their verification status", async () => {
    const inspection = {
      repository_id: "project-1234567890abcdef1234567890abcdef",
      name: "agent_proof",
      current_path: "/tmp/agent_proof",
      path_changed: false,
      identity_kind: "git",
      current_digest: "b".repeat(64),
      current_file_count: 53,
      baseline_count: 2,
      latest_baseline: {
        baseline_id: "baseline-20260830T000000Z-1234abcd",
        created_at: "2026-08-30T00:00:00Z",
        parent_baseline_id: null,
        file_count: 46,
      },
      changes: [
        { path: "backend/service.py", status: "modified", previous_path: null },
        { path: "frontend/src/App.tsx", status: "modified", previous_path: null },
      ],
      current_state_audit: null,
    };
    const report = {
      run_id: "run-20260830T100000Z-1234abcd",
      verdict: "INCONCLUSIVE",
      summary: "Existing tests passed; an independent challenge is required.",
      repository_id: inspection.repository_id,
      baseline_id: inspection.latest_baseline.baseline_id,
      baseline_manifest_digest: "c".repeat(64),
      change_source: "approved_baseline",
      patch_normalized: false,
      protected_inputs_changed: [],
      changed_files: [],
      patch_check: {
        status: "passed",
        command: [],
        exit_code: 0,
        duration_ms: 1,
        output_preview: "",
      },
      test_execution: {
        status: "passed",
        command: [],
        exit_code: 0,
        duration_ms: 10,
        output_preview: "32 passed",
      },
      evidence_path: "artifacts/runs/run/report.json",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(rubric), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(inspection), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(report), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await screen.findByText("Qwen3.6 27B Q6");
    fireEvent.change(screen.getByLabelText(/project path/i), {
      target: { value: "/tmp/agent_proof" },
    });
    fireEvent.change(screen.getByLabelText(/original task or issue/i), {
      target: { value: "Implement bounded independent local-model challenges." },
    });
    fireEvent.click(screen.getByRole("button", { name: /inspect project/i }));

    expect(await screen.findByText("2 unverified change(s)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /verify detected changes/i }));

    expect(await screen.findByText("2 change(s) · tests passed")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Unchanged approved tests passed; an independent challenge is still required.",
      ),
    ).toBeInTheDocument();
  });
});
