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

All game commands and answers are acted on **only** for the configured trivia channel
index. Traffic on any other channel is ignored — **with one deliberate exception** (see
below). Tested.

## Primary-channel `!trivia` advert — the deliberate exception

To help people discover the game, the bot **also listens on the primary channel**
(`PRIMARY_CHANNEL_INDEX`, default `0` — typically "MediumFast") for **exactly one**
command: `!trivia`. When anyone types it there, the bot replies with a short invite and a
Meshtastic **channel-add deep link** so they can join the trivia channel in one tap.

- This is the *only* command honored on the primary channel. `!starttrivia`,
  `!leaderboard`, `!help`, tapback reactions, typed answers — all ignored there. The
  game itself never runs on the primary channel.
- The reply is **split into two messages**: msg1 = the invite + "add the channel:",
  msg2 = the add link by itself. The link is ~87 bytes; even though invite+link happens
  to fit in one 200-byte packet today, keeping the link on its own line guarantees it is
  never truncated by the defensive byte-trimmer or by a future longer invite string, and
  it's the form Will specified. Both messages are byte-validated like every other send.
- The add link is **public** (it only encodes the channel's name/PSK settings, which are
  meant to be shared) so it is safe to commit. It is configurable via `TRIVIA_ADD_LINK`,
  and the primary channel index via `PRIMARY_CHANNEL_INDEX`. If
  `PRIMARY_CHANNEL_INDEX == TRIVIA_CHANNEL_INDEX`, the bot just polls the one channel
  (no double-fetch) and `!trivia` is simply unhandled there.
- MeshMonitor read+write on channel 0 was verified against the live instance before
  shipping (the token has the needed scope; the bot polls both channels each cycle).

## `!help` command

`!help` (trivia channel only) lists every command, one short line each, in a Buzz voice.
It is emitted as **several tiny messages** rather than one block: each line is well under
the byte budget and is flood-spaced like any other send, so the help never risks being
split/truncated by the transport. Tested for content + per-line byte budget.

## Host node as a player (`HOST_CAN_PLAY`) — Will's "launch AND play" ask

Will asked whether the host node ("Will See G2 Base", the node MeshMonitor is bridged to)
could both *launch* and *play* trivia. The subtlety: **the host PROCESS generates the
questions**, so if the host node auto-answered it would be cheating.

**Decision — opt-in flag, default OFF, human-only scoring:**

- `HOST_CAN_PLAY=false` (default): the host node is ignored entirely for answers, exactly
  as before. Safe out of the box.
- `HOST_CAN_PLAY=true`: a *human* tapback or typed answer **observed on the channel from
  the host node** is counted as a normal player answer. That's all the flag does.

Why this is safe (the key invariant): the bot **only ever scores inbound traffic it
observes on the mesh**, and the bot process **never emits an answer** — it sends questions
and flavor text only, never a reaction or a "1".."4" message. So the host node can *only*
score when a real person taps an answer on that node's client; the software cannot
self-answer the questions it just wrote. This is asserted directly in the tests
(`test_bot_process_never_auto_answers`): with `HOST_CAN_PLAY=true` and no human input, the
host node never appears as a player and the bot sends zero reactions.

