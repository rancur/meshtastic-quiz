# Meshtastic Quiz — Plan

A trivia game bot ("Buzz"-style host) for a Meshtastic LoRa mesh, driven through
[MeshMonitor](https://github.com/Yeraze/meshmonitor)'s REST API. Players answer with
emoji tapback reactions (1️⃣2️⃣3️⃣4️⃣) on the question message.

## 1. Verified MeshMonitor capability (researched against a live instance + source)

MeshMonitor exposes a stable **v1 REST API** (`/api/v1/...`, Bearer token auth). The
requested mechanic is natively supported and was observed working on a live mesh:

- **Send a question** — `POST /api/v1/messages` with `{ "text": "...", "channel": 2 }`.
  Returns `201` with `data.requestId` (the Meshtastic packet id) and
  `data.messageId` (`"<nodeNum>_<requestId>"`). Long text (>200 bytes) is auto-split
  into ≤3 parts and returns `202`; >3 parts → `413`. **We keep every send ≤200 bytes**
  so it is always a single packet (one `201`, one packet id to match reactions against).

- **Read reactions (tapbacks)** — A Meshtastic reaction is itself a text message with:
  - `emoji == 1` (reaction flag),
  - `replyId == <packet id of the message being reacted to>`,
  - `text == the emoji character` (e.g. `"1️⃣"`),
  - `fromNodeId == reactor's hex id` (e.g. `"!a1b2c3d4"`).

  We poll `GET /api/v1/messages?channel=2&since=<unix_ts>` and select messages where
  `emoji == 1` and `replyId == question_packet_id`. This was confirmed against live
  channel-2 history: a question with packet id `3205894328` had four reaction rows all
  carrying `replyId: 3205894328`, `emoji: 1`, `text: "1️⃣".."4️⃣"`.

- **Nodes** — `GET /api/v1/sources/{sourceId}/nodes` returns `nodeId` (hex),
  `nodeNum`, `longName`, `shortName`. Dedup by `nodeId` (hex), display `longName`.

- **Channels** — `GET /api/v1/channels` confirms channel index `2` is named `trivia`.

Because the mechanic is fully supported, **tapback answering is the primary path**. A
typed-answer fallback (`1`/`2`/`3`/`4` as a normal text message in the channel) is
implemented behind the same adapter and enabled by config (`ALLOW_TYPED_ANSWERS`),
for radios/clients that cannot send reactions. It does not change the core design.

## 2. Mesh constraints honored

- **200-byte payload budget.** Every outbound string is validated to fit a configurable
  byte budget (default 200, the Meshtastic text limit). Question + 4 options are sent as
  ONE compact message; a programmatic test asserts every question in the bank fits.
- **Latency / slow + lossy.** 90s answer window (per spec). Reactions are polled
  every few seconds; we read with a `since` cursor and a small overlap to tolerate
  out-of-order / delayed delivery. We never assume a reaction arrives instantly.
- **Flood protection.** Minimum inter-send spacing (`MIN_SEND_INTERVAL_S`) so the bot
  never bursts the mesh; host announcements are terse.

## 3. Architecture (transport adapter ⟂ game engine)

```
meshquiz/
  transport.py    # Transport ABC: send_message(text,channel)->packet_id ;
                  #                 fetch_messages(channel, since)->[Msg]
  meshmonitor.py  # MeshMonitorTransport: real v1 REST client (requests)
  mock_transport.py (in tests) # in-memory mesh for full-session simulation
  engine.py       # GameEngine: pure logic, no I/O. timers injected (clock fn).
  questions.py    # bank loader + byte-budget validation
  host.py         # "Buzz" personality flavor text (short, mesh-budget aware)
  bot.py          # wiring: poll loop, command parsing, channel gating, persistence
  config.py       # env-driven config (no secrets/PII in code)
  state.py        # JSON persistence (leaderboard + crash recovery)
  data/questions.json   # the generated question bank
```

The **engine is fully unit-testable without a mesh**: it receives "events"
(command received, reaction received, tick) and emits "actions" (send text). `bot.py`
translates between the engine and the transport. Time is injected as a `now()` callable
so timers are deterministic in tests.

## 4. Game design (modeled on IRC trivia bots: MoxQuizz, frogesport, MansionNET QuizBot)

- **Question selection:** shuffled bag, no repeats within a session; reshuffles only when
  the bag is exhausted. Large multi-category bank.
- **Scoring (speed-graded + correctness):**
  - Correct answer base: **10 pts**.
  - **Speed bonus:** up to **+5 pts** scaled linearly by how early within the 90s window
    the (first) reaction landed (`round(5 * remaining/window)`).
  - **First-correct bonus:** **+3 pts** to the first player to react correctly.
  - Wrong answer: **0** (no penalty — keeps it friendly/fun).
  - A player's score for a question uses their *first* reaction (see edge cases).
  - Documented + tunable in `config.py`; rationale in DECISIONS.md.
- **Leaderboard:** sorted by points desc, then by earliest-to-reach (stable). `!leaderboard`
  prints the top N compactly (byte-budget aware, may span ≤3 lines).
- **Anti-runup guard:** if **not more than 2 distinct players** answer for **3 questions in
  a row**, the game auto-stops with an announcement that it needs more than 1 player.
  ("more than 2 people are answering" read literally = `distinct_answerers <= 2`; we treat
  the spirit ("requires more than 1 person to play") and document the exact
  threshold in DECISIONS.md so it's tunable.)
- **Commands (trivia channel ONLY):** `!starttrivia`, `!stoptrivia`, `!leaderboard`.
  Idempotent start (a second `!starttrivia` while running just nudges, doesn't restart).
- **Player identity:** tracked/deduped by hex `nodeId`; displayed by `longName`
  (falls back to `shortName`/hex). Name refreshed from node db each round.

## 5. Question bank

YOU (the bot author) generate a large, multi-category bank (science, history, geography,
tech, pop culture, sports, nature, food, music, general). Each item:
`{category, difficulty, question, options[4], answer (0-3)}`. Stored as JSON. A test
validates that the rendered question+options message fits the byte budget for EVERY item,
and that `answer` indexes a real option. Monthly refresh: `scripts/refresh_questions.py`
(documented) regenerates/extends and re-runs validation; leaderboard reset semantics on
refresh documented in DECISIONS.md.

## 6. Edge cases handled (full list in DECISIONS.md)

ties, mid-question join, duplicate reactions from same node (first counts), reaction
changed before timeout, bot restart mid-game (state persistence), malformed input,
rate limiting, question with no reactions, leaderboard reset on monthly refresh,
concurrent `!starttrivia` spam, reactions to a *stale* question id, self-reaction by the
bot's own node (ignored), channel gating.

## 7. Tests (the build/test loop)

`pytest` unit tests for: scoring math, speed bonus, first-correct, dedupe-by-hex,
timer expiry, anti-runup guard, idempotent start, channel gating, command parsing,
byte-limit validation of EVERY question, full simulated game session via mock transport,
crash/restore. Iterate until green.

## 8. Deploy (additive, idempotent, safe — NOT run in this build)

A Docker container (a long-running companion-container pattern) on the MeshMonitor
docker network, talking to the v1 API. `deploy/` ships a `docker-compose.yml`,
`Dockerfile`, and a `systemd` unit alternative + `install.sh`. All host/token/channel
values come from `.env` (gitignored). Build + test locally first; leave a tested install
script for an operator to run on the host as the final gated step.

## 9. Publishability

Zero PII in committed code. All deployment specifics in `.env` (gitignored) with a
committed `.env.example` using placeholders. MIT license. README with gameplay walkthrough.
PII scan via the workspace `publish-ready-scan.sh` plus a repo-local grep gate before done.
