# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [1.9.0] - 2026-07-09

### Changed
- **Game math-cap: the competitive `!starttrivia` game is trivia-first now too.** v1.8.0
  fixed the *ambient* 24/7 channel, but the rapid game still drew from a **plain shuffle** of
  the `QUIZ_DIFFICULTY` pool — which at the default `mixed` tier is the whole **~83% Math**
  bank, so a 12-question game was ~10 math questions. It still *felt* like "the trivia is
  mainly math." Buzz now builds each game's draw bag **math-capped**: it keeps every non-math
  question and adds only enough randomly-chosen math to hit `GAME_MATH_MAX_PCT` (default
  **18**), then shuffles. Verified served game mix over a simulated batch on the real bank:
  **~18% math / ~82% real trivia** (geography, science, history, mesh/RF/LoRa deep cuts, …) —
  matching the ambient track so BOTH the game and the 24/7 channel feel trivia-first.
  - **Nothing is deleted — fully reversible.** Math stays in the bank; this is pure
    *selection* weighting. `GAME_MATH_MAX_PCT=0` serves a game with no math (unless the active
    tier is all-math); `=100` disables the cap (plain uniform shuffle = the pre-1.9.0 ~83%
    behavior).
  - **Same reliable tag-based classification** as the ambient cap (`questions.is_math`), so a
    real-trivia question that merely contains a digit is never mis-flagged.
  - **Degenerate tiers never starve the bag:** an all-math or all-non-math tier falls back to
    a plain shuffle rather than emptying the bag.
  - New env knob `GAME_MATH_MAX_PCT` (default 18, range 0–100).

### Unchanged
- The ambient math-cap (v1.8.0), wrong-answer feedback (v1.7.0), the persistent no-repeat
  system, the question bank, difficulty tiers, and scoring are all untouched.

## [1.8.0] - 2026-07-09

### Changed
- **Ambient math-cap: the 24/7 channel is trivia-first again, not a math drill.** The
  v1.6.0 mass-generation grew the bank to ~9.2k questions to clear a literal 365-day
  no-repeat, but MATH was the only verified category that scaled to thousands — so the
  ambient (med+hard) pool ended up **83% Math / 17% real trivia** (7,578 math vs 1,532
  non-math). Served hourly, the channel *felt* like arithmetic homework. Buzz now uses
  **weighted selection** on the ambient track: each hourly fire rolls `AMBIENT_MATH_MAX_PCT`
  (default **18**) to decide whether it may be a math question, then honors the no-repeat
  window *within* the chosen bucket. Verified served mix over a simulated batch:
  **~18% math / ~82% real trivia** (geography, science, history, chemistry, mesh/RF/LoRa
  deep cuts, …) — math is now occasional spice, not the main course.
  - **Nothing is deleted — fully reversible.** The math questions stay in the bank; this is
    pure *selection* weighting. Change one env var to retune: `AMBIENT_MATH_MAX_PCT=0` never
    serves math, `=100` disables the cap entirely (uniform selection = the pre-1.8.0 ~83%
    math behavior).
  - **Reliable classification.** A question is "math" iff its **category tag** is math
    (`Math`/`Arithmetic`/`Number Theory`/… — see `questions.MATH_CATEGORIES`), never by
    scanning the text — so a real-trivia question that merely contains a digit (e.g. the Mesh
    question "Max channels you can configure (indices 0-7)?") is never mis-flagged.
  - **No-repeat still holds, per bucket.** Because non-math is now served ~82% of the time
    from the smaller 1,532-question pool, its effective no-repeat window shrinks to
    **~78 days (~2.6 months)** — `non_math_pool / (0.82 × 24)` — after which it re-serves the
    least-recently-asked non-math question (max spacing, never a recent repeat). Math, served
    ~18%, effectively never repeats (~4.8-year window). Both far better than the pre-fix
    "repeats within hours" problem, and the whole-pool literal-365-day guarantee still holds
    when the cap is disabled.
  - New env knob `AMBIENT_MATH_MAX_PCT` (default 18, range 0–100). The startup log now reports
    the pool math/non-math split, the active cap, and the computed non-math no-repeat window.

