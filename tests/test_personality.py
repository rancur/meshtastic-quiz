"""Personality-system tests: quip determinism, recap byte caps + name truncation, poke
calibration (cooldown, new-player exemption, observable-facts), streak escalation tiers,
no-winner path, recap+question = exactly 2 packets, circuit breaker authority, and the
pure-additive guarantee (PERSONALITY_ENABLED=false == v1.1.0 behavior).

All deterministic — no live mesh, injected clock. The QuipEngine seed defaults to 0 so
selection is reproducible.
"""
import os
import time

import pytest

from meshquiz.bot import TriviaBot
from meshquiz.config import Config
from meshquiz.engine import AmbientStats, GameEngine
from meshquiz.personality import (BANK_SIZES, COMEBACK, NO_WINNER, POKE,
                                  POKE_BOTTOM, STREAK_2, STREAK_3, STREAK_5,
                                  WINNER, QuipEngine)
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
    t = MockTransport(node_names={"!alice001": "Alice", "!bob00002": "Bob",
                                  "!carol003": "Carol", "!dave0004": "Dave"})
    bot = TriviaBot(t, cfg, questions=make_questions())
    return bot, t


def _epoch_at_local_minute(minute_of_hour: int, hour: int = 12) -> float:
    lt = list(time.localtime())
    lt[3] = hour
    lt[4] = minute_of_hour
    lt[5] = 0
    return time.mktime(time.struct_time(lt))


# ---------------- bank sanity ----------------

def test_all_banks_have_at_least_30_lines():
    for name, size in BANK_SIZES.items():
        assert size >= 30, f"{name} has only {size} lines"


def test_banks_have_no_exact_duplicate_lines():
    for bank in (WINNER, STREAK_2, STREAK_3, STREAK_5, NO_WINNER, COMEBACK, POKE, POKE_BOTTOM):
        assert len(set(bank)) == len(bank)


# ---------------- quip determinism + rotation ----------------

def test_quip_selection_deterministic_same_seed():
    a = QuipEngine(seed=0)
    b = QuipEngine(seed=0)
    seq_a = [a.winner("X", streak=1) for _ in range(10)]
    seq_b = [b.winner("X", streak=1) for _ in range(10)]
    assert seq_a == seq_b  # same seed -> identical sequence


def test_quip_rotation_cycles_no_repeat_within_bank_len():
    q = QuipEngine(seed=0)
    n = len(WINNER)
    picks = [q.winner("X", streak=1) for _ in range(n)]
    # full cycle before any repeat
    assert len(set(picks)) == n
    # wraps around: the (n+1)th equals the 1st
    assert q.winner("X", streak=1) == picks[0]


def test_quip_banks_rotate_independently():
    q = QuipEngine(seed=0)
    # advancing the winner bank must not disturb the no_winner bank's starting point
    q.winner("X")
    q.winner("X")
    fresh = QuipEngine(seed=0)
    assert q.no_winner("opt") == fresh.no_winner("opt")


# ---------------- streak escalation tiers ----------------

def test_streak_escalation_tiers_pick_right_bank():
    q = QuipEngine(seed=0)
    assert q.winner("X", streak=1) in [s.format(name="X") for s in WINNER]
    assert q.winner("X", streak=2) in [s.format(name="X", n=2) for s in STREAK_2]
    assert q.winner("X", streak=3) in [s.format(name="X", n=3) for s in STREAK_3]
    assert q.winner("X", streak=5) in [s.format(name="X", n=5) for s in STREAK_5]
    # 4 is still the 3-tier (escalates to 5+ only at 5)
    assert q.winner("X", streak=4) in [s.format(name="X", n=4) for s in STREAK_3]


def test_streak5_interpolates_count():
    q = QuipEngine(seed=0)
    line = q.winner("Zed", streak=7)
    # at least one STREAK_5 line interpolates {n}; the rendered line should contain the count
    # for any bank line that uses {n}. We assert the engine fed n correctly by checking the
    # bank line template produces the same string.
    assert any(tmpl.format(name="Zed", n=7) == line for tmpl in STREAK_5)


