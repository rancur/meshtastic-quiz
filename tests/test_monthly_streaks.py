"""Regression tests for v1.12.0: per-month streak capture + archive integrity.

Both behaviours here exist because of a real incident: on 2026-08-01 a late tapback
carrying a July timestamp arrived AFTER July was archived and crowned, resurrecting a
one-row ``months["2026-07"]`` bucket alongside the genuine 7-player
``history["2026-07"]``. Archiving that remnant would have overwritten a full month of
standings with a single 1-correct row.
"""
import datetime

from zoneinfo import ZoneInfo

from meshquiz.monthly import MonthlyBoard, MonthlyScore

TZ = "America/Phoenix"


def ts(y, m, d, h=12):
    return datetime.datetime(y, m, d, h, tzinfo=ZoneInfo(TZ)).timestamp()


def board():
    return MonthlyBoard(tz_name=TZ)


# --------------------------------------------------------------------------- streaks
def test_best_streak_is_the_high_water_mark_not_the_current_run():
    b = board()
    for correct in (True, True, True, False, True):
        b.record("!a", "A", correct, ts(2026, 8, 2))
    s = b.standings("2026-08")[0]
    assert s.correct == 4
    assert s.streak == 1        # current run: the single correct after the miss
    assert s.best_streak == 3   # the run BEFORE the miss is what the award cares about


def test_perfect_month_streak_equals_correct_count():
    b = board()
    for _ in range(19):
        b.record("!a", "A", True, ts(2026, 8, 2))
    s = b.standings("2026-08")[0]
    assert s.best_streak == s.streak == s.correct == 19


def test_streaks_do_not_leak_across_months():
    b = board()
    for _ in range(5):
        b.record("!a", "A", True, ts(2026, 8, 20))
    for _ in range(2):
        b.record("!a", "A", True, ts(2026, 9, 2))
    assert b.standings("2026-08")[0].best_streak == 5
    assert b.standings("2026-09")[0].best_streak == 2


def test_streaks_survive_archive_and_a_restart():
    b = board()
    for correct in (True, True, False, True):
        b.record("!a", "A", correct, ts(2026, 8, 2))
    rows = b.archive("2026-08")
    assert rows[0]["best_streak"] == 2 and rows[0]["streak"] == 1

    b2 = board()
    for correct in (True, True, False, True):
        b2.record("!a", "A", correct, ts(2026, 8, 2))
    restored = board()
    restored.load(b2.to_dict())          # round-trip through state.json's shape
    s = restored.standings("2026-08")[0]
    assert s.best_streak == 2 and s.streak == 1


# ------------------------------------------------------------- late answer / archive
def test_late_answer_cannot_resurrect_an_archived_month():
    """The exact 2026-07 incident: a tapback landing after the crowning."""
    b = board()
    for _ in range(71):
        b.record("!champ", "Utopia", True, ts(2026, 7, 20))
    b.archive("2026-07")
    b.mark_announced("2026-07")

    b.record("!champ", "Utopia", True, ts(2026, 7, 31, 23))   # the late tapback

    assert "2026-07" not in b.months, "archived month was resurrected"
    assert b.history["2026-07"][0]["correct"] == 71


def test_archive_refuses_to_overwrite_a_fuller_record():
    """Belt and braces: even if a remnant bucket exists, history is not downgraded.

    The remnant is injected directly (``record`` now refuses to create one) so the
    archive-side guard is tested independently of the record-side guard. Two
    independent defences, two independent tests.
    """
    b = board()
    for _ in range(71):
        b.record("!champ", "Utopia", True, ts(2026, 7, 20))
    b.record("!other", "Other", True, ts(2026, 7, 21))
    b.archive("2026-07")
    assert len(b.history["2026-07"]) == 2

    b.months["2026-07"] = {"!champ": MonthlyScore("!champ", "Utopia", 1, 1, ts(2026, 7, 31))}

    kept = b.archive("2026-07")

    assert len(kept) == 2 and kept[0]["correct"] == 71, "history was clobbered"
    assert b.history["2026-07"][0]["correct"] == 71
    assert "2026-07" not in b.months, "remnant bucket should still be cleared"


def test_archive_still_overwrites_with_a_fuller_snapshot():
    """The guard must not FREEZE history: a genuinely bigger re-archive still wins."""
    b = board()
    b.record("!a", "A", True, ts(2026, 8, 2))
    b.archive("2026-08")
    assert b.history["2026-08"][0]["correct"] == 1

    b.months["2026-08"] = {"!a": MonthlyScore("!a", "A", 9, 9, ts(2026, 8, 3))}
    assert b.archive("2026-08")[0]["correct"] == 9
    assert b.history["2026-08"][0]["correct"] == 9


def test_a_normal_new_month_is_unaffected_by_the_guard():
    b = board()
    for _ in range(3):
        b.record("!a", "A", True, ts(2026, 8, 2))
    b.archive("2026-08")
    b.mark_announced("2026-08")
    b.record("!a", "A", True, ts(2026, 9, 1))     # September: a different, open month
    assert b.standings("2026-09")[0].correct == 1
