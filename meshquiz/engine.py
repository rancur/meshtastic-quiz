"""Pure game engine — no I/O, no mesh, no wall-clock.

The engine consumes EVENTS and produces ACTIONS. ``bot.py`` is responsible for turning
real mesh traffic into events and for executing the actions (sending text). Time is
injected via events (``tick(now_s)`` and timestamps on answers), so the engine is fully
deterministic and unit-testable.

Design references: classic IRC trivia bots (MoxQuizz, frogesport, MansionNET QuizBot).
Scoring + anti-runup rationale is documented in DECISIONS.md.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from . import host
from .config import Config
from .questions import Question


class Phase(Enum):
    IDLE = "idle"            # no game running
    ASKING = "asking"        # a question is open for answers
    BETWEEN = "between"      # brief gap between questions


@dataclass
class SendText:
    """An action: send this text to the trivia channel."""
    text: str


@dataclass
class StartQuestion:
    """An action: send the question text, then register its packet id via on_question_sent."""
    question: Question
    index: int  # 1-based question number in this game


# An action is either SendText or StartQuestion.
Action = object


@dataclass
class Player:
    node_id: str           # hex, dedup key
    name: str
    score: int = 0
    answers: int = 0       # number of questions answered (any)
    correct: int = 0
    last_score_ts: int = 0  # for stable tie-break (earlier reacher ranks higher)


@dataclass
class _Answer:
    node_id: str
    option: int            # 0..3
    ts_s: float


class GameEngine:
    def __init__(self, cfg: Config, questions: List[Question], rng: Optional[random.Random] = None):
        self.cfg = cfg
        self._all_questions = list(questions)
        self.rng = rng or random.Random()
        self.phase = Phase.IDLE
        self.players: Dict[str, Player] = {}
        # current question state
        self._bag: List[Question] = []
        self._current: Optional[Question] = None
        self._current_pkt: Optional[int] = None
        self._question_index = 0
        self._asked_count = 0
        self._deadline_s: float = 0.0
        self._between_until_s: float = 0.0
        # answers for the current question, deduped by node_id (FIRST reaction counts)
        self._answers: Dict[str, _Answer] = {}
        self._first_correct_node: Optional[str] = None
        # anti-runup: rolling count of consecutive low-participation questions
        self._low_round_streak = 0

    # ---------------- lifecycle ----------------
    @property
    def running(self) -> bool:
        return self.phase != Phase.IDLE

    def start(self, now_s: float) -> List[Action]:
        """Handle !starttrivia. Idempotent: if running, just nudge."""
        if self.running:
            return [SendText(host.pick(host.GAME_ALREADY))]
        # fresh game: reset per-game session state but KEEP leaderboard across games?
        # DECISION: leaderboard is per-game session; a new !starttrivia resets scores.
        self.players = {}
        self._low_round_streak = 0
        self._asked_count = 0
        self._refill_bag()
        actions: List[Action] = [SendText(host.pick(host.GAME_START))]
        actions += self._begin_question(now_s)
        return actions

    def stop(self, now_s: float, reason: Optional[str] = None) -> List[Action]:
        """Handle !stoptrivia (or internal stop)."""
        if not self.running:
            return []
        self.phase = Phase.IDLE
        self._current = None
        self._current_pkt = None
        self._answers = {}
        msg = reason or host.pick(host.GAME_STOP)
        return [SendText(msg), SendText(self.leaderboard_text())]

    # ---------------- question flow ----------------
    def _refill_bag(self):
        self._bag = list(self._all_questions)
        self.rng.shuffle(self._bag)

    def _begin_question(self, now_s: float) -> List[Action]:
        if not self._bag:
            self._refill_bag()
        if self._asked_count >= self.cfg.questions_per_game:
            return self.stop(now_s)
        self._current = self._bag.pop()
        self._asked_count += 1
        self._question_index = self._asked_count
        self._answers = {}
        self._first_correct_node = None
        self._current_pkt = None  # set by on_question_sent
        self.phase = Phase.ASKING
        self._deadline_s = now_s + self.cfg.question_window_s
        return [StartQuestion(self._current, self._question_index)]

    def on_question_sent(self, packet_id: int) -> None:
        """Called by the bot after it sends the question and learns its packet id."""
        self._current_pkt = packet_id

    @property
    def current_packet_id(self) -> Optional[int]:
        return self._current_pkt

    # ---------------- answers ----------------
    def submit_answer(self, node_id: str, name: str, option: int, ts_s: float) -> None:
        """Record an answer (from a tapback or typed fallback).

        Dedup: only the FIRST answer from a node counts for the current question. A
        changed reaction before timeout does NOT override the first (anti-cheat / fair).
        """
        if self.phase != Phase.ASKING or self._current is None:
            return
        if not (0 <= option < 4):
            return
        if ts_s > self._deadline_s:
            return  # arrived after the window (lossy/late mesh delivery)
        # ensure player exists / refresh display name
        p = self.players.get(node_id)
        if p is None:
            p = Player(node_id=node_id, name=name)
            self.players[node_id] = p
        else:
            if name:
                p.name = name
        if node_id in self._answers:
            return  # first answer already locked
        self._answers[node_id] = _Answer(node_id=node_id, option=option, ts_s=ts_s)

    # ---------------- timing / tick ----------------
    def tick(self, now_s: float) -> List[Action]:
        """Advance time. Returns actions (reveal + scoring, or next question)."""
        if self.phase == Phase.ASKING and now_s >= self._deadline_s:
            return self._close_question(now_s)
        if self.phase == Phase.BETWEEN and now_s >= self._between_until_s:
            return self._begin_question(now_s)
        return []

    def _close_question(self, now_s: float) -> List[Action]:
        q = self._current
        assert q is not None
        actions: List[Action] = []

        # Score, in time order so first-correct is deterministic.
        ordered = sorted(self._answers.values(), key=lambda a: a.ts_s)
        correct_names: List[str] = []
        for a in ordered:
            p = self.players[a.node_id]
            p.answers += 1
            if a.option == q.answer:
                pts = self._score_for(a.ts_s)
                if self._first_correct_node is None:
                    self._first_correct_node = a.node_id
                    pts += self.cfg.first_correct_bonus
                p.score += pts
                p.correct += 1
                p.last_score_ts = int(a.ts_s * 1000)
                correct_names.append((p.name, pts))

        # Reveal + per-correct shoutout (compact — only the first couple to keep bytes low)
        actions.append(SendText(host.pick(host.REVEAL, opt=q.answer_text())))
        if correct_names:
            name, pts = correct_names[0]
            actions.append(SendText(host.pick(host.CORRECT, name=name, pts=pts)))
        else:
            actions.append(SendText(host.pick(host.NOBODY)))

        # Anti-runup accounting: distinct answerers this round.
        distinct = len(self._answers)
        if distinct <= self.cfg.runup_min_players:
            self._low_round_streak += 1
        else:
            self._low_round_streak = 0

        if self._low_round_streak >= self.cfg.runup_max_low_rounds:
            stop_msg = host.pick(host.RUNUP_STOP, n=distinct)
            return actions + self.stop(now_s, reason=stop_msg)

        # End of game?
        if self._asked_count >= self.cfg.questions_per_game:
            return actions + self.stop(now_s)

        # Otherwise go to the between-questions gap.
        self.phase = Phase.BETWEEN
        self._between_until_s = now_s + self.cfg.inter_question_gap_s
        self._current = None
        self._current_pkt = None
        return actions

    def _score_for(self, ts_s: float) -> int:
        remaining = max(0.0, self._deadline_s - ts_s)
        frac = remaining / self.cfg.question_window_s if self.cfg.question_window_s else 0
        speed = round(self.cfg.max_speed_bonus * frac)
        return self.cfg.base_points + speed

    # ---------------- leaderboard ----------------
    def leaderboard(self) -> List[Player]:
        return sorted(
            self.players.values(),
            key=lambda p: (-p.score, p.last_score_ts or float("inf"), p.name.lower()),
        )

    def leaderboard_text(self) -> str:
        board = self.leaderboard()
        if not board:
            return "🏆 No scores yet — !starttrivia to play!"
        lines = ["🏆 LEADERBOARD"]
        for i, p in enumerate(board[: self.cfg.leaderboard_top_n], 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            lines.append(f"{medal} {p.name}: {p.score}")
        return "\n".join(lines)
