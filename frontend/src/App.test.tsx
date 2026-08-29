import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const health = { status: "ok", service: "agentproof", version: "0.1.0" };
const rubric = {
  candidates: ["Qwen3.6 27B Q6", "Qwen3-Coder 30B", "Qwen2.5-Coder 7B"],
  categories: [
    { key: "unsafe_patch_detection", label: "Correctly catches unsafe patches", weight: 40 },
    { key: "correct_patch_acceptance", label: "Does not block correct patches", weight: 20 },
    { key: "executable_tests", label: "Produces relevant, executable tests", weight: 20 },
    { key: "execution_time", label: "Execution time", weight: 10 },
    { key: "resource_efficiency", label: "Tokens and memory usage", weight: 10 },
  ],
  total_weight: 100,
  correctness_is_gate: true,
};

const unsafeReport = {
  run_id: "run-20260829T180000Z-1234abcd",
  verdict: "UNSAFE",
  summary: "The immutable baseline test suite failed after the patch was applied.",
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
  it("shows backend state and the server-owned model rubric", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(rubric), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      screen.getByRole("heading", { name: /review an agent-generated change/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start verification/i })).toBeDisabled();

    await waitFor(() => {
      expect(screen.getAllByText("Backend connected · v0.1.0")).toHaveLength(2);
    });

    expect(screen.getByText("Qwen3.6 27B Q6")).toBeInTheDocument();
    expect(screen.getByText("Correctly catches unsafe patches")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("reports a backend failure without pretending verification is available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Connection refused")));

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Connection refused");
    expect(screen.getByRole("button", { name: /start verification/i })).toBeDisabled();
  });

  it("submits the user-approved inputs and renders an unsafe deterministic verdict", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(rubric), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(unsafeReport), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await screen.findByText("Qwen3.6 27B Q6");
    fireEvent.change(screen.getByLabelText(/repository path/i), {
      target: { value: "/tmp/calculator" },
    });
    fireEvent.change(screen.getByLabelText(/original task or issue/i), {
      target: { value: "Keep the calculator correct." },
    });
    fireEvent.change(screen.getByLabelText(/^candidate patch/i), {
      target: { value: "diff --git a/calculator.py b/calculator.py" },
    });

    const submit = screen.getByRole("button", { name: /start verification/i });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByRole("heading", { name: "Unsafe change detected" })).toBeInTheDocument();
    expect(screen.getByText("The immutable baseline test suite failed after the patch was applied.")).toBeInTheDocument();
    expect(screen.getByText("Patch preflight")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/verifications",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