### Unchanged
- Wrong-answer feedback (v1.7.0), the persistent no-repeat system + history, the question
  bank, and the competitive `!starttrivia` game (which draws from `QUIZ_DIFFICULTY`, separate
  from the ambient pool) are all untouched.

## [1.7.0] - 2026-07-08

### Added
- **Wrong-answer feedback.** Buzz now acknowledges a WRONG guess with a short, friendly
  one-liner (e.g. "❌ Not it, {name} — but Buzz saw your guess! Get the next one.") so a
  player knows their answer registered. Previously a wrong tap got **total silence**, which
  felt like the guess was never seen — while correct answers were celebrated at reveal/recap.
  This closes that correct-vs-wrong asymmetry.
  - **Never leaks the answer.** The ack only confirms the guess was seen + encourages; it
    never reveals or hints at the correct option (others are still guessing). Correct answers
    remain silent in the moment and are still announced only at reveal (rapid game) / the
    hourly recap (ambient), unchanged.
  - **Airtime-bounded / anti-spam.** Feedback rides the existing anti-cheat first-answer
    lock: only a node's FIRST answer per question is ever recorded, so each player gets **at
    most one** wrong-ack per question and a single user physically cannot spam wrong guesses.
    The global `MAX_SENDS_PER_MINUTE` floor still caps total channel airtime regardless.
  - **Both tracks.** Applies to the rapid `!starttrivia` game AND the 24/7 ambient track —
    every flow that accepts answers.
  - New toggle `WRONG_ANSWER_ACK` (default **on**); set false to restore the pre-1.7.0
    silence. New `host.WRONG` line bank (answer-safe, byte-budgeted).

## [1.6.0] - 2026-07-06

### Added
- **Mass question generation → the ambient pool now clears a LITERAL 365-day no-repeat.** The
  v1.5.0 no-repeat window degraded gracefully because the pool (480) was far below the 8,760
  questions an hourly cadence needs for a full year. This release scales the ambient-eligible
  (med+hard) pool to **9,110** (total bank **9,192**), so a full year of hourly draws now has
  **zero** repeats — guaranteed minimum spacing **≈379 days**.
- New generator module [`scripts/gen_bank.py`](scripts/gen_bank.py), invoked from
  `build_questions.py` (BATCH 7). **Correctness by construction, not recall:**
  - **Math** (~7,300, the bulk): answers are **computed** by the generator — multiplication,
    division, powers, roots, percentages, Roman numerals, binary/hex conversion, primes,
    polygons/angle-sums, factorials, GCD/LCM. A separate pass **independently recomputed all
    7,520 math answers** and confirmed 0 errors.
  - **Fact tables** (~1,600): emitted from a single vetted canonical table (full periodic table,
    world capitals, all 50 US state capitals + postal codes, currencies, landmarks, NATO/Greek
    alphabets, verified Meshtastic/LoRa preset table + RF/ham facts) so **every distractor is
    another real row** — guaranteed wrong. Ambiguous/volatile rows (dual capitals, unstable
    currencies) were dropped; changed capitals + elements 100–118 verified 2026-07-06.
  - All generated questions are tagged **hard**, so the curated **medium** tier (the live
    `!starttrivia` game, still 251 questions) is untouched — only the 24/7 ambient
    `challenging` pool gets the deep bank.
- `add()` in `build_questions.py` now de-dupes by normalized question text (hand-authored +
  generated), so the generator can emit freely without ever producing a duplicate.

### Changed
- `tests/test_no_repeat.py` year simulation now asserts **zero repeats across a full year** when
  the pool ≥ 8,760 (the literal-year guarantee), keeping the graceful-degradation assertion for
  smaller pools. 139 tests green.

