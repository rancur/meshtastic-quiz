"""Proof tests for the GAME math-cap (v1.9.0).

Twin of the v1.8.0 ambient math-cap, for the competitive !starttrivia game. Root cause of
"the trivia is mainly math now": the v1.6.0 mass-generation grew the bank to ~9.2k questions
(82.5% Math) to clear the 365-day ambient no-repeat, and the game drew from a PLAIN shuffle
of the whole bank — so a 12-question game was ~10 math questions.

The fix caps the math share of each game's draw bag via ``GAME_MATH_MAX_PCT`` (default 18):
the bag keeps every non-math question and only enough randomly-chosen math to hit the share,
then shuffles. Math is never deleted — pure selection weighting, reversible via the env knob.

These tests exercise the REAL engine bag builder (not a reimplementation) to prove:
  (a) on the real bank, the SERVED game mix tracks the knob (~18%), not the ~83% bank ratio;
  (b) knob=0 serves ZERO math; knob=100 disables the cap (uniform, ~bank ratio);
  (c) a degenerate all-math or all-non-math tier never starves the bag.
"""
import os
import random

from meshquiz.config import Config
from meshquiz.engine import GameEngine
from meshquiz.questions import Question, is_math, load_questions

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "meshquiz", "data", "questions.json")


def _cfg(math_pct, **over):
    cfg = Config(meshmonitor_token="x", game_math_max_pct=math_pct)
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def _served_math_share(bank, math_pct, games=200, per_game=12, seed=0):
    """Play many games; return the math fraction across every question actually drawn."""
    cfg = _cfg(math_pct, questions_per_game=per_game)
    eng = GameEngine(cfg, bank, rng=random.Random(seed))
    math_seen = total = 0
    for _ in range(games):
        bag = eng._build_capped_bag()
        drawn = bag[-per_game:]  # a game pops from the top (end) of the bag
        math_seen += sum(1 for q in drawn if is_math(q))
        total += len(drawn)
    return math_seen / total


# ---------------- (a) served game mix tracks the knob, not the bank ratio ----------------

def test_served_game_math_share_matches_knob_on_real_bank():
    bank = load_questions(BANK)
    bank_math_frac = sum(1 for q in bank if is_math(q)) / len(bank)
    assert bank_math_frac > 0.7, f"expected a math-heavy bank, got {bank_math_frac:.2f}"

    share = _served_math_share(bank, math_pct=18)
    # Should land near 18% (sampling noise), and NOWHERE near the ~83% bank ratio.
    assert 0.13 <= share <= 0.23, f"served game math share {share:.3f} not ~0.18"


def test_knob_zero_serves_no_math():
    bank = load_questions(BANK)
    assert _served_math_share(bank, math_pct=0) == 0.0


def test_knob_100_disables_cap_tracks_bank_ratio():
    bank = load_questions(BANK)
    bank_math_frac = sum(1 for q in bank if is_math(q)) / len(bank)
    share = _served_math_share(bank, math_pct=100)
    assert abs(share - bank_math_frac) < 0.06, (
        f"uncapped served share {share:.3f} should track bank {bank_math_frac:.3f}")


# ---------------- (b) degenerate tiers never starve the bag ------------------------------

def test_all_math_tier_degrades_gracefully():
    only_math = [Question("Math", "hard", f"{i}+{i}?", ["a", "b", "c", "d"], i % 4)
                 for i in range(30)]
    cfg = _cfg(18, questions_per_game=12)
    eng = GameEngine(cfg, only_math, rng=random.Random(0))
    bag = eng._build_capped_bag()
    assert len(bag) == 30, "all-math tier must not be starved by the cap"


def test_all_nonmath_tier_unaffected():
    only_trivia = [Question("Geography", "hard", f"Capital {i}?", ["a", "b", "c", "d"], i % 4)
                   for i in range(30)]
    cfg = _cfg(18, questions_per_game=12)
    eng = GameEngine(cfg, only_trivia, rng=random.Random(0))
    bag = eng._build_capped_bag()
    assert len(bag) == 30 and not any(is_math(q) for q in bag)
