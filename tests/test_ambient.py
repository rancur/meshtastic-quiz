"""Ambient-mode tests: scheduler offset logic, pause-during-game, rate-limit floor,
message-length cap, reminder cadence, and safe-by-default.

All deterministic — no live mesh, no real wall-clock (now_s is injected). We pick a fixed
reference instant whose LOCAL minute we control via the slot-key math.
"""
import os
import time

from meshquiz.bot import TriviaBot
from meshquiz.config import Config
from meshquiz.questions import Question
from tests.mock_transport import MockTransport

TRIVIA = 2


def make_questions(n=20):
    return [Question("Test", "easy", f"Q{i}?",
                     [f"a{i}", f"b{i}", f"c{i}", f"d{i}"], i % 4) for i in range(n)]


def make_bot(tmpdir, **cfg_over):
    state_path = os.path.join(tmpdir, "state.json")
    cfg = Config(meshmonitor_token="x", trivia_channel_index=TRIVIA,
                 question_window_s=90, inter_question_gap_s=5, poll_interval_s=0,
                 min_send_interval_s=0, questions_per_game=5,
                 state_path=state_path, bot_node_id="!bot00000")
    for k, v in cfg_over.items():
        setattr(cfg, k, v)
    t = MockTransport(node_names={"!alice001": "Alice"})
    bot = TriviaBot(t, cfg, questions=make_questions())
    return bot, t


def _epoch_at_local_minute(minute_of_hour: int, hour: int = 12) -> float:
    """Return an epoch second whose LOCAL time is hour:minute:00 (today)."""
    lt = list(time.localtime())
    lt[3] = hour
    lt[4] = minute_of_hour
    lt[5] = 0
    return time.mktime(time.struct_time(lt))


# ---------------- scheduler offset logic ----------------

def test_slot_key_fires_only_at_offset_minute_hourly():
    # interval 60, offset 37 -> fires only at :37, never at :00 (Will's collision fear)
    assert TriviaBot.ambient_slot_key(_epoch_at_local_minute(0), 60, 37) is None
    assert TriviaBot.ambient_slot_key(_epoch_at_local_minute(36), 60, 37) is None
    assert TriviaBot.ambient_slot_key(_epoch_at_local_minute(37), 60, 37) is not None
    assert TriviaBot.ambient_slot_key(_epoch_at_local_minute(38), 60, 37) is None


def test_slot_key_never_fires_at_top_of_hour_for_any_nonzero_offset():
    # whatever the offset (1..59), :00 must never fire (avoids the :00 cron pileup)
    for off in (1, 7, 17, 37, 53, 59):
        assert TriviaBot.ambient_slot_key(_epoch_at_local_minute(0), 60, off) is None


def test_slot_key_distinct_per_hour():
    # consecutive hours at the offset minute yield DIFFERENT keys (so each hour fires once)
    k1 = TriviaBot.ambient_slot_key(_epoch_at_local_minute(37, hour=12), 60, 37)
    k2 = TriviaBot.ambient_slot_key(_epoch_at_local_minute(37, hour=13), 60, 37)
    assert k1 is not None and k2 is not None and k1 != k2


def test_slot_key_subhour_interval_phased_by_offset():
    # interval 30, offset 37 -> fires at :07 and :37
    assert TriviaBot.ambient_slot_key(_epoch_at_local_minute(7), 30, 37) is not None
    assert TriviaBot.ambient_slot_key(_epoch_at_local_minute(37), 30, 37) is not None
    assert TriviaBot.ambient_slot_key(_epoch_at_local_minute(22), 30, 37) is None
    assert TriviaBot.ambient_slot_key(_epoch_at_local_minute(0), 30, 37) is None


# ---------------- end-to-end firing via poll_once ----------------

def test_ambient_fires_once_per_slot_via_poll(tmp_path):
    bot, t = make_bot(str(tmp_path), ambient_enabled=True, ambient_interval_minutes=60,
                      ambient_minute_offset=37)
    fire = _epoch_at_local_minute(37)
    t.set_clock_ms(int(fire * 1000))
    bot.poll_once(now_s=fire)
    n1 = len(t.sent)
    assert n1 >= 1  # something was sent (header+question)
    # polled again in the SAME minute -> no duplicate fire
    bot.poll_once(now_s=fire + 1)
    assert len(t.sent) == n1


def test_ambient_disabled_by_default_sends_nothing(tmp_path):
    bot, t = make_bot(str(tmp_path))  # ambient_enabled defaults False
    fire = _epoch_at_local_minute(37)
    t.set_clock_ms(int(fire * 1000))
    bot.poll_once(now_s=fire)
    assert t.sent == []