Limitation (documented, not blocking): because answers are deduped by node id and the host
operator sees the questions in the same MeshMonitor UI that drives the bot, an operator who
*wants* to cheat could of course read the answer the engine knows. That's a social
constraint, not a technical one — the same is true of any quiz host. The flag exists for
the friendly "operator joins in" case; leave it off for competitive play.

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
Meshtastic text limit). Questions render as `"Question?\n1️⃣ a 2️⃣ b 3️⃣ c 4️⃣ d"` — keycap-emoji
option prefixes since v1.2.1; the `[Cat]` category tag and the `🧠 Brain snack:` ambient
header were **removed in v1.2.2** (Will's format spec) in favor of a single optional standard
lead emoji prepended inline for ambient teasers (`🧠 Question?\n…`, emoji from a rotating
set). A test asserts **every** question in the bank fits, sized against the worst-case lead
emoji (current max observed: **114 bytes** with lead, was 116 with the line-broken header).
Flavor
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

## Ambient mode (rolling 24/7 trivia)

Ambient mode keeps the channel alive between games with one standalone teaser question per
hour. Four design choices, with rationale:

- **Off-`:00` fixed minute (default `:37`), not jitter.** Scheduled mesh traffic tends to
  pile up at the top of the hour (reminders, weather, conversation-starters). A fixed,
  prime, off-`:00` minute provably never collides with `:00` and is *predictable* for
  players ("trivia drops around half-past") — predictability beats per-hour jitter here,
  and it keeps the scheduler trivially testable. Configurable via `AMBIENT_MINUTE_OFFSET`
  so a deployer with their own `:37` traffic can move it. The slot grid is phased by the
  offset, so sub-hour intervals also avoid `:00`.

- **In-process timer, not cron.** The bot already runs a persistent poll loop
  (`run()` → `poll_once()` → `engine.tick()`). Ambient firing is a time check inside that
  same loop (`_maybe_ambient`), consistent with the engine's tick model. A cron job would
  mean a second process contending for the same state file and MeshMonitor connection.

- **Pause while a game is running.** Ambient checks `engine.running` and skips entirely
  during a rapid `!starttrivia` game — no stacking. It resumes on the normal cadence once
  the game ends.

- **Alternating copy.** Every Nth ambient question (`AMBIENT_REMINDER_FREQUENCY`, default
  3) carries the full leaderboard + `!starttrivia` plug; the rest are bare questions, so
  channel regulars aren't nagged with the same reminder every hour. The question is always
  its own byte-validated packet; the reminder, when shown, is a separate short packet.

- **Hard send floor.** `MAX_SENDS_PER_MINUTE` (default 6) is a last-resort circuit breaker
  inside `_send`: a rolling-60s window that drops any send over the cap regardless of game
  or ambient logic. It guarantees no bug anywhere can flood the channel.

- **Safe default: `AMBIENT_ENABLED=false`.** A fresh OSS install must never surprise a
  stranger's mesh, so ambient ships off; an operator opts in on their own node.

## Personality system (v1.2.0)

Will asked for an end-of-hour announcement of who got the previous question right, "lots of
funny things to say as the rounds go on," and "casual pokes at the people who aren't doing
so well." Five decisions:

- **Ambient questions become (lightly) scored.** v1.1.0 ambient questions were standalone
  teasers that opened no answer window — so there was literally no "who got it right" to
  recap. The engine now keeps a *separate, lightweight ambient track* (`_ambient_q`,
  `_ambient_pkt`, `_ambient_answers`) completely independent of the rapid-game state machine
  (`phase`, `players`). It never touches `phase`; a `!starttrivia` game still pauses ambient
  entirely. There is **no in-window deadline**: an ambient question stays open until the next
  one fires (~1h), which matches the mesh's slow async nature — people answer when they see
  it. `resolve_ambient()` closes the previous question and produces the recap. All of this is
  **gated behind `PERSONALITY_ENABLED`**: with it off, the bot never registers an ambient
  packet and never routes ambient reactions, so v1.1.0 behavior is byte-for-byte unchanged.

- **Recap winner semantics match the game.** All correct answerers are "winners"; the FIRST
  correct reactor is the highlighted one (same as the game's first-correct bonus + shoutout).
  The recap names the first winner with a quip and appends `(+N more)`; the whole thing is
  hard byte-capped to one packet.

- **One extra packet, no more.** The recap is its own packet sent immediately before the
  question packet, so a personality hour costs **recap + question = 2 packets** (was 1). The
  `MAX_SENDS_PER_MINUTE` circuit breaker is untouched and remains authoritative.

- **Deterministic rotation, not `random.choice`.** Each quip bank has a monotonic counter and
  selection is `bank[(seed + counter) % len(bank)]`, so a bank cycles fully before repeating
  (regulars don't see repeats for ~`len(bank)` fires ≈ days at hourly) AND tests are stable.
  Banks are ≥30 lines each. The deployed bot seeds from the slot index for cross-run variety;
  tests leave the seed 0.

- **Poke calibration — friendly, fact-based, never cruel.** A poke is chosen at most once per
  recap and only when the target has a **wrong-streak ≥ 2** or sits at the **bottom of a ≥3-
  player board with a real gap**. Pokes reference the *fact* (a streak count, a point gap),
  never identity. Brand-new players are exempt (`NEW_PLAYER_GRACE_SLOTS`), and a per-player
  cooldown (`POKE_COOLDOWN_HOURS`) stops Buzz riding one person hour after hour. Personality
  state (streaks, droughts, cooldowns) **persists across restarts** via `state.json` so the
  running gags survive a reboot — a 5-streak shouldn't reset because the container bounced.
