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


# Difficulty tiers an installer can select via QUIZ_DIFFICULTY. "mixed" = the whole bank
# (legacy default). The bank stores the medium tier under the label "med"; "medium" is the
# operator-facing alias, normalized to "med" when filtering (see questions.select_by_difficulty).
VALID_DIFFICULTIES = frozenset({"easy", "medium", "med", "hard", "mixed"})

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
    # Difficulty tier the bot draws questions from. One of:
    #   easy   - approachable general-knowledge warm-ups (the original v1.x questions)
    #   medium - tougher general + real Meshtastic/LoRa knowledge (the everyday default)
    #   hard   - deep-cut Meshtastic/LoRa internals for mesh nerds
    #   mixed  - the ENTIRE bank, all tiers blended (legacy v1.x behavior)
    # DEFAULT is "mixed" so an existing install with no QUIZ_DIFFICULTY set behaves exactly
    # like before (draws from the whole bank). Operators pick a tier per their crowd.
    # "medium" is accepted as an alias for the bank's "med" difficulty label.
    quiz_difficulty: str = field(
        default_factory=lambda: _env("QUIZ_DIFFICULTY", "mixed").strip().lower())

    # --- Mesh limits ---
    max_payload_bytes: int = field(default_factory=lambda: _env_int("MAX_PAYLOAD_BYTES", 200))

    # --- Ambient mode (rolling solo questions, 24/7, mesh-friendly) ---
    # When enabled, Buzz drops ONE standalone question into the trivia channel on a slow
    # cadence (default: hourly) at a fixed off-:00 minute, so the channel stays alive
    # without anyone running a rapid !starttrivia game. Ambient questions are NOT a game:
    # they don't score, don't open an answer window, and exist only to keep the channel
    # warm + remind folks the game and leaderboard are there.
    #
    # SAFETY DEFAULT: ambient is OFF by default so a fresh install never surprises a
    # stranger's mesh. An operator opts IN on their own node via .env (AMBIENT_ENABLED=true).
    ambient_enabled: bool = field(default_factory=lambda: _env_bool("AMBIENT_ENABLED", False))
    # Minutes between ambient questions. Default 60 (hourly). Hard floor of 5 min applied
    # in validate() — ambient is meant to be SLOW.
    ambient_interval_minutes: int = field(
        default_factory=lambda: _env_int("AMBIENT_INTERVAL_MINUTES", 60))
    # The minute-of-hour to fire on. Default 37: a prime, far from the :00 top-of-hour
    # (and :15/:30/:45 quarter-hour cron clusters) where other mesh traffic piles up.
    # When the interval is exactly 60, ambient fires once per hour AT this minute. For
    # other intervals the offset is used as the phase so firings still avoid :00.
    ambient_minute_offset: int = field(
        default_factory=lambda: _env_int("AMBIENT_MINUTE_OFFSET", 37))
    # Channel to drop ambient questions on. Defaults to the trivia channel.
    ambient_channel_index: int = field(
        default_factory=lambda: _env_int("AMBIENT_CHANNEL_INDEX", -1))
    # Which pool the AMBIENT (24/7) track draws from — DECOUPLED from the rapid-game
    # QUIZ_DIFFICULTY so the channel gets the widest/hardest pool for the no-repeat window.
    #   challenging (DEFAULT) - med + hard tiers (skips easy; deepest hard pool)
    #   mixed / all           - the entire bank
    #   easy / medium / hard  - a single tier
    ambient_difficulty: str = field(
        default_factory=lambda: _env("AMBIENT_DIFFICULTY", "challenging").strip().lower())
    # No-repeat window (days): the ambient track will NOT re-ask a question shown within this
    # many days. Target is a full year. If the eligible pool ever empties (bank too small for
    # the cadence), it degrades gracefully to the least-recently-asked question (max spacing)
    # and logs a warning — never a recent repeat, never a crash.
    ambient_no_repeat_days: int = field(
        default_factory=lambda: _env_int("AMBIENT_NO_REPEAT_DAYS", 365))
    # Every Nth ambient question carries the FULL reminder (leaderboard + !starttrivia
    # plug); the others are a bare question with a tiny tag, so channel regulars aren't
    # nagged hourly. Default 3 (full plug every 3rd question). 1 = always full.
    ambient_reminder_frequency: int = field(
        default_factory=lambda: _env_int("AMBIENT_REMINDER_FREQUENCY", 3))
    # Hard anti-flood floor, independent of all other logic: never send more than this many
    # messages in any rolling 60s, regardless of bugs. A last-resort circuit breaker.
    max_sends_per_minute: int = field(
        default_factory=lambda: _env_int("MAX_SENDS_PER_MINUTE", 6))

    # --- Fallback answering ---
    allow_typed_answers: bool = field(default_factory=lambda: _env_bool("ALLOW_TYPED_ANSWERS", True))

    # --- Wrong-answer feedback (v1.7.0) ---
    # When on, a player's WRONG guess gets a short, friendly acknowledgment so they know
    # their answer registered (Buzz used to stay totally silent on a wrong tap, which felt
    # like the guess was never seen). It NEVER reveals the correct answer — others are still
    # guessing — and it is airtime-bounded: only a node's FIRST answer per question is ever
    # recorded (anti-cheat lock), so each player gets AT MOST one wrong-ack per question and
    # a single user physically cannot spam wrong guesses. Applies to BOTH the rapid game and
    # the 24/7 ambient track (any track that accepts answers). The global MAX_SENDS_PER_MINUTE
    # floor still caps total channel airtime regardless. Default ON; set false to keep Buzz
    # silent on wrong answers (pre-v1.7.0 behavior).
    wrong_answer_ack: bool = field(default_factory=lambda: _env_bool("WRONG_ANSWER_ACK", True))

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

    # --- Personality system (v1.2.0; see DECISIONS.md) ---
    # Master switch for the state-aware quip engine + the hourly ambient RECAP packet that
    # announces who got the previous ambient question right (and casual pokes at strugglers).
    # SAFETY DEFAULT: OFF, consistent with ambient's conservative default — a fresh OSS
    # install behaves exactly like v1.1.0. Opt in with PERSONALITY_ENABLED=true.
    # When off, ambient answers are not even tracked; nothing changes vs v1.1.0.
    personality_enabled: bool = field(
        default_factory=lambda: _env_bool("PERSONALITY_ENABLED", False))
    # Separate toggle for the ambient recap packet specifically. Lets an operator keep
    # richer game-round copy while skipping the extra hourly recap packet. Only consulted
    # when personality_enabled is true.
    recap_enabled: bool = field(default_factory=lambda: _env_bool("RECAP_ENABLED", True))
    # Casual pokes at strugglers. On by default (it's the headline feature), but an
    # operator can keep praise-only by setting POKES_ENABLED=false.
    pokes_enabled: bool = field(default_factory=lambda: _env_bool("POKES_ENABLED", True))
    # Per-player poke cooldown, measured in ambient slots (≈ hours). Buzz won't poke the same
    # player again until this many slots have passed — no riding one person hour after hour.
    poke_cooldown_hours: int = field(
        default_factory=lambda: _env_int("POKE_COOLDOWN_HOURS", 3))
    # Brand-new players are exempt from pokes for this many ambient slots after first seen.
    new_player_grace_slots: int = field(
        default_factory=lambda: _env_int("NEW_PLAYER_GRACE_SLOTS", 2))

    @property
    def ambient_channel(self) -> int:
        """Resolved ambient channel: explicit override, else the trivia channel."""
        return self.trivia_channel_index if self.ambient_channel_index < 0 \
            else self.ambient_channel_index

    def validate(self) -> None:
        if not self.meshmonitor_token:
            raise ValueError("MESHMONITOR_API_TOKEN is required")
        if not self.meshmonitor_url:
            raise ValueError("MESHMONITOR_URL is required")
        if self.question_window_s < 5:
            raise ValueError("QUESTION_WINDOW_S too small")
        if self.ambient_enabled:
            # Ambient is deliberately slow; refuse a too-tight cadence that would crowd
            # the mesh (guards against a fat-fingered AMBIENT_INTERVAL_MINUTES=1).
            if self.ambient_interval_minutes < 5:
                raise ValueError("AMBIENT_INTERVAL_MINUTES too small (min 5)")
            if not (0 <= self.ambient_minute_offset <= 59):
                raise ValueError("AMBIENT_MINUTE_OFFSET must be 0..59")
            if self.ambient_reminder_frequency < 1:
                raise ValueError("AMBIENT_REMINDER_FREQUENCY must be >= 1")
        if self.max_sends_per_minute < 1:
            raise ValueError("MAX_SENDS_PER_MINUTE must be >= 1")
        if self.quiz_difficulty not in VALID_DIFFICULTIES:
            raise ValueError(
                f"QUIZ_DIFFICULTY must be one of {sorted(VALID_DIFFICULTIES)}, "
                f"got {self.quiz_difficulty!r}")
