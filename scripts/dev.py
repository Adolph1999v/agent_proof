"""Start AgentProof on available local ports and open the working surface."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"


def port_is_available(port: int, host: str = HOST) -> bool:
    """Return whether a TCP port can be bound on the local interface."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def find_available_port(preferred: int, attempts: int = 100) -> int:
    """Use the preferred port or the first free port immediately after it."""
    for port in range(preferred, preferred + attempts):
        if port_is_available(port):
            return port
    raise RuntimeError(f"No available local port found after {preferred}")


def build_commands(backend_port: int, frontend_port: int) -> tuple[list[str], list[str]]:
    """Build explicit backend and frontend commands for the current platform."""
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise RuntimeError("npm was not found. Run `make setup` after installing Node.js.")

    backend = [
        sys.executable,
        "-m",
        "uvicorn",
        "agentproof.app:app",
        "--app-dir",
        "backend",
        "--host",
        HOST,
        "--port",
        str(backend_port),
        "--reload",
    ]
    frontend = [
        npm,
        "--prefix",
        "frontend",
        "run",
        "dev",
        "--",
        "--host",
        HOST,
        "--port",
        str(frontend_port),
        "--strictPort",
    ]
    return backend, frontend


def wait_for_server(
    url: str,
    process: subprocess.Popen[bytes],
    timeout_seconds: float = 20,
) -> None:
    """Wait until a child server responds or fails with a useful error."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Development service exited early with code {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:  # noqa: S310
                if response.status < 500:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.15)
    raise RuntimeError(f"Timed out waiting for {url}")


def stop_process(process: subprocess.Popen[bytes]) -> None:
    """Stop one development process and its reloader children."""
    if process.poll() is not None:
        return

    if os.name == "nt":
        process.terminate()
    else:
        os.killpg(process.pid, signal.SIGTERM)

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backend_port = find_available_port(args.backend_port)
    frontend_port = find_available_port(args.frontend_port)
    backend_command, frontend_command = build_commands(backend_port, frontend_port)

    environment = os.environ.copy()
    environment["VITE_API_TARGET"] = f"http://{HOST}:{backend_port}"
    process_options: dict[str, object] = {"cwd": ROOT, "env": environment}
    if os.name == "nt":
        process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        process_options["start_new_session"] = True

    print(
        f"Starting AgentProof (backend :{backend_port}, frontend :{frontend_port})...",
        flush=True,
    )
    backend = subprocess.Popen(backend_command, **process_options)  # type: ignore[arg-type]
    frontend = subprocess.Popen(
        frontend_command,
        **process_options,  # type: ignore[arg-type]
    )
    processes = [backend, frontend]

    try:
        wait_for_server(f"http://{HOST}:{backend_port}/api/health", backend)
        url = f"http://{HOST}:{frontend_port}"
        wait_for_server(url, frontend)
        print(f"AgentProof is ready at {url}", flush=True)
        if not args.no_browser and not webbrowser.open(url):
            print("The browser could not be opened automatically; use the URL above.", flush=True)

        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        return next(
            (process.returncode or 1 for process in processes if process.returncode is not None),
            1,
        )
    except KeyboardInterrupt:
        return 0
    except RuntimeError as error:
        print(f"Unable to start AgentProof: {error}", file=sys.stderr, flush=True)
        return 1
    finally:
        for process in reversed(processes):
            stop_process(process)


if __name__ == "__main__":
    raise SystemExit(main())
