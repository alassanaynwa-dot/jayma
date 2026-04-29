"""Tests du helper de format XOF."""
from core.utils.money import format_xof


def test_format_xof_basic():
    assert format_xof(0) == "0 XOF"
    assert format_xof(10) == "10 XOF"
    assert format_xof(100) == "100 XOF"
    assert format_xof(1000) == "1 000 XOF"
    assert format_xof(10000) == "10 000 XOF"
    assert format_xof(1500000) == "1 500 000 XOF"


def test_format_xof_negative():
    assert format_xof(-500) == "-500 XOF"
    assert format_xof(-12345) == "-12 345 XOF"


def test_format_xof_none():
    assert format_xof(None) == ""


def test_format_xof_no_currency():
    assert format_xof(10000, with_currency=False) == "10 000"
    assert format_xof(0, with_currency=False) == "0"
