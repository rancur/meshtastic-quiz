"""State-aware personality / quip engine for Buzz.

This is the "lots of funny things to say as the rounds go on" layer. Unlike
``host.py`` (small static banks picked at random), this module is:

- **State-aware**: lines are parameterized by streak length, drought length, and the
  leaderboard gap, so the humor visibly *builds* over rounds (escalating running gags).
- **Deterministic**: selection rotates through each bank with a per-bank counter rather
  than ``random.choice``, so regulars don't see repeats for ~``len(bank)`` fires (days, at
  the hourly ambient cadence) AND the tests are fully reproducible. Seed defaults to 0; the
  deployed bot seeds from the ambient slot index for cross-run variety.

Nothing here does I/O or touches the mesh — callers byte-budget-check every line before it
leaves the bot, exactly like ``host.py``.

POKE CALIBRATION ("casual pokes at people who aren't doing so well"):
pokes are friendly bar-banter that reference *observable facts* (wrong streaks, bottom of
the standings) — never a person's identity or worth. Brand-new players are never poked, and
a per-player cooldown stops Buzz riding one person hour after hour. See ``QuipEngine.poke``
and the bot's recap builder for the gating.
"""
from __future__ import annotations

from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Quip banks. Each ≥30 lines so regulars don't see repeats for days. Lines are
# format strings; available fields per bank are noted above each bank.
# ---------------------------------------------------------------------------

# WINNER: {name}. The previous question's winner (first correct on the ambient track,
# or the round winner in a rapid game). Praise, light swagger.
WINNER: List[str] = [
    "🏆 {name} took it. Textbook.",
    "🏆 {name} got there first. Reflexes of a caffeinated squirrel.",
    "✅ {name} nailed it before anyone else blinked.",
    "🏆 Ding ding ding — {name}.",
    "✅ {name} knew that one cold.",
    "🏆 {name} clears it. The mesh bows.",
    "✅ {name} — first and correct. Showoff.",
    "🏆 {name} snagged it. Buzz approves.",
    "✅ Locked in by {name}. Clean.",
    "🏆 {name} read the room and the answer.",
    "✅ {name} didn't even flinch. Correct.",
    "🏆 Point to {name}. Earned.",
    "✅ {name} beat the buzzer and the field.",
    "🏆 {name} makes it look easy.",
    "✅ {name} — that's how it's done.",
    "🏆 {name} called it. Chef's kiss.",
    "✅ {name} swooped in. Nice.",
    "🏆 {name} owns this one.",
    "✅ Smooth answer from {name}.",
    "🏆 {name} with the quick draw.",
    "✅ {name} knew it in their sleep.",
    "🏆 {name} on the board. Respect.",
    "✅ {name} tapped true. Well played.",
    "🏆 {name} solved it while you were still reading.",
    "✅ {name} — correct, and a little smug about it.",
    "🏆 Buzz tips the hat to {name}.",
    "✅ {name} delivered. No notes.",
    "🏆 {name} got it. Of course they did.",
    "✅ Big brain energy from {name}.",
    "🏆 {name} wins the round. Bow if you must.",
    "✅ {name} — sharp as ever.",
    "🏆 {name} nailed the landing.",
]

# STREAK_2: {name},{n}. Two correct in a row — first real streak. Light callout.
STREAK_2: List[str] = [
    "🔥 {name} on a 2-streak. Warming up.",
    "🔥 That's 2 straight for {name}. Eyes up, everyone.",
    "🔥 {name} back-to-back. A pattern emerges.",
    "🔥 Two in a row, {name}. Don't get cocky. (Get a little cocky.)",
    "🔥 {name} stringing them together — 2 now.",
    "🔥 {name} found a rhythm. 2 deep.",
    "🔥 Double up for {name}. The mesh notices.",
    "🔥 {name} x2. Somebody stop them. Nobody will.",
    "🔥 {name} on 2. Quietly dangerous.",
    "🔥 Two straight, {name}. Buzz is intrigued.",
    "🔥 {name} doubling down and cashing in. 2-streak.",
    "🔥 {name} just went 2-for-2. Tidy.",
    "🔥 Streak alert: {name} at 2.",
    "🔥 {name} keeps it rolling — 2.",
    "🔥 {name} with consecutive ws. Count: 2.",
    "🔥 {name} is 2 deep and climbing.",
    "🔥 Back-to-back {name}. The legend stirs.",
    "🔥 {name} on a heater. 2 so far.",
    "🔥 {name} stacked another. That's 2.",
    "🔥 2 straight for {name}. Bookmark this.",
    "🔥 {name} caught fire — 2 in a row.",
    "🔥 {name} times two. Watch this space.",
    "🔥 {name} riding 2. Smooth.",
    "🔥 {name} just made it 2. Hot start.",
    "🔥 {name} won't miss — 2 and counting.",
    "🔥 {name} on a mini-run. 2.",
    "🔥 Two-for-two, {name}. Sneaky good.",
    "🔥 {name} building something here. 2 deep.",
    "🔥 {name} keeps tapping true. Streak: 2.",
    "🔥 {name} at 2. The board trembles slightly.",
    "🔥 {name} doubled it. Respect creeping in.",
    "🔥 {name} — 2 straight, no sweat.",
]

