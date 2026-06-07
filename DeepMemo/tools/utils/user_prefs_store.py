"""Persistent storage for user preferences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from tools.utils.config import DATA_DIR, DEFAULT_USER_PREFS, ensure_data_dir

PREFS_FILE = Path(DATA_DIR) / "user_prefs.json"


def load_user_prefs() -> Dict[str, Any]:
    ensure_data_dir()
    if not PREFS_FILE.exists():
        return DEFAULT_USER_PREFS.copy()
    try:
        data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return DEFAULT_USER_PREFS.copy()
        prefs = DEFAULT_USER_PREFS.copy()
        prefs.update(data)
        return prefs
    except Exception:
        return DEFAULT_USER_PREFS.copy()


def save_user_prefs(prefs: Dict[str, Any]) -> None:
    ensure_data_dir()
    merged = DEFAULT_USER_PREFS.copy()
    merged.update(prefs or {})
    PREFS_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


