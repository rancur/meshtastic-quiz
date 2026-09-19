"""Question bank loading, rendering, and byte-budget validation."""
from __future__ import annotations

import json
import os as _os
import re
from dataclasses import dataclass
from typing import List, Optional

# Rendered question layout (compact, one mesh packet):
#   "Question text\n1️⃣ opt 2️⃣ opt 3️⃣ opt 4️⃣ opt"
# or, with an optional leading emoji (ambient teasers pass one):
#   "🧠 Question text\n1️⃣ opt 2️⃣ opt 3️⃣ opt 4️⃣ opt"
# Players answer with a tapback emoji 1️⃣2️⃣3️⃣4️⃣ on this message, OR by typing the
# digit "1".."4". The keycap prefix makes the tapback-answer mapping visually obvious:
# the option's leading emoji is exactly the tapback to react with.
#
# NOTE: the question line carries NO "[Category]" tag and NO "Brain snack:" style header
# (removed in v1.2.2 — Will's format spec). Options are a single space-separated inline
# line; long options may wrap on the LoRa client but the SOURCE is one line.


def keycap(i: int) -> str:
    """Return the keycap-number emoji for a 1-based option position ``i`` (1->"1️⃣").

    Keycap emoji are ``<digit> U+FE0F U+20E3``. For positions 1..9 we build the single
    digit keycap; for 10+ (never expected — questions are 4-option) we degrade to the
    plain number followed by the combining keycap so rendering never crashes.
    """
    s = str(i)
    if len(s) == 1:
        return f"{s}️⃣"
    # 10+ has no single-glyph keycap; emit each digit's keycap concatenated.
    return "".join(f"{d}️⃣" for d in s)


@dataclass
class Question:
    category: str
    difficulty: str
    question: str
    options: List[str]
    answer: int  # index 0..3

    def __post_init__(self):
        if len(self.options) != 4:
            raise ValueError(f"question must have exactly 4 options: {self.question!r}")
        if not (0 <= self.answer < 4):
            raise ValueError(f"answer index out of range: {self.question!r}")

    def render(self, lead_emoji: Optional[str] = None) -> str:
        """Render the question packet.

        ``lead_emoji`` (e.g. "🧠") is an optional standard emoji prepended inline to the
        question line — used by ambient teasers so the message reads "🧠 In which series…"
        with no category tag. Options are always a single space-separated inline line.
        """
        opts = " ".join(f"{keycap(i+1)} {o}" for i, o in enumerate(self.options))
        head = f"{lead_emoji} {self.question}" if lead_emoji else self.question
        return f"{head}\n{opts}"

    def byte_len(self, lead_emoji: Optional[str] = None) -> int:
        return len(self.render(lead_emoji).encode("utf-8"))

    def answer_text(self) -> str:
        return f"{keycap(self.answer + 1)} {self.options[self.answer]}"


def load_questions(path: str) -> List[Question]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Question(**q) for q in raw]


# --- Math classification (ambient math-cap, v1.8.0) -------------------------------------
# The mass-generation pass (v1.6.0) tagged every arithmetic/number-theory/base-conversion
# question with the category "Math" — that category tag is the reliable, sole signal for
# "this is a drill-style math question," which is what the ambient math-cap down-weights.
# We match on the CATEGORY tag only (never the question text) so a legitimate non-math
# question that merely mentions a number (e.g. "Max channels you can configure (indices
# 0-7)?" in the Mesh category) is NEVER mis-classified as math. The set is lowercased and
# includes the aliases the generator could plausibly emit, so a future bank rebuild that
# labels math questions "arithmetic"/"number theory" is still caught without a code change.
MATH_CATEGORIES = frozenset({
    "math", "maths", "mathematics", "arithmetic",
    "number theory", "number-theory", "numbers",
})