# ---------------- comeback + no-winner ----------------

def test_comeback_renders_drought():
    q = QuipEngine(seed=0)
    line = q.comeback("Ann", 6)
    assert any(tmpl.format(name="Ann", n=6) == line for tmpl in COMEBACK)


def test_no_winner_includes_answer():
    q = QuipEngine(seed=0)
    line = q.no_winner("3) Paris")
    assert "3) Paris" in line


# ---------------- engine ambient resolution ----------------

def test_resolve_ambient_no_question_is_graceful():
    cfg = Config(meshmonitor_token="x")
    eng = GameEngine(cfg, make_questions())
    recap = eng.resolve_ambient()
    assert recap.had_question is False


def test_resolve_ambient_scores_winner_and_streak():
    cfg = Config(meshmonitor_token="x")
    eng = GameEngine(cfg, make_questions())
    q = Question("T", "e", "Q?", ["a", "b", "c", "d"], 1)  # answer index 1
    # round 1
    eng.open_ambient(q, slot_index=100)
    eng.on_ambient_sent(555)
    eng.submit_ambient_answer("!a", "Ann", 1, ts_s=1.0)   # correct
    eng.submit_ambient_answer("!b", "Bob", 0, ts_s=2.0)   # wrong
    r1 = eng.resolve_ambient()
    assert r1.first_winner == "Ann"
    assert r1.first_winner_streak == 1
    assert r1.winner_names == ["Ann"]
    # round 2: Ann correct again -> streak 2
    eng.open_ambient(q, slot_index=101)
    eng.submit_ambient_answer("!a", "Ann", 1, ts_s=1.0)
    r2 = eng.resolve_ambient()
    assert r2.first_winner_streak == 2
    # Bob now has a 1-question wrong streak from round 1
    assert eng.ambient_stats["!b"].wrong_streak == 1


def test_resolve_ambient_comeback_detection():
    cfg = Config(meshmonitor_token="x")
    eng = GameEngine(cfg, make_questions())
    q = Question("T", "e", "Q?", ["a", "b", "c", "d"], 0)
    # slot 10: Ann correct
    eng.open_ambient(q, 10)
    eng.submit_ambient_answer("!a", "Ann", 0, 1.0)
    eng.resolve_ambient()
    # slot 15: Ann correct again after a 5-slot gap -> comeback of 5
    eng.open_ambient(q, 15)
    eng.submit_ambient_answer("!a", "Ann", 0, 1.0)
    r = eng.resolve_ambient()
    assert r.first_winner_comeback == 5


def test_ambient_wrong_answer_gets_immediate_ack():
    from meshquiz.engine import SendText
    from meshquiz import host
    cfg = Config(meshmonitor_token="x")
    eng = GameEngine(cfg, make_questions())
    q = Question("T", "e", "Q?", ["a", "b", "c", "d"], 1)  # answer index 1
    eng.open_ambient(q, slot_index=100)
    eng.on_ambient_sent(555)
    # wrong ambient answer -> immediate ack, no answer leak
    actions = eng.submit_ambient_answer("!b", "Bob", 0, ts_s=1.0)
    assert len(actions) == 1 and isinstance(actions[0], SendText)
    txt = actions[0].text
    assert "Bob" in txt and q.answer_text() not in txt
    assert any(tmpl.format(name="Bob") == txt for tmpl in host.WRONG)
    # correct ambient answer stays silent immediately (celebrated at recap)
    assert eng.submit_ambient_answer("!a", "Ann", 1, ts_s=2.0) == []
    # a locked-out repeat from the same node acks nothing (no spam)
    assert eng.submit_ambient_answer("!b", "Bob", 2, ts_s=3.0) == []


