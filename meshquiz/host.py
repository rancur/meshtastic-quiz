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
# AMBIENT_HEADER : tiny prefix lines marking a message as an ambient teaser (not a game Q).
# AMBIENT_REMINDER : the leaderboard + !starttrivia plug, shown only every Nth question so
#                    channel regulars aren't nagged hourly.
AMBIENT_HEADER = [
    "🧠 Trivia teaser:",
    "🧠 Quick one:",
    "🧠 Brain snack:",
]
AMBIENT_REMINDER = [
    "🏆 !leaderboard for standings · !starttrivia for rapid rounds",
    "Want more? !starttrivia for a full game · 🏆 !leaderboard",
    "!starttrivia anytime for rapid rounds · 🏆 !leaderboard",
]


def pick(lines: List[str], **fmt) -> str:
    return random.choice(lines).format(**fmt)
