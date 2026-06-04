"""Question bank loading, rendering, and byte-budget validation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

# Rendered question layout (compact, one mesh packet):
#   "[Category] Question text\n1️⃣ opt 2️⃣ opt 3️⃣ opt 4️⃣ opt"
# Players answer with a tapback emoji 1️⃣2️⃣3️⃣4️⃣ on this message, OR by typing the
# digit "1".."4". The keycap prefix makes the tapback-answer mapping visually obvious:
# the option's leading emoji is exactly the tapback to react with.


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

    def render(self) -> str:
        opts = " ".join(f"{keycap(i+1)} {o}" for i, o in enumerate(self.options))
        return f"[{self.category}] {self.question}\n{opts}"

    def byte_len(self) -> int:
        return len(self.render().encode("utf-8"))

    def answer_text(self) -> str:
        return f"{keycap(self.answer + 1)} {self.options[self.answer]}"


def load_questions(path: str) -> List[Question]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Question(**q) for q in raw]


def validate_bank(questions: List[Question], max_bytes: int = 200) -> List[str]:
    """Return a list of human-readable problems. Empty list == all good."""
    problems: List[str] = []
    seen = set()
    for i, q in enumerate(questions):
        bl = q.byte_len()
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
