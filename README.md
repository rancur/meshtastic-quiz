# 🎮 Meshtastic Quiz

A trivia game bot for the [Meshtastic](https://meshtastic.org) LoRa mesh network, hosted
by **Buzz** — a witty, PS3-trivia-host-style game master. Players answer by **tapback
(emoji reaction)** with `1️⃣2️⃣3️⃣4️⃣` on the question message. Runs as a small companion
service that talks to [MeshMonitor](https://github.com/Yeraze/meshmonitor)'s REST API — no
direct radio wiring required.

> Inspired by classic IRC trivia bots (MoxQuizz, frogesport, MansionNET QuizBot), adapted
> for the realities of a slow, lossy, byte-constrained LoRa mesh.

## How it plays

```
You:   !starttrivia
Buzz:  🎮 BUZZ TRIVIA is LIVE! React 1️⃣2️⃣3️⃣4️⃣ to answer. Brains on, legends!
Buzz:  [Science] What planet is the Red Planet?
       1) Venus 2) Mars 3) Jupiter 4) Saturn
       (players tapback 2️⃣ on that message...)
Buzz:  ⏱️ Time! Answer: 2) Mars
Buzz:  ✅ Nova nails it! +18
       ...next question...
You:   !leaderboard
Buzz:  🏆 LEADERBOARD
       🥇 Nova: 54
       🥈 Sparkplug: 41
       🥉 Relay9: 30
You:   !stoptrivia
Buzz:  🛑 That's a wrap! Thanks for playing.
```

Players are tracked by their **hex node id** (so nobody can double-score) and shown by
their node **long name**.

## Commands

Game commands work **only in the configured trivia channel**:

| Command | Effect |
| --- | --- |
| `!starttrivia` | Start a game. Idempotent — if one's already running, it just nudges. |
| `!stoptrivia` | End the current game and print the final leaderboard. |
| `!leaderboard` | Print the current standings. |
| `!help` | List all commands (one line each, byte-tight, split across messages). |

**Answering:** tapback react with `1️⃣`/`2️⃣`/`3️⃣`/`4️⃣` on a question. (Typed `1`–`4`
replies also count if `ALLOW_TYPED_ANSWERS=true`.)

### `!trivia` — the one command that works on the PRIMARY channel

The bot **also listens on the primary channel** (`PRIMARY_CHANNEL_INDEX`, default `0`) for
exactly **one** command — a deliberate exception to the trivia-channel-only rule:

| Command | Channel | Effect |
| --- | --- | --- |
| `!trivia` | primary (e.g. `MediumFast`, index 0) | Bot replies with a short invite **and** a channel-add deep link so people on the main channel can join trivia. |

The advert is sent as **two byte-tight messages** (invite, then the link on its own line
so the ~90-char link is never truncated). **No other command works on the primary
channel** — `!starttrivia`, `!leaderboard`, tapbacks, etc. there are ignored. The add link
is configurable via `TRIVIA_ADD_LINK`.

### Host as a player (`HOST_CAN_PLAY`)

By default the bot ignores its own node entirely. Set `HOST_CAN_PLAY=true` to let whoever
operates the **host node** (`BOT_NODE_ID`) also play: a *human* tapback or typed answer
seen from the host node is then counted like any other player's. The **bot process itself
never auto-answers** — it only ever sends questions and flavor text, never reactions — so
this can't be used to cheat. See [DECISIONS.md](DECISIONS.md).

## Ambient mode (rolling 24/7 trivia, mesh-friendly)

Ambient mode keeps the trivia channel **alive between games** by dropping **one standalone
question per hour** — without anyone running a rapid `!starttrivia` game. It's the slow,
polite background hum of the channel, not a flood.

By default an ambient question is a **teaser**: it keeps the channel warm and periodically
reminds folks the game and 🏆 leaderboard are there. With the **personality system** on (see
below) ambient reactions are *also* scored, and each new hour opens with a one-packet recap
of who got the previous question right.

| Setting | Default | What it does |
| --- | --- | --- |
| `AMBIENT_ENABLED` | `false` | Master toggle. **Off by default** so a fresh install never surprises a stranger's mesh — opt in on your own node. |
| `AMBIENT_INTERVAL_MINUTES` | `60` | Minutes between ambient questions. Hard floor of 5 (ambient is meant to be slow). |
| `AMBIENT_MINUTE_OFFSET` | `37` | The minute-of-hour to fire on. `37` is a prime well clear of `:00` (and `:15`/`:30`/`:45`) where scheduled mesh traffic tends to pile up. Ambient **never** fires at the top of the hour. |
| `AMBIENT_CHANNEL_INDEX` | trivia channel | Channel to post ambient questions on (defaults to `TRIVIA_CHANNEL_INDEX`). |
| `AMBIENT_REMINDER_FREQUENCY` | `3` | Every Nth ambient question carries the full `🏆 leaderboard / !starttrivia` plug; the rest are bare questions, so regulars aren't nagged hourly. `1` = always remind. |
| `MAX_SENDS_PER_MINUTE` | `6` | Hard anti-flood floor for **all** sends (game + ambient). A last-resort circuit breaker: the bot will never exceed this in any rolling 60s, regardless of any other logic. |

**Ambient pauses automatically while a rapid `!starttrivia` game is running** — no
stacking, ever. When the game ends, ambient resumes on its normal cadence.

### Mesh etiquette / airtime math

Ambient is designed to be a **rounding error** on the mesh's airtime, the opposite of a
chatty bot. One ambient question is a single ~200-byte text packet, once an hour:

- On a typical **LongFast** preset (SF11/BW250, ~`0.98 kbps` payload throughput), a
  ~200-byte text packet is roughly **1.6–2.5 s of airtime** including header + preamble
  (it varies a little with hop/ack settings).
- Once per hour that's **~2.5 s of airtime in 3,600 s ≈ 0.07 % duty cycle** from ambient.
- Contrast with a feared **one-message-every-90-s** cadence: 40 sends/hour × ~2 s ≈
  **80 s/hour ≈ 2.2 %** — roughly **30× more airtime**, and that's the cadence ambient
  deliberately does *not* run.
- The EU **1 % duty-cycle** ceiling (where it applies) is the usual reference point; hourly
  ambient sits an order of magnitude under it even before counting that real games are
  occasional, not continuous.

The fixed off-`:00` minute keeps ambient from colliding with other scheduled mesh traffic
(reminders, weather, conversation-starters) that tends to cluster at the top of the hour,
and the per-minute send floor (`MAX_SENDS_PER_MINUTE`) guarantees no bug anywhere can turn
the bot into a flooder.

## Personality system (Buzz with opinions)

When `PERSONALITY_ENABLED=true`, Buzz gets a **state-aware quip engine** and an **hourly
recap**. Right before each ambient question, Buzz announces the **outcome of the previous
one** in a single packet:

- **Winner(s):** names who got it right, with streak-escalating praise — a 2-streak gets a
  nod, a 3-streak a hat-trick, a 5+ streak a full coronation. A long winner list truncates
  to `Ann (+3 more)`.
- **No winner:** reveals the answer with a dry one-liner (`🦗 Nobody. Brutal. It was 2) Paris.`).
- **Comebacks:** someone scoring after a drought gets a "welcome back" callout sized to the
  drought length.
- **Casual pokes:** a friendly jab at someone who isn't doing well — *referencing observable
  facts only* (a wrong streak, or bottom of the standings), never the person. Pokes have a
  **per-player cooldown** (Buzz won't ride one person hour after hour) and **skip brand-new
  players** entirely.

The same quip engine enriches **rapid-game round announcements** (`!starttrivia`), so the
humor builds there too. Selection is **deterministic rotation** through 30+-line banks per
category — regulars won't see a repeat for days, and the behavior is fully reproducible.

| Setting | Default | What it does |
| --- | --- | --- |
| `PERSONALITY_ENABLED` | `false` | Master toggle. **Off by default** (matches ambient) — a fresh install behaves exactly like a quiet bot. Off also means ambient questions aren't scored at all. |
| `RECAP_ENABLED` | `true` | Toggle the hourly ambient recap packet specifically (only consulted when personality is on). |
| `POKES_ENABLED` | `true` | The casual pokes. Set `false` to keep praise-only. |
| `POKE_COOLDOWN_HOURS` | `3` | Per-player poke cooldown in ambient slots (≈ hours). |
| `NEW_PLAYER_GRACE_SLOTS` | `2` | Brand-new players are exempt from pokes this many slots after first seen. |

**Packet budget:** the recap is **one byte-capped packet** sent immediately before the
question packet, so a personality-enabled hour sends at most **recap + question = 2
packets** (vs 1 without personality). `MAX_SENDS_PER_MINUTE` remains the authoritative
flood floor. Personality state (streaks, droughts, poke cooldowns) **persists across
restarts** so running gags survive a reboot.

## How it works

```
   Meshtastic radio  ──TCP──>  MeshMonitor  ──REST /api/v1──>  Meshtastic Quiz (Buzz)
                                                                  ├─ transport adapter
                                                                  ├─ pure game engine
                                                                  └─ question bank (JSON)
```

- **Send a question:** `POST /api/v1/messages {text, channel}` → returns the message's
  packet id.
- **Read answers:** poll `GET /api/v1/messages?channel=N&since=...` and collect emoji
  reactions whose `replyId` matches the current question's packet id.
- The **game engine is pure logic** (no I/O, time injected), so the whole game is
  unit-tested against an in-memory mock mesh — no radio needed to develop or test.

See [PLAN.md](PLAN.md) for the full design and the verified MeshMonitor API details, and
[DECISIONS.md](DECISIONS.md) for scoring, edge cases, and tunables.

## Requirements

- A running [MeshMonitor](https://github.com/Yeraze/meshmonitor) instance (4.5+) connected
  to your Meshtastic node, with an **API token** (`Settings → API Tokens`) that has
  `messages:read` and `channel_<N>:write` for your trivia channel.
- A channel configured on your mesh for trivia (note its **index**).
- Python 3.9+ (or just Docker).

## Quick start (Docker — recommended)

```bash
git clone https://github.com/<you>/meshtastic-quiz.git
cd meshtastic-quiz
cp .env.example deploy/.env
$EDITOR deploy/.env          # set MESHMONITOR_URL, MESHMONITOR_API_TOKEN, TRIVIA_CHANNEL_INDEX, BOT_NODE_ID
./deploy/install.sh          # builds + starts the container (idempotent)
```

If MeshMonitor runs in Docker on the same host, set `MESHMONITOR_DOCKER_NETWORK` in
`deploy/.env` to its network (e.g. `meshmonitor_default`) so the bot can reach it by
service name (`http://meshmonitor:3001`).

## Quick start (no Docker)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
$EDITOR .env
set -a; . ./.env; set +a       # export the config into the environment
python -m meshquiz
```

Or install the included systemd unit — see [`deploy/meshtastic-quiz.service`](deploy/meshtastic-quiz.service).

## Configuration

Everything is environment-driven; see [`.env.example`](.env.example) for the full list
(timing, scoring, anti-runup thresholds, byte budget, etc.). **No secrets or
deployment-specific values live in the code** — copy `.env.example` to `.env` (gitignored)
and fill in your own.

## The question bank

~230 curated single-answer questions across 11 categories (Science, History, Geography,
Tech, Pop culture, Sports, Nature, Food, Music, Math, General), each authored to fit the
Meshtastic 200-byte payload limit. The bank lives at
[`meshquiz/data/questions.json`](meshquiz/data/questions.json) and is generated +
validated by [`scripts/build_questions.py`](scripts/build_questions.py).

**Monthly refresh:** add/rotate questions in `build_questions.py`, then run
`python scripts/refresh_questions.py`. It rebuilds the JSON and fails loudly if any
question exceeds the byte budget. Wire it into a monthly cron if you like.

## Development & tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite covers scoring math, speed/first-correct bonuses, dedupe-by-hex, timer expiry,
the anti-runup guard, idempotent start, channel gating, command + emoji parsing, byte-limit
validation of every question, full simulated game sessions over the mock transport, and
crash recovery.

## License

MIT — see [LICENSE](LICENSE).
