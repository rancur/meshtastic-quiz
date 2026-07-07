"""Proof tests for the 365-day ambient no-repeat system (v1.5.0).

The root-cause of "questions repeat too often" was that the 24/7 ambient track picked with
``random.choice`` — random WITH replacement, zero history — so the birthday paradox produced
collisions within hours on a few-hundred-question pool.

These tests exercise the REAL selection code (``TriviaBot._pick_ambient_question`` +
``_record_asked`` + persisted ``_ask_history``) — not a reimplementation — to prove:

  (a) NO premature repeat: simulated over a full year of hourly draws on the real bank, the
      same question never reappears until the ENTIRE pool has cycled (LRU max-spacing).
  (b) A pool sized >= draws/year yields LITERALLY zero repeats within 365 days.
  (c) History PERSISTS across a restart (a rebooted bot still excludes recent questions).
  (d) GRACEFUL fallback: an exhausted pool never crashes and never repeats a recent question.
"""
import os

from meshquiz.bot import TriviaBot
from meshquiz.config import Config
from meshquiz.questions import Question, load_questions, question_key, select_ambient_pool
from tests.mock_transport import MockTransport

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "meshquiz", "data", "questions.json")
HOUR_S = 3600.0
DAY_S = 86400.0


def _bot(tmpdir, pool, no_repeat_days=365):
    state_path = os.path.join(tmpdir, "state.json")
    cfg = Config(meshmonitor_token="x", trivia_channel_index=2, state_path=state_path,
                 ambient_no_repeat_days=no_repeat_days, bot_node_id="!bot00000")
    bot = TriviaBot(MockTransport(), cfg, questions=list(pool))
    bot._ambient_questions = list(pool)  # pin the ambient pool for a deterministic proof
    return bot


def _simulate(bot, draws, start_s=1_700_000_000.0, step_s=HOUR_S):
    """Draw ``draws`` ambient questions on an hourly grid using the REAL picker+recorder.

    Returns the list of question_keys drawn, in order.
    """
    out = []
    now = start_s
    for _ in range(draws):
        q = bot._pick_ambient_question(now)
        bot._record_asked(q, now)
        out.append(question_key(q))
        now += step_s
    return out


def _min_repeat_gap(keys):
    """Smallest gap (in draws) between two consecutive appearances of the same key."""
    last = {}
    gap = None
    for i, k in enumerate(keys):
        if k in last:
            g = i - last[k]
            gap = g if gap is None else min(gap, g)
        last[k] = i
    return gap  # None => no key ever repeated


# ---------------- (a) real bank: no premature repeat over a simulated year ----------------

def test_real_bank_no_premature_repeat_over_a_year(tmp_path):
    pool = select_ambient_pool(load_questions(BANK), "challenging")
    n = len(pool)
    assert n >= 300, f"ambient pool unexpectedly small: {n}"
    bot = _bot(str(tmp_path), pool)
    draws = 24 * 365  # a full year of hourly ambient fires = 8760
    keys = _simulate(bot, draws=draws)

    gap = _min_repeat_gap(keys)
    spacing_days = n / 24.0
    if n >= draws:
        # LITERAL 365-day no-repeat: the pool is deeper than a year of draws, so a full year
        # produces ZERO repeats.
        assert gap is None, f"pool={n} >= {draws} draws but a question repeated (gap={gap})"
        assert len(set(keys)) == draws, "a year of draws should be all-unique questions"
        print(f"\n[proof] ambient pool={n} >= {draws} yearly draws -> ZERO repeats in 365 days; "
              f"LITERAL 365-day no-repeat HOLDS (min spacing {spacing_days:.1f} days)")
    else:
        # Smaller pool: no premature repeat — every question spaced a full pool cycle apart.
        first_cycle = keys[:n]
        assert len(set(first_cycle)) == n, "first cycle repeated before exhausting the pool"
        assert gap is not None and gap >= n, (
            f"a question repeated after only {gap} draws; expected >= pool size {n}")
        print(f"\n[proof] ambient pool={n}; guaranteed min spacing between repeats="
              f"{gap} hours = {spacing_days:.1f} days at hourly cadence")


# ---------------- (b) a pool >= draws/year gives LITERALLY zero repeats in 365 days -------

def test_year_sized_pool_has_zero_repeats_in_365_days(tmp_path):
    draws_per_year = 24 * 365  # 8760 hourly fires
    pool = [Question("Syn", "hard", f"Synthetic question number {i}?",
                     ["a", "b", "c", "d"], i % 4) for i in range(draws_per_year + 240)]
    bot = _bot(str(tmp_path), pool)
    keys = _simulate(bot, draws=draws_per_year)
    assert len(set(keys)) == len(keys), "a year-sized pool must produce ZERO repeats"


# ---------------- (c) history persists across a restart ----------------------------------

def test_history_persists_across_restart(tmp_path):
    pool = select_ambient_pool(load_questions(BANK), "challenging")
    bot = _bot(str(tmp_path), pool)
    start = 1_700_000_000.0
    drawn = _simulate(bot, draws=50, start_s=start)
    bot._persist()  # write state.json (atomic)

    # brand-new bot instance reading the SAME state file (simulates a container restart)
    bot2 = _bot(str(tmp_path), pool)
    assert len(bot2._ask_history) == 50, "restart did not restore the no-repeat history"
    for k in drawn:
        assert k in bot2._ask_history, "a recently-asked question was lost across restart"

    # continue drawing right after the restart: none of the 50 recent questions come back
    # (they are all well inside the 365-day window).
    now = start + 51 * HOUR_S
    more = [question_key(bot2._pick_ambient_question(now + i * HOUR_S)) for i in range(30)]
    assert not (set(more) & set(drawn)), "post-restart draw repeated a pre-restart question"


# ---------------- (d) graceful fallback when the pool is exhausted ------------------------

def test_graceful_fallback_is_lru_not_a_recent_repeat(tmp_path):
    # Tiny pool so the window is guaranteed to exhaust; the picker must degrade to
    # least-recently-asked (max spacing) rather than crash or echo a recent question.
    pool = [Question("Tiny", "hard", f"Tiny q {i}?", ["a", "b", "c", "d"], i % 4)
            for i in range(10)]
    bot = _bot(str(tmp_path), pool, no_repeat_days=365)
    keys = _simulate(bot, draws=500)  # 50x the pool -> forced into fallback repeatedly

    # Never crashes, always returns a valid pool question.
    assert set(keys) <= {question_key(q) for q in pool}
    # Even in fallback, the same question never reappears sooner than a full pool cycle.
    gap = _min_repeat_gap(keys)
    assert gap is not None and gap >= len(pool), (
        f"fallback repeated after {gap} draws; expected >= {len(pool)} (LRU spacing)")
    # And every question keeps getting used (no starvation of any single question).
    assert len(set(keys)) == len(pool)
