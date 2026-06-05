"""Question bank loading, rendering, and byte-budget validation."""
from __future__ import annotations

import json
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
