import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DirectoryPicker from "./DirectoryPicker";

const rootListing = {
  current_path: "/Users/reviewer",
  parent_path: "/Users",
  directories: [
    { name: "Projects", path: "/Users/reviewer/Projects" },
    { name: "Downloads", path: "/Users/reviewer/Downloads" },
  ],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.body.style.overflow = "";
});

describe("DirectoryPicker", () => {
  it("navigates into a directory and returns the chosen absolute path", async () => {
    const projectListing = {
      current_path: "/Users/reviewer/Projects",
      parent_path: "/Users/reviewer",
      directories: [],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(rootListing), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(projectListing), { status: 200 }));
    const onSelect = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DirectoryPicker
        initialPath="/Users/reviewer"
        onCancel={vi.fn()}
        onSelect={onSelect}
        open
      />,
    );

    expect(await screen.findByText("/Users/reviewer")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open folder Projects" }));
    expect(await screen.findByText("/Users/reviewer/Projects")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use this folder" }));

    expect(onSelect).toHaveBeenCalledWith("/Users/reviewer/Projects");
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/filesystem/directories",
      expect.objectContaining({
        body: JSON.stringify({ path: "/Users/reviewer/Projects" }),
        method: "POST",
      }),
    );
  });

  it("can navigate to the parent directory", async () => {
    const parentListing = {
      current_path: "/Users",
      parent_path: "/",
      directories: [],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(rootListing), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(parentListing), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DirectoryPicker
        initialPath="/Users/reviewer"
        onCancel={vi.fn()}
        onSelect={vi.fn()}
        open
      />,
    );

    await screen.findByText("/Users/reviewer");
    fireEvent.click(screen.getByRole("button", { name: "↑ Parent" }));
    expect(await screen.findByText("/Users")).toBeInTheDocument();
  });

  it("recovers from an invalid initial path by opening the home folder", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Path does not exist" }), { status: 400 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(rootListing), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DirectoryPicker
        initialPath="/missing"
        onCancel={vi.fn()}
        onSelect={vi.fn()}
        open
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Path does not exist");
    fireEvent.click(screen.getByRole("button", { name: "Open home folder" }));
    expect(await screen.findByText("/Users/reviewer")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/filesystem/directories",
      expect.objectContaining({ body: JSON.stringify({ path: null }) }),
    );
  });

  it("closes on Escape and restores page scrolling", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(rootListing), { status: 200 })),
    );
    const onCancel = vi.fn();

    const view = render(
      <DirectoryPicker
        initialPath=""
        onCancel={onCancel}
        onSelect={vi.fn()}
        open
      />,
    );

    await waitFor(() => expect(document.body.style.overflow).toBe("hidden"));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledOnce();
    view.unmount();
    expect(document.body.style.overflow).toBe("");
  });
});
