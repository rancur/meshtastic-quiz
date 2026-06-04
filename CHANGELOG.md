# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/).

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