# STREAK_3: {name},{n}. Three in a row — bigger celebration.
STREAK_3: List[str] = [
    "🔥🔥 THREE straight for {name}! This is a heater.",
    "🔥🔥 {name} hits 3 in a row. Somebody check the answer key for leaks.",
    "🔥🔥 {name} x3! The mesh has a problem and its name is {name}.",
    "🔥🔥 Hat trick, {name}! 3 and rolling.",
    "🔥🔥 {name} on 3. This is officially A Run.",
    "🔥🔥 Three consecutive, {name}. Buzz is sweating.",
    "🔥🔥 {name} just went 3-for-3. Unreal.",
    "🔥🔥 {name} at 3 straight. Throne behavior.",
    "🔥🔥 {name} can't be stopped — 3 deep!",
    "🔥🔥 Triple for {name}. The others are taking notes.",
    "🔥🔥 {name} x3 and showing zero mercy.",
    "🔥🔥 3 in a row, {name}! Save some for the rest of the mesh.",
    "🔥🔥 {name} is on THREE. Legendary trajectory.",
    "🔥🔥 {name} stacked a third. This is getting silly.",
    "🔥🔥 {name} hits 3! The leaderboard files a complaint.",
    "🔥🔥 Three straight and counting for {name}.",
    "🔥🔥 {name} on a 3-streak. Buzz is a fan now.",
    "🔥🔥 {name} just made it 3. Cold-blooded.",
    "🔥🔥 {name} x3. The mesh kneels.",
    "🔥🔥 Three for {name}! A genuine running gag forms.",
    "🔥🔥 {name} riding 3. This won't end well (for everyone else).",
    "🔥🔥 {name} keeps it perfect — 3 deep.",
    "🔥🔥 {name} at 3. History in real time.",
    "🔥🔥 {name} won't quit. 3 straight!",
    "🔥🔥 Triple-dip, {name}. Outrageous.",
    "🔥🔥 {name} 3-for-3 and grinning, probably.",
    "🔥🔥 {name} on three. The board is now a hostage.",
    "🔥🔥 {name} hits the hat trick. Bravo.",
    "🔥🔥 {name} x3 — buzzer's afraid of them now.",
    "🔥🔥 {name} 3 in a row. Sound the horns.",
    "🔥🔥 {name} at 3. Buzz is updating the record books.",
    "🔥🔥 Three straight, {name}. This is your hour.",
]

