import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const health = { status: "ok", service: "agentproof", version: "0.2.0" };
const rubric = {
  candidates: ["Qwen3.6 27B Q6"],
  categories: [],
  total_weight: 100,
  correctness_is_gate: true,
};
const deterministicReport = {
  run_id: "run-20260830T100000Z-1234abcd",
  verdict: "INCONCLUSIVE",
  summary: "Baseline evidence passed, but independent challenge tests have not yet been performed.",
  repository_id: null,
  baseline_id: null,
  baseline_manifest_digest: null,
  change_source: "manual_patch",
  patch_normalized: false,
  protected_inputs_changed: [],
  changed_files: [{ path: "service.py", added_lines: 1, deleted_lines: 1, protected: false }],
  patch_check: { status: "passed", command: [], exit_code: 0, duration_ms: 1, output_preview: "" },
  test_execution: { status: "passed", command: [], exit_code: 0, duration_ms: 10, output_preview: "1 passed" },
  evidence_path: "artifacts/runs/run-20260830T100000Z-1234abcd/report.json",
};
const challengeReport = {
  challenge_id: "challenge-20260830T100100Z-5678efab",
  source_run_id: deterministicReport.run_id,
  verdict: "VERIFIED",
  summary: "The independent challenge failed on the baseline and passed on the candidate.",
  proposal: {
    behavior_mode: "change",
    summary: "The requested value changed.",
    invariants: ["value() returns 2"],
    test_sha256: "a".repeat(64),
    test_path: "artifacts/challenge.py",
  },
  model: {
    provider: "openai-compatible:qwen3.6-27b",
    model: "qwen3.6-27b",
    duration_ms: 1000,
    prompt_tokens: 200,
    completion_tokens: 80,
  },
  baseline_execution: { status: "failed", command: [], exit_code: 1, duration_ms: 10, output_preview: "failed" },
  candidate_execution: { status: "passed", command: [], exit_code: 0, duration_ms: 10, output_preview: "passed" },
  evidence_path: "artifacts/challenges/report.json",
  trajectory_path: "artifacts/challenges/trajectory.json",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("independent local-model challenge", () => {
  it("runs after deterministic evidence and presents the execution-owned verdict", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(rubric), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(deterministicReport), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(challengeReport), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await screen.findByText("Qwen3.6 27B Q6");
    fireEvent.click(screen.getByRole("button", { name: /explicit patch/i }));
    fireEvent.change(screen.getByLabelText(/project path/i), {
      target: { value: "/tmp/service" },
    });
    fireEvent.change(screen.getByLabelText(/original task or issue/i), {
      target: { value: "Change the service value from 1 to 2." },
    });
    fireEvent.change(screen.getByLabelText(/^candidate patch/i), {
      target: { value: "diff --git a/service.py b/service.py" },
    });
    fireEvent.click(screen.getByRole("button", { name: /verify explicit patch/i }));

    expect(await screen.findByRole("button", { name: /run local challenge/i })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: /run local challenge/i }));

    expect(
      await screen.findByRole("heading", { name: /verified by an independent challenge/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("qwen3.6-27b")).not.toHaveLength(0);
    expect(screen.getByText("value() returns 2")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/challenges",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
