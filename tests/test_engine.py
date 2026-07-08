"""Engine unit tests: scoring, dedupe, timers, anti-runup, idempotent start, leaderboard."""
import pytest

from meshquiz.config import Config
from meshquiz.engine import GameEngine, Phase, SendText, StartQuestion
from meshquiz.questions import Question


def make_cfg(**over):
    cfg = Config(meshmonitor_token="x")
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def make_questions(n=20):
    qs = []
    for i in range(n):
        # answer index cycles; options unique
        qs.append(Question("Test", "easy", f"Q{i}?",
                           [f"a{i}", f"b{i}", f"c{i}", f"d{i}"], i % 4))
    return qs


def start_game(cfg=None, qs=None, seed=0):
    cfg = cfg or make_cfg(questions_per_game=5, question_window_s=90,
                          inter_question_gap_s=5, runup_max_low_rounds=3, runup_min_players=2)
    qs = qs or make_questions()
    import random
    eng = GameEngine(cfg, qs, rng=random.Random(seed))
    actions = eng.start(now_s=0.0)
    # first action is GAME_START text, last should be a StartQuestion
    sq = [a for a in actions if isinstance(a, StartQuestion)]
    assert sq, "start should begin a question"
    eng.on_question_sent(packet_id=111)
    return eng


def test_idempotent_start():
    eng = start_game()
    pkt_before = eng.current_packet_id
    # a second start while running should NOT begin a new question
    actions = eng.start(now_s=1.0)
    assert all(isinstance(a, SendText) for a in actions)
    assert not any(isinstance(a, StartQuestion) for a in actions)
    assert eng.current_packet_id == pkt_before


def test_correct_answer_scores_base_plus_speed_plus_first():
    cfg = make_cfg(questions_per_game=5, question_window_s=90, base_points=10,
                   max_speed_bonus=5, first_correct_bonus=3)
    eng = start_game(cfg)
    q = eng._current
    # answer immediately at t=0 -> full speed bonus 5, +first-correct 3 = 18
    eng.submit_answer("!aaa", "Alice", q.answer, ts_s=0.0)
    eng.tick(now_s=90.0)  # close question
    p = eng.players["!aaa"]
    assert p.score == 10 + 5 + 3


def test_speed_bonus_decays():
    cfg = make_cfg(questions_per_game=5, question_window_s=90, base_points=10,
                   max_speed_bonus=5, first_correct_bonus=0)
    eng = start_game(cfg)
    q = eng._current
    # answer at the very end -> ~0 speed bonus
    eng.submit_answer("!aaa", "Alice", q.answer, ts_s=89.9)
    eng.tick(now_s=90.0)
    assert eng.players["!aaa"].score == 10  # base only


def test_wrong_answer_no_points():
    eng = start_game()
    q = eng._current
    wrong = (q.answer + 1) % 4
    eng.submit_answer("!bbb", "Bob", wrong, ts_s=1.0)
    eng.tick(now_s=90.0)
    assert eng.players["!bbb"].score == 0


def test_dedupe_first_reaction_counts():
    eng = start_game()
    q = eng._current
    wrong = (q.answer + 1) % 4
    # first answer wrong, then changes to correct before timeout -> first (wrong) stands
    eng.submit_answer("!ccc", "Cara", wrong, ts_s=1.0)
    eng.submit_answer("!ccc", "Cara", q.answer, ts_s=2.0)
    eng.tick(now_s=90.0)
    assert eng.players["!ccc"].score == 0


def test_late_answer_ignored():
    eng = start_game()
    q = eng._current
    eng.submit_answer("!ddd", "Dan", q.answer, ts_s=200.0)  # after deadline 90
    eng.tick(now_s=90.0)
    assert "!ddd" not in eng.players or eng.players["!ddd"].score == 0


def test_first_correct_bonus_only_first():
    cfg = make_cfg(questions_per_game=5, question_window_s=90, base_points=10,
                   max_speed_bonus=0, first_correct_bonus=3)
    eng = start_game(cfg)
    q = eng._current
    eng.submit_answer("!a", "A", q.answer, ts_s=5.0)
    eng.submit_answer("!b", "B", q.answer, ts_s=6.0)
    eng.tick(now_s=90.0)
    assert eng.players["!a"].score == 13   # base + first-correct
    assert eng.players["!b"].score == 10   # base only


