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
from .personality import QuipEngine
from .questions import Question, is_math


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
    game_streak: int = 0    # consecutive correct THIS game (drives streak-escalation quips)


@dataclass
class _Answer:
    node_id: str
    option: int            # 0..3
    ts_s: float


@dataclass
class AmbientStats:
    """Persistent per-node personality state for the rolling ambient track.

    Survives restarts (serialized into state.json) so running gags — streaks, droughts,
    poke cooldowns — keep building across the 24/7 cadence. ``slot`` values are the integer
    ambient-slot index (the N in ``ambient:N``), a gap-free hourly grid, so "rounds since X"
    is a clean subtraction.
    """
    node_id: str
    name: str = ""
    correct: int = 0            # lifetime correct ambient answers (drives the ambient board)
    answered: int = 0           # lifetime ambient answers, any
    correct_streak: int = 0     # consecutive correct (streak-escalation quips)
    wrong_streak: int = 0       # consecutive wrong (poke calibration + comeback detection)
    last_correct_slot: int = -1  # ambient slot of last correct answer (-1 = never)
    first_seen_slot: int = -1   # first ambient slot we saw them (new-player poke exemption)
    last_poked_slot: int = -1   # last slot we poked them (per-player cooldown)


@dataclass
class AmbientRecap:
    """Outcome of resolving the previous ambient question (drives the recap packet)."""
    had_question: bool                 # False on the very first fire (nothing to recap)
    answer_text: str = ""
    winner_names: List[str] = field(default_factory=list)  # correct answerers, first-correct first
    first_winner: Optional[str] = None
    first_winner_streak: int = 0
    first_winner_comeback: int = 0     # drought length snapped (>0 => comeback), else 0


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
        # --- ambient personality track (independent of the rapid-game state above) ---
        # The CURRENTLY-OPEN ambient question and the reactions to it. There is no in-window
        # deadline: an ambient question stays "open" until the next ambient question fires
        # (~1h), matching the mesh's slow async nature. resolve_ambient() closes it.
        self._ambient_q: Optional[Question] = None
        self._ambient_pkt: Optional[int] = None
        self._ambient_answers: Dict[str, _Answer] = {}
        self._ambient_slot: int = -1   # slot index the open question was posted in
        # persistent per-node personality stats (restored from / saved to state.json)
        self.ambient_stats: Dict[str, AmbientStats] = {}
        # quip engine: deterministic rotation. Inert unless cfg.personality_enabled.
        self.quips = QuipEngine(seed=0)

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
        self._bag = self._build_capped_bag()

    def _build_capped_bag(self) -> List[Question]:
        """Build a shuffled draw bag for a game, MATH-CAPPED so the competitive game is
        trivia-first (v1.9.0).

        Same problem the v1.8.0 ambient math-cap solved, now for the rapid !starttrivia
        game: the bank is ~83% Math (mass-generated in v1.6.0 to clear the 365-day ambient
        no-repeat), so a plain shuffle of the whole bank made a 12-question game ~10 math
        questions — "the trivia is mainly math." We cap math to at most
        ``GAME_MATH_MAX_PCT`` of the bag (default 18%) by INCLUDING every non-math question
        and only enough randomly-chosen math questions to hit that share, then shuffle. A
        game draws ``questions_per_game`` from the top, so the served mix tracks the cap.

        Math is never deleted — pure selection weighting, fully reversible via the env knob:
          - GAME_MATH_MAX_PCT=0   => a game has ZERO math (unless the tier is ALL math).
          - GAME_MATH_MAX_PCT=100 => uncapped uniform shuffle (pre-1.9.0 behavior).
        Classification is tag-based (questions.is_math), so a real-trivia question that
        merely contains a digit is never mis-flagged. If the active tier is all-math or
        all-non-math, we degrade to a plain shuffle rather than starve the bag.
        """
        pool = list(self._all_questions)
        pct = self.cfg.game_math_max_pct
        if pct >= 100:
            self.rng.shuffle(pool)
            return pool
        math = [q for q in pool if is_math(q)]
        nonmath = [q for q in pool if not is_math(q)]
        # Degenerate pools: nothing to cap against -> plain shuffle of what we have.
        if not math or not nonmath:
            self.rng.shuffle(pool)
            return pool
        self.rng.shuffle(math)
        self.rng.shuffle(nonmath)
        if pct <= 0:
            bag = list(nonmath)
        else:
            # Keep every non-math question; add just enough math so math is <= pct% of the
            # bag: math_count / (nonmath + math_count) = pct/100  ->  math_count =
            # nonmath * pct / (100 - pct). At least 1 so a low cap still allows some spice.
            frac = pct / (100 - pct)
            max_math = max(1, int(len(nonmath) * frac))
            bag = nonmath + math[:max_math]
        self.rng.shuffle(bag)
        return bag

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
    def submit_answer(self, node_id: str, name: str, option: int, ts_s: float) -> List[Action]:
        """Record an answer (from a tapback or typed fallback).

        Dedup: only the FIRST answer from a node counts for the current question. A
        changed reaction before timeout does NOT override the first (anti-cheat / fair).

        Returns immediate actions to execute. A WRONG first answer yields a short ack (so
        the player knows their guess registered) — see ``_wrong_ack``. A CORRECT answer
        returns [] and stays silent here: it is announced at reveal, unchanged, so the
        correct option is never leaked while others are still guessing. All the guard
        early-returns yield [] (nothing was recorded, so nothing to acknowledge). Because
        only a node's FIRST answer is recorded, each player gets AT MOST one wrong-ack per
        question and a single user cannot spam wrong guesses.
        """
        if self.phase != Phase.ASKING or self._current is None:
            return []
        if not (0 <= option < 4):
            return []
        if ts_s > self._deadline_s:
            return []  # arrived after the window (lossy/late mesh delivery)
        # ensure player exists / refresh display name
        p = self.players.get(node_id)
        if p is None:
            p = Player(node_id=node_id, name=name)
            self.players[node_id] = p
        else:
            if name:
                p.name = name
        if node_id in self._answers:
            return []  # first answer already locked
        self._answers[node_id] = _Answer(node_id=node_id, option=option, ts_s=ts_s)
        if option != self._current.answer:
            return self._wrong_ack(p.name or name or node_id)
        return []

    def _wrong_ack(self, name: str) -> List[Action]:
        """Build the immediate wrong-answer acknowledgment, or [] if disabled.

        Shared by both the rapid game and the ambient track. NEVER references the correct
        answer (others are still guessing). Gated by cfg.wrong_answer_ack (default on).
        """
        if not getattr(self.cfg, "wrong_answer_ack", True):
            return []
        return [SendText(host.pick(host.WRONG, name=name))]

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
        first_winner_streak = 0
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
                p.game_streak += 1
                p.last_score_ts = int(a.ts_s * 1000)
                if not correct_names:
                    first_winner_streak = p.game_streak
                correct_names.append((p.name, pts))
            else:
                p.game_streak = 0

        # Reveal + per-correct shoutout (compact — only the first couple to keep bytes low).
        # When personality is on, the shoutout/no-winner copy routes through the state-aware
        # quip engine (streak-escalating winner praise; dry no-winner reveal). Otherwise the
        # original host banks are used unchanged (v1.1.0 behavior).
        actions.append(SendText(host.pick(host.REVEAL, opt=q.answer_text())))
        if correct_names:
            name, pts = correct_names[0]
            if getattr(self.cfg, "personality_enabled", False):
                quip = self.quips.winner(name, streak=first_winner_streak)
                actions.append(SendText(f"{quip} +{pts}"))
            else:
                actions.append(SendText(host.pick(host.CORRECT, name=name, pts=pts)))
        else:
            if getattr(self.cfg, "personality_enabled", False):
                actions.append(SendText(self.quips.no_winner(q.answer_text())))
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

    # ---------------- ambient personality track ----------------
    # These methods are ONLY exercised when the bot has personality enabled; with it off the
    # bot never registers an ambient packet or feeds ambient answers, so this track is inert
    # and v1.1.0 behavior is unchanged.

    def open_ambient(self, question: Question, slot_index: int) -> None:
        """Mark a freshly-sent ambient question as the open one (call after sending)."""
        self._ambient_q = question
        self._ambient_pkt = None
        self._ambient_answers = {}
        self._ambient_slot = slot_index

    def on_ambient_sent(self, packet_id: int) -> None:
        self._ambient_pkt = packet_id

    @property
    def ambient_packet_id(self) -> Optional[int]:
        return self._ambient_pkt

    @property
    def has_open_ambient(self) -> bool:
        return self._ambient_q is not None

    def submit_ambient_answer(self, node_id: str, name: str, option: int, ts_s: float) -> List[Action]:
        """Record a first-reaction-wins answer to the open ambient question.

        No deadline: any reaction to the open ambient packet counts until the next ambient
        question replaces it. Same anti-cheat dedupe as the game (first answer locks).

        Returns immediate actions like the rapid game: a WRONG first answer yields a short
        ack so the player knows Buzz saw their tap (a correct answer stays silent — it is
        celebrated in the next hourly recap, and the answer is never leaked mid-round).
        Because only a node's FIRST ambient answer is recorded, each player gets AT MOST one
        wrong-ack per ambient question.
        """
        if self._ambient_q is None or not (0 <= option < 4):
            return []
        if node_id in self._ambient_answers:
            return []
        self._ambient_answers[node_id] = _Answer(node_id=node_id, option=option, ts_s=ts_s)
        # touch first_seen for new-player exemption (cheap to do here so even a wrong
        # first answer marks them as "seen")
        st = self.ambient_stats.get(node_id)
        if st is None:
            st = AmbientStats(node_id=node_id, name=name, first_seen_slot=self._ambient_slot)
            self.ambient_stats[node_id] = st
        if name:
            st.name = name
        if st.first_seen_slot < 0:
            st.first_seen_slot = self._ambient_slot
        if option != self._ambient_q.answer:
            return self._wrong_ack(st.name or name or node_id)
        return []

    def resolve_ambient(self) -> AmbientRecap:
        """Close the open ambient question: score it, update stats, return a recap summary.

        Returns ``AmbientRecap(had_question=False)`` when there is no open question (the very
        first fire), so the caller can skip the recap packet gracefully. After resolving, the
        open question is cleared (the caller then opens the next one).
        """
        q = self._ambient_q
        if q is None:
            return AmbientRecap(had_question=False)
        cur_slot = self._ambient_slot
        ordered = sorted(self._ambient_answers.values(), key=lambda a: a.ts_s)
        winner_names: List[str] = []
        first_winner = None
        first_streak = 0
        first_comeback = 0
        for a in ordered:
            st = self.ambient_stats.get(a.node_id)
            if st is None:
                st = AmbientStats(node_id=a.node_id, first_seen_slot=cur_slot)
                self.ambient_stats[a.node_id] = st
            st.answered += 1
            if a.option == q.answer:
                st.correct += 1
                drought = (cur_slot - st.last_correct_slot) if st.last_correct_slot >= 0 else 0
                st.correct_streak += 1
                st.wrong_streak = 0
                st.last_correct_slot = cur_slot
                winner_names.append(st.name or a.node_id)
                if first_winner is None:
                    first_winner = st.name or a.node_id
                    first_streak = st.correct_streak
                    # comeback only if they had a real prior history (>1 round gap)
                    first_comeback = drought if drought >= 2 else 0
            else:
                st.correct_streak = 0
                st.wrong_streak += 1
        recap = AmbientRecap(
            had_question=True,
            answer_text=q.answer_text(),
            winner_names=winner_names,
            first_winner=first_winner,
            first_winner_streak=first_streak,
            first_winner_comeback=first_comeback,
        )
        # clear the open question; caller opens the next one
        self._ambient_q = None
        self._ambient_pkt = None
        self._ambient_answers = {}
        return recap

    def ambient_leaderboard(self) -> List[AmbientStats]:
        """Ambient standings by lifetime correct (drives bottom-of-board poke targeting)."""
        return sorted(
            self.ambient_stats.values(),
            key=lambda s: (-s.correct, (s.name or s.node_id).lower()),
        )

    def poke_target(self, cfg: Config, cur_slot: int) -> Optional[AmbientStats]:
        """Pick a poke target per the calibration rules, or None.

        Friendly bar-banter, never cruel: targets only ever chosen on OBSERVABLE facts
        (a wrong streak, or bottom of a real board), never identity. Brand-new players are
        exempt, and a per-player cooldown stops Buzz riding one person hour after hour.
        """
        if not getattr(cfg, "pokes_enabled", True):
            return None
        board = self.ambient_leaderboard()

        def eligible(st: AmbientStats) -> bool:
            # never poke a brand-new player
            if st.first_seen_slot < 0:
                return False
            if cur_slot - st.first_seen_slot < cfg.new_player_grace_slots:
                return False
            # per-player cooldown
            if st.last_poked_slot >= 0 and cur_slot - st.last_poked_slot < cfg.poke_cooldown_hours:
                return False
            return True

        # 1) prefer the player on the longest wrong streak (>=2)
        streakers = sorted(
            (s for s in self.ambient_stats.values() if s.wrong_streak >= 2 and eligible(s)),
            key=lambda s: -s.wrong_streak,
        )
        if streakers:
            return streakers[0]
        # 2) else the BOTTOM of a real board (>=3 players, a meaningful gap to the leader)
        if len(board) >= 3:
            bottom = board[-1]
            gap = board[0].correct - bottom.correct
            if gap >= 1 and eligible(bottom):
                return bottom
        return None

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
