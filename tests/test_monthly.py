"""Monthly champion + leaderboard-reset tests (v1.11.0).

Covers the rules that would be expensive to get wrong on a live mesh:

- **byte budget** — every composed packet fits MAX_PAYLOAD_BYTES measured in UTF-8 BYTES
  (emoji are 3-4 bytes each), including worst-case long names and a big tie,
- **two-message cap** — the primary channel never receives more than 2 messages,
- **idempotency** — running the job twice, or late (box asleep at month-end), announces and
  resets exactly once,
- **archive-before-reset** — the finished month's standings survive the reset,
- **timezone** — the month boundary is local (America/Phoenix), not UTC,
- **ties** — shared, both names announced,
- **empty month** — nothing is sent at all,
- **safe default** — the whole feature is off unless explicitly enabled.

All deterministic over the in-memory MockTransport. No live mesh, no wall-clock.
"""
import os
from datetime import datetime, timezone

from meshquiz import host, monthly
from meshquiz.bot import TriviaBot
from meshquiz.config import Config
from meshquiz.monthly import MonthlyBoard
from meshquiz.questions import Question
from tests.mock_transport import MockTransport

TRIVIA = 2
PRIMARY = 0
PHOENIX = "America/Phoenix"
LIMIT = 200

# A realistic channel-add deep link (public by design — this is the thing we hand out).
# Same shape/length as a real one so the byte-budget tests are honest.
ADD_LINK = ("https://meshtastic.org/e/?add=true"
            "#CgsSATEaBnRyaXZpYRIYCAEY-gEgCygFOAFAB0gBUB5YFGgByAYB")


def make_questions(n=20):
    return [Question("Test", "easy", f"Q{i}?",
                     [f"a{i}", f"b{i}", f"c{i}", f"d{i}"], i % 4) for i in range(n)]


def make_bot(tmpdir, **cfg_over):
    state_path = os.path.join(tmpdir, "state.json")
    cfg = Config(meshmonitor_token="x", trivia_channel_index=TRIVIA,
                 primary_channel_index=PRIMARY,
                 question_window_s=90, inter_question_gap_s=5, poll_interval_s=0,
                 min_send_interval_s=0, questions_per_game=5,
                 state_path=state_path, bot_node_id="!bot00000",
                 monthly_recap_enabled=True, monthly_timezone=PHOENIX,
                 trivia_channel_name="trivia", add_link=ADD_LINK)
    for k, v in cfg_over.items():
        setattr(cfg, k, v)
    t = MockTransport(node_names={"!alice001": "Alice", "!bob00002": "Bob"})
    bot = TriviaBot(t, cfg, questions=make_questions())
    return bot, t


def ts(y, m, d, hh=12, mm=0, tz=PHOENIX):
    """Epoch seconds for a LOCAL wall-clock instant in ``tz``."""
    from zoneinfo import ZoneInfo
    return datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tz)).timestamp()


def seed_month(bot, key_year, key_month, scores):
    """Give players N correct answers each inside the given month."""
    for i, (node, name, n) in enumerate(scores):
        for k in range(n):
            bot.engine.monthly.record(node, name, True,
                                      ts(key_year, key_month, 5, 9, (i * 7 + k) % 60))


# ---------------- timezone: the month boundary is LOCAL, not UTC ----------------

def test_month_key_uses_local_timezone_not_utc():
    # 2026-07-31 23:00 in Phoenix is 2026-08-01 06:00 UTC. The month must still be July —
    # a UTC boundary would roll the board over on the wrong local day.
    late_july = ts(2026, 7, 31, 23, 0)
    assert monthly.month_key(late_july, PHOENIX) == "2026-07"
    assert datetime.fromtimestamp(late_july, timezone.utc).strftime("%Y-%m") == "2026-08"


def test_month_key_rolls_at_local_midnight():
    assert monthly.month_key(ts(2026, 7, 31, 23, 59), PHOENIX) == "2026-07"
    assert monthly.month_key(ts(2026, 8, 1, 0, 1), PHOENIX) == "2026-08"


def test_phoenix_has_no_dst_so_summer_and_winter_agree():
    # Arizona doesn't observe DST; both boundaries are UTC-7 year round.
    assert monthly.month_key(ts(2026, 1, 31, 23, 30), PHOENIX) == "2026-01"
    assert monthly.month_key(ts(2026, 6, 30, 23, 30), PHOENIX) == "2026-06"


def test_bad_timezone_falls_back_instead_of_crashing():
    assert monthly.month_key(ts(2026, 7, 15), "Not/AZone").count("-") == 1


# ---------------- byte budget (the hard mesh constraint) ----------------

