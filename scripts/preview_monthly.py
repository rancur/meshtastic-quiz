#!/usr/bin/env python3
"""Preview the month-end champion announcement WITHOUT touching the mesh.

Prints the exact packets the monthly wrap-up would transmit — the trivia-channel message
and the (at most two) primary-channel messages — each with its UTF-8 byte count against
the configured payload budget. It also shows the standings that produced them.

**It never sends, never archives, never resets, and never marks a month announced.** It
constructs no transport at all, so there is no code path from this script to the radio.
Use it to sanity-check the copy and the byte budget before enabling MONTHLY_RECAP_ENABLED.

Usage (from the repo root, with the deployment's env loaded):

    python3 scripts/preview_monthly.py                 # the most recent finished month
    python3 scripts/preview_monthly.py 2026-07         # a specific month
    python3 scripts/preview_monthly.py --demo          # synthetic data, no state file

Exit codes: 0 = a preview was produced (or the month is legitimately empty), 1 = the month
could not be resolved (bad key / no state file).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from meshquiz import host, monthly, state  # noqa: E402
from meshquiz.config import Config  # noqa: E402


def _load_board(cfg: Config) -> monthly.MonthlyBoard:
    board = monthly.MonthlyBoard(
        tz_name=cfg.monthly_timezone,
        history_months=cfg.monthly_history_months,
        max_lookback_months=cfg.monthly_max_lookback_months,
    )
    board.load(state.load_state(cfg.state_path).get("monthly"))
    return board


def _seed_demo(board: monthly.MonthlyBoard, key: str) -> None:
    """Synthetic standings so the copy can be eyeballed on a fresh install."""
    import time
    from datetime import datetime
    year, mon = (int(x) for x in key.split("-"))
    base = datetime(year, mon, 15, 12, 0).timestamp() or time.time()
    for i, (node, name, n) in enumerate([
        ("!demo0001", "Desert Fox", 41),
        ("!demo0002", "Saguaro Sam", 38),
        ("!demo0003", "Mesh Gremlin", 12),
    ]):
        for k in range(n):
            board.record(node, name, True, base + i * 60 + k)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("month", nargs="?", help="month to preview, as YYYY-MM")
    ap.add_argument("--demo", action="store_true",
                    help="use synthetic standings instead of the live state file")
    args = ap.parse_args()

    cfg = Config()
    board = monthly.MonthlyBoard(
        tz_name=cfg.monthly_timezone,
        history_months=cfg.monthly_history_months,
        max_lookback_months=cfg.monthly_max_lookback_months,
    ) if args.demo else _load_board(cfg)

    key = args.month
    if key is None:
        finished = sorted(k for k in board.months
                          if k < monthly.month_key(monthly.now(), cfg.monthly_timezone))
        key = finished[-1] if finished else monthly.month_key(monthly.now(),
                                                             cfg.monthly_timezone)
    if args.demo:
        _seed_demo(board, key)

    print(f"state file : {cfg.state_path}")
    print(f"timezone   : {cfg.monthly_timezone or '(system local)'}")
    print(f"budget     : {cfg.max_payload_bytes} B/packet, "
          f"max {monthly.MAX_PRIMARY_MESSAGES} primary messages")
    print(f"channels   : trivia={cfg.trivia_channel_index} "
          f"({cfg.trivia_channel_name!r})  primary={cfg.primary_channel_index}")
    print(f"month      : {key}  ({monthly.month_label(key)})")
    print()

    standings = board.standings(key)
    if standings:
        print("standings:")
        for i, s in enumerate(standings[:10], 1):
            print(f"  {i:>2}. {s.name or s.node_id:<28} {s.correct} correct "
                  f"/ {s.answered} answered")
    else:
        print("standings: (none recorded for this month)")
    print()

    # Render EVERY copy variant so the byte budget is checked against the worst case, not
    # just whichever line the random picker would have chosen tonight.
    for i, (trivia_tpl, winner_tpl) in enumerate(
            [(t, w) for t in host.MONTHLY_TRIVIA for w in host.MONTHLY_PRIMARY_WINNER], 1):
        ann = monthly.build_announcement(
            board, key,
            limit=cfg.max_payload_bytes,
            trivia_template=trivia_tpl,
            winner_template=winner_tpl,
            promo_templates=host.MONTHLY_PRIMARY_PROMO,
            channel_name=cfg.trivia_channel_name,
            add_link=cfg.add_link,
        )
        if ann.empty:
            print(ann.describe())
            break
        print(f"--- copy variant {i} ---")
        print(ann.describe())
        over = [m for m in [ann.trivia_message] + ann.primary_messages
                if monthly.byte_len(m) > cfg.max_payload_bytes]
        assert not over, f"OVER BUDGET: {over}"
        assert len(ann.primary_messages) <= monthly.MAX_PRIMARY_MESSAGES
        print()

    print("PREVIEW ONLY — nothing was transmitted, archived, or reset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
