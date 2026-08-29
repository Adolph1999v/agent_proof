import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
      screen.getByRole("heading", { name: /do not trust “done.” make the patch prove it/i }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Backend connected · v0.1.0")).toBeInTheDocument();
    });

    expect(screen.getByText("Qwen3.6 27B Q6")).toBeInTheDocument();
    expect(screen.getByText("Correctly catches unsafe patches")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("reports a backend failure without pretending verification is available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Connection refused")));

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Connection refused");
    expect(screen.getByRole("button", { name: /verify a patch/i })).toBeDisabled();
  });
});