## [1.5.0] - 2026-07-06

### Fixed
- **The 24/7 ambient track no longer repeats questions.** Root cause: ambient question
  selection was `random.choice(pool)` — random **with replacement**, with **zero history**.
  On a few-hundred-question pool at the hourly cadence the birthday paradox produced
  collisions within hours (felt as "the same questions keep coming up"). Selection is now a
  **persistent 365-day no-repeat**: a question shown in the last `AMBIENT_NO_REPEAT_DAYS`
  days (default 365) is excluded; the next question is picked **randomly among eligible**
  ones. History (`{question_key: last_asked_epoch}`) is stored in `state.json`, written
  atomically, and survives restarts/redeploys. Any question sent to the channel — rapid-game
  **or** ambient — stamps the shared history, so the two tracks never echo each other.

### Added
- **+183 new fact-checked questions** (379 → **562**; med **160→251**, hard **139→229**),
  skewed medium/hard per Will's "make the questions harder too." Every fact is canonical +
  stable or verified 2026-07-06 (Meshtastic/LoRa specifics against the official radio-settings
  + channels docs; debatable/volatile facts deliberately excluded).
- **`AMBIENT_DIFFICULTY`** (default `challenging` = med+hard) decouples the 24/7 ambient pool
  from the competitive `QUIZ_DIFFICULTY` knob, giving the no-repeat window the widest/hardest
  pool to cycle through (**480** questions med+hard).
- **`AMBIENT_NO_REPEAT_DAYS`** (default 365). **Graceful degradation:** if the pool is too
  small for the cadence to cover a full year, selection falls back to the **least-recently-
  asked** question (maximum possible spacing) and logs a warning — never a recent repeat,
  never a crash. Guaranteed spacing = (pool size ÷ questions-per-day) days; a literal 365-day
  window at hourly needs ~8760 questions in the pool.

### Tests
- `tests/test_no_repeat.py`: simulates a **full year of hourly draws** and proves no question
  reappears before the whole pool cycles (LRU max-spacing); a year-sized pool yields literally
  zero repeats in 365 days; history persists across a restart; the exhausted-pool fallback is
  LRU (no crash, no recent repeat, no starvation). 139 tests green.

## [1.4.1] - 2026-06-06

### Fixed
- **Typed answers (`1`–`4`) to the ambient question were silently dropped.** The typed-answer
  path only fed the rapid `!starttrivia` game (`engine.running`); when no game was running, a
  typed reply to the open ambient question never reached the ambient scoring track, even though
  the equivalent emoji tapback did. Players who typed their answer instead of tapping back got
  **zero credit** on the 24/7 ambient track. Now a typed answer whose `reply_to` matches the
  open ambient packet scores on the ambient track, mirroring the emoji path. Stray `1`–`4`
  chatter with no `reply_to` is still ignored, so nothing spurious is credited.
  (Found via a full replay of the live AZ mesh's channel-2 history: two correct typed answers
  had been lost.)

### Tests
- `tests/test_ambient.py`: `test_ambient_typed_answer_is_captured_and_scored` (regression for
  the dropped typed ambient answer), `test_ambient_typed_answer_without_reply_is_ignored`
  (stray typed chatter stays unscored), and `test_ambient_emoji_reaction_is_captured`
  (baseline tapback capture). 135 tests green.

## [1.4.0] - 2026-06-05

### Added
- **+97 new fact-checked questions, broadening the bank well past Meshtastic** (Will's ask:
  "Add even more questions. Not just about meshtastic.") spread across the existing trivia
  categories plus **two new categories for the AZ mesh crowd:**
  - **`Space`** (16 Q) — planets, the Sun, moons, Saturn's rings, Olympus Mons, Ganymede,
    Sputnik, Voyager 1, Hubble, Perseverance, the ISS, Halley's Comet, the Milky Way.
  - **`AZ` / Southwest local flavor** (14 Q) — Phoenix, the Grand Canyon + the Colorado River
    that carved it, the saguaro, AZ's nickname/state bird/state flower, the 5 C's, Sedona,
    Lake Havasu's London Bridge, statehood (1912), the Sonoran Desert, and AZ skipping DST.