def test_ambient_off_minute_sends_nothing(tmp_path):
    bot, t = make_bot(str(tmp_path), ambient_enabled=True, ambient_minute_offset=37)
    off = _epoch_at_local_minute(15)  # not the offset minute
    t.set_clock_ms(int(off * 1000))
    bot.poll_once(now_s=off)
    assert t.sent == []


# ---------------- pause during an active game ----------------

def test_ambient_paused_while_game_running(tmp_path):
    bot, t = make_bot(str(tmp_path), ambient_enabled=True, ambient_minute_offset=37)
    # start a rapid game
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    assert bot.engine.running
    sent_before = len(t.sent)
    # now hit the ambient offset minute WHILE the game is live -> ambient must NOT fire
    fire = _epoch_at_local_minute(37)
    t.set_clock_ms(int(fire * 1000))
    # keep the game from auto-advancing into a send storm: just verify no AMBIENT teaser.
    bot.poll_once(now_s=fire)
    from meshquiz import host
    ambient_msgs = [m for m in t.sent
                    if any(m.text.startswith(e) for e in host.AMBIENT_LEAD_EMOJI)]
    assert ambient_msgs == []
    # (sent may have grown from game ticks, but no ambient teaser among them)
    assert len(t.sent) >= sent_before


# ---------------- rate-limit floor ----------------

def test_rate_limit_floor_drops_excess_sends(tmp_path):
    bot, t = make_bot(str(tmp_path), max_sends_per_minute=3)
    # force many sends in the same monotonic window
    sent = [bot._send(f"msg{i}") for i in range(10)]
    delivered = [s for s in sent if s is not None]
    assert len(delivered) == 3  # hard cap held
    assert len(t.sent) == 3


def test_rate_limit_window_recovers(tmp_path, monkeypatch):
    bot, t = make_bot(str(tmp_path), max_sends_per_minute=2)
    fake = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: fake["t"])
    assert bot._send("a") is not None
    assert bot._send("b") is not None
    assert bot._send("c") is None  # capped
    fake["t"] += 61.0  # roll past the 60s window
    assert bot._send("d") is not None  # recovered


# ---------------- message-length cap ----------------

def test_ambient_messages_within_byte_budget(tmp_path):
    # use a long question to stress the cap. Keycap-prefixed options (7 bytes each vs 3
    # for the old "N)") cost ~20 bytes more per question, so this fixture is sized to land
    # just under the 200B default budget (render asserted below) — still a worst-case
    # near-cap question, which is the point of this test. The ambient build prepends a
    # standard lead emoji, so we size against the WORST-CASE lead (validate_bank does too).
    from meshquiz.questions import WORST_LEAD_EMOJI
    longq = Question("Geography", "hard",
                     "Which landlocked country has the longest official name commonly used?",
                     ["Option one is long", "Option two long",
                      "Option three long", "Option four text"], 0)
    assert longq.byte_len(WORST_LEAD_EMOJI) <= 200, \
        f"fixture must fit the cap with lead emoji, got {longq.byte_len(WORST_LEAD_EMOJI)}B"
    bot, t = make_bot(str(tmp_path), ambient_enabled=True, ambient_reminder_frequency=1)
    bot._questions = [longq]
    msgs = bot._build_ambient_messages()
    assert len(msgs) >= 2  # question packet (emoji + Q) + reminder packet
    for m in msgs:
        assert len(m.encode("utf-8")) <= bot.cfg.max_payload_bytes


# ---------------- reminder cadence ----------------

def test_ambient_reminder_every_nth(tmp_path):
    bot, t = make_bot(str(tmp_path), ambient_enabled=True, ambient_reminder_frequency=3)
    has_reminder = []
    for _ in range(6):
        msgs = bot._build_ambient_messages()
        has_reminder.append(any("!starttrivia" in m or "leaderboard" in m for m in msgs))
    # full reminder on the 3rd and 6th, not on 1,2,4,5
    assert has_reminder == [False, False, True, False, False, True]


def test_ambient_reminder_frequency_one_always_reminds(tmp_path):
    bot, t = make_bot(str(tmp_path), ambient_enabled=True, ambient_reminder_frequency=1)
    for _ in range(3):
        msgs = bot._build_ambient_messages()
        assert any("!starttrivia" in m or "leaderboard" in m for m in msgs)


# ---------------- config validation ----------------

def test_config_rejects_too_tight_ambient_interval():
    import pytest
    cfg = Config(meshmonitor_token="x", ambient_enabled=True, ambient_interval_minutes=1)
    with pytest.raises(ValueError):
        cfg.validate()


def test_config_ambient_channel_defaults_to_trivia():
    cfg = Config(meshmonitor_token="x", trivia_channel_index=2, ambient_channel_index=-1)
    assert cfg.ambient_channel == 2
    cfg2 = Config(meshmonitor_token="x", trivia_channel_index=2, ambient_channel_index=5)
    assert cfg2.ambient_channel == 5
