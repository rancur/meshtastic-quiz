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
import time
from typing import Dict, List, Optional

from . import host, state
from .config import ANSWER_EMOJI, ANSWER_TYPED, Config
from .engine import GameEngine, SendText, StartQuestion
from .questions import Question, load_questions, validate_bank
from .transport import MeshMessage, Transport

log = logging.getLogger("meshquiz.bot")

CMD_START = "!starttrivia"
CMD_STOP = "!stoptrivia"
CMD_BOARD = "!leaderboard"


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
        problems = validate_bank(questions, cfg.max_payload_bytes)
        if problems:
            raise ValueError("question bank failed validation:\n" + "\n".join(problems[:20]))
        self.engine = GameEngine(cfg, questions)
        self._cursor_ms = 0
        self._last_send_s = 0.0
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

    def _persist(self):
        board = [{"node_id": p.node_id, "name": p.name, "score": p.score}
                 for p in self.engine.leaderboard()]
        state.save_state(self.cfg.state_path, cursor_ms=self._cursor_ms,
                         was_running=self.engine.running, leaderboard=board)

    # ---------- sending (byte budget + flood control) ----------
    def _send(self, text: str) -> Optional[int]:
        # enforce byte budget: trim defensively (questions are pre-validated; flavor text
        # is short, but never let a stray long line break the mesh)
        if len(text.encode("utf-8")) > self.cfg.max_payload_bytes:
            text = self._truncate_bytes(text, self.cfg.max_payload_bytes)
        # min spacing between sends
        gap = self.cfg.min_send_interval_s - (time.monotonic() - self._last_send_s)
        if gap > 0:
            time.sleep(gap)
        try:
            pkt = self.t.send_message(text, self.cfg.trivia_channel_index)
            self._last_send_s = time.monotonic()
            return pkt
        except Exception as e:
            log.error("send failed: %s", e)
            return None

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
        try:
            msgs = self.t.fetch_messages(self.cfg.trivia_channel_index, since_ms)
        except Exception as e:
            log.error("fetch failed: %s", e)
            msgs = []

        for m in msgs:
            if m.timestamp_ms > self._cursor_ms:
                self._cursor_ms = m.timestamp_ms
            if m.packet_id in self._processed_pkts:
                continue
            self._processed_pkts.add(m.packet_id)
            self._handle_message(m, now_s)

        # advance timers
        self._run_actions(self.engine.tick(now_s))
        self._persist()
        self._gc_processed()

    def _gc_processed(self):
        # keep the processed-set bounded
        if len(self._processed_pkts) > 5000:
            self._processed_pkts = set(list(self._processed_pkts)[-2000:])

    def _handle_message(self, m: MeshMessage, now_s: float):
        # CHANNEL GATING: only act on the trivia channel.
        if m.channel != self.cfg.trivia_channel_index:
            return
        # ignore the bot's own node entirely (it doesn't play)
        if self.cfg.bot_node_id and m.from_node_id == self.cfg.bot_node_id:
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
        elif self.cfg.allow_typed_answers and self.engine.running:
            opt = typed_to_option(text)
            if opt is not None:
                self.engine.submit_answer(m.from_node_id, self._name_for(m.from_node_id),
                                          opt, m.timestamp_ms / 1000.0)

    def _handle_reaction(self, m: MeshMessage, now_s: float):
        if not self.engine.running:
            return
        cur = self.engine.current_packet_id
        if cur is None or m.reply_to != cur:
            return  # reaction to a different / stale message
        opt = emoji_to_option(m.text)
        if opt is None:
            return
        self.engine.submit_answer(m.from_node_id, self._name_for(m.from_node_id),
                                  opt, m.timestamp_ms / 1000.0)

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