- The expansion carries a **deliberate harder skew** (Will, this morning): of the 97 new
  questions only 4 are easy — **45 medium + 48 hard**.

### Changed
- **Bank grown 282 → 379 questions** across **14 categories** (added `Space`, `AZ`). Per-tier
  counts: **easy 80, medium 160, hard 139** — the hard tier now outweighs easy.

### Fact-checking
- Every non-common-knowledge fact was WebSearch-verified 2026-06-05: AZ symbols/geography
  (azgovernor.gov "Arizona Facts", statesymbolsusa.org), the Grand Canyon (nps.gov), London
  Bridge (Wikipedia), and all Space facts (NASA `science.nasa.gov`, Wikipedia). Contested
  facts (e.g. Nile-vs-Amazon "longest river") were avoided.

### Tests
- 133 tests (was 130). Added v1.4.0 guards in `tests/test_difficulty.py`: bank ≥360 with
  `hard >= easy` (the skew holds), and the new `Space` + `AZ` categories are present.

### Byte budget
- Full 379-question bank re-validated: worst case **124 B** with the leading ambient emoji
  (budget 200 B) — unchanged from v1.3.0. Every question, all tiers, fits one LoRa packet.

## [1.3.0] - 2026-06-05

### Added
- **Installer-selectable difficulty tiers (`QUIZ_DIFFICULTY`).** Operators choose how hard
  Buzz plays: `easy`, `medium`, `hard`, or `mixed`. The bot narrows its question bag to the
  chosen tier at startup. `medium` is an alias for the bank's `med` label. **Default is
  `mixed`** (the whole bank) so existing installs that never set the variable behave exactly
  like v1.2.x — fully backward compatible. A tier that somehow ends up empty falls back to
  the full bank (a missing tier can never brick the bot) and logs the fallback.
- **50 new fact-checked Meshtastic / LoRa questions (`Mesh` category).** The medium and hard
  tiers now lean into the mesh itself — LoRa modem presets and their range/airtime tradeoffs
  (SF, bandwidth, coding rate, link budget), the default `LongFast` preset, hop-limit
  mechanics (default 3, max 7, decrement-on-rebroadcast), managed-flood routing + SNR-based
  contention windows, channels/PSK and AES-128/256 encryption, device roles (CLIENT /
  CLIENT_MUTE / ROUTER / REPEATER / TRACKER / SENSOR / ROUTER_LATE), MQTT bridging
  (`mqtt.meshtastic.org`, uplink/downlink), the US 915 MHz ISM band, and antenna basics
  (dBi). Every new question was verified against the official meshtastic.org docs.

### Changed
- **Bank grown 232 → 282 questions** across 12 categories (added `Mesh`). Per-tier counts:
  easy 76, medium 115, hard 91 — every selectable tier well past the 25-question target.

### Tests
- New `tests/test_difficulty.py`: tier filtering, `medium`→`med` aliasing, mixed/blank/legacy
  backward-compat, empty-tier fallback, `QUIZ_DIFFICULTY` config validation, live per-tier
  coverage (25+ each + Meshtastic depth in `hard`), and bot-bag narrowing.

### Byte budget
- Full 282-question bank re-validated: worst case **124 B** with the leading ambient emoji
  (budget 200 B). Every question, all tiers, fits one LoRa packet.

## [1.2.2] - 2026-06-03

