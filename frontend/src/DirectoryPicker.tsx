import { useEffect, useRef, useState } from "react";

type DirectoryEntry = {
  name: string;
  path: string;
};

type DirectoryListing = {
  current_path: string;
  parent_path: string | null;
  directories: DirectoryEntry[];
};

type DirectoryPickerProps = {
  initialPath: string;
  onCancel: () => void;
  onSelect: (path: string) => void;
  open: boolean;
};

type BrowserState =
  | { status: "loading" }
  | { status: "ready"; listing: DirectoryListing }
  | { status: "error"; message: string };

export default function DirectoryPicker({
  initialPath,
  onCancel,
  onSelect,
  open,
}: DirectoryPickerProps) {
  const [state, setState] = useState<BrowserState>({ status: "loading" });
  const closeButton = useRef<HTMLButtonElement>(null);
  const requestSequence = useRef(0);

  async function browse(path: string | null) {
    const requestId = ++requestSequence.current;
    setState({ status: "loading" });
    try {
      const response = await fetch("/api/filesystem/directories", {
        body: JSON.stringify({ path }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const payload = (await response.json()) as DirectoryListing | { detail?: string };
      if (!response.ok || !("directories" in payload)) {
        throw new Error("detail" in payload ? payload.detail : "Unable to browse this folder.");
      }
      if (requestId === requestSequence.current) {
        setState({ status: "ready", listing: payload });
      }
    } catch (error: unknown) {
      if (requestId === requestSequence.current) {
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Unable to browse this folder.",
        });
      }
    }
  }

  useEffect(() => {
    if (!open) return;
    void browse(initialPath.trim() || null);
    closeButton.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      requestSequence.current += 1;
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [initialPath, onCancel, open]);

  if (!open) return null;

  return (
    <div
      className="directory-picker-backdrop"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) onCancel();
      }}
      role="presentation"
    >
      <section
        aria-describedby="directory-picker-description"
        aria-labelledby="directory-picker-title"
        aria-modal="true"
        className="directory-picker"
        role="dialog"
      >
        <header className="directory-picker-header">
          <div>
            <span className="section-id">Local filesystem</span>
            <h2 id="directory-picker-title">Choose a project folder</h2>
            <p id="directory-picker-description">
              Browse directories on this computer. AgentProof reads no file contents here.
            </p>
          </div>
          <button
            aria-label="Close folder picker"
            className="directory-picker-close"
            onClick={onCancel}
            ref={closeButton}
            type="button"
          >
            ×
          </button>
        </header>

        {state.status === "ready" ? (
          <>
            <div className="directory-location">
              <button
                disabled={!state.listing.parent_path}
                onClick={() => void browse(state.listing.parent_path)}
                type="button"
              >
                ↑ Parent
              </button>
              <code title={state.listing.current_path}>{state.listing.current_path}</code>
            </div>

            <div className="directory-list">
              {state.listing.directories.length ? (
                state.listing.directories.map((directory) => (
                  <button
                    aria-label={`Open folder ${directory.name}`}
                    className="directory-entry"
                    key={directory.path}
                    onClick={() => void browse(directory.path)}
                    type="button"
                  >
                    <span aria-hidden="true">DIR</span>
                    <strong>{directory.name}</strong>
                    <i aria-hidden="true">→</i>
                  </button>
                ))
              ) : (
                <p className="directory-empty">This folder contains no accessible subfolders.</p>
              )}
            </div>

            <footer className="directory-picker-actions">
              <button className="secondary-action" onClick={onCancel} type="button">
                Cancel
              </button>
              <button
                className="primary-action"
                onClick={() => onSelect(state.listing.current_path)}
                type="button"
              >
                Use this folder
              </button>
            </footer>
          </>
        ) : state.status === "error" ? (
          <div className="directory-picker-message" role="alert">
            <strong>Folder unavailable</strong>
            <p>{state.message}</p>
            <button onClick={() => void browse(null)} type="button">
              Open home folder
            </button>
          </div>
        ) : (
          <div className="directory-picker-message" role="status">
            <span className="directory-loader" aria-hidden="true" />
            <strong>Loading folders…</strong>
          </div>
        )}
      </section>
    </div>
  );
}
