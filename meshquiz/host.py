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


def pick(lines: List[str], **fmt) -> str:
    return random.choice(lines).format(**fmt)
