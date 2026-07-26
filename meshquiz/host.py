"""'Buzz'-style host personality.

Short, punchy, encouraging flavor text with light trash talk — kept tiny because every
line goes over the mesh (byte budget). Pick lines at random for variety. The host NEVER
emits anything that isn't byte-budget checked by the caller.
"""
from __future__ import annotations

import random
from typing import List

NAME = "Buzz"

GAME_START = [
    "🎮 BUZZ TRIVIA is LIVE! React 1️⃣2️⃣3️⃣4️⃣ to answer. Brains on, legends!",
    "🎮 It's quiz o'clock! I'm Buzz. Tap 1️⃣2️⃣3️⃣4️⃣ to lock your answer. Let's go!",
    "🎮 BUZZ here! New game! Answer with a tapback 1️⃣2️⃣3️⃣4️⃣. No googling, champ.",
]

GAME_ALREADY = [
    "🎮 Easy tiger — a game's already running! Jump in with a tapback.",
    "🎮 Game's live already! Quit stalling and tap an answer.",
]

GAME_STOP = [
    "🛑 That's a wrap! Thanks for playing. !leaderboard for the carnage.",
    "🛑 Game over! See ya next round. Type !leaderboard for final scores.",
]

CORRECT = [
    "✅ {name} nails it! +{pts}",
    "✅ Boom! {name} +{pts}",
    "✅ {name} is on FIRE 🔥 +{pts}",
]

REVEAL = [
    "⏱️ Time! Answer: {opt}",
    "⏱️ Pencils down! It was: {opt}",
]

# WRONG: {name}. Immediate acknowledgment of a WRONG guess so the player knows Buzz saw it.
# HARD RULE: never reveal or hint at the correct answer (others are still guessing) — these
# lines only confirm the guess registered + offer encouragement. Kept short for the mesh
# byte budget. Picked at random (decoupled from the personality quip engine so it works
# even when PERSONALITY_ENABLED is off).
WRONG = [
    "❌ Not it, {name} — but Buzz saw your guess! Get the next one.",
    "❌ Nope, {name}! Nice try. Better luck next question.",
    "❌ Swing and a miss, {name}. Buzz clocked it — stay in it!",
    "❌ Not quite, {name}! Shake it off, next one's yours.",
    "❌ Sorry {name}, wrong tap — but you're seen. Next!",
    "❌ Ooh, not it {name}. Buzz logged it. On to the next!",
    "❌ {name}, that's a miss — regroup for the next round!",
    "❌ Close but no, {name}! Buzz noticed. Keep at it.",
    "❌ Missed it, {name}! No points this time, but nice hustle.",
    "❌ Not the one, {name}. Buzz caught your tap — redeem it next!",
]

NOBODY = [
    "🦗 Crickets... nobody got it. Brutal.",
    "🦗 Zero correct. The questions win this round.",
]

TAUNT_LOW = [
    "👀 Need more players! Grab a friend.",
    "👀 Lonely out here. Rally the mesh!",
]

RUNUP_STOP = [
    "🛑 Not enough players ({n}) — trivia needs more than 1 brain! Game stopped. !starttrivia when the squad's here.",
    "🛑 Too quiet ({n} playing). Buzz needs a crowd! Stopped — !starttrivia to revive.",
]

ONLY_IN_CHANNEL = "🤖 Buzz only does trivia in the trivia channel."

# --- !help (in the trivia channel) ---
# Buzz-flavored, but kept SHORT. Returned as a list of messages so each fits the byte
# budget; the bot sends them in order (and re-splits defensively if a line is too long).
HELP_LINES = [
    "🤖 Buzz here! Commands:",
    "!starttrivia - start a game",
    "!stoptrivia - end + show scores",
    "!leaderboard - standings",
    "!help - this list",
    "Answer by tapback 1️⃣2️⃣3️⃣4️⃣ on a question. Brains on!",
]

# --- !trivia advert (on the PRIMARY channel) ---
# msg1 = invite + call to action; msg2 = the channel-add deep link. The link alone is
# ~90 bytes, so it MUST be its own message (see DECISIONS.md). The link itself comes from
# config (Config.add_link) so it is never hard-coded twice.
TRIVIA_ADVERT_INTRO = "🎮 Buzz runs live TRIVIA on the 'trivia' channel! Tapback to play. Add the channel:"


