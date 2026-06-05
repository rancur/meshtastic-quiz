"""Difficulty-tier selection tests.

Covers the installer-selectable difficulty feature:
- `select_by_difficulty` filtering (easy / medium / med / hard / mixed),
- "medium" -> "med" aliasing,
- backward compatibility: no/blank/"mixed" QUIZ_DIFFICULTY == the whole bank,
- empty-tier fallback to the full bank (a missing tier must never brick the bot),
- Config validation of QUIZ_DIFFICULTY,
- the live bank actually carries a meaningful number of questions per tier,
- the TriviaBot narrows its engine bag to the requested tier.

All exercised over the in-memory MockTransport — no live mesh.
"""
import json
import os

import pytest

from meshquiz.config import VALID_DIFFICULTIES, Config
from meshquiz.questions import Question, load_questions, select_by_difficulty
from tests.mock_transport import MockTransport

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "meshquiz", "data", "questions.json")
TRIVIA = 2


def _mixed_bank():
    return [
        Question("Sci", "easy", "Easy Q1?", ["a", "b", "c", "d"], 0),
        Question("Sci", "easy", "Easy Q2?", ["a", "b", "c", "d"], 1),
        Question("Mesh", "med", "Med Q1?", ["a", "b", "c", "d"], 2),
        Question("Mesh", "med", "Med Q2?", ["a", "b", "c", "d"], 3),
        Question("Mesh", "med", "Med Q3?", ["a", "b", "c", "d"], 0),
        Question("Mesh", "hard", "Hard Q1?", ["a", "b", "c", "d"], 1),
    ]


# ---------------- select_by_difficulty ----------------

def test_select_easy_returns_only_easy():
    picked = select_by_difficulty(_mixed_bank(), "easy")
    assert {q.difficulty for q in picked} == {"easy"}
    assert len(picked) == 2


def test_select_hard_returns_only_hard():
    picked = select_by_difficulty(_mixed_bank(), "hard")
    assert {q.difficulty for q in picked} == {"hard"}
    assert len(picked) == 1


def test_medium_alias_maps_to_med_label():
    bank = _mixed_bank()
    via_alias = select_by_difficulty(bank, "medium")
    via_label = select_by_difficulty(bank, "med")
    assert {q.question for q in via_alias} == {q.question for q in via_label}
    assert len(via_alias) == 3


def test_mixed_returns_whole_bank():
    bank = _mixed_bank()
    assert len(select_by_difficulty(bank, "mixed")) == len(bank)


@pytest.mark.parametrize("legacy", ["", None, "all"])
def test_blank_or_legacy_is_whole_bank(legacy):
    """No difficulty set (legacy installs) draws from the entire bank — unchanged v1.x."""
    bank = _mixed_bank()
    assert len(select_by_difficulty(bank, legacy)) == len(bank)


def test_case_insensitive_tier():
    assert len(select_by_difficulty(_mixed_bank(), "HARD")) == 1
    assert len(select_by_difficulty(_mixed_bank(), "  Easy ")) == 2


def test_empty_tier_falls_back_to_full_bank():
    """A tier with zero questions must NOT yield an empty bag — fall back to the whole bank."""
    only_easy = [Question("Sci", "easy", "Q?", ["a", "b", "c", "d"], 0)]
    picked = select_by_difficulty(only_easy, "hard")
    assert len(picked) == len(only_easy)  # fell back


# ---------------- Config validation ----------------

def test_config_default_difficulty_is_mixed():
    cfg = Config(meshmonitor_token="x")
    assert cfg.quiz_difficulty == "mixed"


@pytest.mark.parametrize("tier", sorted(VALID_DIFFICULTIES))
def test_config_accepts_all_valid_tiers(tier):
    cfg = Config(meshmonitor_token="x", quiz_difficulty=tier)
    cfg.validate()  # must not raise


def test_config_rejects_unknown_difficulty():
    cfg = Config(meshmonitor_token="x", quiz_difficulty="impossible")
    with pytest.raises(ValueError):
        cfg.validate()


# ---------------- live bank coverage ----------------

def test_live_bank_has_enough_per_tier():
    """Each selectable tier should carry a meaningfully large set (spec target: 25+)."""
    qs = load_questions(BANK)
    for tier in ("easy", "medium", "hard"):
        picked = select_by_difficulty(qs, tier)
        assert len(picked) >= 25, f"tier {tier} only has {len(picked)} questions"


def test_live_bank_has_meshtastic_questions_in_hard():
    """The hard tier must include real Meshtastic-domain questions, not just trivia."""
    qs = load_questions(BANK)
    hard = select_by_difficulty(qs, "hard")
    mesh = [q for q in hard if q.category == "Mesh"]
    assert len(mesh) >= 10, f"expected Meshtastic depth in hard tier, got {len(mesh)}"


# ---------------- bot wiring ----------------

def test_bot_narrows_engine_bag_to_tier(tmp_path):
    from meshquiz.bot import TriviaBot
    cfg = Config(meshmonitor_token="x", trivia_channel_index=TRIVIA,
                 state_path=str(tmp_path / "state.json"), quiz_difficulty="hard")
    bot = TriviaBot(MockTransport(), cfg, questions=_mixed_bank())
    # the engine should only know about the hard-tier question(s)
    assert all(q.difficulty == "hard" for q in bot.engine._all_questions)
    assert len(bot.engine._all_questions) == 1


def test_bot_mixed_keeps_whole_bank(tmp_path):
    from meshquiz.bot import TriviaBot
    cfg = Config(meshmonitor_token="x", trivia_channel_index=TRIVIA,
                 state_path=str(tmp_path / "state.json"))  # default mixed
    bank = _mixed_bank()
    bot = TriviaBot(MockTransport(), cfg, questions=bank)
    assert len(bot.engine._all_questions) == len(bank)