def test_ambient_wrong_ack_can_be_disabled():
    cfg = Config(meshmonitor_token="x", wrong_answer_ack=False)
    eng = GameEngine(cfg, make_questions())
    q = Question("T", "e", "Q?", ["a", "b", "c", "d"], 1)
    eng.open_ambient(q, slot_index=100)
    assert eng.submit_ambient_answer("!b", "Bob", 0, ts_s=1.0) == []


# ---------------- poke calibration ----------------

def _seed_struggler(eng, node, name, wrong_streak, first_seen=0, last_poked=-1):
    st = AmbientStats(node_id=node, name=name, wrong_streak=wrong_streak,
                      first_seen_slot=first_seen, last_poked_slot=last_poked, answered=5)
    eng.ambient_stats[node] = st
    return st


def test_poke_targets_wrong_streaker():
    cfg = Config(meshmonitor_token="x", poke_cooldown_hours=3, new_player_grace_slots=2)
    eng = GameEngine(cfg, make_questions())
    _seed_struggler(eng, "!b", "Bob", wrong_streak=4, first_seen=0)
    target = eng.poke_target(cfg, cur_slot=10)
    assert target is not None and target.node_id == "!b"


def test_poke_skips_brand_new_player():
    cfg = Config(meshmonitor_token="x", new_player_grace_slots=2)
    eng = GameEngine(cfg, make_questions())
    # struggling but FIRST SEEN this very slot -> exempt
    _seed_struggler(eng, "!n", "Newbie", wrong_streak=5, first_seen=10)
    assert eng.poke_target(cfg, cur_slot=10) is None
    # one slot later still within grace (grace=2)
    assert eng.poke_target(cfg, cur_slot=11) is None
    # grace elapsed
    assert eng.poke_target(cfg, cur_slot=12) is not None


def test_poke_cooldown_honored():
    cfg = Config(meshmonitor_token="x", poke_cooldown_hours=3, new_player_grace_slots=2)
    eng = GameEngine(cfg, make_questions())
    _seed_struggler(eng, "!b", "Bob", wrong_streak=4, first_seen=0, last_poked=8)
    # poked at slot 8, cooldown 3 -> not eligible at 9,10; eligible at 11
    assert eng.poke_target(cfg, cur_slot=9) is None
    assert eng.poke_target(cfg, cur_slot=10) is None
    assert eng.poke_target(cfg, cur_slot=11) is not None


def test_poke_disabled_returns_none():
    cfg = Config(meshmonitor_token="x", pokes_enabled=False)
    eng = GameEngine(cfg, make_questions())
    _seed_struggler(eng, "!b", "Bob", wrong_streak=9, first_seen=0)
    assert eng.poke_target(cfg, cur_slot=99) is None


def test_poke_bottom_of_board_when_no_streaker():
    cfg = Config(meshmonitor_token="x", new_player_grace_slots=0)
    eng = GameEngine(cfg, make_questions())
    # 3-player board, clear gap, nobody on a wrong streak
    eng.ambient_stats["!a"] = AmbientStats("!a", "Ann", correct=5, first_seen_slot=0)
    eng.ambient_stats["!b"] = AmbientStats("!b", "Bob", correct=3, first_seen_slot=0)
    eng.ambient_stats["!c"] = AmbientStats("!c", "Cy", correct=0, first_seen_slot=0)
    target = eng.poke_target(cfg, cur_slot=50)
    assert target is not None and target.node_id == "!c"  # bottom


def test_pokes_reference_only_facts_not_identity():
    # every poke template references streak count {n}, gap {gap}, or name — never anything
    # about who the person is. Spot-check: no slurs / identity words; uses {name} only as a
    # handle and a numeric fact.
    for tmpl in POKE:
        assert "{name}" in tmpl and "{n}" in tmpl
    for tmpl in POKE_BOTTOM:
        assert "{name}" in tmpl and "{gap}" in tmpl


# ---------------- recap packet construction ----------------