def _all_composed(names, score, limit=LIMIT):
    """Every packet every copy variant could produce, for a given winner list."""
    out = []
    for tpl in host.MONTHLY_TRIVIA:
        out.append(monthly.compose_trivia_message("2026-07", names, score, limit, tpl))
    for tpl in host.MONTHLY_PRIMARY_WINNER:
        out.extend(monthly.compose_primary_messages(
            "2026-07", names, score, limit, tpl, host.MONTHLY_PRIMARY_PROMO,
            "trivia", ADD_LINK))
    return out


def test_every_message_fits_the_byte_budget():
    cases = [
        (["Alice"], 41),
        (["Alice", "Bob"], 41),
        # emoji + long node names are the worst case: emoji are 3-4 UTF-8 bytes each
        (["🛰️ Superstition Mtn Repeater Node 7", "🌵 Camelback Base Station"], 128),
        ([f"Player{i}" for i in range(12)], 9),
        (["A" * 120], 3),
    ]
    for names, score in cases:
        for msg in _all_composed(names, score):
            assert monthly.byte_len(msg) <= LIMIT, \
                f"{monthly.byte_len(msg)}B > {LIMIT}B for {names}: {msg!r}"


def test_byte_budget_is_measured_in_bytes_not_characters():
    # A 4-byte emoji name must be counted as 4 bytes. Build a name that is under the limit
    # in CHARACTERS but over it in BYTES, and confirm composition still fits.
    name = "🏆" * 90  # 90 chars, 360 bytes
    for msg in _all_composed([name], 5):
        assert monthly.byte_len(msg) <= LIMIT
        assert len(msg) <= LIMIT  # trivially true once bytes fit, but assert both


def test_tight_budget_still_produces_single_packet_messages():
    for limit in (120, 150, 200, 237):
        for msg in _all_composed(["Alice", "Bob", "Carol"], 22, limit=limit):
            assert monthly.byte_len(msg) <= limit


def test_add_link_is_never_truncated():
    msgs = monthly.compose_primary_messages(
        "2026-07", ["Alice"], 41, LIMIT, host.MONTHLY_PRIMARY_WINNER[0],
        host.MONTHLY_PRIMARY_PROMO, "trivia", ADD_LINK)
    promo = msgs[-1]
    assert ADD_LINK in promo, "the add link must survive intact — a cut link is a dead link"
    assert "…" not in promo


def test_promo_is_dropped_rather_than_shipping_a_broken_link():
    # Pathological: the link alone blows the packet. Better one message than a dead link.
    msgs = monthly.compose_primary_messages(
        "2026-07", ["Alice"], 41, 60, host.MONTHLY_PRIMARY_WINNER[0],
        host.MONTHLY_PRIMARY_PROMO, "trivia", ADD_LINK)
    assert len(msgs) == 1
    assert monthly.byte_len(msgs[0]) <= 60


# ---------------- the two-message cap on the primary channel ----------------

def test_primary_never_exceeds_two_messages():
    for names in (["Alice"], ["Alice", "Bob"], [f"P{i}" for i in range(20)]):
        for tpl in host.MONTHLY_PRIMARY_WINNER:
            msgs = monthly.compose_primary_messages(
                "2026-07", names, 7, LIMIT, tpl, host.MONTHLY_PRIMARY_PROMO,
                "trivia", ADD_LINK)
            assert len(msgs) <= monthly.MAX_PRIMARY_MESSAGES == 2


def test_end_to_end_sends_exactly_two_primary_and_one_trivia_message(tmp_path):
    bot, t = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41), ("!bob00002", "Bob", 12)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))

    primary = [m for m in t.sent if m.channel == PRIMARY]
    trivia = [m for m in t.sent if m.channel == TRIVIA]
    assert len(primary) == 2, [m.text for m in primary]
    assert len(trivia) == 1
    # champion named on BOTH channels; the promo carries the channel name AND the key/link
    assert "Alice" in primary[0].text and "Alice" in trivia[0].text
    assert "trivia" in primary[1].text and ADD_LINK in primary[1].text
    for m in t.sent:
        assert monthly.byte_len(m.text) <= LIMIT


def test_promo_carries_channel_name_and_key_from_config(tmp_path):
    # Name + link must come from CONFIG, never a hardcoded guess.
    link = "https://meshtastic.org/e/?add=true#CgsSAaAaBlRyaXZpYRIA"
    bot, t = make_bot(str(tmp_path), trivia_channel_name="Trivia", add_link=link)
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 5)])
    bot._maybe_monthly(ts(2026, 8, 1, 1, 0))
    promo = [m for m in t.sent if m.channel == PRIMARY][-1]
    assert "Trivia" in promo.text
    assert link in promo.text


# ---------------- idempotency ----------------

def test_running_twice_announces_and_resets_only_once(tmp_path):
    bot, t = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    first = len(t.sent)
    assert first == 3
    for _ in range(5):
        bot._maybe_monthly(ts(2026, 8, 1, 0, 45))
    assert len(t.sent) == first, "a second run must not re-announce"


