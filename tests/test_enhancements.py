"""Tests for the 1.0 enhancements:

- `!help` in the trivia channel (multi-message output + byte validation),
- `!trivia` advert on the PRIMARY channel (incl. the multi-message add-link split, and
  that NO other command works on the primary channel),
- channel-0 listening (the bot polls both the trivia and primary channels),
- HOST_CAN_PLAY flag behavior (incl. that the bot process never auto-answers).

All exercised over the in-memory MockTransport — no live mesh.
"""
import os

from meshquiz import host
from meshquiz.bot import TriviaBot
from meshquiz.config import ANSWER_EMOJI, Config
from meshquiz.questions import Question
from tests.mock_transport import MockTransport

TRIVIA = 2
PRIMARY = 0


def make_questions(n=20):
    return [Question("Test", "easy", f"Q{i}?",
                     [f"a{i}", f"b{i}", f"c{i}", f"d{i}"], i % 4) for i in range(n)]


def make_bot(tmpdir, **cfg_over):
    state_path = os.path.join(tmpdir, "state.json")
    cfg = Config(meshmonitor_token="x", trivia_channel_index=TRIVIA,
                 primary_channel_index=PRIMARY,
                 question_window_s=90, inter_question_gap_s=5, poll_interval_s=0,
                 min_send_interval_s=0, questions_per_game=5,
                 state_path=state_path, bot_node_id="!bot00000")
    for k, v in cfg_over.items():
        setattr(cfg, k, v)
    t = MockTransport(node_names={"!alice001": "Alice", "!bot00000": "G2 Base"})
    bot = TriviaBot(t, cfg, questions=make_questions())
    return bot, t


# ---------------- !help ----------------