# --- Ambient mode (rolling solo questions, see config.ambient_*) ---
# An ambient question is a STANDALONE teaser: it does NOT open a scored round. The point
# is to keep the channel warm and periodically remind folks the game + leaderboard exist.
#
# To stay one-packet-per-message, the ambient send is built as a LIST of messages
# (same pattern as !help / !trivia): the question itself is always its own message
# (already byte-validated by the question bank), and the reminder — when shown — is a
# SECOND short message. This guarantees neither packet can blow the byte budget no matter
# how long the question is.
#
# AMBIENT_LEAD_EMOJI : a small rotating set of STANDARD emoji, ONE of which leads the
#   question line inline (e.g. "🧠 In which series…"). Replaces the old "🧠 Brain snack:"
#   category-flavored header lines (removed v1.2.2, Will's format spec): no category tag,
#   no separate header packet — just one clean emoji + the question. Kept tiny + standard
#   so it renders on any LoRa client and stays well within the byte budget.
# AMBIENT_REMINDER : the leaderboard + !starttrivia plug, shown only every Nth question so
#                    channel regulars aren't nagged hourly.
AMBIENT_LEAD_EMOJI = ["🧠", "💡", "🎯", "❓", "✨"]
AMBIENT_REMINDER = [
    "🏆 !leaderboard for standings · !starttrivia for rapid rounds",
    "Want more? !starttrivia for a full game · 🏆 !leaderboard",
    "!starttrivia anytime for rapid rounds · 🏆 !leaderboard",
]


# --- Monthly champion + board reset (v1.11.0, see monthly.py / DECISIONS.md) ------------
# Copy for the end-of-month wrap. Placeholders: {month} (e.g. JULY), {who} (champion or
# co-champions), {n} (correct answers), {next_month}, {ch} (trivia channel name).
#
# BYTE DISCIPLINE: these are the LONGEST form of each line. monthly.compose_* measures the
# rendered UTF-8 length and falls back to shorter winner phrasings ("A, B +2", "a 4-way
# tie") if a long name list would push a packet over budget, so every line here can afford
# to read naturally. tests/test_monthly.py renders all of them against worst-case names.

# Trivia channel: the players' own wrap-up. One packet.
MONTHLY_TRIVIA = [
    "🏆 {month} CHAMPION: {who} — {n} correct! Board resets for {next_month}, everyone back to 0. Go get it.",
    "🏆 That's {month} done! {who} takes it with {n} correct. Fresh board for {next_month} — new month, new champ.",
    "🏆 {month} champ: {who}, {n} correct. Scores wiped for {next_month} — everybody starts level. Tap in!",
]

# PRIMARY channel message 1 of 2: the crown. Read by the whole mesh, so it says what Buzz
# is as well as who won.
MONTHLY_PRIMARY_WINNER = [
    "🏆 Buzz Trivia — {month} champion: {who}, {n} correct! New month, board's reset, everyone starts at 0.",
    "🏆 {month} Buzz Trivia champion: {who} ({n} correct). Board's been reset — this month is anyone's.",
]

# PRIMARY channel message 2 of 2: the recruiting pitch. The channel-add link is appended by
# monthly._compose_promo on its own line, so these are PREFIXES only, ordered longest-first
# — the first one that leaves room for the link (link length varies by channel) is used.
MONTHLY_PRIMARY_PROMO = [
    "🎮 Want in on next month? Buzz runs trivia 24/7 on the '{ch}' channel. Add it:",
    "🎮 Play next month — Buzz runs trivia on the '{ch}' channel. Add it:",
    "🎮 Join trivia on '{ch}':",
    "🎮 Trivia channel:",
]


def pick(lines: List[str], **fmt) -> str:
    return random.choice(lines).format(**fmt)


def template(lines: List[str]) -> str:
    """Pick a RAW line, leaving its placeholders unfilled.

    Used where the caller must render the same template several times at different lengths
    (the monthly composer tries progressively shorter winner phrasings until one fits the
    packet), which `pick` — which formats immediately — can't express.
    """
    return random.choice(lines)
