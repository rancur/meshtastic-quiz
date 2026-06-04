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
    assert "1️⃣ 3" in r and "2️⃣ 4" in r
    # v1.2.2: NO category tag in the rendered question.
    assert "[Sci]" not in r and "[" not in r
    assert q.answer_text() == "2️⃣ 4"


def test_render_has_no_category_tag():
    """v1.2.2 format spec: the question line carries no "[Category]" prefix."""
    q = Question("Pop", "easy", "In which series is Frodo?",
                 ["LOTR", "Potter", "Olympus", "Star Wars"], 0)
    r = q.render()
    assert r.startswith("In which series is Frodo?"), r
    assert "[Pop]" not in r and "[" not in r


def test_render_with_lead_emoji_inline():
    """Ambient teasers prepend a single standard emoji inline on the question line —
    no separate header packet, no category tag."""
    q = Question("Pop", "easy", "In which series is Frodo?",
                 ["LOTR", "Potter", "Olympus", "Star Wars"], 0)
    r = q.render(lead_emoji="🧠")
    # emoji + space + question, all on the first line
    first_line = r.split("\n", 1)[0]
    assert first_line == "🧠 In which series is Frodo?", first_line
    assert "Brain snack" not in r and "teaser" not in r.lower()


def test_render_options_are_single_inline_line():
    """Options render as ONE space-separated line: "1️⃣ a 2️⃣ b 3️⃣ c 4️⃣ d" — not one
    option per line."""
    q = Question("Pop", "easy", "Who?", ["Frodo", "Harry P", "Percy", "Luke"], 0)
    r = q.render()
    lines = r.split("\n")
    assert len(lines) == 2, f"expected question line + one options line, got {lines}"
    assert lines[1] == "1️⃣ Frodo 2️⃣ Harry P 3️⃣ Percy 4️⃣ Luke", lines[1]


def test_render_uses_keycap_emoji_prefixes():
    """Every option is prefixed with the keycap-number emoji (1️⃣2️⃣3️⃣4️⃣), not "N)"."""
    q = Question("Geo", "easy", "Capital of France?",
                 ["London", "Paris", "Berlin", "Rome"], 1)
    r = q.render()
    for kc, opt in zip(["1️⃣", "2️⃣", "3️⃣", "4️⃣"], q.options):
        assert f"{kc} {opt}" in r
    # the old numeric "N)" prefix must be gone
    assert "1)" not in r and "2)" not in r
    # recap/answer line is keycap-consistent too: "2️⃣ Paris" not "2) Paris"
    assert q.answer_text() == "2️⃣ Paris"


def test_typed_digit_answers_still_match():
    """Players may still type a bare digit "1".."4"; the keycap render must not break
    the typed-answer parsing path (digit -> 0-based option index)."""
    from meshquiz.bot import typed_to_option, emoji_to_option

    for digit, idx in [("1", 0), ("2", 1), ("3", 2), ("4", 3)]:
        assert typed_to_option(digit) == idx
    # and the keycap tapback maps to the same index as the rendered prefix
    for kc, idx in [("1️⃣", 0), ("2️⃣", 1), ("3️⃣", 2), ("4️⃣", 3)]:
        assert emoji_to_option(kc) == idx