# STREAK_5: {name},{n}. Five-plus — maximum celebration; {n} interpolated for escalation.
STREAK_5: List[str] = [
    "👑 {n} IN A ROW for {name}?! Hand them the crown already.",
    "👑 {name} is on {n} straight. This is no longer trivia, it's a coronation.",
    "👑 {n}-streak, {name}! The mesh is officially a {name} fan club.",
    "👑 {name} x{n}. Somebody unplug them, it's only fair.",
    "👑 {name} hits {n} in a row. Buzz has questions. {name} has all the answers.",
    "👑 {n} STRAIGHT for {name}. Legend status: confirmed.",
    "👑 {name} on {n}! Nobody else even gets a turn anymore.",
    "👑 {name} at {n} consecutive. The leaderboard is just {name}'s diary now.",
    "👑 {n} in a row, {name}. We're naming a node after you.",
    "👑 {name} x{n}. The buzzer has filed a restraining order.",
    "👑 {name} riding a {n}-streak. This is folklore.",
    "👑 {name} hits {n}! Save some glory for the grandkids.",
    "👑 {n} straight, {name}. The mesh is yours. We just live here.",
    "👑 {name} on {n} and climbing. Send help (for everyone else).",
    "👑 {name} x{n}. Trivia has a final boss and it's {name}.",
    "👑 {n}-for-{n}, {name}. Buzz bows so low it hurts.",
    "👑 {name} at {n}! History is being typed in real time.",
    "👑 {name} on a {n}-streak. The questions surrender.",
    "👑 {n} in a row for {name}. We're in the {name} era now.",
    "👑 {name} x{n}. Statues will be commissioned.",
    "👑 {name} hits {n} straight. Absolutely diabolical.",
    "👑 {name} on {n}. The leaderboard gap is a canyon now.",
    "👑 {n} consecutive, {name}! Buzz is just narrating your highlight reel.",
    "👑 {name} won't stop. {n} deep and counting.",
    "👑 {name} at {n}. The other players are spectators.",
    "👑 {n} STRAIGHT, {name}. Frame this hour.",
    "👑 {name} x{n}. Even the crickets are impressed.",
    "👑 {name} on {n}! Somebody write a ballad.",
    "👑 {n}-streak {name}. The mesh trembles and applauds.",
    "👑 {name} hits {n}. Untouchable. Unbothered. Undefeated.",
    "👑 {name} at {n} in a row. Buzz concedes. You win the hour, the day, the mesh.",
    "👑 {n} for {name}! Legends only. Bow if you must.",
]

# NO_WINNER: {opt} = the answer text. Dry/funny reveal when nobody got it.
NO_WINNER: List[str] = [
    "🦗 Nobody. Brutal. It was {opt}.",
    "🦗 Crickets all around. The answer? {opt}.",
    "🦗 Zero correct. The question wins. It was {opt}.",
    "🦗 A clean sweep — for the question. {opt}, by the way.",
    "🦗 Nobody got it. {opt}. Now you know.",
    "🦗 Whiff city. It was {opt}.",
    "🦗 The mesh draws a blank. Answer: {opt}.",
    "🦗 Tough crowd, tougher question. {opt}.",
    "🦗 No takers. It was {opt}. Mark it down.",
    "🦗 Collective shrug detected. {opt}.",
    "🦗 Nada. The answer was {opt}.",
    "🦗 Swing and a miss, everyone. {opt}.",
    "🦗 That one stumped the whole mesh. {opt}.",
    "🦗 Goose egg. It was {opt}.",
    "🦗 Buzz wins this round by forfeit. {opt}.",
    "🦗 Nobody home. The answer: {opt}.",
    "🦗 The question goes undefeated. {opt}.",
    "🦗 Empty board. {opt} was the move.",
    "🦗 Not a single soul. {opt}.",
    "🦗 Hard pass from everyone. It was {opt}.",
    "🦗 The silence is deafening. {opt}.",
    "🦗 Zero for the mesh. {opt}, for the record.",
    "🦗 That one had teeth. {opt}.",
    "🦗 Big swing, big miss, all of you. {opt}.",
    "🦗 Buzz expected better. (Kidding.) {opt}.",
    "🦗 The answer hid well. {opt}.",
    "🦗 Nobody cracked it. {opt}.",
    "🦗 A humbling round. {opt}.",
    "🦗 The mesh blinked. It was {opt}.",
    "🦗 Clean miss across the board. {opt}.",
    "🦗 No glory this time. {opt}.",
    "🦗 The question takes the W. {opt}.",
]

