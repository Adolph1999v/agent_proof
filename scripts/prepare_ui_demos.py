"""Create standalone, disposable UI demo repositories from checked-in fixtures."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PROJECT_ROOT / "demo_fixtures"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "ui_demo_cases"
CASE_NAMES = ("public_dateutil_empty_input", "unsafe_deleted_test")


def _git(repository: Path, *arguments: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Git could not prepare the demo.")


def prepare(output: Path) -> Path:
    """Build both baseline repos and patches without replacing an existing folder."""
    destination = output.expanduser().resolve()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Demo folder already exists: {destination}")
    if destination == FIXTURE_ROOT or FIXTURE_ROOT in destination.parents:
        raise ValueError("Choose an output folder outside demo_fixtures.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".agentproof-ui-demos-", dir=destination.parent
    ) as temporary:
        staged = Path(temporary) / "ui_demo_cases"
        staged.mkdir()
        shutil.copytree(FIXTURE_ROOT / "changes", staged / "changes")
        for name in CASE_NAMES:
            repository = staged / name
            shutil.copytree(FIXTURE_ROOT / name, repository)
            _git(repository, "init", "--quiet")
            _git(repository, "add", ".")
            _git(
                repository,
                "-c",
                "user.name=AgentProof Demo",
                "-c",
                "user.email=demo@agentproof.local",
                "commit",
                "--quiet",
                "-m",
                "Approved demo baseline",
            )
        staged.rename(destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="New folder for the demo repos (default: artifacts/ui_demo_cases)",
    )
    args = parser.parse_args()
    try:
        destination = prepare(args.output)
    except (FileExistsError, ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
    print(f"UI demo repositories ready: {destination}")


if __name__ == "__main__":
    main()