def is_math(q: "Question") -> bool:
    """True iff ``q`` is a drill-style math question (by its CATEGORY tag, case-insensitive).

    Classification is intentionally tag-based (not text-based): the ambient math-cap must
    down-weight ONLY the generated arithmetic/number bank, never a real-trivia question that
    happens to contain a digit. See ``MATH_CATEGORIES``.
    """
    return (q.category or "").strip().lower() in MATH_CATEGORIES


def question_key(q: "Question") -> str:
    """Stable identity for a question, used as the no-repeat history key.

    We key on the normalized question TEXT (strip + lowercase) — the same key the bank's
    duplicate check uses (validate_bank) — so history survives option reordering / typo
    fixes and cannot collide across two distinct questions (duplicates are rejected at
    build time). This makes the persisted last-asked map robust to a bank rebuild: editing
    a question's options keeps its history; only changing the question text mints a new key
    (correct — it is effectively a new question).
    """
    return q.question.strip().lower()


# Map an operator-facing difficulty name to the difficulty label stored on each Question.
# "medium" is the friendly alias for the bank's historical "med" label.
_DIFFICULTY_ALIAS = {"medium": "med"}


def select_by_difficulty(questions: List["Question"], difficulty: str) -> List["Question"]:
    """Return the subset of ``questions`` matching the requested difficulty tier.

    ``difficulty`` is the operator-chosen tier (see config.QUIZ_DIFFICULTY):
      - "mixed"  -> the whole bank, untouched (legacy v1.x behavior; the default).
      - "easy" / "medium"/"med" / "hard" -> only that tier.

    "medium" and "med" are equivalent. The match is case-insensitive on the stored label.
    If a tier somehow has NO questions (e.g. a hand-trimmed bank), we fall back to the FULL
    bank rather than starting a game with an empty bag — a missing tier must never brick the
    bot. The caller logs the fallback.
    """
    tier = (difficulty or "mixed").strip().lower()
    if tier in ("mixed", "", "all"):
        return list(questions)
    tier = _DIFFICULTY_ALIAS.get(tier, tier)
    picked = [q for q in questions if (q.difficulty or "").strip().lower() == tier]
    return picked if picked else list(questions)


def select_ambient_pool(questions: List["Question"], mode: str) -> List["Question"]:
    """Pool the 24/7 AMBIENT track draws from — decoupled from the rapid-game difficulty tier.

    The rapid !starttrivia game uses QUIZ_DIFFICULTY (a competitive knob). The ambient
    channel is a different job: keep the channel warm with the WIDEST, HARDEST pool possible
    so the 365-day no-repeat window has the deepest bank to cycle through. ``mode`` is
    AMBIENT_DIFFICULTY:

      - "challenging" (DEFAULT) -> med + hard only. Skips easy warm-ups (Will's "make it
        harder"), and unions the two biggest tiers for the deepest no-repeat pool.
      - "mixed"/"all"          -> the entire bank (max depth, includes easy).
      - "easy"/"medium"/"med"/"hard" -> that single tier (same semantics as the game).

    Falls back to the full bank if a mode somehow yields an empty pool, so ambient can never
    brick on a mis-set knob (the caller logs the fallback).
    """
    m = (mode or "challenging").strip().lower()
    if m == "challenging":
        picked = [q for q in questions
                  if (q.difficulty or "").strip().lower() in ("med", "hard")]
        return picked if picked else list(questions)
    return select_by_difficulty(questions, m)


# Heaviest standard lead emoji that ambient may prepend (used for worst-case byte sizing).
# Ambient picks from AMBIENT_LEAD_EMOJI in host.py; we size against the largest UTF-8 one
# plus its separating space so the bank can never blow the 200B packet cap in any rotation.
WORST_LEAD_EMOJI = "🧠"  # 4 bytes (a single space adds 1) — represents the worst case here.


