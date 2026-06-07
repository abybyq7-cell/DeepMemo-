"""Lightweight structural checks for the public repository layout."""

from pathlib import Path


def test_public_layout_contains_expected_directories():
    root = Path(__file__).resolve().parents[1]
    for name in ["backend", "frontend", "tools", "memory", "tests", "docs"]:
        assert (root / name).exists()


def test_readme_exists():
    root = Path(__file__).resolve().parents[1]
    assert (root / "README.md").exists()
