from datetime import date

import pytest

from parser import format_date, parse_date


def test_valid_date_is_parsed() -> None:
    fallback = date(2000, 1, 1)
    assert parse_date("2026-08-31", fallback) == date(2026, 8, 31)


def test_outer_whitespace_is_ignored() -> None:
    fallback = date(2000, 1, 1)
    assert parse_date(" 2026-08-31\n", fallback) == date(2026, 8, 31)


def test_invalid_format_is_rejected() -> None:
    fallback = date(2000, 1, 1)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_date("31/08/2026", fallback)


def test_date_formatting_is_preserved() -> None:
    assert format_date(date(2026, 8, 31)) == "2026-08-31"
