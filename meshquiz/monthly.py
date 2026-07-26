"""Monthly champion + leaderboard reset (v1.11.0).

At the end of every calendar month Buzz crowns that month's trivia champion, announces it
on BOTH the trivia channel and the PRIMARY channel, and resets the monthly board so the
next month starts everyone at zero.

This module is PURE: month math, standings, archiving, and message composition. It has no
I/O and no wall-clock of its own (``now_s`` is always injected), so every rule below is
unit-testable without a mesh. ``bot.py`` owns the sending; ``engine.py`` feeds it answers.

Hard rules encoded here (see DECISIONS.md for rationale):

- **At most TWO messages on the primary channel**, ever — the champion line and the
  join-the-trivia-channel promo. ``MAX_PRIMARY_MESSAGES`` is the invariant, enforced by
  ``compose_primary_messages`` and asserted in tests.
- **Every composed message is a single LoRa packet.** Composition measures UTF-8 BYTES
  (never characters — the emoji in this copy are 3-4 bytes each) and degrades the copy
  until it fits. The channel-add link is never truncated (a cut link is a dead link):
  prefix text is shortened instead.
- **A reset can never lose data.** ``archive()`` writes the finished month's standings into
  ``history`` BEFORE clearing the live scores. Archive-then-clear is one call so there is
  no code path that clears without archiving.
- **Idempotent.** Announced months are recorded in ``announced``; ``pending_months()``
  never returns a month that was already announced, so a second run (or a late run after
  the box was asleep at month-end) does nothing.
- **Local time, not UTC.** Month boundaries are resolved in the operator's timezone
  (``MONTHLY_TIMEZONE``, e.g. ``America/Phoenix``), so a month ends at local midnight
  rather than 5-7 hours early/late on the wrong local day.
- **Empty month = silence.** A month nobody scored in is archived and marked announced,
  but NOTHING is sent — the primary channel is never spammed with an empty podium.
- **Ties are shared, not broken.** Everyone level on top is announced as co-champion.
"""
from __future__ import annotations

import calendar
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence

log = logging.getLogger("meshquiz.monthly")

# HARD INVARIANT: the month-end announcement may occupy at most this many messages on the
# PRIMARY channel (champion + promo). The primary channel is shared with the whole mesh —
# two packets a month is the entire airtime budget we allow ourselves there.
MAX_PRIMARY_MESSAGES = 2

# How many months back a still-unannounced month may be crowned. Anything older is stale
# (the bot was off for a long time / the feature was only just enabled) and is archived
# silently rather than announcing a champion nobody remembers.
DEFAULT_MAX_LOOKBACK_MONTHS = 2


def month_key(ts_s: float, tz_name: str = "") -> str:
    """Return the ``YYYY-MM`` month bucket for ``ts_s`` in the configured local timezone.

    ``tz_name`` empty => the process's local time (the container's ``TZ``), matching how
    ambient scheduling already reasons about wall-clock. Naming a zone explicitly
    (``America/Phoenix``) is preferred: it makes the month boundary correct regardless of
    the host's TZ, and it is what the tests pin against.
    """
    return _localtime(ts_s, tz_name).strftime("%Y-%m")


def _localtime(ts_s: float, tz_name: str = "") -> datetime:
    if tz_name:
        try:
            from zoneinfo import ZoneInfo
            return datetime.fromtimestamp(ts_s, ZoneInfo(tz_name))
        except Exception as e:  # unknown zone / missing tzdata -> fall back, never crash
            log.warning("MONTHLY_TIMEZONE=%r unusable (%s); using system local time",
                        tz_name, e)
    return datetime.fromtimestamp(ts_s)


def month_label(key: str) -> str:
    """``"2026-07"`` -> ``"JULY"`` (uppercase, no year — the year is obvious in context)."""
    try:
        year, mon = key.split("-")
        return calendar.month_name[int(mon)].upper()
    except (ValueError, IndexError, KeyError):
        return key


def next_month_label(key: str) -> str:
    """``"2026-07"`` -> ``"AUGUST"``. Used for the "fresh board for X" line."""
    try:
        year, mon = (int(x) for x in key.split("-"))
        return calendar.month_name[1 if mon == 12 else mon + 1].upper()
    except (ValueError, IndexError, KeyError):
        return "NEXT MONTH"


