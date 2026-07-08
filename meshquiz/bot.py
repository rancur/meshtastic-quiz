"""Bot wiring: poll the mesh, translate traffic into engine events, execute actions.

Responsibilities (the engine has none of these):
- channel gating (commands only act on the trivia channel),
- command parsing (!starttrivia / !stoptrivia / !leaderboard),
- mapping tapback reactions (and optional typed answers) to answer options,
- deduping players by hex node id while displaying long names,
- sending text within the byte budget + min-send spacing (flood protection),
- crash-recovery cursor so a restart doesn't replay old traffic.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Dict, List, Optional

from dataclasses import asdict, fields

from . import host, state
from .config import ANSWER_EMOJI, ANSWER_TYPED, Config
from .engine import AmbientStats, GameEngine, SendText, StartQuestion
from .questions import (
    Question,
    load_questions,
    question_key,
    select_ambient_pool,
    select_by_difficulty,
    validate_bank,
)
from .transport import MeshMessage, Transport

log = logging.getLogger("meshquiz.bot")

CMD_START = "!starttrivia"
CMD_STOP = "!stoptrivia"
CMD_BOARD = "!leaderboard"
CMD_HELP = "!help"
CMD_TRIVIA = "!trivia"  # advert command, usable on the PRIMARY channel only


def emoji_to_option(text: str) -> Optional[int]:
    """Map a reaction emoji char to an answer index 0..3, or None.

    Keycap-number emoji are ``<digit> U+FE0F U+20E3`` (e.g. "1️⃣"). Some clients drop the
    U+FE0F variation selector. We normalize by checking the leading ASCII digit together
    with the U+20E3 combining keycap mark, which is the stable signal.
    """
    t = (text or "").strip()
    if not t:
        return None
    KEYCAP = "⃣"
    if KEYCAP in t and t[0] in ("1", "2", "3", "4"):
        return int(t[0]) - 1
    # exact match fallback
    for i, e in enumerate(ANSWER_EMOJI):
        if t == e:
            return i
    return None


def typed_to_option(text: str) -> Optional[int]:
    t = (text or "").strip()
    if t in ANSWER_TYPED:
        return ANSWER_TYPED.index(t)
    return None


class TriviaBot:
    def __init__(self, transport: Transport, cfg: Config, questions: Optional[List[Question]] = None):
        self.t = transport
        self.cfg = cfg
        if questions is None:
            questions = load_questions(cfg.questions_path)
        # Validate the FULL bank up front (every question must be byte-safe regardless of
        # which tier is active), then narrow to the operator's chosen difficulty tier.
        problems = validate_bank(questions, cfg.max_payload_bytes)
        if problems:
            raise ValueError("question bank failed validation:\n" + "\n".join(problems[:20]))
        # Keep the FULL bank (all tiers) — the ambient pool + the no-repeat key set are drawn
        # from it, decoupled from the rapid-game difficulty narrowing below.
        self._full_bank = list(questions)
        full_count = len(questions)
        questions = select_by_difficulty(questions, cfg.quiz_difficulty)
        if cfg.quiz_difficulty not in ("mixed", "", "all") and len(questions) == full_count \
                and full_count > 0:
            # select_by_difficulty fell back to the whole bank because the requested tier
            # was empty — surface it so a misconfigured tier is visible in the logs.
            log.warning("QUIZ_DIFFICULTY=%r matched no questions; using the full bank (%d)",
                        cfg.quiz_difficulty, full_count)
        log.info("question bank: %d of %d loaded for difficulty=%r",
                 len(questions), full_count, cfg.quiz_difficulty)
        self.engine = GameEngine(cfg, questions)
        self._questions = list(questions)  # rapid-game pool (respects QUIZ_DIFFICULTY)
        # AMBIENT pool is decoupled from the game tier (AMBIENT_DIFFICULTY, default med+hard)
        # so the 24/7 channel draws from the widest/hardest pool for the no-repeat window.
        self._ambient_questions = select_ambient_pool(
            self._full_bank, cfg.ambient_difficulty)
        log.info("ambient pool: %d questions (AMBIENT_DIFFICULTY=%r); no-repeat window=%d days",
                 len(self._ambient_questions), cfg.ambient_difficulty, cfg.ambient_no_repeat_days)
        # No-repeat history: question_key -> last-asked epoch seconds. Persisted in state.json.
        self._ask_history: Dict[str, float] = {}
        self._cursor_ms = 0
        self._last_send_s = 0.0
        # Hard anti-flood floor: timestamps (monotonic) of recent sends, pruned to the last
        # 60s. _send refuses if this window is already full — a last-resort circuit breaker
        # that holds regardless of any other bug in scheduling/game logic.
        self._send_times: List[float] = []
        # Ambient mode bookkeeping.
        self._ambient_last_fire_key: Optional[str] = None  # dedup: one fire per slot
        self._ambient_count = 0  # how many ambient questions sent (drives reminder cadence)
        self._pending_ambient_q: Optional[Question] = None  # question awaiting packet-id reg
        self._pending_ambient_lead: Optional[str] = None  # lead emoji used on the pending Q
        self._rng = random.Random()
        self._processed_pkts: set = set()  # reactions/commands already handled
        self._names: Dict[str, str] = {}
        self._restore()

    # ---------- persistence ----------
    def _restore(self):
        st = state.load_state(self.cfg.state_path)
        if "cursor_ms" in st:
            self._cursor_ms = st["cursor_ms"]
            self._cursor_seeded = True
        else:
            # Fresh deploy: seed the cursor on the first poll from that poll's `now`,
            # so we do NOT replay the channel's entire pre-existing history. Until then
            # the cursor is 0 and `_cursor_seeded` is False.
            self._cursor_ms = 0
            self._cursor_seeded = False
        # leaderboard restore is informational; a new game resets scores by design.
        # Ambient personality stats DO persist (running gags survive restarts).
        valid = {f.name for f in fields(AmbientStats)}
        for row in st.get("ambient_stats", []) or []:
            try:
                clean = {k: v for k, v in row.items() if k in valid}
                s = AmbientStats(**clean)
                if s.node_id:
                    self.engine.ambient_stats[s.node_id] = s
            except (TypeError, AttributeError):
                continue
        # Restore the no-repeat history. Prune to keys still present in the current bank so a
        # retired question can't leave a stale entry lingering forever (bounded to bank size).
        known = {question_key(q) for q in self._full_bank}
        hist = st.get("ask_history", {}) or {}
        for key, ts in hist.items():
            if key in known:
                try:
                    self._ask_history[key] = float(ts)
                except (TypeError, ValueError):
                    continue

    def _persist(self):
        board = [{"node_id": p.node_id, "name": p.name, "score": p.score}
                 for p in self.engine.leaderboard()]
        ambient = [asdict(s) for s in self.engine.ambient_stats.values()]
        state.save_state(self.cfg.state_path, cursor_ms=self._cursor_ms,
                         was_running=self.engine.running, leaderboard=board,
                         ambient_stats=ambient, ask_history=self._ask_history)

    # ---------- sending (byte budget + flood control) ----------
    def _send(self, text: str, channel: Optional[int] = None) -> Optional[int]:
        # enforce byte budget: trim defensively (questions are pre-validated; flavor text
        # is short, but never let a stray long line break the mesh)
        if len(text.encode("utf-8")) > self.cfg.max_payload_bytes:
            text = self._truncate_bytes(text, self.cfg.max_payload_bytes)
        ch = self.cfg.trivia_channel_index if channel is None else channel
        # HARD ANTI-FLOOD FLOOR (last-resort circuit breaker): never exceed
        # max_sends_per_minute in any rolling 60s, no matter what upstream logic asks for.
        # This is independent of min_send_interval_s spacing and game/ambient logic — a
        # structural cap so a bug anywhere can't flood the channel.
        now_m = time.monotonic()
        self._send_times = [t for t in self._send_times if now_m - t < 60.0]
        if len(self._send_times) >= self.cfg.max_sends_per_minute:
            log.error("RATE LIMIT: %d sends in last 60s >= cap %d; DROPPING send: %r",
                      len(self._send_times), self.cfg.max_sends_per_minute, text[:40])
            return None
        # min spacing between sends
        gap = self.cfg.min_send_interval_s - (now_m - self._last_send_s)
        if gap > 0:
            time.sleep(gap)
        try:
            pkt = self.t.send_message(text, ch)
            self._last_send_s = time.monotonic()
            self._send_times.append(self._last_send_s)
            return pkt
        except Exception as e:
            log.error("send failed: %s", e)
            return None

    def _send_lines(self, lines: List[str], channel: Optional[int] = None) -> None:
        """Send a sequence of messages, each independently byte-validated + flood-spaced.

        Used for multi-message output (e.g. the `!trivia` advert+link) so that a
        block of text is delivered as several tight packets rather than one oversize one.
        """
        for line in lines:
            if line:
                self._send(line, channel)

    @staticmethod
    def _pack_lines(lines: List[str], limit: int, sep: str = "\n") -> List[str]:
        """Pack a list of lines into the MINIMUM number of messages, each <= limit bytes.

        Greedy bin-packing on line boundaries: lines are joined with `sep` and a new
        message is started only when adding the next line would exceed the byte budget.
        Never splits a line mid-word. If a single line is itself over budget it becomes
        its own message (the caller's `_send` truncates defensively as a last resort).
        Used by `!help` so the help text goes out as one message (or the fewest possible),
        never one-message-per-rule.
        """
        msgs: List[str] = []
        cur = ""
        sep_b = len(sep.encode("utf-8"))
        for line in lines:
            if not line:
                continue
            if not cur:
                cur = line
                continue
            # would appending `sep + line` to the current message stay within budget?
            if len(cur.encode("utf-8")) + sep_b + len(line.encode("utf-8")) <= limit:
                cur += sep + line
            else:
                msgs.append(cur)
                cur = line
        if cur:
            msgs.append(cur)
        return msgs

    @staticmethod
    def _truncate_bytes(text: str, limit: int) -> str:
        b = text.encode("utf-8")
        if len(b) <= limit:
            return text
        return b[: limit - 1].decode("utf-8", errors="ignore") + "…"

    # ---------- action execution ----------
    def _run_actions(self, actions: List) -> None:
        for a in actions:
            if isinstance(a, SendText):
                self._send(a.text)
            elif isinstance(a, StartQuestion):
                pkt = self._send(a.question.render())
                if pkt is not None:
                    self.engine.on_question_sent(pkt)
                    # Any question SENT to the channel (rapid-game OR ambient) stamps the
                    # shared no-repeat history, so ambient won't echo a question the game
                    # just used (channel-wide no-repeat, not just ambient-vs-ambient).
                    self._record_asked(a.question)
                else:
                    log.error("failed to send question; engine has no packet id to match")

    # ---------- name resolution ----------
    def _refresh_names(self):
        try:
            self._names = self.t.list_node_names() or self._names
        except Exception as e:  # pragma: no cover
            log.warning("name refresh failed: %s", e)

    def _name_for(self, node_id: str) -> str:
        name = self._names.get(node_id)
        if name:
            return name
        # Lazily refresh the node directory the first time we see an unknown node, so a
        # player who joins mid-game still gets a display name without waiting for the
        # periodic refresh.
        self._refresh_names()
        return self._names.get(node_id) or node_id

    # ---------- main step (one poll cycle) ----------
    def poll_once(self, now_s: Optional[float] = None) -> None:
        now_s = time.time() if now_s is None else now_s
        # On a fresh deploy (no persisted cursor), seed the cursor to this poll's time so
        # we ignore the channel's pre-existing history rather than replaying it.
        if not self._cursor_seeded:
            self._cursor_ms = int(now_s * 1000)
            self._cursor_seeded = True
        # Overlap the cursor slightly to tolerate out-of-order/late delivery, then dedupe
        # by packet id so we never double-process.
        since_ms = max(0, self._cursor_ms - 10_000)
        # Poll the trivia channel AND the primary channel. The primary channel is listened
        # to ONLY for the `!trivia` advert command (gated in _handle_message); everything
        # else there is ignored. Skip the second fetch if both indices are the same.
        channels = [self.cfg.trivia_channel_index]
        if self.cfg.primary_channel_index != self.cfg.trivia_channel_index:
            channels.append(self.cfg.primary_channel_index)
        msgs: List[MeshMessage] = []
        for ch in channels:
            try:
                msgs.extend(self.t.fetch_messages(ch, since_ms))
            except Exception as e:
                log.error("fetch failed (channel %s): %s", ch, e)
        msgs.sort(key=lambda m: m.timestamp_ms)

        for m in msgs:
            if m.timestamp_ms > self._cursor_ms:
                self._cursor_ms = m.timestamp_ms
            if m.packet_id in self._processed_pkts:
                continue
            self._processed_pkts.add(m.packet_id)
            self._handle_message(m, now_s)

        # advance timers
        self._run_actions(self.engine.tick(now_s))
        # ambient mode: drop a standalone teaser question on its slow off-:00 cadence,
        # but ONLY when no rapid game is running (no stacking).
        self._maybe_ambient(now_s)
        self._persist()
        self._gc_processed()

    def _gc_processed(self):
        # keep the processed-set bounded
        if len(self._processed_pkts) > 5000:
            self._processed_pkts = set(list(self._processed_pkts)[-2000:])

    def _is_own_node(self, node_id: str) -> bool:
        return bool(self.cfg.bot_node_id) and node_id == self.cfg.bot_node_id

    def _handle_message(self, m: MeshMessage, now_s: float):
        # PRIMARY-CHANNEL EXCEPTION: on the primary channel the bot does ONE thing —
        # respond to `!trivia` with the advert + channel-add link. Everything else
        # (including all other commands, reactions, typed answers) is ignored there.
        if m.channel == self.cfg.primary_channel_index \
                and m.channel != self.cfg.trivia_channel_index:
            self._handle_primary(m)
            return

        # CHANNEL GATING: otherwise only act on the trivia channel.
        if m.channel != self.cfg.trivia_channel_index:
            return

        # The host node is normally ignored entirely (it doesn't play). When HOST_CAN_PLAY
        # is on, a HUMAN tapback/typed answer from the host node IS allowed to score — but
        # the host node may NOT drive game-control commands here beyond what any player
        # can do, and the bot PROCESS never emits answers of its own (it only ever sends
        # questions/flavor text, never reactions). So host-as-player is purely about
        # counting inbound human answers, never self-answering.
        if self._is_own_node(m.from_node_id) and not self.cfg.host_can_play:
            return

        if m.is_reaction:
            self._handle_reaction(m, now_s)
            return

        text = (m.text or "").strip()
        low = text.lower()
        if low == CMD_START:
            self._run_actions(self.engine.start(now_s))
        elif low == CMD_STOP:
            self._run_actions(self.engine.stop(now_s))
        elif low == CMD_BOARD:
            self._send(self.engine.leaderboard_text())
        elif low == CMD_HELP:
            # One combined help reply (the fewest messages that fit the byte budget),
            # NOT one message per rule. Packs on line boundaries; splits to 2+ only if
            # the full text exceeds the payload limit.
            self._send_lines(self._pack_lines(host.HELP_LINES, self.cfg.max_payload_bytes))
        elif self.cfg.allow_typed_answers:
            opt = typed_to_option(text)
            if opt is None:
                return
            if self.engine.running:
                # rapid game in progress: typed answer counts for the open question
                self._run_actions(self.engine.submit_answer(
                    m.from_node_id, self._name_for(m.from_node_id),
                    opt, m.timestamp_ms / 1000.0))
            else:
                # No game running: a typed answer that REPLIES to the open ambient question
                # scores on the ambient track, mirroring the emoji-tapback path. The reply_to
                # must match the open ambient packet so stray "1".."4" chatter is never
                # credited. (Without this, typed ambient answers were silently dropped —
                # v1.4.1 fix; real point loss observed on the live AZ mesh.)
                amb = self.engine.ambient_packet_id
                if amb is not None and m.reply_to == amb:
                    self._run_actions(self.engine.submit_ambient_answer(
                        m.from_node_id, self._name_for(m.from_node_id),
                        opt, m.timestamp_ms / 1000.0))

    def _handle_primary(self, m: MeshMessage):
        """Primary-channel handler: the SOLE allowed command here is `!trivia`."""
        if m.is_reaction:
            return
        if (m.text or "").strip().lower() != CMD_TRIVIA:
            return
        # One combined advert reply (intro + channel-add deep link) packed into the
        # FEWEST messages that fit the byte budget — same pattern as `!help`. The
        # combined text is ~173B (< 200B default), so this goes out as a SINGLE
        # message; it only splits to 2+ if the payload ever exceeds the byte limit.
        self._send_lines(
            self._pack_lines([host.TRIVIA_ADVERT_INTRO, self.cfg.add_link],
                             self.cfg.max_payload_bytes),
            channel=self.cfg.primary_channel_index)

    def _handle_reaction(self, m: MeshMessage, now_s: float):
        opt = emoji_to_option(m.text)
        if opt is None:
            return
        if self.engine.running:
            cur = self.engine.current_packet_id
            if cur is None or m.reply_to != cur:
                return  # reaction to a different / stale message
            self._run_actions(self.engine.submit_answer(
                m.from_node_id, self._name_for(m.from_node_id),
                opt, m.timestamp_ms / 1000.0))
            return
        # No rapid game running: a reaction to the OPEN ambient question scores on the
        # ambient personality track (only when personality is enabled — otherwise the
        # engine never has an open ambient packet and this is a no-op).
        amb = self.engine.ambient_packet_id
        if amb is not None and m.reply_to == amb:
            self._run_actions(self.engine.submit_ambient_answer(
                m.from_node_id, self._name_for(m.from_node_id),
                opt, m.timestamp_ms / 1000.0))

    # ---------- ambient mode ----------
    @staticmethod
    def ambient_slot_key(now_s: float, interval_minutes: int, minute_offset: int) -> Optional[str]:
        """Return a stable per-slot key when ``now_s`` falls in an ambient firing slot, else None.

        Pure + deterministic (uses LOCAL time so the off-:00 offset matches wall-clock
        minutes the way operators/players reason about it). A "slot" is the
        ``interval_minutes`` grid phased by ``minute_offset``:

        - interval 60, offset 37  -> one slot per hour, at :37 (never :00).
        - interval 30, offset 37  -> :07 and :37 each hour.
        - interval 15, offset 37  -> :07, :22, :37, :52.

        We fire at most once per slot: the key is the absolute minute index of the slot's
        start, so a caller deduping on this key fires exactly once even though it's polled
        many times within the firing minute. None is returned when the current minute is
        not the first minute of a slot (so polls in between never fire).
        """
        lt = time.localtime(now_s)
        # absolute minute index since epoch-local-midnight reference is fine; use a long
        # running minute counter from the localtime fields (days since 1970 * 1440 + ...).
        # We only need RELATIVE alignment, so a per-day minute index plus the day ordinal
        # gives a globally monotonic, gap-free grid.
        from datetime import date
        day_ord = date(lt.tm_year, lt.tm_mon, lt.tm_mday).toordinal()
        abs_min = day_ord * 1440 + lt.tm_hour * 60 + lt.tm_min
        # phase the grid so a slot boundary lands on `minute_offset` within the hour:
        # shift by -offset, snap to the interval grid, and require we're AT a boundary.
        phased = abs_min - minute_offset
        if phased % interval_minutes != 0:
            return None
        slot_index = phased // interval_minutes
        return f"ambient:{slot_index}"

    def _maybe_ambient(self, now_s: float) -> None:
        if not self.cfg.ambient_enabled:
            return
        # NEVER stack on top of a rapid game — pause ambient entirely while one runs.
        if self.engine.running:
            return
        if not self._questions:
            return
        key = self.ambient_slot_key(now_s, self.cfg.ambient_interval_minutes,
                                    self.cfg.ambient_minute_offset)
        if key is None or key == self._ambient_last_fire_key:
            return
        self._ambient_last_fire_key = key
        self._send_ambient(slot_index=self._slot_index(key), now_s=now_s)

    # ---------- no-repeat selection ----------
    def _record_asked(self, question: Question, now_s: Optional[float] = None) -> None:
        """Stamp a question as asked NOW in the persistent no-repeat history."""
        self._ask_history[question_key(question)] = time.time() if now_s is None else now_s

    def _pick_ambient_question(self, now_s: float) -> Question:
        """Choose the next ambient question honoring the 365-day no-repeat window.

        1. ELIGIBLE = pool questions never asked, or last asked >= window ago. Pick RANDOMLY
           among them (unpredictable, not sequential).
        2. GRACEFUL FALLBACK: if none are eligible (bank too small for the cadence), pick the
           LEAST-RECENTLY-ASKED question (max possible spacing) — never a recent repeat, never
           a crash — random tiebreak among equally-old ones. Log a warning so the operator
           sees the bank needs to grow / the cadence needs to slow.
        The chosen question is stamped by the caller once it actually sends.
        """
        pool = self._ambient_questions or self._questions
        window_s = max(0, self.cfg.ambient_no_repeat_days) * 86400
        eligible = [q for q in pool
                    if (now_s - self._ask_history.get(question_key(q), float("-inf"))) >= window_s]
        if eligible:
            return self._rng.choice(eligible)
        # pool exhausted within the window -> least-recently-asked (oldest last-asked wins)
        oldest_ts = min(self._ask_history.get(question_key(q), float("-inf")) for q in pool)
        stalest = [q for q in pool
                   if self._ask_history.get(question_key(q), float("-inf")) <= oldest_ts]
        log.warning(
            "ambient no-repeat pool EXHAUSTED within %d-day window (pool=%d): falling back to "
            "least-recently-asked. Grow the bank or slow AMBIENT_INTERVAL_MINUTES for full "
            "365-day coverage.", self.cfg.ambient_no_repeat_days, len(pool))
        return self._rng.choice(stalest)

    @staticmethod
    def _slot_index(key: str) -> int:
        """Extract the integer slot index from an ``ambient:<N>`` key (for personality math)."""
        try:
            return int(key.split(":", 1)[1])
        except (IndexError, ValueError):
            return 0

    def _build_recap_text(self, slot_index: int) -> Optional[str]:
        """Resolve the previous ambient question and render the ONE recap packet, or None.

        Returns None when (a) personality/recap is off, or (b) there's no previous ambient
        question (first fire ever) — the caller then simply skips the recap packet. The
        returned string is byte-capped here so the recap is guaranteed to be a single packet.
        """
        if not (self.cfg.personality_enabled and self.cfg.recap_enabled):
            # still clear any open question so stale state can't leak, but no recap text
            self.engine.resolve_ambient()
            return None
        recap = self.engine.resolve_ambient()
        if not recap.had_question:
            return None  # first fire — nothing to recap
        q = self.engine.quips
        names = recap.winner_names
        if names:
            # headline: streak-escalating / comeback / plain winner praise on the FIRST winner
            if recap.first_winner_comeback >= 2:
                head = q.comeback(recap.first_winner, recap.first_winner_comeback)
            else:
                head = q.winner(recap.first_winner, streak=recap.first_winner_streak)
            extra = len(names) - 1
            if extra > 0:
                head = f"{head} (+{extra} more)"
            text = head
        else:
            text = q.no_winner(recap.answer_text)
        # optional poke clause appended only if it still fits the single-packet budget.
        # The cooldown is stamped ONLY when the poke actually survives into the text — a poke
        # dropped for budget must not consume the player's cooldown (else they'd be wrongly
        # skipped next hour).
        target, poke = self._build_poke(slot_index)
        if poke:
            combined = f"{text} {poke}"
            if len(combined.encode("utf-8")) <= self.cfg.max_payload_bytes:
                text = combined
                target.last_poked_slot = slot_index  # stamp cooldown only on actual use
        return self._truncate_bytes(text, self.cfg.max_payload_bytes)

    def _build_poke(self, slot_index: int):
        """Pick a calibrated poke target + render its line. Returns (target, text) or
        (None, None) if no eligible target. Does NOT stamp the cooldown — the caller stamps
        it only if the poke actually makes it into the sent packet."""
        target = self.engine.poke_target(self.cfg, slot_index)
        if target is None:
            return None, None
        q = self.engine.quips
        if target.wrong_streak >= 2:
            return target, q.poke_streak(target.name or target.node_id, target.wrong_streak)
        board = self.engine.ambient_leaderboard()
        gap = (board[0].correct - target.correct) if board else 0
        return target, q.poke_bottom(target.name or target.node_id, gap)

    def _build_ambient_messages(self, slot_index: int = 0, now_s: Optional[float] = None) -> List[str]:
        """Build the ambient send as a list of one-packet messages.

        Order (when personality on): [recap]? + header+question + [reminder]?. The recap is
        its OWN packet immediately before the question, so the hour sends at most recap +
        question = 2 packets (was 1). Each element is independently byte-validated.

        Also opens the new ambient question on the engine's personality track so reactions to
        it get scored for next hour's recap. ``slot_index`` is the ambient slot we're firing.
        """
        now_s = time.time() if now_s is None else now_s
        # 365-day no-repeat pick (random among eligible; LRU fallback) — NOT random-with-
        # replacement. Stamp it NOW so back-to-back builds can't reselect it before send.
        q = self._pick_ambient_question(now_s)
        self._record_asked(q, now_s)
        msgs: List[str] = []
        recap = self._build_recap_text(slot_index)
        if recap:
            msgs.append(recap)
        # Ambient question: a single standard emoji leads the question line inline (no
        # category tag, no separate header packet — v1.2.2 format). The whole question is
        # one byte-validated packet.
        lead = self._rng.choice(host.AMBIENT_LEAD_EMOJI)
        self._pending_ambient_lead = lead
        msgs.append(q.render(lead))
        self._ambient_count += 1
        if self._ambient_count % max(1, self.cfg.ambient_reminder_frequency) == 0:
            msgs.append(host.pick(host.AMBIENT_REMINDER))
        # register the new open ambient question (only meaningful when personality on; when
        # off, open_ambient sets state the engine never reads because reactions aren't routed)
        if self.cfg.personality_enabled:
            self.engine.open_ambient(q, slot_index)
        self._pending_ambient_q = q  # the question whose packet id we must register on send
        return msgs

    def _send_ambient(self, slot_index: int = 0, now_s: Optional[float] = None) -> None:
        self._pending_ambient_q = None
        self._pending_ambient_lead = None
        msgs = self._build_ambient_messages(slot_index, now_s)
        log.info("ambient: firing (#%d, %d packet(s), slot=%d)",
                 self._ambient_count, len(msgs), slot_index)
        # Send each packet; capture the packet id of the QUESTION message so reactions to it
        # are matched on the ambient track. The question is the message equal to the pending
        # question's render() (or the first line that starts with it, when header+question
        # were packed into one packet).
        qtext = self._pending_ambient_q.render(self._pending_ambient_lead) \
            if self._pending_ambient_q else None
        for line in msgs:
            if not line:
                continue
            pkt = self._send(line, channel=self.cfg.ambient_channel)
            if pkt is not None and qtext is not None and self.cfg.personality_enabled \
                    and qtext in line:
                self.engine.on_ambient_sent(pkt)
                qtext = None  # only register once

    # ---------- run loop ----------
    def run(self):  # pragma: no cover - long-running loop
        self.cfg.validate()
        self._refresh_names()
        log.info("Buzz online. Trivia channel index=%s", self.cfg.trivia_channel_index)
        name_refresh_every = 30  # cycles
        i = 0
        while True:
            self.poll_once()
            i += 1
            if i % name_refresh_every == 0:
                self._refresh_names()
            time.sleep(self.cfg.poll_interval_s)