def test_late_fire_after_the_box_was_asleep_announces_once(tmp_path):
    # Box asleep through midnight on the 1st; first poll is days later.
    bot, t = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    bot._maybe_monthly(ts(2026, 8, 4, 9, 15))
    assert len(t.sent) == 3
    bot._maybe_monthly(ts(2026, 8, 4, 9, 20))
    assert len(t.sent) == 3


def test_idempotent_across_restart(tmp_path):
    bot, t = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    assert len(t.sent) == 3

    # New process, same state file: the announced ledger must come back with it.
    bot2, t2 = make_bot(str(tmp_path))
    assert "2026-07" in bot2.engine.monthly.announced
    bot2._maybe_monthly(ts(2026, 8, 1, 6, 0))
    assert t2.sent == [], "a restart on the 1st must not re-announce July"


def test_state_is_committed_before_any_packet_is_sent(tmp_path):
    """A crash mid-send must not produce a duplicate next boot."""
    bot, t = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])

    sent_before_commit = []
    real_send = bot.t.send_message

    def failing_send(text, channel):
        sent_before_commit.append(text)
        raise RuntimeError("radio died mid-announcement")

    bot.t.send_message = failing_send
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    bot.t.send_message = real_send
    assert sent_before_commit, "it did try to send"

    bot2, t2 = make_bot(str(tmp_path))
    assert "2026-07" in bot2.engine.monthly.announced
    bot2._maybe_monthly(ts(2026, 8, 2, 0, 40))
    assert t2.sent == []


def test_a_second_month_still_announces(tmp_path):
    bot, t = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    seed_month(bot, 2026, 8, [("!bob00002", "Bob", 17)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    assert len(t.sent) == 3 and "Alice" in t.sent[0].text
    bot._maybe_monthly(ts(2026, 9, 1, 0, 40))
    assert len(t.sent) == 6 and "Bob" in t.sent[3].text


# ---------------- archive + reset safety ----------------

def test_reset_archives_the_month_before_clearing_it(tmp_path):
    bot, _ = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41), ("!bob00002", "Bob", 12)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))

    board = bot.engine.monthly
    assert "2026-07" not in board.months, "the live month must be reset to zero"
    archived = board.history["2026-07"]
    assert [(r["name"], r["correct"]) for r in archived] == [("Alice", 41), ("Bob", 12)]


def test_archive_survives_a_restart(tmp_path):
    bot, _ = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    bot2, _ = make_bot(str(tmp_path))
    assert bot2.engine.monthly.history["2026-07"][0]["correct"] == 41


def test_new_month_scores_are_untouched_by_the_reset(tmp_path):
    bot, _ = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    seed_month(bot, 2026, 8, [("!bob00002", "Bob", 3)])
    bot._maybe_monthly(ts(2026, 8, 1, 12, 0))
    assert bot.engine.monthly.months["2026-08"]["!bob00002"].correct == 3


def test_history_is_bounded(tmp_path):
    board = MonthlyBoard(tz_name=PHOENIX, history_months=3)
    for m in range(1, 9):
        board.record("!n", "N", True, ts(2026, m, 5))
        board.archive(f"2026-{m:02d}")
    assert len(board.history) == 3
    assert sorted(board.history) == ["2026-06", "2026-07", "2026-08"]


# ---------------- ties ----------------

def test_tie_for_first_is_shared_and_both_are_named(tmp_path):
    bot, t = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 30), ("!bob00002", "Bob", 30),
                              ("!carol003", "Carol", 12)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    text = " ".join(m.text for m in t.sent)
    assert "Alice" in text and "Bob" in text
    assert "Carol" not in text


def test_big_tie_degrades_but_still_shows_it_is_a_tie():
    names = [f"LongPlayerName{i}" for i in range(9)]
    msgs = monthly.compose_primary_messages(
        "2026-07", names, 4, LIMIT, host.MONTHLY_PRIMARY_WINNER[0],
        host.MONTHLY_PRIMARY_PROMO, "trivia", ADD_LINK)
    assert monthly.byte_len(msgs[0]) <= LIMIT
    assert ("+" in msgs[0]) or ("9-way tie" in msgs[0])


def test_champions_helper_returns_everyone_on_the_top_score():
    board = MonthlyBoard(tz_name=PHOENIX)
    for node, name, n in [("!a", "A", 5), ("!b", "B", 5), ("!c", "C", 4)]:
        for _ in range(n):
            board.record(node, name, True, ts(2026, 7, 5))
    champs = board.champions(board.standings("2026-07"))
    assert sorted(c.name for c in champs) == ["A", "B"]


# ---------------- empty month ----------------