def _month_ord(key: str) -> int:
    """Absolute month index, so month arithmetic/comparison is a plain subtraction."""
    year, mon = (int(x) for x in key.split("-"))
    return year * 12 + (mon - 1)


@dataclass
class MonthlyScore:
    """One player's running total for one month.

    ``correct`` is the month's currency: total correct answers across BOTH tracks (the
    rapid ``!starttrivia`` game and the 24/7 ambient question). Correct-answer COUNT is
    used rather than game points because points only exist on the rapid track — counting
    correct answers is the one unit both tracks share, so an ambient regular and a game
    sprinter compete on the same board.
    """
    node_id: str
    name: str = ""
    correct: int = 0
    answered: int = 0
    last_correct_ts: float = 0.0   # tie-break metadata + "when did they lock their total"


class MonthlyBoard:
    """Per-month standings, the archive of finished months, and the announced ledger."""

    def __init__(self, tz_name: str = "", history_months: int = 12,
                 max_lookback_months: int = DEFAULT_MAX_LOOKBACK_MONTHS):
        self.tz_name = tz_name
        self.history_months = max(1, history_months)
        self.max_lookback_months = max(1, max_lookback_months)
        # live scores, bucketed by month key. Bucketing by the ANSWER's month (not "the
        # current month") means a rollover that happens while the bot is mid-poll can never
        # credit an August answer to July, and a late announcement never loses August's
        # already-accumulating scores.
        self.months: Dict[str, Dict[str, MonthlyScore]] = {}
        # finished months, archived BEFORE their reset. This is what makes a reset safe.
        self.history: Dict[str, List[dict]] = {}
        # months already announced — the idempotency ledger.
        self.announced: List[str] = []

    # ---------------- recording ----------------
    def record(self, node_id: str, name: str, correct: bool, ts_s: float) -> None:
        """Credit one answer to the month that ``ts_s`` falls in (local time)."""
        if not node_id:
            return
        key = month_key(ts_s, self.tz_name)
        bucket = self.months.setdefault(key, {})
        s = bucket.get(node_id)
        if s is None:
            s = MonthlyScore(node_id=node_id, name=name or node_id)
            bucket[node_id] = s
        if name:
            s.name = name
        s.answered += 1
        if correct:
            s.correct += 1
            s.last_correct_ts = max(s.last_correct_ts, ts_s)

    # ---------------- standings ----------------
    def standings(self, key: str) -> List[MonthlyScore]:
        """Month standings, best first. Ordered by correct desc, then who got there first."""
        return sorted(
            self.months.get(key, {}).values(),
            key=lambda s: (-s.correct, s.last_correct_ts or float("inf"),
                           (s.name or s.node_id).lower()),
        )

    @staticmethod
    def champions(standings: Sequence[MonthlyScore]) -> List[MonthlyScore]:
        """Everyone tied at the top score.

        TIE POLICY: a tie is SHARED, not broken. Two players on 41 correct are both
        champions and both get named. Breaking a tie on "who got there first" would hand
        the title to whoever happened to answer earlier in the month, which is a timing
        artifact, not a better month. An empty/zero-score month yields [] (see
        ``is_empty``) so nothing is ever announced for a month nobody scored in.
        """
        if not standings:
            return []
        top = standings[0].correct
        if top <= 0:
            return []
        return [s for s in standings if s.correct == top]

    @staticmethod
    def is_empty(standings: Sequence[MonthlyScore]) -> bool:
        """True when the month has no scoring activity worth announcing.

        Covers both "nobody played at all" and "people played but nobody ever got one
        right" — in either case there is no champion, so we stay silent.
        """
        return not standings or standings[0].correct <= 0

    # ---------------- month lifecycle ----------------
    def pending_months(self, now_s: float) -> List[str]:
        """Finished months that still need announcing, oldest first.

        A month qualifies when it is strictly BEFORE the current local month, has not been
        announced, and is within ``max_lookback_months``. Because the ledger is consulted
        here, this returns [] on a second run — the whole idempotency story in one place.
        """
        cur = month_key(now_s, self.tz_name)
        cur_ord = _month_ord(cur)
        out = []
        for key in self.months:
            try:
                age = cur_ord - _month_ord(key)
            except (ValueError, IndexError):
                continue
            if age <= 0 or key in self.announced:
                continue
            out.append((age, key))
        return [k for age, k in sorted(out, reverse=True) if age <= self.max_lookback_months]

    def stale_months(self, now_s: float) -> List[str]:
        """Unannounced months too old to crown — archived silently (never announced)."""
        cur_ord = _month_ord(month_key(now_s, self.tz_name))
        out = []
        for key in self.months:
            try:
                age = cur_ord - _month_ord(key)
            except (ValueError, IndexError):
                continue
            if age > self.max_lookback_months and key not in self.announced:
                out.append(key)
        return sorted(out)

    def archive(self, key: str) -> List[dict]:
        """ARCHIVE-THEN-RESET, as one indivisible step.

        The month's standings are copied into ``history`` and only then are the live scores
        for that month dropped. There is deliberately NO public "reset" that skips the
        archive — a reset without a snapshot is data loss, so the two are the same call.
        Returns the archived rows.
        """
        rows = [asdict(s) for s in self.standings(key)]
        self.history[key] = rows
        self.months.pop(key, None)          # <- the reset, only ever after the snapshot
        self._trim_history()
        return rows

    def mark_announced(self, key: str) -> None:
        if key not in self.announced:
            self.announced.append(key)
        # keep the ledger bounded but far longer than the lookback window
        if len(self.announced) > 24:
            self.announced = sorted(self.announced)[-24:]

    def _trim_history(self) -> None:
        if len(self.history) > self.history_months:
            for key in sorted(self.history)[: len(self.history) - self.history_months]:
                self.history.pop(key, None)

    # ---------------- persistence ----------------
    def to_dict(self) -> dict:
        return {
            "months": {k: [asdict(s) for s in v.values()] for k, v in self.months.items()},
            "history": self.history,
            "announced": list(self.announced),
        }

    def load(self, data: Optional[dict]) -> None:
        """Restore from ``state.json``. Malformed rows are skipped, never fatal."""
        if not isinstance(data, dict):
            return
        valid = {"node_id", "name", "correct", "answered", "last_correct_ts"}
        for key, rows in (data.get("months") or {}).items():
            bucket: Dict[str, MonthlyScore] = {}
            for row in rows or []:
                try:
                    s = MonthlyScore(**{k: v for k, v in row.items() if k in valid})
                except (TypeError, ValueError):
                    continue
                if s.node_id:
                    bucket[s.node_id] = s
            if bucket:
                self.months[key] = bucket
        hist = data.get("history") or {}
        if isinstance(hist, dict):
            self.history.update({k: v for k, v in hist.items() if isinstance(v, list)})
        for key in data.get("announced") or []:
            if isinstance(key, str) and key not in self.announced:
                self.announced.append(key)


