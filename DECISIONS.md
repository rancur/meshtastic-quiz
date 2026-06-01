# Design Decisions

Rationale for non-obvious choices, edge-case handling, and any places the spec was
ambiguous. Everything here is tunable via environment variables (see `.env.example`).

## Answering mechanic: tapback reactions (primary) + typed fallback

Verified against a live MeshMonitor instance and the MeshMonitor source: a Meshtastic
reaction (tapback) is itself a message with `emoji == 1` (reaction flag), `replyId ==
<packet id of the message reacted to>`, `text == the emoji character`, and `fromNodeId ==
the reactor`. The bot sends a question (getting back its `requestId` == packet id), then
polls `GET /api/v1/messages?channel=N&since=...` and collects reactions whose `replyId`
matches the current question's packet id. This is the exact requested mechanic and it
works.

A **typed-answer fallback** (`1`/`2`/`3`/`4` as a normal channel message) is available
behind `ALLOW_TYPED_ANSWERS` (default on) for radios/clients that cannot emit reactions.
It does not change scoring. Set it to `false` for a pure tapback game.

## Scoring scheme

- Correct: **10 base** + **0–5 speed bonus** (linear in remaining time / window) +
  **3 first-correct bonus** (only the first correct reactor).
- Wrong: **0** (no penalty — keeps it friendly).
- Modeled on modern IRC trivia bots (MoxQuizz, frogesport, MansionNET QuizBot) which
  reward speed and the first correct answer. All three values are env-tunable.

## A player's answer = their FIRST reaction (dedupe + anti-cheat)

A node's first reaction within the window is locked in. Changing your reaction afterward
does **not** override it. Rationale: prevents "wait to see what others pick" gaming, and
makes scoring deterministic. Dedup key is the **hex node id** (`fromNodeId`), so a player
can't farm points from multiple reactions; the display name is the node `longName`
(refreshed from MeshMonitor's node directory; falls back to shortName/hex).

## Anti-runup guard — spec ambiguity resolved

The spec contained a tension: *"if NOT more than 2 people are answering for more than
3 questions in a row, announce the game has stopped and requires more than 1 person to
play."* Literally "not more than 2" = ≤2, which would make a normal 2-player game
impossible — contradicting "requires more than 1 person to play" and "anyone can play."

**Resolution:** the guard's intent is to stop a single person farming the leaderboard
alone. We interpret it as: auto-stop when **distinct answering players ≤ `RUNUP_MIN_PLAYERS`
(default 1)** for **`RUNUP_MAX_LOW_ROUNDS` (default 3)** questions in a row. So a lone
player triggers the stop after 3 quiet rounds; two or more keep the game alive. Both
thresholds are env-tunable, so anyone who wants the strict literal reading can set
`RUNUP_MIN_PLAYERS=2`. The streak resets the moment a healthy round happens.

## Idempotent start

A second `!starttrivia` while a game is running does **not** restart or add a question — it
just nudges ("a game's already running"). Implemented in the engine, tested at both engine
and bot level (including spam from a different node).

## Channel gating

All commands and answers are acted on **only** for the configured trivia channel index.
Traffic on any other channel is ignored. Tested.

## Bot restart mid-game

On restart the bot restores its **message cursor** (so it doesn't replay old channel
history) but does **not** resume a half-finished question — the mesh has moved on and we
may have missed reactions during downtime. The leaderboard is per-game by design, so a
clean restart simply means the operator runs `!starttrivia` again. On a *fresh* deploy
(no prior state) the cursor seeds to "now" so the bot never replays the channel's entire
back-history on first boot.

## Leaderboard reset semantics

The leaderboard is **per game session**: each `!starttrivia` starts scores from zero.
This keeps games self-contained and avoids unbounded cross-game accumulation on a
low-traffic mesh. A monthly **question** refresh is independent and does not touch scores.
(If a persistent season-long leaderboard is ever wanted, it's a small extension on top of
`state.py`, which already persists a leaderboard snapshot.)

## Mesh byte budget

Every outbound message is validated against `MAX_PAYLOAD_BYTES` (default 200, the
Meshtastic text limit). Questions render as `"[Cat] Question?\n1) a 2) b 3) c 4) d"`; a
test asserts **every** question in the bank fits (current max observed: ~96 bytes). Flavor
text is kept short; the sender also hard-truncates as a last-resort safety net so a stray
long line can never exceed the budget and get split/rejected by MeshMonitor.

## Flood protection

The sender enforces `MIN_SEND_INTERVAL_S` (default 2s) between outbound messages so the
bot never bursts the mesh. The poll loop runs every `POLL_INTERVAL_S` (default 4s).

## Question with no correct reactions / nobody answers

Handled: the engine reveals the answer and posts a "nobody got it" line. A round with
zero/low distinct answerers counts toward the anti-runup streak.

## Late / out-of-order / lossy delivery

Reactions arriving after the deadline are ignored for scoring. The poll uses a 10s cursor
overlap and dedupes by packet id, so late-delivered-but-in-window reactions are still
counted and nothing is double-processed.

## Self-reactions

If `BOT_NODE_ID` is set, the bot ignores messages/reactions from its own node entirely.
(The bot does not react to its own questions, but this guards against any echo.)

## Ties on the leaderboard

Equal scores are broken by **earliest to reach that standing** (the player who scored
their points sooner ranks higher), then alphabetically — stable and intuitive.