def validate_bank(questions: List[Question], max_bytes: int = 200) -> List[str]:
    """Return a list of human-readable problems. Empty list == all good.

    Byte budget is checked against the WORST case: a question rendered WITH a leading
    ambient emoji (the heaviest packet shape that ever goes over the air).
    """
    problems: List[str] = []
    seen = set()
    for i, q in enumerate(questions):
        bl = q.byte_len(WORST_LEAD_EMOJI)
        if bl > max_bytes:
            problems.append(f"#{i} [{q.category}] {bl}B > {max_bytes}B: {q.question!r}")
        if q.answer not in range(4):
            problems.append(f"#{i} bad answer index {q.answer}")
        if len(set(o.strip().lower() for o in q.options)) != 4:
            problems.append(f"#{i} duplicate options: {q.question!r}")
        key = q.question.strip().lower()
        if key in seen:
            problems.append(f"#{i} duplicate question: {q.question!r}")
        seen.add(key)
    return problems


# --- Single-defensible-answer gate (v1.12.0) ------------------------------------------
# WHY THIS EXISTS
# ---------------
# 2026-09-18 the ambient track served:
#     "Star Wars hero with lightsaber?  1️⃣ Han 2️⃣ Luke 3️⃣ Yoda 4️⃣ Leia"
# keyed to Luke. Luke, Yoda AND Leia all wield lightsabers in canon (and Han ignites one
# on Hoth), so three of the four options were defensible and everyone who answered 3 or 4
# was scored wrong by an arbitrary key.
#
# The general shape of that bug is the CATEGORY QUESTION: the stem names a SET
# ("Star Wars heroes with lightsabers", "cacti native to Arizona", "citrus fruits") and
# more than one option belongs to that set. What makes a question safe is a UNIQUENESS
# MARKER that pins exactly one member: a superlative ("largest"), an ordinal ("third from
# the Sun"), "only"/"first", an explicit negation ("which is NOT..."), a numeric answer, or
# a functional relation whose right-hand side is single-valued ("capital of France",
# "element with the symbol Fe", "who wrote X").
#
# WHAT IS AND IS NOT MECHANICAL
# -----------------------------
# No regex can know that Yoda owns a lightsaber — that is world knowledge. So the gate does
# NOT try to decide correctness. It decides SHAPE, which is mechanical and deterministic:
# a question that asks for set membership WITHOUT a uniqueness marker is a suspect, and
# every suspect must carry a recorded adjudication in single_answer_review.json or the
# build fails. That converts an unbounded semantic problem into a bounded, reviewed list,
# and — the point — a NEW question of this shape cannot enter the bank unreviewed. It is a
# gate, not an instruction: it fails the build, it does not merely advise.
#
# Deliberately NOT caught (documented limits, see DECISIONS.md):
#   * a question with a uniqueness marker whose marker is a LIE ("Largest planet?" keyed to
#     Mars) — that is a factual error, not an ambiguity shape;
#   * two options that name the same thing ("Chili" vs "Pepper" for paprika) where the stem
#     is not category-shaped;
#   * a category question whose set genuinely has one member (most of the registry) — those
#     are flagged and then cleared by review, which is the intended cost.


# A marker that pins the answer to exactly one member => NOT a category question.
_UNIQUENESS_MARKER = re.compile(r"""(?xi)
      \b(?:\w+est|most|least|only|first|last|main|primary|chief|sole|fewest)\b
    | \b(?:second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b
    | \bNOT\b
    | \bhow\s+(?:many|much|long)\b
    | \bwhat\s+year\b | \bwhich\s+year\b | \bin\s+what\s+year\b
    | \bsymbol\b | \bstands?\s+for\b | \babbrev | \breal\s+name\b
    | \bcapital\s+of\b | \bformula\b | \batomic\s+number\b | \broman\s+numeral\b
    | \bcomes?\s+(?:immediately\s+)?(?:after|before)\b
    | \bknown\s+as\b | \bcalled\b | \bnamed\b
    | \binvented\b | \bdiscovered\b | \bwrote\b | \bpainted\b | \bdirected\b
    | \bcomposer\s+of\b | \bauthor\s+of\b | \bco-?founded\b | \bfounded\b
    | ['"‘’“”]   # a quoted title/phrase anchors the answer
    | \d                              # a digit or identifier in the stem anchors it
""")