# COMEBACK: {name},{n} = drought length in slots. Someone scores after a dry spell.
COMEBACK: List[str] = [
    "🎉 {name} is BACK! First one right in {n} rounds. Welcome home.",
    "🎉 Look who remembered how to win — {name}! ({n}-round drought, snapped.)",
    "🎉 {name} breaks the slump after {n}. The comeback is real.",
    "🎉 {name} returns to the winner's circle. Took {n} rounds.",
    "🎉 Dust off, {name} — that's your first in {n}!",
    "🎉 {name} ends the drought! {n} rounds of waiting, paid off.",
    "🎉 The {name} renaissance begins. {n}-round dry spell over.",
    "🎉 {name} found their footing again after {n}. Nice.",
    "🎉 {name} back on the board after {n} quiet rounds.",
    "🎉 Comeback szn for {name} — first in {n}.",
    "🎉 {name} shakes off {n} rounds of rust. Correct!",
    "🎉 {name} climbs out of the hole. {n} rounds, done.",
    "🎉 That's {name} ending a {n}-round cold streak. Warm again.",
    "🎉 {name} rises! {n}-round drought officially history.",
    "🎉 {name} got one! First in {n}. Buzz cheered a little.",
    "🎉 The wait is over, {name}. {n} rounds, finally a W.",
    "🎉 {name} snaps back after {n}. Don't call it a fluke.",
    "🎉 {name} reboots. {n}-round slump cleared.",
    "🎉 {name} re-enters the chat (correctly). {n}-round gap closed.",
    "🎉 {name} breaks through after {n}! Momentum, maybe.",
    "🎉 {name} off the schneid — {n} rounds, snapped.",
    "🎉 {name} back in business. {n}-round drought broken.",
    "🎉 {name} resurfaces with a correct one. {n} rounds later.",
    "🎉 {name} ends the cold spell. {n} rounds, gone.",
    "🎉 {name} got there! First in {n}. Welcome back to the light.",
    "🎉 {name} rallies after {n}. The mesh missed you.",
    "🎉 {name} turns it around — {n}-round drought done.",
    "🎉 {name} re-emerges victorious after {n}.",
    "🎉 {name} cracks one after {n} dry rounds. Redemption.",
    "🎉 {name} back from the wilderness. {n} rounds, over.",
    "🎉 {name} finally! {n}-round drought, demolished.",
    "🎉 {name} answers the bell after {n}. Comeback confirmed.",
]

# POKE: {name},{n} = wrong-streak length (or 0 if poked for bottom-of-board). Friendly
# bar-banter at strugglers — references the FACT, never the person. Gated hard by the bot
# (cooldown + new-player exemption + observable-facts-only). Spiciest stays kind.
POKE: List[str] = [
    "😏 {name}, that's {n} misses running. The questions are winning.",
    "😏 {name} on a {n}-question cold streak. We believe in you. Mostly.",
    "😏 Hey {name}, the answer button's the OTHER one. {n} in a row.",
    "😏 {name} at {n} straight misses. Buzz is rooting for the underdog (you).",
    "😏 {name}, {n} wrong in a row is almost a talent. Almost.",
    "😏 {name} keeps the streak alive — {n} misses. Bold strategy.",
    "😏 {name}, the leaderboard sent a search party. {n}-miss streak.",
    "😏 {name} bringing up the rear with style. {n} in a row.",
    "😏 {name}, {n} straight whiffs. The crickets know you by name.",
    "😏 Buzz to {name}: it's not the questions, it's... {n} misses.",
    "😏 {name} testing every wrong answer first. {n} down.",
    "😏 {name}, {n} misses deep. Process of elimination, eventually.",
    "😏 {name} holding the cellar steady. {n}-question slump.",
    "😏 {name}, at {n} wrong you're basically a control group.",
    "😏 {name} on {n} straight L's. Character building, this.",
    "😏 {name}, the right answer waved at you. {n} times.",
    "😏 {name} keeping the floor warm. {n} misses running.",
    "😏 {name}, {n} in a row wrong — that's commitment.",
    "😏 Buzz believes in {name}. The {n}-miss streak does not.",
    "😏 {name}, you've found {n} ways to not get it. Science!",
    "😏 {name} anchoring the standings again. {n}-question chill.",
    "😏 {name}, {n} straight. The buzzer feels bad for you (a little).",
    "😏 {name} on a {n}-miss heater. Of the wrong kind.",
    "😏 {name}, that's {n}. Even the dog at home is concerned.",
    "😏 {name} collecting wrong answers like trading cards. {n} now.",
    "😏 {name}, {n} misses. Have you tried the correct one?",
    "😏 {name} steady at the bottom. {n}-question slide.",
    "😏 {name}, {n} in a row — the comeback story writes itself. Eventually.",
    "😏 Buzz to {name}: {n} misses and a great attitude. One of those is improving.",
    "😏 {name}, the standings miss you up top. {n}-miss skid.",
    "😏 {name} on {n} wrong. Statistically, one's gotta land soon. Statistically.",
    "😏 {name}, {n} straight misses — you're not last, you're 'pre-first'.",
]