def test_empty_month_sends_nothing(tmp_path):
    bot, t = make_bot(str(tmp_path))
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    assert t.sent == []


def test_month_where_everyone_answered_wrong_sends_nothing(tmp_path):
    bot, t = make_bot(str(tmp_path))
    bot.engine.monthly.record("!alice001", "Alice", False, ts(2026, 7, 9))
    bot.engine.monthly.record("!bob00002", "Bob", False, ts(2026, 7, 10))
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    assert t.sent == [], "no champion with zero correct answers — stay quiet"
    # still archived + marked so it isn't reconsidered forever
    assert "2026-07" in bot.engine.monthly.announced
    assert "2026-07" not in bot.engine.monthly.months


# ---------------- gating / safety defaults ----------------

def test_disabled_by_default(tmp_path):
    bot, t = make_bot(str(tmp_path), monthly_recap_enabled=False)
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    assert t.sent == []
    # ...and nothing was reset, so enabling it later still crowns July
    assert bot.engine.monthly.months["2026-07"]["!alice001"].correct == 41


def test_fresh_config_defaults_to_off():
    assert Config(meshmonitor_token="x").monthly_recap_enabled is False


def test_dry_run_transmits_nothing_and_does_not_reset(tmp_path):
    bot, t = make_bot(str(tmp_path), monthly_dry_run=True)
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    for _ in range(3):
        bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    assert t.sent == [], "MONTHLY_DRY_RUN must never transmit"
    assert "2026-07" not in bot.engine.monthly.announced
    assert bot.engine.monthly.months["2026-07"]["!alice001"].correct == 41
    # the preview text is the real text
    ann = bot.build_monthly_announcement("2026-07")
    assert "Alice" in ann.trivia_message and len(ann.primary_messages) == 2
    assert "41" in ann.describe()


def test_primary_crosspost_can_be_disabled(tmp_path):
    bot, t = make_bot(str(tmp_path), monthly_announce_primary=False)
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    assert [m.channel for m in t.sent] == [TRIVIA]


def test_no_crosspost_when_primary_is_the_trivia_channel(tmp_path):
    bot, t = make_bot(str(tmp_path), primary_channel_index=TRIVIA)
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    assert len(t.sent) == 1


def test_never_announces_mid_game(tmp_path):
    bot, t = make_bot(str(tmp_path))
    seed_month(bot, 2026, 7, [("!alice001", "Alice", 41)])
    bot.engine.start(ts(2026, 8, 1, 0, 30))
    t.sent.clear()
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    assert t.sent == [], "the wrap-up must not land mid-round"


def test_stale_month_is_archived_silently(tmp_path):
    bot, t = make_bot(str(tmp_path))
    seed_month(bot, 2026, 1, [("!alice001", "Alice", 41)])
    bot._maybe_monthly(ts(2026, 8, 1, 0, 40))
    assert t.sent == [], "a champion from 7 months ago is not news"
    assert bot.engine.monthly.history["2026-01"][0]["correct"] == 41


def test_current_month_is_never_announced_early(tmp_path):
    bot, t = make_bot(str(tmp_path))
    seed_month(bot, 2026, 8, [("!alice001", "Alice", 41)])
    bot._maybe_monthly(ts(2026, 8, 31, 23, 59))
    assert t.sent == []
    assert bot.engine.monthly.months["2026-08"]["!alice001"].correct == 41


# ---------------- scoring integration (both tracks feed one board) ----------------

def test_game_and_ambient_answers_both_count(tmp_path):
    bot, t = make_bot(str(tmp_path), personality_enabled=True)
    july = ts(2026, 7, 15, 10, 0)

    # rapid game round
    bot.engine.start(july)
    q = bot.engine._current
    bot.engine.on_question_sent(999)
    bot.engine.submit_answer("!alice001", "Alice", q.answer, july + 1)
    bot.engine.tick(july + 200)

    # ambient round
    aq = make_questions(1)[0]
    bot.engine.open_ambient(aq, 1)
    bot.engine.on_ambient_sent(1001)
    bot.engine.submit_ambient_answer("!alice001", "Alice", aq.answer, july + 300)
    bot.engine.resolve_ambient()

    assert bot.engine.monthly.months["2026-07"]["!alice001"].correct == 2


def test_answers_are_bucketed_by_their_own_timestamp_across_the_boundary(tmp_path):
    bot, _ = make_bot(str(tmp_path))
    bot.engine.monthly.record("!alice001", "Alice", True, ts(2026, 7, 31, 23, 58))
    bot.engine.monthly.record("!alice001", "Alice", True, ts(2026, 8, 1, 0, 2))
    assert bot.engine.monthly.months["2026-07"]["!alice001"].correct == 1
    assert bot.engine.monthly.months["2026-08"]["!alice001"].correct == 1
