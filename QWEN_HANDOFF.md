# Qwen Handoff — Task 1

## Objective

Task 1 implemented only the read-only backend directory-browsing API required by a future frontend picker. No frontend work was performed.

## Files changed

- `backend/agentproof/app.py` — added `POST /api/filesystem/directories` endpoint and `DirectoryEntry` import
- `backend/agentproof/models.py` — added `DirectoryBrowseRequest` and `DirectoryBrowseResponse` Pydantic models
- `backend/agentproof/directory_browser.py` — pure helper `browse_directory()` with robust error handling per child
- `backend/tests/test_directory_browser.py` — 25 tests covering pure helper and HTTP endpoint
- `QWEN_HANDOFF.md` — this handoff document

No frontend files were changed.

## API contract

- **Endpoint:** `POST /api/filesystem/directories`
- **Body:** optional JSON with nullable `path` field
- **Default:** when `path` is `null`, omitted, or whitespace-only, defaults to the user's home directory
- **Response fields:**
  - `current_path` — resolved absolute path of the browsed directory
  - `parent_path` — parent directory path, or `null` at the filesystem root
  - `directories` — list of immediate child directories, each with `name` and `path`, sorted case-insensitively by name
- **HTTP 400 conditions:** path cannot be resolved, path does not exist, or path is not a directory

## Security and portability decisions

- Read-only: no filesystem modifications during browsing.
- Immediate child directories only; no recursive scan.
- No file contents are returned.
- No shell commands are used.
- Operating-system-neutral: uses `pathlib` and direct Python filesystem APIs (`os.scandir`).
- Inaccessible children (entries that raise `OSError` on `is_dir()` or on `resolve()`) are skipped individually without failing the request.

## Tests added

All tests live in `backend/tests/test_directory_browser.py` (25 total):

- **Pure helper tests (13):** default-to-home for `None`/empty/whitespace paths, immediate child listing, case-insensitive sorting, file exclusion, path normalization, parent path correctness, root-parent-is-null, nonexistent path raises, file path raises, inaccessible `is_dir()` child skipped, no filesystem modification, child `Path.resolve()` failure skipped.
- **HTTP endpoint tests (12):** null path returns home, omitted path returns home, children sorted in response, files excluded, correct field names, nonexistent path returns 400, file path returns 400, inaccessible child skipped via endpoint, no filesystem modification via endpoint, parent path in response, root parent path is null.

## Commands run and exact results

| Command | Result |
|---------|--------|
| `.venv/bin/python -m pytest backend/tests/test_directory_browser.py` | 25 passed |
| `make test-backend` | 61 passed |
| `make lint-backend` | passed |
| `git diff --check` | passed (no whitespace errors) |

## Known limitations

- There is currently no frontend folder-picker interface.
- Users cannot access this endpoint through mouse navigation yet.
- Task 2 must connect a frontend modal to the backend API.

## Items requiring reviewer attention

- The new filesystem-browsing security boundary: the endpoint is read-only by design, but it exposes directory structure information. Review whether additional path restrictions (e.g., confinement to a user-approved project root) are required before frontend integration.
- The inaccessible-child tests (`test_inaccessible_child_skipped_without_failing`, `test_child_resolve_failure_skipped_without_failing`, and their HTTP counterparts) use monkey-patched `os.DirEntry.is_dir` and `Path.resolve` to simulate permission errors. These are accurate for the error-handling logic but do not exercise real filesystem permission denial.
