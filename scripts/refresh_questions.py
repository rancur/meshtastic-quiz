#!/usr/bin/env python3
"""Monthly question-bank refresh entry point.

The bank is authored in ``build_questions.py``. The intended monthly cadence is:

  1. Extend / rotate the QUESTIONS list in ``build_questions.py`` (add a new month's
     batch; optionally retire stale ones).
  2. Run this script. It rebuilds ``meshquiz/data/questions.json`` and re-validates that
     every rendered question fits the mesh byte budget. It exits non-zero on any problem,
     so it is safe to wire into CI or a cron job.

This indirection exists so automated refreshers (cron) call a stable entry point even if
the authoring mechanism changes (e.g. a future LLM-backed generator that appends to
``build_questions.py`` or writes JSON directly).

Leaderboard semantics on refresh: the question bank and the leaderboard are independent.
Refreshing questions does NOT reset the leaderboard. The leaderboard resets per game
(each !starttrivia starts fresh) — see DECISIONS.md.
"""
import runpy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    # delegate to the authoritative builder (which validates + writes the JSON)
    sys.argv = [os.path.join(HERE, "build_questions.py")]
    runpy.run_path(os.path.join(HERE, "build_questions.py"), run_name="__main__")
