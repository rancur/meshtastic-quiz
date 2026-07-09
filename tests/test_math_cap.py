"""Proof tests for the AMBIENT math-cap (v1.8.0).

Root cause of "the trivia is mostly math now": the v1.6.0 mass-generation grew the bank to
~9.2k questions to clear a literal 365-day no-repeat, but MATH was the only category that
scaled to thousands — so the ambient (med+hard) pool ended up ~83% Math. Served hourly, the
24/7 channel FELT like a math drill.

The fix is WEIGHTED SELECTION in the real ambient picker (``TriviaBot._pick_ambient_question``):
each fire rolls ``AMBIENT_MATH_MAX_PCT`` to decide math-vs-real-trivia, then honors the
no-repeat window within the chosen bucket. Math is never deleted — pure selection weighting,
fully reversible via the env knob.

These tests exercise the REAL picker + recorder (not a reimplementation) to prove:
  (a) the SERVED math share tracks AMBIENT_MATH_MAX_PCT (default ~18%), not the ~83% bank ratio;
  (b) knob=0 serves ZERO math; knob=100 disables the cap (uniform, ~bank ratio);
  (c) the math classifier is tag-based and never mis-flags a numeric non-math question;
  (d) no-repeat still holds per bucket — non-math window shrinks (expected) but never repeats
      sooner than a full non-math cycle; math effectively never repeats.
"""
import os

from meshquiz.bot import TriviaBot
from meshquiz.config import Config
from meshquiz.questions import (
    Question,
    is_math,
    load_questions,
    question_key,
    select_ambient_pool,
)
from tests.mock_transport import MockTransport

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "meshquiz", "data", "questions.json")
HOUR_S = 3600.0


def _bot(tmpdir, pool, math_pct=18, no_repeat_days=365):
    state_path = os.path.join(tmpdir, "state.json")
    cfg = Config(meshmonitor_token="x", trivia_channel_index=2, state_path=state_path,
                 ambient_no_repeat_days=no_repeat_days, bot_node_id="!bot00000",
                 ambient_math_max_pct=math_pct)
    bot = TriviaBot(MockTransport(), cfg, questions=list(pool))
    bot._ambient_questions = list(pool)  # pin the ambient pool for a deterministic proof
    return bot


def _simulate(bot, draws, start_s=1_700_000_000.0, step_s=HOUR_S):
    out = []
    now = start_s
    for _ in range(draws):
        q = bot._pick_ambient_question(now)
        bot._record_asked(q, now)
        out.append(q)
        now += step_s
    return out


def _min_repeat_gap(keys):
    last, gap = {}, None
    for i, k in enumerate(keys):
        if k in last:
            g = i - last[k]
            gap = g if gap is None else min(gap, g)
        last[k] = i
    return gap


# ---------------- (a) served math share tracks the knob, not the bank ratio --------------

def test_served_math_share_matches_knob_on_real_bank(tmp_path):
    pool = select_ambient_pool(load_questions(BANK), "challenging")
    bank_math_frac = sum(1 for q in pool if is_math(q)) / len(pool)
    assert bank_math_frac > 0.7, f"expected a math-heavy bank, got {bank_math_frac:.2f}"

    bot = _bot(str(tmp_path), pool, math_pct=18)
    # Simulate well within the non-math no-repeat window (steady state, no forced overflow).
    drawn = _simulate(bot, draws=1000)
    math_share = sum(1 for q in drawn if is_math(q)) / len(drawn)
    # Should land near 18% (binomial noise on 1000 draws), and NOWHERE near the ~83% bank ratio.
    assert 0.13 <= math_share <= 0.23, f"served math share {math_share:.3f} not ~0.18"
    print(f"\n[proof] bank is {bank_math_frac*100:.0f}% math but served mix is "
          f"{math_share*100:.1f}% math / {(1-math_share)*100:.1f}% real trivia (knob=18)")


def test_knob_zero_serves_no_math(tmp_path):
    pool = select_ambient_pool(load_questions(BANK), "challenging")
    bot = _bot(str(tmp_path), pool, math_pct=0)
    drawn = _simulate(bot, draws=500)
    assert all(not is_math(q) for q in drawn), "knob=0 must never serve a math question"


def test_knob_100_disables_cap_uniform_bank_ratio(tmp_path):
    pool = select_ambient_pool(load_questions(BANK), "challenging")
    bank_math_frac = sum(1 for q in pool if is_math(q)) / len(pool)
    bot = _bot(str(tmp_path), pool, math_pct=100)
    drawn = _simulate(bot, draws=1500)
    math_share = sum(1 for q in drawn if is_math(q)) / len(drawn)
    # Uncapped => uniform selection => served share tracks the bank ratio (~0.83).
    assert abs(math_share - bank_math_frac) < 0.06, (
        f"uncapped served share {math_share:.3f} should track bank {bank_math_frac:.3f}")


# ---------------- (b) classifier is tag-based and never mis-flags numeric trivia ---------

def test_classifier_is_tag_based_not_text_based():
    numeric_but_not_math = Question(
        "Mesh", "hard", "Max channels you can configure (indices 0-7)?",
        ["6", "7", "8", "9"], 2)
    assert not is_math(numeric_but_not_math)
    assert is_math(Question("Math", "hard", "What is 14 × 45?", ["620", "630", "640", "650"], 1))
    # alias tags a future rebuild might emit are still caught
    assert is_math(Question("Arithmetic", "hard", "2+2?", ["3", "4", "5", "6"], 1))
    assert is_math(Question("number theory", "hard", "Is 7 prime?", ["y", "n", "?", "!"], 0))


# ---------------- (c) no-repeat holds per bucket (non-math window shrinks, math ~never) ---

def test_non_math_no_repeat_holds_per_bucket_cycle(tmp_path):
    # Small synthetic pool: 20 non-math + 200 math, knob=18. Non-math is served ~82%, so it
    # cycles fast; but it must still never repeat sooner than a full non-math cycle (20).
    pool = [Question("Geography", "hard", f"Real trivia {i}?", ["a", "b", "c", "d"], i % 4)
            for i in range(20)]
    pool += [Question("Math", "hard", f"What is {i}+{i}?", ["a", "b", "c", "d"], i % 4)
             for i in range(200)]
    bot = _bot(str(tmp_path), pool, math_pct=18, no_repeat_days=365)
    drawn = _simulate(bot, draws=600)

    nonmath_keys = [question_key(q) for q in drawn if not is_math(q)]
    math_keys = [question_key(q) for q in drawn if is_math(q)]
    # non-math cycles (repeats) but never sooner than a full 20-question cycle
    nm_gap = _min_repeat_gap(nonmath_keys)
    assert nm_gap is None or nm_gap >= 20, f"non-math repeated after {nm_gap} (< 20-cycle)"
    # math served rarely -> within 600 draws it should not have exhausted its 200-pool window
    m_gap = _min_repeat_gap(math_keys)
    assert m_gap is None, f"math repeated (gap={m_gap}) — should be effectively never here"
    # and the served mix is trivia-dominant
    share = len(math_keys) / len(drawn)
    assert 0.10 <= share <= 0.26, f"served math share {share:.3f} off target"
