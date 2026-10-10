# Execution isolation — current limits and proposed next step

This is an assessment, not an implemented sandbox. Today, select only projects whose tests you
trust to run on your computer.

## What AgentProof does now

- It inventories a selected project, preserves approved tests and pytest settings, and runs checks
  in AgentProof-owned disposable copies. Candidate test changes cannot replace approved evidence.
- Most verifier and challenge Git commands have a 30-second timeout; pytest requests are bounded at
  120 seconds. Project-store Git calls do not all have timeouts. Snapshot size is limited to 25 MB
  per file and 250 MB per snapshot. Model context and displayed output are bounded. A test timeout
  is recorded as a timeout rather than a pass.
- It validates model-generated challenge syntax and blocks many dangerous Python operations before
  running that challenge. Challenge runs get a small environment with temporary `HOME` and `TMPDIR`
  inside the copy. The initial project audit and approved tests have fewer environment restrictions.
- First inspection can write a small identity marker inside the selected project's Git metadata or
  `.agentproof` folder. Candidate patches and pytest run in copies, not in the selected source tree.

## What it does not protect

A disposable copy keeps ordinary relative test writes away from the selected project. It does not
confine the test process. Approved tests, imported application code, pytest configuration, and generated
challenges still run as the user's normal operating-system account. They can try to read other
folders and environment secrets, write outside the copy, access the network, or start subprocesses.
Static checks on one generated test cannot make its imported code safe. The child process inherits
host access; setting `HOME` or `TMPDIR` does not remove it.

The current subprocess timeout ends the direct command, but does not guarantee cleanup of every
grandchild. CPU, memory, process count, disk writes, and network traffic have no operating-system
limit. Output is captured before its saved preview is shortened, so a noisy test could use excess
memory. These limits make current execution unsuitable for unknown or hostile repositories.

## Practical next version on macOS

Offer an **opt-in isolated runner** using a local Linux VM-backed container runtime, such as
[Colima](https://github.com/abiosoft/colima/blob/main/README.md?plain=1) with the Docker CLI. Keep
the local model call on the host; only repository commands and pytest enter the runner. Use a pinned
Python image, a non-root user, no host home or Docker socket mount, and no direct mount of the
selected project. Copy the approved inputs into a size-limited writable workspace; make the rest
of the container read-only. Disable networking (`--network none`), drop privileges, and set CPU,
memory, process-count, output, and disk budgets. Docker documents the relevant
[run limits](https://docs.docker.com/reference/cli/docker/container/run) and
[network isolation](https://docs.docker.com/engine/network/drivers/none/). A local VM adds a boundary
between the Linux container and macOS, but its configuration and mounts still need review.

Use one job ID to track the whole process tree. On timeout or cancellation, stop and remove the
container, wait for cleanup, and keep the exit reason and bounded logs. If the runtime is missing,
report that isolated execution is unavailable; never silently describe the current local runner as
isolated. The first version should use fixed limits and a small trusted-project test suite before
allowing user-adjustable limits.

## Later cross-platform approach

Keep one narrow execution interface for create, run, collect, and destroy. Use local Linux
containers on Linux and VM-backed containers on macOS and Windows, with the same pinned image,
input manifest, output format, and fail-closed policy. Treat the container or VM as untrusted after
each run and discard it. Test host-file access, outbound network attempts, fork bombs, memory and
disk exhaustion, huge output, timeouts, cancellation, and crash recovery on every supported OS.
If a secure runner cannot start or enforce a required limit, return `INCONCLUSIVE` with the exact
reason; never convert an isolation failure into `VERIFIED`.