def test_help_command_replies_in_trivia_channel(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!help", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    # multiple messages sent, all on the trivia channel
    assert len(t.sent) == len(host.HELP_LINES)
    assert all(m.channel == TRIVIA for m in t.sent)
    blob = "\n".join(m.text for m in t.sent)
    # lists every command
    for cmd in ("!starttrivia", "!stoptrivia", "!leaderboard", "!help"):
        assert cmd in blob


def test_help_command_case_insensitive(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "  !HELP ", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    assert len(t.sent) == len(host.HELP_LINES)


def test_help_lines_within_byte_budget(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!help", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    for m in t.sent:
        assert len(m.text.encode("utf-8")) <= bot.cfg.max_payload_bytes, \
            f"oversize help line: {m.text!r}"
    # and the static source lines too
    for line in host.HELP_LINES:
        assert len(line.encode("utf-8")) <= 200


def test_help_does_not_work_on_primary_channel(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!help", channel=PRIMARY, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    assert t.sent == []  # help is trivia-channel-only


# ---------------- !trivia advert on primary channel ----------------

def test_trivia_advert_on_primary_channel(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!trivia", channel=PRIMARY, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    # exactly two messages: intro + add link, both on the PRIMARY channel
    assert len(t.sent) == 2
    assert all(m.channel == PRIMARY for m in t.sent)
    assert t.sent[0].text == host.TRIVIA_ADVERT_INTRO
    assert t.sent[1].text == bot.cfg.add_link
    assert t.sent[1].text.startswith("https://meshtastic.org/e/?add=true#")


def test_trivia_advert_messages_within_byte_budget(tmp_path):
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!trivia", channel=PRIMARY, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    assert len(t.sent) == 2
    for m in t.sent:
        assert len(m.text.encode("utf-8")) <= bot.cfg.max_payload_bytes


def test_add_link_split_into_separate_message(tmp_path):
    # The link must be delivered as its own packet (not concatenated with the intro),
    # so it is never truncated.
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!trivia", channel=PRIMARY, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    link_msgs = [m for m in t.sent if m.text == bot.cfg.add_link]
    assert len(link_msgs) == 1
    assert "#" in link_msgs[0].text  # the fragment survived intact


def test_trivia_command_does_NOT_work_in_trivia_channel(tmp_path):
    # !trivia is a PRIMARY-channel-only command; in the trivia channel it is just chatter.
    bot, t = make_bot(str(tmp_path))
    t.inject_text("!alice001", "!trivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    assert t.sent == []


def test_other_commands_ignored_on_primary_channel(tmp_path):
    # On the primary channel ONLY !trivia is honored. Game-control commands are ignored.
    bot, t = make_bot(str(tmp_path))
    for i, cmd in enumerate(("!starttrivia", "!stoptrivia", "!leaderboard", "!help")):
        t.inject_text("!alice001", cmd, channel=PRIMARY, ts_ms=1000 + i)
    t.set_clock_ms(1100)
    bot.poll_once(now_s=1.1)
    assert not bot.engine.running
    assert t.sent == []


def test_reaction_on_primary_channel_ignored(tmp_path):
    bot, t = make_bot(str(tmp_path))
    # start a game in trivia
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    qpkt = bot.engine.current_packet_id
    q = bot.engine._current
    sent_before = len(t.sent)
    # a tapback on the PRIMARY channel must never score
    t.inject_reaction("!alice001", ANSWER_EMOJI[q.answer], reply_to=qpkt,
                      channel=PRIMARY, ts_ms=5000)
    t.set_clock_ms(5000); bot.poll_once(now_s=5.0)
    # the only player so far should have no score from a primary-channel reaction
    assert "!alice001" not in bot.engine.players or \
        bot.engine.players["!alice001"].score == 0
    # nothing extra advertised either
    assert len(t.sent) == sent_before


# ---------------- channel-0 listening ----------------

def test_bot_polls_both_channels(tmp_path):
    bot, t = make_bot(str(tmp_path))
    fetched = []
    orig = t.fetch_messages

    def spy(channel, since_ms, limit=200):
        fetched.append(channel)
        return orig(channel, since_ms, limit)

    t.fetch_messages = spy
    bot.poll_once(now_s=1.0)
    assert TRIVIA in fetched
    assert PRIMARY in fetched


def test_single_fetch_when_primary_equals_trivia(tmp_path):
    # If a deployment puts trivia on the primary channel, we don't double-fetch.
    bot, t = make_bot(str(tmp_path), primary_channel_index=TRIVIA)
    fetched = []
    orig = t.fetch_messages

    def spy(channel, since_ms, limit=200):
        fetched.append(channel)
        return orig(channel, since_ms, limit)

    t.fetch_messages = spy
    bot.poll_once(now_s=1.0)
    assert fetched.count(TRIVIA) == 1


# ---------------- HOST_CAN_PLAY ----------------

def test_host_ignored_by_default(tmp_path):
    # Default: host node's reactions never score.
    bot, t = make_bot(str(tmp_path))  # host_can_play defaults False
    assert bot.cfg.host_can_play is False
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    qpkt = bot.engine.current_packet_id
    q = bot.engine._current
    t.inject_reaction("!bot00000", ANSWER_EMOJI[q.answer], reply_to=qpkt,
                      channel=TRIVIA, ts_ms=5000)
    t.set_clock_ms(5000); bot.poll_once(now_s=5.0)
    t.set_clock_ms(95000); bot.poll_once(now_s=95.0)
    assert "!bot00000" not in bot.engine.players


def test_host_can_play_human_reaction_scores(tmp_path):
    bot, t = make_bot(str(tmp_path), host_can_play=True)
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    qpkt = bot.engine.current_packet_id
    q = bot.engine._current
    # a HUMAN tapback observed FROM the host node on the channel
    t.inject_reaction("!bot00000", ANSWER_EMOJI[q.answer], reply_to=qpkt,
                      channel=TRIVIA, ts_ms=5000)
    t.set_clock_ms(5000); bot.poll_once(now_s=5.0)
    t.set_clock_ms(95000); bot.poll_once(now_s=95.0)
    assert "!bot00000" in bot.engine.players
    assert bot.engine.players["!bot00000"].score > 0
    assert bot.engine.players["!bot00000"].name == "G2 Base"


def test_host_can_play_typed_answer_scores(tmp_path):
    bot, t = make_bot(str(tmp_path), host_can_play=True, allow_typed_answers=True)
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    q = bot.engine._current
    t.inject_text("!bot00000", str(q.answer + 1), channel=TRIVIA, ts_ms=5000)
    t.set_clock_ms(5000); bot.poll_once(now_s=5.0)
    t.set_clock_ms(95000); bot.poll_once(now_s=95.0)
    assert bot.engine.players["!bot00000"].score > 0


def test_bot_process_never_auto_answers(tmp_path):
    # CRITICAL anti-cheat invariant: even with HOST_CAN_PLAY on, the bot PROCESS must
    # never emit an answer for the host. The only messages the bot sends are questions /
    # flavor text — NEVER a reaction or a "1".."4" typed answer. So if no human reacts,
    # the host node never appears as a player and never scores.
    bot, t = make_bot(str(tmp_path), host_can_play=True)
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000); bot.poll_once(now_s=1.0)
    # advance through a full question with NO human reactions at all
    t.set_clock_ms(95000); bot.poll_once(now_s=95.0)
    # the bot never injected a reaction into the channel...
    assert not any(m.is_reaction for m in t.sent)
    # ...and the host node has no score (it never auto-answered)
    assert "!bot00000" not in bot.engine.players
