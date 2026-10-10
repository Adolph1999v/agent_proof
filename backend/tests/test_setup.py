"""The documented setup must keep generated Python files inside a moved project."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_make_commands_use_local_paths_after_move_to_folder_with_spaces(
    tmp_path: Path,
) -> None:
    if shutil.which("make") is None:
        pytest.skip("The Makefile setup is available on macOS and Linux.")

    moved_project = tmp_path / "moved project"
    moved_project.mkdir()
    (moved_project / "frontend").mkdir()
    shutil.copyfile(PROJECT_ROOT / "Makefile", moved_project / "Makefile")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    script = (
        "#!/bin/sh\n"
        'printf "%s|%s|%s|%s\\n" "${0##*/}" "$UV_CACHE_DIR" '
        '"$UV_PYTHON_INSTALL_DIR" "$*" >> "$AGENTPROOF_SETUP_LOG"\n'
    )
    for name in ("uv", "npm"):
        executable = fake_bin / name
        executable.write_text(script, encoding="utf-8")
        executable.chmod(0o755)

    log = tmp_path / "setup-calls.txt"
    result = subprocess.run(
        ["make", "setup"],
        cwd=moved_project,
        env={
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "AGENTPROOF_SETUP_LOG": str(log),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    calls = [line.split("|", 3) for line in log.read_text(encoding="utf-8").splitlines()]
    assert calls == [
        [
            "uv",
            str(moved_project / ".uv-cache"),
            str(moved_project / ".python"),
            "python install --no-bin 3.12",
        ],
        [
            "uv",
            str(moved_project / ".uv-cache"),
            str(moved_project / ".python"),
            "venv --python 3.12 .venv",
        ],
        [
            "uv",
            str(moved_project / ".uv-cache"),
            "",
            "pip install --python .venv/bin/python -r requirements.txt",
        ],
        ["npm", "", "", "install"],
    ]

    python_bin = moved_project / ".venv" / "bin"
    python_bin.mkdir(parents=True)
    fake_python = python_bin / "python"
    fake_python.write_text(
        '#!/bin/sh\nprintf "python|%s|%s\\n" "$PYTHONPATH" "$*" '
        '>> "$AGENTPROOF_SETUP_LOG"\n',
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    result = subprocess.run(
        ["make", "lock", "phase3-smoke", "evaluate", "CASE=example"],
        cwd=moved_project,
        env={
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "AGENTPROOF_SETUP_LOG": str(log),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text(encoding="utf-8").splitlines()[4:] == [
        f"uv|{moved_project / '.uv-cache'}||pip compile pyproject.toml --extra dev "
        "--output-file requirements.txt",
        f"python|{moved_project / 'backend'}|scripts/phase3_smoke.py",
        f"python|{moved_project / 'backend'}|scripts/evaluate.py --case example",
    ]