def test_recap_byte_cap_with_long_names(tmp_path):
    bot, t = make_bot(str(tmp_path), personality_enabled=True, recap_enabled=True,
                      pokes_enabled=False)
    eng = bot.engine
    q = Question("T", "e", "Q?", ["a", "b", "c", "d"], 0)
    eng.open_ambient(q, 100)
    # many correct answerers with long names -> headline + "(+N more)" must stay one packet
    for i in range(8):
        eng.submit_ambient_answer(f"!n{i}", "A" * 40 + str(i), 0, ts_s=float(i))
    text = bot._build_recap_text(slot_index=101)
    assert text is not None
    assert len(text.encode("utf-8")) <= bot.cfg.max_payload_bytes
    assert "+7 more" in text  # 8 winners -> first + 7 more


def test_poke_cooldown_not_consumed_when_dropped_for_budget(tmp_path):
    # A poke that doesn't fit the packet must NOT stamp the player's cooldown, or they'd be
    # wrongly skipped next hour. Force a tiny budget so the poke can never fit.
    bot, t = make_bot(str(tmp_path), personality_enabled=True, recap_enabled=True,
                      pokes_enabled=True, new_player_grace_slots=0, max_payload_bytes=60)
    eng = bot.engine
    eng.ambient_stats["!b"] = AmbientStats("!b", "Bob", correct=0, wrong_streak=4,
                                           first_seen_slot=0, answered=4, last_poked_slot=-1)
    q = Question("T", "e", "Q?", ["a", "b", "c", "d"], 0)
    eng.open_ambient(q, 100)
    eng.submit_ambient_answer("!a", "Ann", 0, 1.0)  # a winner so headline alone ~fills budget
    text = bot._build_recap_text(slot_index=101)
    assert text is not None and len(text.encode("utf-8")) <= 60
    # poke dropped (didn't fit) -> cooldown NOT stamped
    assert eng.ambient_stats["!b"].last_poked_slot == -1


def test_recap_no_winner_path(tmp_path):
    bot, t = make_bot(str(tmp_path), personality_enabled=True, recap_enabled=True)
    eng = bot.engine
    q = Question("Geo", "e", "Capital?", ["London", "Paris", "Rome", "Bonn"], 1)
    eng.open_ambient(q, 100)
    eng.submit_ambient_answer("!a", "Ann", 0, 1.0)  # wrong
    text = bot._build_recap_text(slot_index=101)
    assert text is not None
    assert "2️⃣ Paris" in text  # reveal the answer (keycap-prefixed, matches render)
    assert len(text.encode("utf-8")) <= bot.cfg.max_payload_bytes


def test_recap_first_fire_returns_none(tmp_path):
    bot, t = make_bot(str(tmp_path), personality_enabled=True, recap_enabled=True)
    # no open ambient question yet -> graceful skip
    assert bot._build_recap_text(slot_index=1) is None


def test_recap_disabled_when_personality_off(tmp_path):
    bot, t = make_bot(str(tmp_path), personality_enabled=False)
    eng = bot.engine
    q = Question("T", "e", "Q?", ["a", "b", "c", "d"], 0)
    eng.open_ambient(q, 100)
    eng.submit_ambient_answer("!a", "Ann", 0, 1.0)
    assert bot._build_recap_text(slot_index=101) is None


# ---------------- end-to-end: recap + question = exactly 2 packets ----------------