# ---------------------------------------------------------------------------------------
# Message composition. Every function here returns text that is GUARANTEED to fit the byte
# budget; the caller may send the result verbatim.
# ---------------------------------------------------------------------------------------

def byte_len(text: str) -> int:
    """UTF-8 byte length — the only length that matters on LoRa."""
    return len(text.encode("utf-8"))


def _fits(text: str, limit: int) -> bool:
    return byte_len(text) <= limit


def _truncate_bytes(text: str, limit: int) -> str:
    b = text.encode("utf-8")
    if len(b) <= limit:
        return text
    return b[: max(0, limit - 3)].decode("utf-8", errors="ignore") + "…"


def _first_fitting(candidates: Sequence[str], limit: int) -> str:
    """First candidate inside the budget; last one hard-truncated if none fit."""
    for c in candidates:
        if c and _fits(c, limit):
            return c
    return _truncate_bytes(candidates[-1] if candidates else "", limit)


def name_variants(names: Sequence[str]) -> List[str]:
    """Progressively shorter ways to say "these people won", longest first.

    A tie is shared, so all winners are named when they fit; as the budget tightens we drop
    to "A, B +2" and finally to "a N-way tie" — the tie is always still visible, we just
    stop enumerating it.
    """
    names = [n for n in names if n]
    if not names:
        return [""]
    if len(names) == 1:
        return [names[0]]
    out = [", ".join(names[:-1]) + " & " + names[-1]]
    for keep in range(len(names) - 1, 0, -1):
        out.append(", ".join(names[:keep]) + f" +{len(names) - keep}")
    out.append(f"a {len(names)}-way tie")
    return out


