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
  | { status: "error"; message: string; previousListing?: DirectoryListing };

export default function DirectoryPicker({
  initialPath,
  onCancel,
  onSelect,
  open,
}: DirectoryPickerProps) {
  const [state, setState] = useState<BrowserState>({ status: "loading" });
  const [history, setHistory] = useState<string[]>([]);
  const closeButton = useRef<HTMLButtonElement>(null);
  const requestSequence = useRef(0);

  async function browse(
    path: string | null,
    previousListing?: DirectoryListing,
  ): Promise<boolean> {
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
        return true;
      }
    } catch (error: unknown) {
      if (requestId === requestSequence.current) {
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Unable to browse this folder.",
          previousListing,
        });
      }
    }
    return false;
  }

  async function navigate(path: string | null) {
    const previousListing = state.status === "ready" ? state.listing : undefined;
    if (await browse(path, previousListing)) {
      const previousPath = previousListing?.current_path;
      if (previousPath) setHistory((paths) => [...paths, previousPath]);
    }
  }

  async function goBack() {
    const previousPath = history.at(-1);
    if (!previousPath) return;
    if (await browse(previousPath, state.status === "ready" ? state.listing : undefined)) {
      setHistory((paths) => paths.slice(0, -1));
    }
  }

  useEffect(() => {
    if (!open) return;
    setHistory([]);
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

  const visibleDirectories =
    state.status === "ready"
      ? state.listing.directories.filter((directory) => !directory.name.startsWith("."))
      : [];
  const currentFolderName =
    state.status === "ready"
      ? state.listing.current_path.split("/").filter(Boolean).at(-1) || "/"
      : "";
  const previousListing = state.status === "error" ? state.previousListing : undefined;

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
              <div className="directory-navigation">
                <button
                  aria-label="Go back one folder"
                  disabled={!history.length}
                  onClick={() => void goBack()}
                  title="Back"
                  type="button"
                >
                  ←
                </button>
                <button
                  aria-label="Go to parent folder"
                  disabled={!state.listing.parent_path}
                  onClick={() => void navigate(state.listing.parent_path)}
                  title="Up one level"
                  type="button"
                >
                  ↑
                </button>
              </div>
              <div className="directory-current" title={state.listing.current_path}>
                <span aria-hidden="true" className="directory-folder-icon" />
                <strong>{currentFolderName}</strong>
              </div>
            </div>

            <div className="directory-list">
              {visibleDirectories.length ? (
                visibleDirectories.map((directory) => (
                  <button
                    aria-label={`Open folder ${directory.name}`}
                    className="directory-entry"
                    key={directory.path}
                    onClick={() => void navigate(directory.path)}
                    type="button"
                  >
                    <span aria-hidden="true" className="directory-folder-icon" />
                    <strong>{directory.name}</strong>
                    <i aria-hidden="true">›</i>
                  </button>
                ))
              ) : (
                <p className="directory-empty">This folder contains no visible subfolders.</p>
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
            {previousListing && (
              <button
                onClick={() => setState({ status: "ready", listing: previousListing })}
                type="button"
              >
                Return to previous folder
              </button>
            )}
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