def test_timer_does_not_close_early():
    eng = start_game()
    assert eng.tick(now_s=10.0) == []     # still within window
    assert eng.phase == Phase.ASKING


def test_between_then_next_question():
    cfg = make_cfg(questions_per_game=5, question_window_s=90, inter_question_gap_s=5)
    eng = start_game(cfg)
    eng.tick(now_s=90.0)            # close q1 -> BETWEEN
    assert eng.phase == Phase.BETWEEN
    actions = eng.tick(now_s=95.0)  # gap elapsed -> next question
    assert any(isinstance(a, StartQuestion) for a in actions)
    assert eng.phase == Phase.ASKING


def test_game_ends_after_n_questions():
    cfg = make_cfg(questions_per_game=2, question_window_s=10, inter_question_gap_s=1)
    eng = start_game(cfg)
    eng.on_question_sent(1)
    eng.submit_answer("!a", "A", eng._current.answer, ts_s=1.0)
    eng.submit_answer("!b", "B", eng._current.answer, ts_s=1.0)
    eng.tick(now_s=10.0)            # close q1 (2 players -> not low)
    eng.tick(now_s=11.0)            # next q2
    eng.on_question_sent(2)
    eng.submit_answer("!a", "A", eng._current.answer, ts_s=12.0)
    eng.submit_answer("!b", "B", eng._current.answer, ts_s=12.0)
    actions = eng.tick(now_s=21.0)  # close q2 -> game should end
    assert eng.phase == Phase.IDLE
    # stop emits leaderboard text
    assert any(isinstance(a, SendText) and "LEADERBOARD" in a.text for a in actions)


def test_anti_runup_stops_after_low_streak():
    cfg = make_cfg(questions_per_game=10, question_window_s=10, inter_question_gap_s=1,
                   runup_min_players=2, runup_max_low_rounds=3)
    eng = start_game(cfg)
    t = 0
    pkt = 1
    for rnd in range(3):
        eng.on_question_sent(pkt); pkt += 1
        # only 1 player answers each round -> distinct (1) <= 2 -> low round
        eng.submit_answer("!solo", "Solo", eng._current.answer, ts_s=t + 1)
        actions = eng.tick(now_s=t + 10)  # close
        t += 11
        if rnd < 2:
            eng.tick(now_s=t)  # advance to next q
    assert eng.phase == Phase.IDLE  # auto-stopped on 3rd low round
    assert any(isinstance(a, SendText) and "more than 1" in a.text or "needs a crowd" in a.text
               for a in actions)


def test_anti_runup_resets_on_good_round():
    cfg = make_cfg(questions_per_game=10, question_window_s=10, inter_question_gap_s=1,
                   runup_min_players=2, runup_max_low_rounds=3)
    eng = start_game(cfg)
    # 2 low rounds (1 player each)
    t = 0; pkt = 1
    for _ in range(2):
        eng.on_question_sent(pkt); pkt += 1
        eng.submit_answer("!solo", "Solo", eng._current.answer, ts_s=t + 1)
        eng.tick(now_s=t + 10); t += 11
        eng.tick(now_s=t)
    # now a healthy round: 3 players -> resets streak
    eng.on_question_sent(pkt); pkt += 1
    for n in ("!x", "!y", "!z"):
        eng.submit_answer(n, n, eng._current.answer, ts_s=t + 1)
    eng.tick(now_s=t + 10); t += 11
    assert eng.phase != Phase.IDLE   # not stopped
    assert eng._low_round_streak == 0


def test_leaderboard_sorting_and_ties():
    cfg = make_cfg(questions_per_game=5, question_window_s=90, base_points=10,
                   max_speed_bonus=0, first_correct_bonus=0)
    eng = start_game(cfg)
    q = eng._current
    eng.submit_answer("!a", "Alice", q.answer, ts_s=5.0)
    eng.submit_answer("!b", "Bob", q.answer, ts_s=3.0)   # earlier
    eng.tick(now_s=90.0)
    board = eng.leaderboard()
    # equal scores (10 each) -> earlier reacher (Bob) ranks higher
    assert board[0].name == "Bob"
    assert board[1].name == "Alice"


