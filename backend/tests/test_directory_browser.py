"""Tests for the read-only directory-browsing endpoint and helper."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
import pytest
from agentproof.app import app
from agentproof.directory_browser import DirectoryBrowseError, browse_directory

# ---------------------------------------------------------------------------
# HTTP helper (mirrors test_api.py)
# ---------------------------------------------------------------------------

def _request(method: str, path: str, payload: dict | None = None) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=payload)

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------

class TestBrowseDirectoryPure:
    """Unit tests for the browse_directory helper function."""

    def test_none_path_defaults_to_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / "proj").mkdir()
        current, parent, children = browse_directory(None)
        assert current == str(tmp_path)
        assert parent is not None
        assert len(children) == 1
        assert children[0][0] == "proj"

    def test_empty_string_path_defaults_to_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        current, _parent, _children = browse_directory("")
        assert current == str(tmp_path)

    def test_whitespace_path_defaults_to_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        current, _parent, _children = browse_directory("   ")
        assert current == str(tmp_path)

    def test_returns_immediate_child_directories(self, tmp_path: Path) -> None:
        (tmp_path / "alpha").mkdir()
        (tmp_path / "beta").mkdir()
        (tmp_path / "alpha" / "nested").mkdir()
        (tmp_path / "file.txt").write_text("data")
        current, _parent, children = browse_directory(str(tmp_path))
        names = [c[0] for c in children]
        assert names == ["alpha", "beta"]
        assert current == str(tmp_path)

    def test_children_sorted_case_insensitively(self, tmp_path: Path) -> None:
        (tmp_path / "Zulu").mkdir()
        (tmp_path / "alpha").mkdir()
        (tmp_path / "Bravo").mkdir()
        _current, _parent, children = browse_directory(str(tmp_path))
        names = [c[0] for c in children]
        assert names == ["alpha", "Bravo", "Zulu"]

    def test_excludes_regular_files(self, tmp_path: Path) -> None:
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file1.txt").write_text("a")
        (tmp_path / "file2.py").write_text("b")
        _current, _parent, children = browse_directory(str(tmp_path))
        names = [c[0] for c in children]
        assert names == ["subdir"]

    def test_current_path_is_normalized_absolute(self, tmp_path: Path) -> None:
        subdir = tmp_path / "sub"
        subdir.mkdir()
        # Pass a redundant path to verify normalization
        target = str(subdir / ".." / "sub")
        current, _parent, _children = browse_directory(target)
        assert current == str(subdir)
        assert Path(current).is_absolute()

    def test_parent_path_correct(self, tmp_path: Path) -> None:
        (tmp_path / "child").mkdir()
        current, parent, _children = browse_directory(str(tmp_path / "child"))
        assert current == str(tmp_path / "child")
        assert parent == str(tmp_path)

    def test_parent_path_null_at_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Simulate a root-like directory where parent == self
        fake_root = tmp_path / "fake_root"
        fake_root.mkdir()

        original_resolve = Path.resolve
        original_parent = Path.parent.fget

        def patched_resolve(p: Path) -> Path:
            resolved = original_resolve(p)
            if str(resolved).startswith(str(fake_root)):
                return fake_root
            return resolved

        @property
        def patched_parent(p: Path) -> Path:
            parent = original_parent.__get__(p, Path)
            if str(p) == str(fake_root):
                return fake_root
            return parent

        monkeypatch.setattr(Path, "resolve", patched_resolve)
        monkeypatch.setattr(Path, "parent", patched_parent)

        current, parent, _children = browse_directory(str(fake_root))
        assert parent is None

    def test_nonexistent_path_raises(self) -> None:
        with pytest.raises(DirectoryBrowseError, match="does not exist"):
            browse_directory("/nonexistent/path/agentproof_test_12345")

    def test_file_path_raises(self, tmp_path: Path) -> None:
        file_path = tmp_path / "file.txt"
        file_path.write_text("data")
        with pytest.raises(DirectoryBrowseError, match="not a directory"):
            browse_directory(str(file_path))

    def test_inaccessible_child_skipped_without_failing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "good").mkdir()
        (tmp_path / "bad").mkdir()

        original_is_dir = os.DirEntry.is_dir

        def patched_is_dir(self) -> bool:
            if "bad" in self.path:
                raise OSError("Permission denied")
            return original_is_dir(self)

        monkeypatch.setattr(os.DirEntry, "is_dir", patched_is_dir)

        _current, _parent, children = browse_directory(str(tmp_path))
        names = [c[0] for c in children]
        assert names == ["good"]
        assert "bad" not in names

    def test_browsing_does_not_modify_filesystem(self, tmp_path: Path) -> None:
        (tmp_path / "d1").mkdir()
        (tmp_path / "f1.txt").write_text("data")
        initial_contents = set(tmp_path.iterdir())

        browse_directory(str(tmp_path))

        assert set(tmp_path.iterdir()) == initial_contents

    def test_child_resolve_failure_skipped_without_failing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "good1").mkdir()
        (tmp_path / "bad_child").mkdir()
        (tmp_path / "good2").mkdir()

        original_resolve = Path.resolve

        def patched_resolve(p: Path) -> Path:
            if "bad_child" in str(p):
                raise OSError("Cannot resolve child path")
            return original_resolve(p)

        monkeypatch.setattr(Path, "resolve", patched_resolve)

        _current, _parent, children = browse_directory(str(tmp_path))
        names = [c[0] for c in children]
        assert names == ["good1", "good2"]
        assert "bad_child" not in names


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

class TestDirectoryBrowseEndpoint:
    """Integration tests against the FastAPI endpoint."""

    def test_null_path_returns_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / "mydir").mkdir()

        response = _request("POST", "/api/filesystem/directories", {"path": None})

        assert response.status_code == 200
        payload = response.json()
        assert payload["current_path"] == str(tmp_path)
        assert len(payload["directories"]) == 1
        assert payload["directories"][0]["name"] == "mydir"

    def test_omitted_path_returns_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / "x").mkdir()

        response = _request("POST", "/api/filesystem/directories", {})

        assert response.status_code == 200
        assert len(response.json()["directories"]) == 1

    def test_children_sorted_in_response(self, tmp_path: Path) -> None:
        (tmp_path / "Zebra").mkdir()
        (tmp_path / "apple").mkdir()

        response = _request("POST", "/api/filesystem/directories", {"path": str(tmp_path)})

        assert response.status_code == 200
        names = [d["name"] for d in response.json()["directories"]]
        assert names == ["apple", "Zebra"]

    def test_files_excluded_in_response(self, tmp_path: Path) -> None:
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file.txt").write_text("data")

        response = _request("POST", "/api/filesystem/directories", {"path": str(tmp_path)})

        assert response.status_code == 200
        dirs = response.json()["directories"]
        assert len(dirs) == 1
        assert dirs[0]["name"] == "subdir"

    def test_response_has_correct_field_names(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()

        response = _request("POST", "/api/filesystem/directories", {"path": str(tmp_path)})

        assert response.status_code == 200
        payload = response.json()
        assert "current_path" in payload
        assert "parent_path" in payload
        assert "directories" in payload
        assert len(payload["directories"]) == 1
        assert "name" in payload["directories"][0]
        assert "path" in payload["directories"][0]

    def test_nonexistent_path_returns_400(self) -> None:
        response = _request(
            "POST",
            "/api/filesystem/directories",
            {"path": "/nonexistent/path/agentproof_test_xyz"},
        )

        assert response.status_code == 400
        assert "detail" in response.json()

    def test_file_path_returns_400(self, tmp_path: Path) -> None:
        file_path = tmp_path / "file.txt"
        file_path.write_text("data")

        response = _request(
            "POST",
            "/api/filesystem/directories",
            {"path": str(file_path)},
        )

        assert response.status_code == 400
        assert "detail" in response.json()

    def test_inaccessible_child_skipped_via_endpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "good").mkdir()
        (tmp_path / "bad").mkdir()

        original_is_dir = os.DirEntry.is_dir

        def patched_is_dir(self) -> bool:
            if "bad" in self.path:
                raise OSError("Permission denied")
            return original_is_dir(self)

        monkeypatch.setattr(os.DirEntry, "is_dir", patched_is_dir)

        response = _request(
            "POST",
            "/api/filesystem/directories",
            {"path": str(tmp_path)},
        )

        assert response.status_code == 200
        names = [d["name"] for d in response.json()["directories"]]
        assert names == ["good"]

    def test_browsing_does_not_modify_filesystem_via_endpoint(self, tmp_path: Path) -> None:
        (tmp_path / "d1").mkdir()
        (tmp_path / "f1.txt").write_text("data")
        initial = set(tmp_path.iterdir())

        _request("POST", "/api/filesystem/directories", {"path": str(tmp_path)})

        assert set(tmp_path.iterdir()) == initial

    def test_parent_path_in_response(self, tmp_path: Path) -> None:
        (tmp_path / "child").mkdir()

        response = _request(
            "POST",
            "/api/filesystem/directories",
            {"path": str(tmp_path / "child")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["parent_path"] == str(tmp_path)

    def test_parent_path_null_at_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_root = tmp_path / "fake_root"
        fake_root.mkdir()

        original_resolve = Path.resolve
        original_parent = Path.parent.fget

        def patched_resolve(p: Path) -> Path:
            resolved = original_resolve(p)
            if str(resolved).startswith(str(fake_root)):
                return fake_root
            return resolved

        @property
        def patched_parent(p: Path) -> Path:
            parent = original_parent.__get__(p, Path)
            if str(p) == str(fake_root):
                return fake_root
            return parent

        monkeypatch.setattr(Path, "resolve", patched_resolve)
        monkeypatch.setattr(Path, "parent", patched_parent)

        response = _request(
            "POST",
            "/api/filesystem/directories",
            {"path": str(fake_root)},
        )

        assert response.status_code == 200
        assert response.json()["parent_path"] is None
