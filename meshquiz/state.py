"""Lightweight JSON persistence for crash recovery + cross-restart cursor.

We persist:
- the last-seen message timestamp cursor (so a restart doesn't replay old traffic), and
- a snapshot of the current leaderboard + whether a game was running.

DECISION (see DECISIONS.md): on restart we do NOT resume a half-finished question (the
mesh has moved on). We restore the leaderboard and, if a game was running, announce that
the bot restarted and the operator can !starttrivia to continue. This avoids scoring on a
question whose reactions we may have missed during downtime.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Dict, Optional


def _atomic_write(path: str, data: dict) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load_state(path: str) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path: str, *, cursor_ms: int, was_running: bool, leaderboard: Optional[list] = None) -> None:
    _atomic_write(path, {
        "cursor_ms": cursor_ms,
        "was_running": was_running,
        "leaderboard": leaderboard or [],
    })
