"""Restart must not replay old channel history (v1.11.1).

`fetch_messages` asks the server for messages `since` the cursor, but a MeshMonitor that
ignores that parameter returns its whole recent page instead — observed live: ~1000
messages, two weeks deep, for every value of `since`. The only guard was the in-memory
`_processed_pkts` set, which is empty on every boot, so each restart re-executed every
`!starttrivia` / `!help` / `!leaderboard` still in that page: a routine redeploy put a
burst of packets on the air and started a game nobody asked for.

These tests pin the client-side enforcement of the cursor plus the catch-up bound, using a
transport that deliberately IGNORES `since` the way the real server does.
"""
import os

from meshquiz.bot import TriviaBot
from meshquiz.config import Config
from meshquiz.questions import Question
from tests.mock_transport import MockTransport

TRIVIA = 2
PRIMARY = 0
HOUR_MS = 3_600_000


class IgnoresSinceTransport(MockTransport):
    """MockTransport that ignores `since_ms` — i.e. the real MeshMonitor's behavior."""

    def fetch_messages(self, channel, since_ms, limit=200):
        return [m for m in self.inbox if m.channel == channel][:limit]


def make_questions(n=20):
    return [Question("Test", "easy", f"Q{i}?",
                     [f"a{i}", f"b{i}", f"c{i}", f"d{i}"], i % 4) for i in range(n)]


def make_bot(tmpdir, transport=None, **cfg_over):
    cfg = Config(meshmonitor_token="x", trivia_channel_index=TRIVIA,
                 primary_channel_index=PRIMARY, question_window_s=90,
                 inter_question_gap_s=5, poll_interval_s=0, min_send_interval_s=0,
                 questions_per_game=5, state_path=os.path.join(tmpdir, "state.json"),
                 bot_node_id="!bot00000")
    for k, v in cfg_over.items():
        setattr(cfg, k, v)
    t = transport if transport is not None else IgnoresSinceTransport(
        node_names={"!alice001": "Alice"})
    return TriviaBot(t, cfg, questions=make_questions()), t


def test_restart_does_not_replay_old_commands(tmp_path):
    now_s = 1_800_000_000.0
    now_ms = int(now_s * 1000)
    t = IgnoresSinceTransport(node_names={"!alice001": "Alice"})
    # a fortnight of history sitting in the server's page, including live commands
    t.inject_text("!alice001", "!starttrivia", TRIVIA, now_ms - 14 * 24 * HOUR_MS)
    t.inject_text("!alice001", "!help", TRIVIA, now_ms - 5 * 24 * HOUR_MS)
    t.inject_text("!alice001", "!leaderboard", TRIVIA, now_ms - 3 * HOUR_MS)
    t.inject_text("!alice001", "!trivia", PRIMARY, now_ms - 2 * HOUR_MS)

    bot, _ = make_bot(str(tmp_path), transport=t)
    bot.poll_once(now_s)

    assert t.sent == [], "a restart must not re-execute history: " + repr(
        [m.text for m in t.sent])
    assert not bot.engine.running, "a stale !starttrivia must not start a game"


def test_fresh_commands_still_work(tmp_path):
    now_s = 1_800_000_000.0
    bot, t = make_bot(str(tmp_path))
    bot.poll_once(now_s)          # seed the cursor
    t.inject_text("!alice001", "!leaderboard", TRIVIA, int(now_s * 1000) + 1000)
    bot.poll_once(now_s + 2)
    assert any("LEADERBOARD" in m.text or "No scores yet" in m.text for m in t.sent)


def test_catchup_bound_ignores_a_cold_command_after_downtime(tmp_path):
    now_s = 1_800_000_000.0
    bot, t = make_bot(str(tmp_path), max_message_age_s=300)
    bot.poll_once(now_s)
    t.sent.clear()
    # bot was down for hours; the command is inside the cursor window but long cold
    t.inject_text("!alice001", "!starttrivia", TRIVIA, int((now_s + 60) * 1000))
    bot.poll_once(now_s + 5 * HOUR_MS / 1000)
    assert t.sent == []
    assert not bot.engine.running


def test_catchup_bound_can_be_disabled(tmp_path):
    now_s = 1_800_000_000.0
    bot, t = make_bot(str(tmp_path), max_message_age_s=0)
    bot.poll_once(now_s)
    t.sent.clear()
    t.inject_text("!alice001", "!leaderboard", TRIVIA, int((now_s + 60) * 1000))
    bot.poll_once(now_s + 4000)
    assert t.sent, "with the bound off, the cursor alone governs"


def test_recent_traffic_is_never_dropped(tmp_path):
    """The guard must not eat in-flight/slightly-late mesh delivery."""
    now_s = 1_800_000_000.0
    bot, t = make_bot(str(tmp_path))
    bot.poll_once(now_s)
    t.sent.clear()
    t.inject_text("!alice001", "!help", TRIVIA, int((now_s - 8) * 1000))  # 8s late
    bot.poll_once(now_s + 1)
    assert any("Buzz here" in m.text for m in t.sent)