def test_leaderboard_text_compact():
    eng = start_game()
    txt = eng.leaderboard_text()
    assert "LEADERBOARD" in txt or "No scores" in txt


def test_submit_ignored_when_idle():
    cfg = make_cfg(questions_per_game=5)
    qs = make_questions()
    import random
    eng = GameEngine(cfg, qs, rng=random.Random(0))
    eng.submit_answer("!a", "A", 0, ts_s=1.0)  # not running
    assert eng.players == {}


def test_stop_when_idle_noop():
    cfg = make_cfg()
    import random
    eng = GameEngine(cfg, make_questions(), rng=random.Random(0))
    assert eng.stop(now_s=1.0) == []


def test_wrong_answer_gets_immediate_ack():
    from meshquiz import host
    eng = start_game()
    q = eng._current
    wrong = (q.answer + 1) % 4
    actions = eng.submit_answer("!bbb", "Bob", wrong, ts_s=1.0)
    assert len(actions) == 1 and isinstance(actions[0], SendText)
    txt = actions[0].text
    assert "Bob" in txt
    # never leaks the correct answer text
    assert q.answer_text() not in txt
    assert q.options[q.answer] not in txt
    # it's one of the WRONG bank lines
    assert any(tmpl.format(name="Bob") == txt for tmpl in host.WRONG)


def test_correct_answer_is_silent_immediately():
    eng = start_game()
    q = eng._current
    actions = eng.submit_answer("!aaa", "Alice", q.answer, ts_s=1.0)
    assert actions == []  # correct stays silent until reveal (no leak)


def test_wrong_ack_only_first_guess_per_user():
    # first-answer lock means a single user can NEVER spam wrong-acks
    eng = start_game()
    q = eng._current
    wrong = (q.answer + 1) % 4
    other_wrong = (q.answer + 2) % 4
    first = eng.submit_answer("!bbb", "Bob", wrong, ts_s=1.0)
    assert len(first) == 1  # acked once
    second = eng.submit_answer("!bbb", "Bob", other_wrong, ts_s=2.0)
    assert second == []  # locked out entirely — no second ack


def test_wrong_ack_can_be_disabled():
    cfg = make_cfg(questions_per_game=5, question_window_s=90, wrong_answer_ack=False)
    eng = start_game(cfg)
    q = eng._current
    wrong = (q.answer + 1) % 4
    assert eng.submit_answer("!bbb", "Bob", wrong, ts_s=1.0) == []


def test_wrong_ack_late_or_idle_returns_nothing():
    eng = start_game()
    q = eng._current
    wrong = (q.answer + 1) % 4
    assert eng.submit_answer("!d", "Dan", wrong, ts_s=200.0) == []  # after deadline
    cfg = make_cfg()
    import random
    idle = GameEngine(cfg, make_questions(), rng=random.Random(0))
    assert idle.submit_answer("!x", "X", 0, ts_s=1.0) == []  # not running


def test_no_repeat_within_session():
    cfg = make_cfg(questions_per_game=20, question_window_s=5, inter_question_gap_s=1)
    qs = make_questions(20)
    import random
    eng = GameEngine(cfg, qs, rng=random.Random(1))
    eng.start(now_s=0.0)
    seen = [eng._current.question]
    t = 0; pkt = 1
    eng.on_question_sent(pkt)
    while eng.running and eng._current is not None:
        # two players keep it alive
        eng.submit_answer("!a", "A", eng._current.answer, ts_s=t + 1)
        eng.submit_answer("!b", "B", eng._current.answer, ts_s=t + 1)
        eng.tick(now_s=t + 5); t += 6
        eng.tick(now_s=t)
        if eng.running and eng._current is not None:
            seen.append(eng._current.question)
            pkt += 1; eng.on_question_sent(pkt)
    assert len(seen) == len(set(seen)), "questions repeated within a session"
    assert len(seen) == cfg.questions_per_game
