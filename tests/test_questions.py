"""Question bank integrity + byte-budget tests."""
import json
import os

from meshquiz.questions import Question, load_questions, validate_bank

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "meshquiz", "data", "questions.json")


def test_bank_loads():
    qs = load_questions(BANK)
    assert len(qs) >= 200, f"expected a large bank, got {len(qs)}"


def test_every_question_fits_byte_budget():
    qs = load_questions(BANK)
    problems = validate_bank(qs, max_bytes=200)
    assert problems == [], "byte/validation problems:\n" + "\n".join(problems)


def test_every_answer_index_valid():
    qs = load_questions(BANK)
    for q in qs:
        assert 0 <= q.answer < 4
        assert len(q.options) == 4


def test_categories_diverse():
    qs = load_questions(BANK)
    cats = {q.category for q in qs}
    assert len(cats) >= 8, f"want broad categories, got {cats}"


def test_no_duplicate_questions():
    qs = load_questions(BANK)
    texts = [q.question.strip().lower() for q in qs]
    assert len(texts) == len(set(texts)), "duplicate questions present"


def test_question_requires_four_options():
    import pytest
    with pytest.raises(ValueError):
        Question("X", "easy", "q?", ["a", "b", "c"], 0)


def test_question_answer_bounds():
    import pytest
    with pytest.raises(ValueError):
        Question("X", "easy", "q?", ["a", "b", "c", "d"], 9)


def test_render_contains_options():
    q = Question("Sci", "easy", "What is 2+2?", ["3", "4", "5", "6"], 1)
    r = q.render()
    assert "1) 3" in r and "2) 4" in r and "[Sci]" in r
    assert q.answer_text() == "2) 4"
