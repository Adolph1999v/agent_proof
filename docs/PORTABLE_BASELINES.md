# Portable baseline backup and restore — proposed design

This is a design for review. Export and restore are not implemented.

## What exists today

Each selected project has a stable ID in its Git metadata, or in `.agentproof/repository-id` for a
non-Git folder. AgentProof stores that project's record, approved baseline manifests, and files
identified by SHA-256 hash under `artifacts/projects/<project-id>/`. The record also contains local
folder paths. Each baseline points to its parent and, for Git projects, records the source commit.
Moving a folder with its identity marker keeps its history; a second live folder with the same ID is
rejected.

## Backup contents

Export one project at a time as a versioned archive. Include its identity kind and ID, an ordered
list of all approved baseline summaries and manifests, and only the file objects those manifests
reference. Keep hashes, parent links, task descriptions, and original approval times. Show the file
list and archive size before saving. Treat all approved source content as private: a source file can
contain a secret even when its name looks harmless.

Never include local paths, the selected working folder or `.git` directory, model files, caches,
virtual environments, temporary clones, current-state audits, model prompts, run reports, or
trajectories. Block export when a baseline includes a known secret-file path such as `.env` or a
private key; do not silently omit that file and break the history. An old `evidence_run_id` may remain
as historical text, but the restored app must label its report unavailable unless that report exists
locally. Hash checks detect damaged data; they do not prove who created the archive.

## Restore rules

The user selects an archive and a target project folder. AgentProof first opens the archive as
**data only** in a bounded staging area. It accepts only the expected files and schema version,
rejects absolute or `..` paths, archive symlinks, oversized or duplicate entries, invalid IDs,
broken parent chains, cross-project references, and missing objects. It recomputes every object hash
and each baseline's manifest digest before showing a preview. No imported file is executed.

Compare the archive's ID and identity kind with the target marker and local history. A moved folder
with its marker can retain its ID. If the marker is missing, matching Git ancestry or file content
is supporting evidence, not enough to claim identity automatically; the user must explicitly link
it. Reject an incompatible Git lineage, a copied ID active at another live path, or a different
repository using the same ID. Different IDs always keep separate histories.

Show the baseline count, date range, source files, space needed, and whether this is a new import,
an exact duplicate, a safe append, or a conflict. Exact duplicates change nothing. Append only
baselines whose parent chain matches the existing history, after explicit confirmation. A conflicting
manifest or object stops the restore; never replace existing history. For a new project, stage and
verify the whole directory before publishing it. For an append, lock that project, add only new
objects and manifests, and update a backed-up project record last. On error, leave the recorded
history and target folder unchanged and remove unreferenced new files. Restoring history does not
approve the target's current files or run its tests; the user inspects the project afterward.

## Tests before implementation

- Round-trip several baselines for Git and non-Git projects, including a moved folder.
- Reject a different repository, a copied live identity, incompatible Git ancestry, and a missing
  marker without explicit linking.
- Verify exact-duplicate no-op, confirmed append, divergent history rejection, and rollback after
  an interrupted import.
- Reject changed objects or manifests, missing files, bad parent links, cross-project references,
  unsafe paths or symlinks, duplicate archive entries, and oversized archives.
- Confirm local paths, secret-file paths, reports, prompts, caches, and model files never enter an
  export; confirm import never executes archive content or approves the current project.
