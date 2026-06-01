"""Configuration for Meshtastic Quiz.

Every deployment-specific or secret value is read from the environment so that the
committed code contains ZERO personal/network info. See ``.env.example`` for the full
list of variables and ``deploy/`` for how they are wired in.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# The four answer emoji, in option order (index 0..3). These are the keycap-number
# emoji that Meshtastic clients send as tapback reactions.
ANSWER_EMOJI: List[str] = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
# Plain-text equivalents accepted when ALLOW_TYPED_ANSWERS is on.
ANSWER_TYPED = ["1", "2", "3", "4"]


@dataclass
class Config:
    """Runtime configuration. Defaults are safe placeholders; real values come from env."""

    # --- MeshMonitor transport ---
    meshmonitor_url: str = field(default_factory=lambda: _env("MESHMONITOR_URL", "http://meshmonitor:3001"))
    meshmonitor_token: str = field(default_factory=lambda: _env("MESHMONITOR_API_TOKEN", ""))
    # Optional explicit source id (multi-source MeshMonitor). Blank = use the primary source.
    source_id: str = field(default_factory=lambda: _env("MESHMONITOR_SOURCE_ID", ""))
    http_timeout_s: float = field(default_factory=lambda: _env_float("HTTP_TIMEOUT_S", 15.0))

    # --- Channel / gating ---
    trivia_channel_index: int = field(default_factory=lambda: _env_int("TRIVIA_CHANNEL_INDEX", 2))
    # The PRIMARY channel index. The bot also listens here, but ONLY for the `!trivia`
    # advert command (a deliberate exception to "commands only work in the trivia
    # channel"). All OTHER commands are ignored on this channel.
    primary_channel_index: int = field(default_factory=lambda: _env_int("PRIMARY_CHANNEL_INDEX", 0))
    # The Meshtastic channel-add deep link advertised by `!trivia` on the primary channel.
    # This is a PUBLIC link (safe to commit). Override per-deployment for your own channel.
    add_link: str = field(default_factory=lambda: _env(
        "TRIVIA_ADD_LINK",
        "https://meshtastic.org/e/?add=true#CgsSATEaBnRyaXZpYRIYCAEY-gEgCygFOAFAB0gBUB5YFGgByAYB",
    ))

    # --- Game timing ---
    question_window_s: int = field(default_factory=lambda: _env_int("QUESTION_WINDOW_S", 90))
    inter_question_gap_s: int = field(default_factory=lambda: _env_int("INTER_QUESTION_GAP_S", 8))
    poll_interval_s: float = field(default_factory=lambda: _env_float("POLL_INTERVAL_S", 4.0))
    min_send_interval_s: float = field(default_factory=lambda: _env_float("MIN_SEND_INTERVAL_S", 2.0))

    # --- Scoring (see DECISIONS.md) ---
    base_points: int = field(default_factory=lambda: _env_int("BASE_POINTS", 10))
    max_speed_bonus: int = field(default_factory=lambda: _env_int("MAX_SPEED_BONUS", 5))
    first_correct_bonus: int = field(default_factory=lambda: _env_int("FIRST_CORRECT_BONUS", 3))

    # --- Anti-runup guard ---
    # If the number of DISTINCT answering players is <= this value for
    # `runup_max_low_rounds` questions in a row, auto-stop the game.
    runup_min_players: int = field(default_factory=lambda: _env_int("RUNUP_MIN_PLAYERS", 1))
    runup_max_low_rounds: int = field(default_factory=lambda: _env_int("RUNUP_MAX_LOW_ROUNDS", 3))

    # --- Questions ---
    questions_per_game: int = field(default_factory=lambda: _env_int("QUESTIONS_PER_GAME", 12))
    leaderboard_top_n: int = field(default_factory=lambda: _env_int("LEADERBOARD_TOP_N", 5))

    # --- Mesh limits ---
    max_payload_bytes: int = field(default_factory=lambda: _env_int("MAX_PAYLOAD_BYTES", 200))

    # --- Fallback answering ---
    allow_typed_answers: bool = field(default_factory=lambda: _env_bool("ALLOW_TYPED_ANSWERS", True))

    # --- Persistence ---
    state_path: str = field(default_factory=lambda: _env("STATE_PATH", "data/state.json"))
    questions_path: str = field(default_factory=lambda: _env("QUESTIONS_PATH", "data/questions.json"))

    # --- Identity ---
    # The bot's own node hex id (e.g. "!abcdef12"), so it can ignore its own reactions.
    # Optional: if blank, self-reactions are simply included (the bot does not react).
    bot_node_id: str = field(default_factory=lambda: _env("BOT_NODE_ID", ""))

    # --- Host-can-play (opt-in; see DECISIONS.md) ---
    # When true, a HUMAN tapback/typed answer originating from the host node
    # (`bot_node_id`) is counted as a normal player answer, so the operator of the host
    # node can both launch AND play. The bot PROCESS still never auto-answers its own
    # questions — only inbound traffic seen on the channel is ever scored, and the bot
    # never emits answer reactions. Default false: host node is ignored entirely.
    host_can_play: bool = field(default_factory=lambda: _env_bool("HOST_CAN_PLAY", False))

    def validate(self) -> None:
        if not self.meshmonitor_token:
            raise ValueError("MESHMONITOR_API_TOKEN is required")
        if not self.meshmonitor_url:
            raise ValueError("MESHMONITOR_URL is required")
        if self.question_window_s < 5:
            raise ValueError("QUESTION_WINDOW_S too small")
