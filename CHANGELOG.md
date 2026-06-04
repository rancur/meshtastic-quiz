# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/).

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
