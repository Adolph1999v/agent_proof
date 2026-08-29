from unittest.mock import patch

from scripts.dev import build_commands, find_available_port


def test_find_available_port_skips_a_port_that_is_in_use() -> None:
    with patch("scripts.dev.port_is_available", side_effect=[False, True]):
        selected = find_available_port(8000)

    assert selected == 8001


def test_build_commands_connects_vite_and_uvicorn_to_selected_ports() -> None:
    backend, frontend = build_commands(8010, 5180)

    assert backend[-3:] == ["--port", "8010", "--reload"]
    assert frontend[1:4] == ["--prefix", "frontend", "run"]
    assert frontend[-3:] == ["--port", "5180", "--strictPort"]