### Changed
- **Clean question format — no category tag, no "Brain snack:" header.** Rendered questions
  no longer carry a `[Category]` prefix, and ambient teasers no longer emit a separate
  `🧠 Brain snack:` / `🧠 Quick one:` header line. Per Will's format spec, an ambient
  question now reads as a single **standard emoji + the question** on one line, e.g.
  `🧠 In which series would you find the character…`.
- **Rotating lead emoji.** Ambient questions lead with one emoji picked from a small,
  standard set — `🧠 💡 🎯 ❓ ✨` (`host.AMBIENT_LEAD_EMOJI`) — so the channel stays varied
  without any category labeling. Rapid-game questions render with no lead emoji (the host
  `GAME_START` banner already sets the scene). `render(lead_emoji=…)` is the single knob.
- **Inline keycap answer options confirmed.** Options remain one space-separated line:
  `1️⃣ Frodo 2️⃣ Harry P 3️⃣ Percy 4️⃣ Luke` (kept from v1.2.1). The recap/reveal answer line
  stays keycap-consistent (`2️⃣ Paris`).

### Byte budget
- Re-validated the full **232-question** bank against the new layout. Dropping the
  `[Category]` tag and the separate header packet *saves* bytes; the inline options were
  already a single line. Worst case is now **114 B** *with* the leading emoji (was 116 B in
  v1.2.1), comfortably under the 200 B single-packet cap. `validate_bank` now sizes against
  the worst-case lead emoji so no rotation can blow the cap.

### Tests
- Updated render/ambient/bot fixtures for the no-tag, lead-emoji, inline layout; added
  `test_render_has_no_category_tag`, `test_render_with_lead_emoji_inline`, and
  `test_render_options_are_single_inline_line`. Suite: **110 passing**.

## [1.2.1] - 2026-06-03

### Changed
- **Keycap-emoji answer options.** Rendered questions now prefix each option with the
  matching keycap-number emoji — `1️⃣ London 2️⃣ Paris 3️⃣ Berlin 4️⃣ Rome` — instead of the
  old `1) London 2) Paris …`. The leading emoji of each option is now *exactly* the tapback
  to react with, making the tapback-to-answer mapping visually obvious on a mesh client.
- **Recap/reveal lines match.** `answer_text()` (used by the hourly recap and the rapid-game
  reveal) is keycap-consistent too — `2️⃣ Paris`, not `2) Paris`.

### Compatibility
- **Answer parsing is unchanged and fully tolerant**: players may still type a bare digit
  `1`–`4`, and tapback reactions with the keycap emoji map to the same option index as
  before (`emoji_to_option` already keyed on the `U+20E3` keycap mark). No behavior change
  for existing players.
- **Byte budget verified.** Keycap prefixes cost 7 bytes vs 3 for `N)` (~+20 B per
  4-option question). The full 232-question bank renders at a max of **116 B**, well under
  the 200 B single-packet cap; `validate_bank` enforces the cap at load against the new
  render.

### Tests
- Updated `render`/`answer_text` and recap/byte-budget fixtures for the keycap format; added
  `test_render_uses_keycap_emoji_prefixes` and `test_typed_digit_answers_still_match`.
  Suite: 107 passing.

## [1.2.0] - 2026-06-03

