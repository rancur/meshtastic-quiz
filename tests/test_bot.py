"""Bot integration tests using the mock transport (no live mesh)."""
import os
import tempfile

import pytest

from meshquiz.bot import TriviaBot, emoji_to_option, typed_to_option
from meshquiz.config import ANSWER_EMOJI, Config
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
    t = MockTransport(node_names={"!alice001": "Alice", "!bob00002": "Bob"})
    bot = TriviaBot(t, cfg, questions=make_questions())
    return bot, t


def last_question_pkt(t):
    # the most recent sent message that looks like a question ("[Test]")
    for m in reversed(t.sent):
        if m.text.startswith("[Test]"):
            return m.packet_id
    return None


def test_emoji_mapping():
    assert emoji_to_option("1️⃣") == 0
    assert emoji_to_option("2️⃣") == 1
    assert emoji_to_option("4️⃣") == 3
    assert emoji_to_option("❤️") is None
    assert emoji_to_option("") is None


def test_emoji_mapping_without_variation_selector():
    # keycap without U+FE0F: digit + U+20E3
    for i, d in enumerate("1234"):
        assert emoji_to_option(d + "⃣") == i
    # surrounding whitespace tolerated
    assert emoji_to_option("  3️⃣  ") == 2
    # a bare digit is NOT a reaction emoji (handled as a typed answer instead)
    assert emoji_to_option("1") is None


def test_typed_mapping():
    assert typed_to_option("3") == 2
    assert typed_to_option(" 4 ") == 3
    assert typed_to_option("hello") is None