def compose_trivia_message(key: str, names: Sequence[str], score: int, limit: int,
                           template: str) -> str:
    """The trivia-channel announcement (one packet)."""
    label, nxt = month_label(key), next_month_label(key)
    return _first_fitting(
        [template.format(month=label, who=who, n=score, next_month=nxt)
         for who in name_variants(names)],
        limit)


def compose_primary_messages(key: str, names: Sequence[str], score: int, limit: int,
                             winner_template: str, promo_templates: Sequence[str],
                             channel_name: str, add_link: str) -> List[str]:
    """The PRIMARY-channel announcement: champion + promo, in AT MOST 2 messages.

    Message 1 crowns the month. Message 2 is the recruiting pitch and carries the trivia
    channel's NAME and its channel-add link (the key). They are separate messages because
    the link alone is ~100 B — merging them would overflow one packet, and splitting into
    three would break the two-message rule.

    The link is NEVER truncated. If prefix + link cannot fit, the prefix degrades until it
    does, and in the pathological case where the link alone exceeds the budget the promo is
    dropped entirely (one message rather than a corrupt link).
    """
    msgs = [
        _first_fitting(
            [winner_template.format(month=month_label(key), who=who, n=score)
             for who in name_variants(names)],
            limit),
        _compose_promo(limit, promo_templates, channel_name, add_link),
    ]
    msgs = [m for m in msgs if m]
    # Belt and braces: the invariant is structural, not merely conventional.
    assert len(msgs) <= MAX_PRIMARY_MESSAGES, "primary channel is limited to 2 messages"
    return msgs


def _compose_promo(limit: int, promo_templates: Sequence[str], channel_name: str,
                   add_link: str) -> str:
    """Promo packet: "join the trivia channel" + the channel name + the add link."""
    link = (add_link or "").strip()
    if not link:
        return _truncate_bytes(
            (promo_templates[0] if promo_templates else "").format(ch=channel_name), limit)
    if not _fits(link, limit):
        # A split link is a dead link and a truncated one is worse. Say nothing.
        log.error("channel add link is %d B, over the %d B budget — promo suppressed",
                  byte_len(link), limit)
        return ""
    room = limit - byte_len(link) - 1  # -1 for the newline separator
    for tpl in promo_templates:
        prefix = tpl.format(ch=channel_name)
        if _fits(prefix, room):
            return f"{prefix}\n{link}"
    return link  # nothing fit: ship the bare link, still a working invite


@dataclass
class MonthlyAnnouncement:
    """Exactly what a month-end run would transmit — the unit the preview mode prints."""
    month: str
    champions: List[str] = field(default_factory=list)
    score: int = 0
    empty: bool = False
    trivia_message: str = ""
    primary_messages: List[str] = field(default_factory=list)

    def describe(self) -> str:
        """Human-readable preview: every packet with its exact UTF-8 byte count."""
        if self.empty:
            return (f"[{self.month}] no scoring activity — archived + marked announced, "
                    f"NOTHING sent (empty months never touch the mesh).")
        out = [f"[{self.month}] champion(s): {', '.join(self.champions)} "
               f"({self.score} correct)"]
        out.append(f"  trivia channel  (1 msg): {self.trivia_message!r} "
                   f"[{byte_len(self.trivia_message)} B]")
        for i, m in enumerate(self.primary_messages, 1):
            out.append(f"  primary channel ({i}/{len(self.primary_messages)}): {m!r} "
                       f"[{byte_len(m)} B]")
        return "\n".join(out)


def build_announcement(board: MonthlyBoard, key: str, *, limit: int, trivia_template: str,
                       winner_template: str, promo_templates: Sequence[str],
                       channel_name: str, add_link: str) -> MonthlyAnnouncement:
    """Compose (but do NOT send, archive, or reset) a month's announcement."""
    standings = board.standings(key)
    if board.is_empty(standings):
        return MonthlyAnnouncement(month=key, empty=True)
    champs = board.champions(standings)
    names = [c.name or c.node_id for c in champs]
    score = champs[0].correct
    return MonthlyAnnouncement(
        month=key,
        champions=names,
        score=score,
        trivia_message=compose_trivia_message(key, names, score, limit, trivia_template),
        primary_messages=compose_primary_messages(
            key, names, score, limit, winner_template, promo_templates,
            channel_name, add_link),
    )


def now() -> float:  # pragma: no cover - trivial seam for tests
    return time.time()