# Stems that ask "which member of this set?" — the shape that can hold several answers.
_CATEGORY_SHAPES = (
    ("which-is-a", re.compile(r"^which\s+(?:one\s+)?(?:of\s+(?:these|the\s+following)\s+)?is\s+(?:a|an)\b", re.I)),
    ("which-of-these", re.compile(r"^which\s+of\s+(?:these|the\s+following)\b", re.I)),
    ("which-*", re.compile(r"^which\b", re.I)),
    ("X-with-Y", re.compile(r"\bwith\s+(?:a\s|an\s|the\s)?[\w\- ]{2,20}\?$", re.I)),
    ("X-that-Y", re.compile(r"^[\w' \-]{2,40}\s+that\s+[\w' \-]{2,40}\?$", re.I)),
    ("X-is-a-Y", re.compile(r"\bis\s+(?:a|an)\s+[\w\- ]{2,25}\?$", re.I)),
)

_NUMERIC_OPTION = re.compile(r"^[-+]?[\d.,/%]+\s*\w{0,4}$")

# Where the recorded adjudications live (question text -> one-line justification).
SINGLE_ANSWER_REVIEW_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                          "data", "single_answer_review.json")


def category_question_shape(q: "Question") -> Optional[str]:
    """Return the name of the category-question shape ``q`` matches, else ``None``.

    Returns ``None`` when the options are all numeric (a numeric answer is a value, not a
    set membership) or when the stem carries a uniqueness marker.
    """
    text = (q.question or "").strip()
    if all(_NUMERIC_OPTION.match(o.strip()) for o in q.options):
        return None
    if _UNIQUENESS_MARKER.search(text):
        return None
    for name, pattern in _CATEGORY_SHAPES:
        if pattern.search(text):
            return name
    return None


def is_category_question(q: "Question") -> bool:
    """True iff ``q`` asks for membership of a set with no uniqueness marker to pin it."""
    return category_question_shape(q) is not None


def load_single_answer_review(path: Optional[str] = None) -> dict:
    """Load the recorded adjudications: ``{normalized question text: justification}``.

    A missing file is an EMPTY registry, not a pass — every category question then fails
    the gate. Fail closed: a lost registry must break the build, never silently allow.
    """
    path = path or SINGLE_ANSWER_REVIEW_PATH
    if not _os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {k.strip().lower(): v for k, v in (raw.get("reviewed") or {}).items()}


def validate_single_answer(questions: List["Question"], reviewed: Optional[dict] = None) -> List[str]:
    """Return human-readable problems. Empty list == every category question is adjudicated.

    Two failure modes, both build-breaking:
      * an UNREVIEWED category question — someone added a set-membership question and nobody
        checked whether more than one option belongs to the set;
      * a STALE registry entry — a justification for a question no longer in the bank, which
        would otherwise let the file rot into a rubber stamp.
    """
    reviewed = load_single_answer_review() if reviewed is None else {
        k.strip().lower(): v for k, v in reviewed.items()
    }
    problems: List[str] = []
    present = set()
    for i, q in enumerate(questions):
        shape = category_question_shape(q)
        if shape is None:
            continue
        key = question_key(q)
        present.add(key)
        entry = reviewed.get(key)
        if not entry or not str(entry).strip():
            problems.append(
                f"#{i} [{q.category}] UNREVIEWED category question ({shape}): {q.question!r} "
                f"{q.options} -> keyed {q.options[q.answer]!r}. Confirm exactly ONE option "
                f"belongs to the set the question names, then record why in "
                f"meshquiz/data/single_answer_review.json."
            )
    for key in sorted(set(reviewed) - present):
        problems.append(
            f"stale review entry (no such category question in the bank): {key!r} — "
            f"remove it from meshquiz/data/single_answer_review.json"
        )
    return problems