def test_recap_plus_question_exactly_two_packets(tmp_path):
    bot, t = make_bot(str(tmp_path), ambient_enabled=True, personality_enabled=True,
                      recap_enabled=True, pokes_enabled=False, ambient_minute_offset=37,
                      ambient_reminder_frequency=99)  # no reminder packet this run
    # pin the ambient pool to a single known-answer question (answer index 0 == "1️⃣")
    bot._questions = bot._ambient_questions = [Question("T", "e", "Q?", ["a", "b", "c", "d"], 0)]
    # FIRST fire (slot N): no previous question -> 1 packet (header+question packed)
    fire1 = _epoch_at_local_minute(37, hour=12)
    t.set_clock_ms(int(fire1 * 1000))
    bot.poll_once(now_s=fire1)
    first_count = len(t.sent)
    assert first_count == 1  # graceful first-run skip: only the question packet
    qpkt = bot.engine.ambient_packet_id
    assert qpkt is not None  # question registered for scoring

    # a player answers the ambient question correctly
    t.inject_reaction("!alice001", "1️⃣", reply_to=qpkt, channel=TRIVIA,
                      ts_ms=int(fire1 * 1000) + 5000)
    bot.poll_once(now_s=fire1 + 10)

    # SECOND fire (next hour): recap packet + question packet = exactly 2 new packets
    sent_before = len(t.sent)
    fire2 = _epoch_at_local_minute(37, hour=13)
    t.set_clock_ms(int(fire2 * 1000))
    bot.poll_once(now_s=fire2)
    new_packets = len(t.sent) - sent_before
    assert new_packets == 2, f"expected recap+question=2, got {new_packets}"
    # first new packet is the recap (mentions the winner Alice or a streak/✅), second is Q
    recap_msg = t.sent[sent_before].text
    assert "Alice" in recap_msg


def test_circuit_breaker_still_authoritative_with_personality(tmp_path):
    bot, t = make_bot(str(tmp_path), personality_enabled=True, max_sends_per_minute=3)
    sent = [bot._send(f"m{i}") for i in range(10)]
    assert len([s for s in sent if s is not None]) == 3
    assert len(t.sent) == 3


# ---------------- persistence of personality state ----------------

def test_ambient_stats_persist_across_restart(tmp_path):
    bot, t = make_bot(str(tmp_path), personality_enabled=True)
    bot.engine.ambient_stats["!a"] = AmbientStats("!a", "Ann", correct=4, correct_streak=4,
                                                  first_seen_slot=0, last_correct_slot=10)
    bot._persist()
    # new bot, same state path -> stats restored (running gag survives restart)
    bot2, t2 = make_bot(str(tmp_path), personality_enabled=True)
    assert "!a" in bot2.engine.ambient_stats
    s = bot2.engine.ambient_stats["!a"]
    assert s.correct == 4 and s.correct_streak == 4


# ---------------- pure-additive guarantee ----------------

def test_personality_off_no_ambient_scoring(tmp_path):
    # with personality off, ambient reactions are never scored (no open packet registered)
    bot, t = make_bot(str(tmp_path), ambient_enabled=True, personality_enabled=False,
                      ambient_minute_offset=37)
    fire = _epoch_at_local_minute(37)
    t.set_clock_ms(int(fire * 1000))
    bot.poll_once(now_s=fire)
    assert bot.engine.ambient_packet_id is None  # nothing registered for scoring
    assert bot.engine.ambient_stats == {}


def test_game_round_quip_with_personality_on(tmp_path):
    bot, t = make_bot(str(tmp_path), personality_enabled=True, question_window_s=10,
                      inter_question_gap_s=1, questions_per_game=1)
    # start a game, answer correctly, close it -> winner quip (not the plain host CORRECT)
    t.inject_text("!alice001", "!starttrivia", channel=TRIVIA, ts_ms=1000)
    t.set_clock_ms(1000)
    bot.poll_once(now_s=1.0)
    qpkt = bot.engine.current_packet_id
    assert qpkt is not None
    t.inject_reaction("!alice001", "1️⃣", reply_to=qpkt, channel=TRIVIA, ts_ms=2000)
    t.set_clock_ms(2000)
    bot.poll_once(now_s=2.0)
    # advance past the window to close the question
    t.set_clock_ms(20000)
    bot.poll_once(now_s=20.0)
    texts = " ".join(m.text for m in t.sent)
    assert "Alice" in texts  # winner named via the quip engine