def test_channel_gating_ignores_other_channels(tmp_path):
    bot, t = make_bot(str(tmp_path))
    # !starttrivia on the WRONG channel (0) must be ignored
    t.inject_text("!alice001", "!starttrivia", channel=0, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    assert not bot.engine.running
    assert t.sent == []  # bot said nothing


def test_start_command_starts_game(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    assert bot.engine.running
    assert last_question_pkt(t) is not None


def test_idempotent_start_via_bot(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    first_pkt = bot.engine.current_packet_id
    n_questions = sum(1 for m in t.sent if m.text.startswith("[Test]"))
    # spam start again
    t.inject_text("!bob00002", "!starttrivia", channel=TRIVIA, ts_ms=2000)
    t.set_clock_ms(2000); bot.poll_once(now_s=2.0)
    assert bot.engine.current_packet_id == first_pkt
    n_after = sum(1 for m in t.sent if m.text.startswith("[Test]"))
    assert n_after == n_questions  # no extra question started


def test_reaction_answer_scores(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    qpkt = bot.engine.current_packet_id
    q = bot.engine._current
    # Alice reacts with the CORRECT keycap emoji
    correct_emoji = ANSWER_EMOJI[q.answer]
    t.inject_reaction("!alice001", correct_emoji, reply_to=qpkt, channel=TRIVIA, ts_ms=5000)
    t.set_clock_ms(5000); bot.poll_once(now_s=5.0)
    # close the question
    t.set_clock_ms(95000); bot.poll_once(now_s=95.0)
    assert bot.engine.players["!alice001"].score > 0
    assert bot.engine.players["!alice001"].name == "Alice"  # display name resolved


def test_dedupe_by_hex_node_id(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    qpkt = bot.engine.current_packet_id
    q = bot.engine._current
    # same node reacts twice (different emoji) -> only first counts, one player entry
    t.inject_reaction("!alice001", ANSWER_EMOJI[(q.answer + 1) % 4], reply_to=qpkt,
                      channel=TRIVIA, ts_ms=4000)
    t.inject_reaction("!alice001", ANSWER_EMOJI[q.answer], reply_to=qpkt,
                      channel=TRIVIA, ts_ms=6000)
    t.set_clock_ms(7000); bot.poll_once(now_s=7.0)
    t.set_clock_ms(95000); bot.poll_once(now_s=95.0)
    assert len(bot.engine.players) == 1
    # first reaction was wrong -> 0 points
    assert bot.engine.players["!alice001"].score == 0


def test_reaction_to_stale_message_ignored(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    q = bot.engine._current
    # react to a non-current packet id
    t.inject_reaction("!alice001", ANSWER_EMOJI[q.answer], reply_to=999999,
                      channel=TRIVIA, ts_ms=5000)
    t.set_clock_ms(5000); bot.poll_once(now_s=5.0)
    t.set_clock_ms(95000); bot.poll_once(now_s=95.0)
    assert bot.engine.players.get("!alice001", None) is None or \
        bot.engine.players["!alice001"].score == 0


def test_bot_ignores_its_own_reactions(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    qpkt = bot.engine.current_packet_id
    q = bot.engine._current
    t.inject_reaction("!bot00000", ANSWER_EMOJI[q.answer], reply_to=qpkt,
                      channel=TRIVIA, ts_ms=5000)
    t.set_clock_ms(5000); bot.poll_once(now_s=5.0)
    assert "!bot00000" not in bot.engine.players


def test_typed_answer_fallback(tmp_path):
    bot, t = make_bot(str(tmp_path), allow_typed_answers=True)
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    q = bot.engine._current
    typed = str(q.answer + 1)  # "1".."4"
    t.inject_text("!bob00002", typed, channel=TRIVIA, ts_ms=5000)
    t.set_clock_ms(5000); bot.poll_once(now_s=5.0)
    t.set_clock_ms(95000); bot.poll_once(now_s=95.0)
    assert bot.engine.players["!bob00002"].score > 0


def test_typed_answer_disabled(tmp_path):
    bot, t = make_bot(str(tmp_path), allow_typed_answers=False)
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    q = bot.engine._current
    t.inject_text("!bob00002", str(q.answer + 1), channel=TRIVIA, ts_ms=5000)
    t.set_clock_ms(5000); bot.poll_once(now_s=5.0)
    t.set_clock_ms(95000); bot.poll_once(now_s=95.0)
    assert "!bob00002" not in bot.engine.players


def test_leaderboard_command(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!leaderboard", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    assert any("LEADERBOARD" in m.text or "No scores" in m.text for m in t.sent)


def test_stop_command(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    assert bot.engine.running
    t.inject_text("!alice001", "!stoptrivia", channel=TRIVIA, ts_ms=2000)
    t.set_clock_ms(2000); bot.poll_once(now_s=2.0)
    assert not bot.engine.running


def test_all_sent_messages_within_byte_budget(tmp_path):
    bot, t = make_bot(str(tmp_path))
    # run a full session with reactions
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    clock = 1000
    for _ in range(40):
        clock += 5000
        qpkt = bot.engine.current_packet_id
        if qpkt and bot.engine._current is not None:
            q = bot.engine._current
            t.inject_reaction("!alice001", ANSWER_EMOJI[q.answer], reply_to=qpkt,
                              channel=TRIVIA, ts_ms=clock)
            t.inject_reaction("!bob00002", ANSWER_EMOJI[q.answer], reply_to=qpkt,
                              channel=TRIVIA, ts_ms=clock)
        clock += 90000
        t.set_clock_ms(clock); bot.poll_once(now_s=clock / 1000.0)
        if not bot.engine.running:
            break
    for m in t.sent:
        assert len(m.text.encode("utf-8")) <= 200, f"oversize send: {m.text!r}"


def test_full_session_two_players_winner(tmp_path):
    bot, t = make_bot(str(tmp_path), questions_per_game=3, first_correct_bonus=3,
                      max_speed_bonus=0, base_points=10)
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    clock = 1000
    guard = 0
    while bot.engine.running and guard < 50:
        guard += 1
        # only act when a question is actually open (skip BETWEEN-phase polls)
        if bot.engine.current_packet_id is not None and bot.engine._current is not None:
            qpkt = bot.engine.current_packet_id
            q = bot.engine._current
            # Alice first & correct, Bob correct but later
            t.inject_reaction("!alice001", ANSWER_EMOJI[q.answer], reply_to=qpkt,
                              channel=TRIVIA, ts_ms=clock + 1000)
            t.inject_reaction("!bob00002", ANSWER_EMOJI[q.answer], reply_to=qpkt,
                              channel=TRIVIA, ts_ms=clock + 2000)
            t.set_clock_ms(clock + 5000); bot.poll_once(now_s=(clock + 5000) / 1000.0)
        # advance time past the window + inter-question gap so the next question opens
        clock += 100000
        t.set_clock_ms(clock); bot.poll_once(now_s=clock / 1000.0)
    board = bot.engine.leaderboard()
    assert board[0].name == "Alice"  # first-correct bonus each round
    assert board[0].score > board[1].score


def test_crash_recovery_restores_cursor(tmp_path):
    state_path = os.path.join(str(tmp_path), "state.json")
    cfg = Config(meshmonitor_token="x", trivia_channel_index=TRIVIA, poll_interval_s=0,
                 min_send_interval_s=0, state_path=state_path, bot_node_id="!bot00000")
    t = MockTransport()
    bot = TriviaBot(t, cfg, questions=make_questions())
    t.inject_text("!alice001", "!leaderboard", channel=TRIVIA, ts_ms=50000)
    t.set_clock_ms(50000); bot.poll_once(now_s=50.0)
    assert bot._cursor_ms >= 50000
    # new bot instance reads persisted cursor
    bot2 = TriviaBot(t, cfg, questions=make_questions())
    assert bot2._cursor_ms >= 50000


def test_malformed_input_does_not_crash(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "", channel=TRIVIA, ts_ms=1000)
    t.inject_text("!alice001", "!STARTTRIVIA  ", channel=TRIVIA, ts_ms=1100)  # case/space
    t.inject_text("!alice001", "random chatter", channel=TRIVIA, ts_ms=1200)
    t.set_clock_ms(1200); bot.poll_once(now_s=1.2)
    # case-insensitive + trimmed command should have started a game
    assert bot.engine.running


def test_bad_question_bank_rejected(tmp_path):
    state_path = os.path.join(str(tmp_path), "state.json")
    cfg = Config(meshmonitor_token="x", state_path=state_path)
    t = MockTransport()
    big = "x" * 300
    bad = [Question("C", "easy", big, ["a", "b", "c", "d"], 0)]
    with pytest.raises(ValueError):
        TriviaBot(t, cfg, questions=bad)
