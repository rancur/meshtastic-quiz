"""Question bank loading, rendering, and byte-budget validation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

# Rendered question layout (compact, one mesh packet):
#   "[Category] Question text\n1) opt 2) opt 3) opt 4) opt"
# Players answer with a tapback emoji 1️⃣2️⃣3️⃣4️⃣ on this message.


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
        opts = " ".join(f"{i+1}) {o}" for i, o in enumerate(self.options))
        return f"[{self.category}] {self.question}\n{opts}"

    def byte_len(self) -> int:
        return len(self.render().encode("utf-8"))

    def answer_text(self) -> str:
        return f"{self.answer + 1}) {self.options[self.answer]}"


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