### Added
- **Personality system** — a state-aware quip engine + hourly recap so Buzz has "lots of
  funny things to say as the rounds go on."
  - **Hourly recap packet**: immediately before each ambient question, Buzz announces the
    **previous** ambient question's outcome in a single byte-capped packet — winner(s) with
    a quip (long lists truncate to `Ann (+N more)`), or a dry answer-reveal when nobody got
    it. First fire ever has no previous question and the recap is skipped gracefully.
  - **Ambient questions are now (lightly) scored** when personality is on: reactions to the
    open ambient question are tracked (first-reaction-wins, same anti-cheat dedupe as the
    game) and resolved into the next hour's recap. With personality **off**, ambient is a
    pure teaser exactly as in v1.1.0.
  - **Escalating running gags**: streak-escalation praise (2 / 3 / 5+ correct in a row get
    progressively bigger celebrations, parameterized by streak length), comeback lines
    sized to drought length, and a dry no-winner reveal.
  - **Casual pokes** at strugglers — friendly bar-banter that references *observable facts
    only* (wrong streaks, bottom of the standings), never identity. Includes a **per-player
    poke cooldown** (won't ride one person hour after hour) and a **new-player exemption**
    (brand-new players are never poked).
  - **Deterministic-seeded rotation** through 30+-line banks per category, so regulars don't
    see repeats for days and tests are fully reproducible (no `random.choice` repeats).
  - The same quip engine **enriches rapid-game (`!starttrivia`) round announcements**.
  - **Persistent personality state**: streaks, droughts, and poke cooldowns survive bot
    restarts (serialized into `state.json`), so running gags keep building across the 24/7
    cadence.
  - New config: `PERSONALITY_ENABLED` (default `false`), `RECAP_ENABLED` (default `true`),
    `POKES_ENABLED` (default `true`), `POKE_COOLDOWN_HOURS` (default `3`),
    `NEW_PLAYER_GRACE_SLOTS` (default `2`).

### Changed
- A personality-enabled ambient hour now sends **recap + question = 2 packets** (was 1).
  `MAX_SENDS_PER_MINUTE` remains the authoritative flood floor; recap is one packet.

### Tests
- 27 new tests (104 total): quip determinism + bank rotation, recap byte caps with long
  names, poke cooldown + new-player exemption + facts-only calibration, streak-escalation
  tiers, no-winner path, recap+question = exactly 2 packets via `poll_once`, circuit-breaker
  authority with personality on, personality-state persistence, and the pure-additive
  guarantee (`PERSONALITY_ENABLED=false` ⇒ identical to v1.1.0).

### Docs
- README: personality-system section (recap, escalation, poke calibration, packet budget).
- DECISIONS.md: rationale for scoring ambient questions + the deterministic quip rotation.

## [1.1.0] - 2026-06-03

### Added
- **Ambient mode** — optional rolling 24/7 trivia that drops one standalone teaser
  question into the trivia channel on a slow cadence (default hourly) at a fixed off-`:00`
  minute, keeping the channel alive between rapid `!starttrivia` games.
  - New config: `AMBIENT_ENABLED` (default `false`), `AMBIENT_INTERVAL_MINUTES` (default
    `60`, hard floor 5), `AMBIENT_MINUTE_OFFSET` (default `37` — prime, never `:00`),
    `AMBIENT_CHANNEL_INDEX` (defaults to the trivia channel),
    `AMBIENT_REMINDER_FREQUENCY` (default `3` — full leaderboard/`!starttrivia` plug every
    Nth question, bare question otherwise).
  - Ambient **pauses automatically while a `!starttrivia` game is running** — no stacking.
  - Ambient questions are teasers: they are **not scored** and don't open an answer window.
- **Hard anti-flood floor** — `MAX_SENDS_PER_MINUTE` (default `6`): a last-resort circuit
  breaker in the sender that drops any send exceeding the cap in a rolling 60s window,
  regardless of game or ambient logic.

### Docs
- README: ambient-mode section with config reference and **mesh-etiquette / airtime math**
  (hourly ~200 B ≈ 0.07 % duty cycle vs a feared 90 s cadence ≈ 2.2 %).
- DECISIONS.md: rationale for offset strategy, in-process timer, pause-during-game,
  alternating copy, send floor, and the safe-by-default toggle.

### Safety
- Ambient ships **off by default** so a fresh OSS install never surprises a stranger's
  mesh; operators opt in on their own node.

## [1.0.0]

- Initial release: tapback-driven trivia for Meshtastic via MeshMonitor — `!starttrivia`
  rapid games, leaderboard, anti-grind guard, `!trivia` primary-channel advert,
  `!help`, optional `HOST_CAN_PLAY`.