# Bottom-of-board pokes (no wrong-streak needed): {name},{gap} = points behind the leader.
POKE_BOTTOM: List[str] = [
    "😏 {name} parked at the bottom, {gap} behind the leader. Cozy down there?",
    "😏 {name}, the leader's {gap} points ahead. Just saying.",
    "😏 {name} holding last place hostage. {gap} back.",
    "😏 {name}, {gap} points off the pace. Plenty of room to climb.",
    "😏 {name} anchoring the board — {gap} behind. Someone's gotta.",
    "😏 {name}, you're {gap} back. The view from the bottom is... a view.",
    "😏 {name} keeping the cellar lights on. {gap} behind the top.",
    "😏 {name}, {gap} points back and counting. The leader says hi.",
    "😏 {name} at the foot of the table, {gap} adrift.",
    "😏 {name}, {gap} behind. This is your villain-origin moment.",
    "😏 {name} bringing up the rear, {gap} off the lead.",
    "😏 {name}, {gap} points down. The only way is up, mathematically.",
    "😏 {name} last but not least. Okay, mostly last. {gap} back.",
    "😏 {name}, the gap to first is {gap}. We're choosing to call it 'potential'.",
    "😏 {name} on the bottom rung, {gap} behind. Sturdy rung though.",
    "😏 {name}, {gap} points back. Buzz saved you a seat down here.",
    "😏 {name} holding down last, {gap} adrift. Loyalty, that is.",
    "😏 {name}, {gap} behind the leader. A challenge, not a verdict.",
    "😏 {name} at the base of the leaderboard. {gap} to climb.",
    "😏 {name}, {gap} back. Rome wasn't built in a round either.",
    "😏 {name} keeping last place company. {gap} off the top.",
    "😏 {name}, the leader's {gap} clear. Comeback fuel, that is.",
    "😏 {name} dwelling at the bottom, {gap} behind. For now.",
    "😏 {name}, {gap} down. The basement has good acoustics.",
    "😏 {name} last on the board, {gap} adrift. Underdog energy.",
    "😏 {name}, {gap} behind the pack-leader. Buzz is patient.",
    "😏 {name} propping up the standings, {gap} back.",
    "😏 {name}, {gap} points off first. The grind starts now.",
    "😏 {name} at the tail end, {gap} behind. Long game, right?",
    "😏 {name}, {gap} back from glory. Or at least from not-last.",
    "😏 {name} rooted to the bottom, {gap} adrift. We'll wait.",
    "😏 {name}, {gap} behind. Every legend starts in the cellar. Allegedly.",
]


class QuipEngine:
    """Deterministic, state-aware quip selector.

    Each bank cycles independently via a monotonic counter so a given bank's lines rotate
    through fully before repeating. ``seed`` shifts the starting point (the bot seeds it
    from the ambient slot index for cross-run variety; tests leave it 0 for reproducibility).
    """

    def __init__(self, seed: int = 0):
        self.seed = int(seed)
        self._counters: Dict[int, int] = {}

    def _pick(self, bank: List[str], **fmt) -> str:
        bank_key = id(bank)
        c = self._counters.get(bank_key, 0)
        self._counters[bank_key] = c + 1
        line = bank[(self.seed + c) % len(bank)]
        return line.format(**fmt)

    # ----- winner / streak escalation -----
    def winner(self, name: str, streak: int = 1) -> str:
        """Winner praise, escalating by correct-streak tier (2 / 3 / 5+)."""
        if streak >= 5:
            return self._pick(STREAK_5, name=name, n=streak)
        if streak >= 3:
            return self._pick(STREAK_3, name=name, n=streak)
        if streak >= 2:
            return self._pick(STREAK_2, name=name, n=streak)
        return self._pick(WINNER, name=name)

    def comeback(self, name: str, drought: int) -> str:
        return self._pick(COMEBACK, name=name, n=drought)

    def no_winner(self, opt: str) -> str:
        return self._pick(NO_WINNER, opt=opt)

    # ----- pokes -----
    def poke_streak(self, name: str, wrong_streak: int) -> str:
        return self._pick(POKE, name=name, n=wrong_streak)

    def poke_bottom(self, name: str, gap: int) -> str:
        return self._pick(POKE_BOTTOM, name=name, gap=gap)


# Convenience for callers that just want bank sizes (tests / docs).
BANK_SIZES = {
    "WINNER": len(WINNER), "STREAK_2": len(STREAK_2), "STREAK_3": len(STREAK_3),
    "STREAK_5": len(STREAK_5), "NO_WINNER": len(NO_WINNER), "COMEBACK": len(COMEBACK),
    "POKE": len(POKE), "POKE_BOTTOM": len(POKE_BOTTOM),
}
