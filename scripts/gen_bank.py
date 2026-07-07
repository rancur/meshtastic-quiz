#!/usr/bin/env python3
"""Programmatic mass question generation (v1.6.0) — correctness by construction.

Phase-2 mandate (Will): scale the ambient-eligible (med+hard) pool past **8,760** so a
LITERAL 365-day no-repeat holds at the hourly cadence. Hand-authoring ~8,000 verified
questions is infeasible without hallucinating, so instead we GENERATE them from sources where
correctness is guaranteed:

  * MATH — the answer is **computed** by this module (never recalled), and every distractor is
    a different number. Multiplication, division, powers, roots, percentages, Roman numerals,
    binary/hex conversion, primes, polygons, factorials, GCD/LCM, etc. Zero hallucination risk.
  * FACT TABLES — a single **vetted canonical table** (periodic table, world capitals, US state
    capitals, currencies, landmarks, NATO/Greek alphabets, verified Meshtastic/LoRa/RF facts).
    Every distractor is drawn from OTHER real rows of the same table, so it is guaranteed wrong.
    Ambiguous/volatile rows (dual capitals, unstable currencies, contested facts) were dropped.

Everything is emitted through the caller's ``add(cat, diff, q, opts, ans)`` (which de-dupes by
normalized question text) and then byte/schema-validated by ``build_questions.main()``. All
generated questions are tagged **hard** so the curated MEDIUM tier (the live competitive game)
stays pristine while the 24/7 ambient "challenging" pool (med+hard) gets the deep bank.

Deterministic: a fixed RNG seed makes the distractor choices + sampling reproducible, so a
rebuild produces a stable questions.json.
"""
from __future__ import annotations

import random
from math import factorial, gcd

_RNG = random.Random(20260706)
HARD = "hard"


# --------------------------------------------------------------------------------------
# core MC emitter: build 4 DISTINCT options containing the correct answer, place it randomly
# --------------------------------------------------------------------------------------
def _emit(add, cat, q, correct, distractor_candidates):
    """Emit one MC question if we can find 3 distinct wrong options; else silently skip."""
    correct_s = str(correct)
    cands = [str(d) for d in distractor_candidates]
    _RNG.shuffle(cands)
    seen = {correct_s}
    picked = []
    for c in cands:
        if c in seen:
            continue
        seen.add(c)
        picked.append(c)
        if len(picked) == 3:
            break
    if len(picked) < 3:
        return
    opts = picked + [correct_s]
    _RNG.shuffle(opts)
    add(cat, HARD, q, opts, opts.index(correct_s))


def _near_ints(v, *, positive=True):
    """A spread of plausible near-miss integers around ``v`` (for numeric distractors)."""
    v = int(v)
    deltas = [1, -1, 2, -2, 3, -3, 5, -5, 9, -9, 10, -10, 11, -11, 20, -20, 100, -100]
    out = []
    for d in deltas:
        x = v + d
        if (not positive) or x > 0:
            out.append(x)
    return out


# ======================================================================================
# MATH GENERATORS (answers computed → correct by construction)
# ======================================================================================
def gen_multiplication(add, cap):
    pairs = [(a, b) for a in range(12, 100) for b in range(a, 100)]
    _RNG.shuffle(pairs)
    n = 0
    for a, b in pairs:
        p = a * b
        cands = _near_ints(p) + [(a + 1) * b, (a - 1) * b, a * (b + 1), a * (b - 1)]
        _emit(add, "Math", f"What is {a} × {b}?", p, cands)
        n += 1
        if n >= cap:
            break


def gen_division(add, cap):
    pairs = [(a, b) for b in range(3, 40) for a in range(6, 100)]
    _RNG.shuffle(pairs)
    n = 0
    for a, b in pairs:
        p = a * b
        _emit(add, "Math", f"What is {p} ÷ {b}?", a, _near_ints(a))
        n += 1
        if n >= cap:
            break


def gen_addsub(add, cap):
    n = 0
    seen = set()
    while n < cap:
        a = _RNG.randint(137, 9987)
        b = _RNG.randint(114, 8899)
        if _RNG.random() < 0.5:
            key = ("+", a, b)
            if key in seen:
                continue
            seen.add(key)
            _emit(add, "Math", f"What is {a} + {b}?", a + b, _near_ints(a + b))
        else:
            hi, lo = max(a, b), min(a, b)
            key = ("-", hi, lo)
            if key in seen or hi == lo:
                continue
            seen.add(key)
            _emit(add, "Math", f"What is {hi} − {lo}?", hi - lo, _near_ints(hi - lo))
        n += 1


def gen_percent(add, cap):
    xs = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 80, 90]
    ys = [y for y in range(40, 2001, 20)]
    combos = [(x, y) for x in xs for y in ys]
    _RNG.shuffle(combos)
    n = 0
    for x, y in combos:
        r = x * y // 100
        if r <= 0:
            continue
        cands = _near_ints(r) + [r * 2, r // 2, r + y // 10, abs(r - y // 10)]
        _emit(add, "Math", f"What is {x}% of {y}?", r, cands)
        n += 1
        if n >= cap:
            break


def gen_squares(add, cap):
    n = 0
    for k in range(12, 100):
        s = k * k
        cands = [(k + 1) ** 2, (k - 1) ** 2, s + 2 * k, s - 2 * k] + _near_ints(s)
        _emit(add, "Math", f"What is {k} squared?", s, cands)
        n += 1
        if n >= cap:
            break


def gen_cubes(add, cap):
    n = 0
    for k in range(3, 40):
        c = k ** 3
        cands = [(k + 1) ** 3, (k - 1) ** 3, c + k * k, c - k * k] + _near_ints(c)
        _emit(add, "Math", f"What is {k} cubed?", c, cands)
        n += 1
        if n >= cap:
            break


def gen_roots(add, cap):
    n = 0
    for k in range(12, 100):
        _emit(add, "Math", f"What is the square root of {k * k}?", k, _near_ints(k))
        n += 1
        if n >= cap:
            break


def gen_powers(add, cap):
    specs = []
    for e in range(4, 21):
        specs.append((2, e))
    for e in range(3, 13):
        specs.append((3, e))
    for e in range(3, 9):
        specs.append((5, e))
    for e in range(3, 10):
        specs.append((10, e))
    _RNG.shuffle(specs)
    n = 0
    for b, e in specs:
        v = b ** e
        cands = [b ** (e + 1), b ** (e - 1), v * 2, v // 2, v + b, v - b] + _near_ints(v)
        _emit(add, "Math", f"What is {b} to the power of {e}?", v, cands)
        n += 1
        if n >= cap:
            break


_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _to_roman(num):
    out, n = [], num
    for val, sym in _ROMAN:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def gen_roman(add, cap):
    nums = list(range(1, 101)) + list(range(105, 400, 5)) + list(range(400, 2026, 15))
    _RNG.shuffle(nums)
    half = cap // 2
    n = 0
    for num in nums:                       # number -> roman
        r = _to_roman(num)
        dcands = [_to_roman(num + d) for d in (1, -1, 4, -4, 5, -5, 10, -10, 9, -9, 50, -50)
                  if num + d > 0]
        _emit(add, "Math", f"What is {num} in Roman numerals?", r, dcands)
        n += 1
        if n >= half:
            break
    _RNG.shuffle(nums)
    n = 0
    for num in nums:                       # roman -> number
        r = _to_roman(num)
        _emit(add, "Math", f"What number is the Roman numeral {r}?", num, _near_ints(num))
        n += 1
        if n >= cap - half:
            break


def gen_binary(add, cap):
    nums = list(range(2, 256))
    _RNG.shuffle(nums)
    half = cap // 2
    n = 0
    for num in nums:                       # decimal -> binary
        b = format(num, "b")
        dcands = [format(num + 1, "b"), format(num - 1, "b"), format(num ^ 1, "b"),
                  format(num ^ 2, "b"), format(num + 2, "b")]
        _emit(add, "Math", f"What is {num} in binary?", b, dcands)
        n += 1
        if n >= half:
            break
    _RNG.shuffle(nums)
    n = 0
    for num in nums:                       # binary -> decimal
        b = format(num, "b")
        _emit(add, "Math", f"What is binary {b} in decimal?", num, _near_ints(num))
        n += 1
        if n >= cap - half:
            break


def gen_hex(add, cap):
    nums = list(range(10, 256))
    _RNG.shuffle(nums)
    half = cap // 2
    n = 0
    for num in nums:                       # decimal -> hex
        h = format(num, "X")
        dcands = [format(num + 1, "X"), format(num - 1, "X"), format(num + 16, "X"),
                  format(abs(num - 16), "X"), format(num ^ 1, "X")]
        _emit(add, "Math", f"What is {num} in hexadecimal?", h, dcands)
        n += 1
        if n >= half:
            break
    _RNG.shuffle(nums)
    n = 0
    for num in nums:                       # hex -> decimal
        h = format(num, "X")
        _emit(add, "Math", f"What is hex {h} in decimal?", num, _near_ints(num))
        n += 1
        if n >= cap - half:
            break


def _is_prime(k):
    if k < 2:
        return False
    if k % 2 == 0:
        return k == 2
    i = 3
    while i * i <= k:
        if k % i == 0:
            return False
        i += 2
    return True


def gen_primes(add, cap):
    primes = [p for p in range(11, 998) if _is_prime(p)]
    _RNG.shuffle(primes)
    n = 0
    for p in primes:
        comps = []
        d = 1
        while len(comps) < 8 and d < 40:
            for cand in (p + d, p - d):
                if cand > 3 and not _is_prime(cand) and cand not in comps:
                    comps.append(cand)
            d += 1
        if len(comps) < 3:
            continue
        _emit(add, "Math", "Which of these numbers is prime?", p, comps)
        n += 1
        if n >= cap:
            break


_POLY = {3: "Triangle", 4: "Quadrilateral", 5: "Pentagon", 6: "Hexagon", 7: "Heptagon",
         8: "Octagon", 9: "Nonagon", 10: "Decagon", 11: "Hendecagon", 12: "Dodecagon",
         20: "Icosagon"}


def gen_polygons(add, cap):
    names = list(_POLY.values())
    n = 0
    for sides, name in _POLY.items():      # sides -> name and name -> sides
        others = [v for v in names if v != name]
        _emit(add, "Math", f"A polygon with {sides} sides is called a?", name, others)
        _emit(add, "Math", f"How many sides does a {name.lower()} have?", sides,
              _near_ints(sides))
        n += 2
    for sides in range(3, 21):             # interior angle sum
        s = (sides - 2) * 180
        cands = [s + 180, s - 180, s + 360, abs(s - 360), s + 90]
        _emit(add, "Math", f"Sum of interior angles of a {sides}-sided polygon?", s, cands)
        n += 1
        if n >= cap:
            break


def gen_factorials(add, cap):
    for k in range(3, 13):
        f = factorial(k)                    # correct k! (computed, not accumulated)
        cands = [factorial(k + 1), f // k, f * (k + 1), f + k, f - k] + _near_ints(f)
        _emit(add, "Math", f"What is {k} factorial ({k}!)?", f, cands)


def gen_gcd_lcm(add, cap):
    n = 0
    seen = set()
    while n < cap:
        a = _RNG.randint(6, 96)
        b = _RNG.randint(6, 96)
        if a == b or (a, b) in seen or (b, a) in seen:
            continue
        seen.add((a, b))
        g = gcd(a, b)
        lcm = a * b // g
        if _RNG.random() < 0.5:
            _emit(add, "Math", f"What is the greatest common divisor of {a} and {b}?", g,
                  _near_ints(g) + [1, a, b])
        else:
            _emit(add, "Math", f"What is the lowest common multiple of {a} and {b}?", lcm,
                  _near_ints(lcm) + [a * b, a + b])
        n += 1


def gen_misc_math(add):
    # place value / powers of ten
    zeros = {"one hundred": 2, "one thousand": 3, "ten thousand": 4, "one hundred thousand": 5,
             "one million": 6, "ten million": 7, "one billion": 9, "one trillion": 12}
    allz = list(zeros.values())
    for word, z in zeros.items():
        _emit(add, "Math", f"How many zeros are in {word}?", z, [x for x in allz if x != z] +
              _near_ints(z))
    # metric prefixes (value as power of ten count)
    metric = {"kilo": 3, "mega": 6, "giga": 9, "tera": 12, "hecto": 2, "deca": 1}
    for name, z in metric.items():
        _emit(add, "Math", f"The prefix '{name}' means ten to the power of?", z,
              [v for v in metric.values() if v != z] + _near_ints(z))
    # time units
    time_units = [("seconds in a minute", 60), ("minutes in an hour", 60),
                  ("hours in a day", 24), ("days in a week", 7), ("months in a year", 12),
                  ("seconds in an hour", 3600), ("minutes in a day", 1440),
                  ("days in a leap year", 366), ("weeks in a year", 52),
                  ("seconds in a day", 86400), ("hours in a week", 168)]
    for label, v in time_units:
        _emit(add, "Math", f"How many {label}?", v, _near_ints(v) + [v * 2, v // 2])


# ======================================================================================
# FACT-TABLE GENERATORS (distractors = other real rows → guaranteed wrong)
# ======================================================================================
# Periodic table: (Z, symbol, name). Verified — names/symbols 100-118 confirmed vs the IUPAC
# list; 1-99 are stable canonical chemistry.
_ELEMENTS = [
    (1, "H", "Hydrogen"), (2, "He", "Helium"), (3, "Li", "Lithium"), (4, "Be", "Beryllium"),
    (5, "B", "Boron"), (6, "C", "Carbon"), (7, "N", "Nitrogen"), (8, "O", "Oxygen"),
    (9, "F", "Fluorine"), (10, "Ne", "Neon"), (11, "Na", "Sodium"), (12, "Mg", "Magnesium"),
    (13, "Al", "Aluminium"), (14, "Si", "Silicon"), (15, "P", "Phosphorus"), (16, "S", "Sulfur"),
    (17, "Cl", "Chlorine"), (18, "Ar", "Argon"), (19, "K", "Potassium"), (20, "Ca", "Calcium"),
    (21, "Sc", "Scandium"), (22, "Ti", "Titanium"), (23, "V", "Vanadium"), (24, "Cr", "Chromium"),
    (25, "Mn", "Manganese"), (26, "Fe", "Iron"), (27, "Co", "Cobalt"), (28, "Ni", "Nickel"),
    (29, "Cu", "Copper"), (30, "Zn", "Zinc"), (31, "Ga", "Gallium"), (32, "Ge", "Germanium"),
    (33, "As", "Arsenic"), (34, "Se", "Selenium"), (35, "Br", "Bromine"), (36, "Kr", "Krypton"),
    (37, "Rb", "Rubidium"), (38, "Sr", "Strontium"), (39, "Y", "Yttrium"), (40, "Zr", "Zirconium"),
    (41, "Nb", "Niobium"), (42, "Mo", "Molybdenum"), (43, "Tc", "Technetium"), (44, "Ru", "Ruthenium"),
    (45, "Rh", "Rhodium"), (46, "Pd", "Palladium"), (47, "Ag", "Silver"), (48, "Cd", "Cadmium"),
    (49, "In", "Indium"), (50, "Sn", "Tin"), (51, "Sb", "Antimony"), (52, "Te", "Tellurium"),
    (53, "I", "Iodine"), (54, "Xe", "Xenon"), (55, "Cs", "Caesium"), (56, "Ba", "Barium"),
    (57, "La", "Lanthanum"), (58, "Ce", "Cerium"), (59, "Pr", "Praseodymium"), (60, "Nd", "Neodymium"),
    (61, "Pm", "Promethium"), (62, "Sm", "Samarium"), (63, "Eu", "Europium"), (64, "Gd", "Gadolinium"),
    (65, "Tb", "Terbium"), (66, "Dy", "Dysprosium"), (67, "Ho", "Holmium"), (68, "Er", "Erbium"),
    (69, "Tm", "Thulium"), (70, "Yb", "Ytterbium"), (71, "Lu", "Lutetium"), (72, "Hf", "Hafnium"),
    (73, "Ta", "Tantalum"), (74, "W", "Tungsten"), (75, "Re", "Rhenium"), (76, "Os", "Osmium"),
    (77, "Ir", "Iridium"), (78, "Pt", "Platinum"), (79, "Au", "Gold"), (80, "Hg", "Mercury"),
    (81, "Tl", "Thallium"), (82, "Pb", "Lead"), (83, "Bi", "Bismuth"), (84, "Po", "Polonium"),
    (85, "At", "Astatine"), (86, "Rn", "Radon"), (87, "Fr", "Francium"), (88, "Ra", "Radium"),
    (89, "Ac", "Actinium"), (90, "Th", "Thorium"), (91, "Pa", "Protactinium"), (92, "U", "Uranium"),
    (93, "Np", "Neptunium"), (94, "Pu", "Plutonium"), (95, "Am", "Americium"), (96, "Cm", "Curium"),
    (97, "Bk", "Berkelium"), (98, "Cf", "Californium"), (99, "Es", "Einsteinium"), (100, "Fm", "Fermium"),
    (101, "Md", "Mendelevium"), (102, "No", "Nobelium"), (103, "Lr", "Lawrencium"),
    (104, "Rf", "Rutherfordium"), (105, "Db", "Dubnium"), (106, "Sg", "Seaborgium"),
    (107, "Bh", "Bohrium"), (108, "Hs", "Hassium"), (109, "Mt", "Meitnerium"),
    (110, "Ds", "Darmstadtium"), (111, "Rg", "Roentgenium"), (112, "Cn", "Copernicium"),
    (113, "Nh", "Nihonium"), (114, "Fl", "Flerovium"), (115, "Mc", "Moscovium"),
    (116, "Lv", "Livermorium"), (117, "Ts", "Tennessine"), (118, "Og", "Oganesson"),
]


def gen_elements(add):
    syms = [e[1] for e in _ELEMENTS]
    names = [e[2] for e in _ELEMENTS]
    znums = [e[0] for e in _ELEMENTS]
    for z, sym, name in _ELEMENTS:
        _emit(add, "Science", f"What is the chemical symbol for {name}?", sym,
              [s for s in syms if s != sym])
        _emit(add, "Science", f"Which element has the symbol {sym}?", name,
              [nm for nm in names if nm != name])
        _emit(add, "Science", f"What is the atomic number of {name}?", z,
              [x for x in znums if x != z] + _near_ints(z))
        _emit(add, "Science", f"Which element has atomic number {z}?", name,
              [nm for nm in names if nm != name])


# World capitals — curated to countries with a SINGLE unambiguous capital (dual-capital or
# recently-contested ones deliberately dropped). Changed capitals verified 2026-07-06.
_CAPITALS = {
    "Afghanistan": "Kabul", "Albania": "Tirana", "Algeria": "Algiers", "Angola": "Luanda",
    "Argentina": "Buenos Aires", "Armenia": "Yerevan", "Australia": "Canberra", "Austria": "Vienna",
    "Azerbaijan": "Baku", "Bahamas": "Nassau", "Bahrain": "Manama", "Bangladesh": "Dhaka",
    "Belarus": "Minsk", "Belgium": "Brussels", "Bhutan": "Thimphu", "Botswana": "Gaborone",
    "Brazil": "Brasilia", "Bulgaria": "Sofia", "Cambodia": "Phnom Penh", "Cameroon": "Yaounde",
    "Canada": "Ottawa", "Chile": "Santiago", "China": "Beijing", "Colombia": "Bogota",
    "Costa Rica": "San Jose", "Croatia": "Zagreb", "Cuba": "Havana", "Cyprus": "Nicosia",
    "Czechia": "Prague", "Denmark": "Copenhagen", "Dominican Republic": "Santo Domingo",
    "Ecuador": "Quito", "Egypt": "Cairo", "El Salvador": "San Salvador", "Estonia": "Tallinn",
    "Ethiopia": "Addis Ababa", "Fiji": "Suva", "Finland": "Helsinki", "France": "Paris",
    "Georgia": "Tbilisi", "Germany": "Berlin", "Ghana": "Accra", "Greece": "Athens",
    "Guatemala": "Guatemala City", "Honduras": "Tegucigalpa", "Hungary": "Budapest",
    "Iceland": "Reykjavik", "India": "New Delhi", "Indonesia": "Jakarta", "Iran": "Tehran",
    "Iraq": "Baghdad", "Ireland": "Dublin", "Italy": "Rome", "Ivory Coast": "Yamoussoukro",
    "Jamaica": "Kingston", "Japan": "Tokyo", "Jordan": "Amman", "Kazakhstan": "Astana",
    "Kenya": "Nairobi", "Kuwait": "Kuwait City", "Laos": "Vientiane", "Latvia": "Riga",
    "Lebanon": "Beirut", "Libya": "Tripoli", "Lithuania": "Vilnius", "Luxembourg": "Luxembourg",
    "Madagascar": "Antananarivo", "Malaysia": "Kuala Lumpur", "Mali": "Bamako", "Malta": "Valletta",
    "Mexico": "Mexico City", "Mongolia": "Ulaanbaatar", "Morocco": "Rabat", "Mozambique": "Maputo",
    "Myanmar": "Nay Pyi Taw", "Namibia": "Windhoek", "Nepal": "Kathmandu", "Netherlands": "Amsterdam",
    "New Zealand": "Wellington", "Nicaragua": "Managua", "Nigeria": "Abuja", "North Korea": "Pyongyang",
    "Norway": "Oslo", "Oman": "Muscat", "Pakistan": "Islamabad", "Panama": "Panama City",
    "Paraguay": "Asuncion", "Peru": "Lima", "Philippines": "Manila", "Poland": "Warsaw",
    "Portugal": "Lisbon", "Qatar": "Doha", "Romania": "Bucharest", "Russia": "Moscow",
    "Rwanda": "Kigali", "Saudi Arabia": "Riyadh", "Senegal": "Dakar", "Serbia": "Belgrade",
    "Singapore": "Singapore", "Slovakia": "Bratislava", "Slovenia": "Ljubljana", "Somalia": "Mogadishu",
    "South Korea": "Seoul", "Spain": "Madrid", "Sudan": "Khartoum", "Sweden": "Stockholm",
    "Switzerland": "Bern", "Syria": "Damascus", "Taiwan": "Taipei", "Tanzania": "Dodoma",
    "Thailand": "Bangkok", "Tunisia": "Tunis", "Turkey": "Ankara", "Turkmenistan": "Ashgabat",
    "Uganda": "Kampala", "Ukraine": "Kyiv", "United Arab Emirates": "Abu Dhabi",
    "United Kingdom": "London", "Uruguay": "Montevideo", "Uzbekistan": "Tashkent",
    "Venezuela": "Caracas", "Vietnam": "Hanoi", "Yemen": "Sanaa", "Zambia": "Lusaka",
}


def gen_capitals(add):
    countries = list(_CAPITALS.keys())
    caps = list(_CAPITALS.values())
    for country, cap in _CAPITALS.items():
        _emit(add, "Geography", f"What is the capital of {country}?", cap,
              [c for c in caps if c != cap])
        _emit(add, "Geography", f"{cap} is the capital of which country?", country,
              [c for c in countries if c != country])


# Currency by country — name is stable even across redenominations; unstable ones dropped.
_CURRENCIES = {
    "Japan": "Yen", "China": "Yuan", "United Kingdom": "Pound", "India": "Rupee", "Russia": "Ruble",
    "United States": "Dollar", "Mexico": "Peso", "Brazil": "Real", "South Korea": "Won",
    "Thailand": "Baht", "Vietnam": "Dong", "Sweden": "Krona", "Norway": "Krone", "Denmark": "Krone",
    "Switzerland": "Franc", "Poland": "Zloty", "Turkey": "Lira", "Israel": "Shekel",
    "Saudi Arabia": "Riyal", "Qatar": "Riyal", "United Arab Emirates": "Dirham", "South Africa": "Rand",
    "Nigeria": "Naira", "Ghana": "Cedi", "Kenya": "Shilling", "Indonesia": "Rupiah",
    "Malaysia": "Ringgit", "Pakistan": "Rupee", "Bangladesh": "Taka", "Iraq": "Dinar",
    "Kuwait": "Dinar", "Czechia": "Koruna", "Hungary": "Forint", "Ukraine": "Hryvnia",
    "Argentina": "Peso", "Chile": "Peso", "Peru": "Sol", "Canada": "Dollar", "Australia": "Dollar",
    "New Zealand": "Dollar", "Iceland": "Krona", "Romania": "Leu", "Serbia": "Dinar",
    "France": "Euro", "Germany": "Euro", "Italy": "Euro", "Spain": "Euro", "Greece": "Euro",
    "Ethiopia": "Birr", "Egypt": "Pound", "Morocco": "Dirham", "Philippines": "Peso",
    "Mongolia": "Tugrik", "Kazakhstan": "Tenge", "Venezuela": "Bolivar",
}


def gen_currencies(add):
    curr = list(set(_CURRENCIES.values()))
    for country, c in _CURRENCIES.items():
        _emit(add, "Geography", f"What is the currency of {country}?", c,
              [x for x in curr if x != c])


# US state capitals + postal abbreviations (canonical).
_US_STATES = [
    ("Alabama", "Montgomery", "AL"), ("Alaska", "Juneau", "AK"), ("Arizona", "Phoenix", "AZ"),
    ("Arkansas", "Little Rock", "AR"), ("California", "Sacramento", "CA"), ("Colorado", "Denver", "CO"),
    ("Connecticut", "Hartford", "CT"), ("Delaware", "Dover", "DE"), ("Florida", "Tallahassee", "FL"),
    ("Georgia", "Atlanta", "GA"), ("Hawaii", "Honolulu", "HI"), ("Idaho", "Boise", "ID"),
    ("Illinois", "Springfield", "IL"), ("Indiana", "Indianapolis", "IN"), ("Iowa", "Des Moines", "IA"),
    ("Kansas", "Topeka", "KS"), ("Kentucky", "Frankfort", "KY"), ("Louisiana", "Baton Rouge", "LA"),
    ("Maine", "Augusta", "ME"), ("Maryland", "Annapolis", "MD"), ("Massachusetts", "Boston", "MA"),
    ("Michigan", "Lansing", "MI"), ("Minnesota", "Saint Paul", "MN"), ("Mississippi", "Jackson", "MS"),
    ("Missouri", "Jefferson City", "MO"), ("Montana", "Helena", "MT"), ("Nebraska", "Lincoln", "NE"),
    ("Nevada", "Carson City", "NV"), ("New Hampshire", "Concord", "NH"), ("New Jersey", "Trenton", "NJ"),
    ("New Mexico", "Santa Fe", "NM"), ("New York", "Albany", "NY"), ("North Carolina", "Raleigh", "NC"),
    ("North Dakota", "Bismarck", "ND"), ("Ohio", "Columbus", "OH"), ("Oklahoma", "Oklahoma City", "OK"),
    ("Oregon", "Salem", "OR"), ("Pennsylvania", "Harrisburg", "PA"), ("Rhode Island", "Providence", "RI"),
    ("South Carolina", "Columbia", "SC"), ("South Dakota", "Pierre", "SD"), ("Tennessee", "Nashville", "TN"),
    ("Texas", "Austin", "TX"), ("Utah", "Salt Lake City", "UT"), ("Vermont", "Montpelier", "VT"),
    ("Virginia", "Richmond", "VA"), ("Washington", "Olympia", "WA"), ("West Virginia", "Charleston", "WV"),
    ("Wisconsin", "Madison", "WI"), ("Wyoming", "Cheyenne", "WY"),
]


def gen_us_states(add):
    caps = [s[1] for s in _US_STATES]
    names = [s[0] for s in _US_STATES]
    abbrs = [s[2] for s in _US_STATES]
    for name, cap, ab in _US_STATES:
        _emit(add, "Geography", f"What is the capital of {name} (US state)?", cap,
              [c for c in caps if c != cap])
        _emit(add, "Geography", f"{cap} is the capital of which US state?", name,
              [n for n in names if n != name])
        _emit(add, "Geography", f"What is the US postal abbreviation for {name}?", ab,
              [a for a in abbrs if a != ab])


# Landmark -> country (canonical, unambiguous).
_LANDMARKS = {
    "the Eiffel Tower": "France", "the Colosseum": "Italy", "the Great Wall": "China",
    "the Taj Mahal": "India", "the Statue of Liberty": "United States",
    "Christ the Redeemer": "Brazil", "Machu Picchu": "Peru", "the Pyramids of Giza": "Egypt",
    "the Sydney Opera House": "Australia", "the Leaning Tower of Pisa": "Italy",
    "the Acropolis": "Greece", "Petra": "Jordan", "Angkor Wat": "Cambodia",
    "Stonehenge": "United Kingdom", "the Sagrada Familia": "Spain", "the Brandenburg Gate": "Germany",
    "the Burj Khalifa": "United Arab Emirates", "Mount Fuji": "Japan", "the Kremlin": "Russia",
    "the Golden Gate Bridge": "United States", "the Little Mermaid statue": "Denmark",
    "Table Mountain": "South Africa", "the Blue Mosque": "Turkey", "Chichen Itza": "Mexico",
}


def gen_landmarks(add):
    countries = list(set(_LANDMARKS.values()))
    for lm, country in _LANDMARKS.items():
        _emit(add, "Geography", f"In which country is {lm}?", country,
              [c for c in countries if c != country])


def gen_geo_superlatives(add):
    facts = [
        ("Which is the largest ocean?", "Pacific", ["Atlantic", "Indian", "Arctic", "Southern"]),
        ("Which is the smallest ocean?", "Arctic", ["Atlantic", "Indian", "Pacific", "Southern"]),
        ("Which is the largest country by area?", "Russia", ["Canada", "China", "USA", "Brazil"]),
        ("Which is the largest island in the world?", "Greenland",
         ["New Guinea", "Borneo", "Madagascar", "Iceland"]),
        ("The world's tallest mountain above sea level is?", "Mount Everest",
         ["K2", "Denali", "Kilimanjaro", "Mont Blanc"]),
        ("The largest hot desert on Earth is the?", "Sahara",
         ["Gobi", "Kalahari", "Mojave", "Atacama"]),
        ("The deepest lake on Earth is?", "Lake Baikal",
         ["Lake Superior", "Lake Tanganyika", "Caspian Sea", "Lake Victoria"]),
        ("The longest river in Africa is the?", "Nile", ["Congo", "Niger", "Zambezi", "Orange"]),
        ("The largest lake by area is the?", "Caspian Sea",
         ["Lake Superior", "Lake Victoria", "Lake Baikal", "Lake Huron"]),
        ("The highest waterfall in the world is?", "Angel Falls",
         ["Niagara Falls", "Victoria Falls", "Iguazu Falls", "Yosemite Falls"]),
        ("The largest continent by area is?", "Asia",
         ["Africa", "North America", "Europe", "Antarctica"]),
        ("The tallest mountain in Africa is?", "Kilimanjaro",
         ["Mount Kenya", "Atlas", "Mount Meru", "Ras Dashen"]),
    ]
    for q, correct, distractors in facts:
        _emit(add, "Geography", q, correct, distractors)


def gen_planets(add):
    order = ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
    ordinals = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"]
    for i, planet in enumerate(order):
        _emit(add, "Space", f"Which planet is the {ordinals[i]} from the Sun?", planet,
              [p for p in order if p != planet])
    extra = [
        ("Largest planet in the solar system?", "Jupiter", ["Saturn", "Neptune", "Uranus", "Earth"]),
        ("Smallest planet in the solar system?", "Mercury", ["Mars", "Venus", "Pluto", "Earth"]),
        ("Hottest planet in the solar system?", "Venus", ["Mercury", "Mars", "Jupiter", "Earth"]),
        ("Which planet has the most prominent ring system?", "Saturn",
         ["Jupiter", "Uranus", "Neptune", "Mars"]),
        ("Which planet is known as the Red Planet?", "Mars", ["Venus", "Jupiter", "Mercury", "Saturn"]),
    ]
    for q, correct, distractors in extra:
        _emit(add, "Space", q, correct, distractors)


_NATO = {"A": "Alfa", "B": "Bravo", "C": "Charlie", "D": "Delta", "E": "Echo", "F": "Foxtrot",
         "G": "Golf", "H": "Hotel", "I": "India", "J": "Juliett", "K": "Kilo", "L": "Lima",
         "M": "Mike", "N": "November", "O": "Oscar", "P": "Papa", "Q": "Quebec", "R": "Romeo",
         "S": "Sierra", "T": "Tango", "U": "Uniform", "V": "Victor", "W": "Whiskey", "X": "X-ray",
         "Y": "Yankee", "Z": "Zulu"}


def gen_nato(add):
    words = list(_NATO.values())
    for letter, word in _NATO.items():
        _emit(add, "General", f"In the NATO phonetic alphabet, what stands for '{letter}'?", word,
              [w for w in words if w != word])


_GREEK = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta", "Iota", "Kappa",
          "Lambda", "Mu", "Nu", "Xi", "Omicron", "Pi", "Rho", "Sigma", "Tau", "Upsilon", "Phi",
          "Chi", "Psi", "Omega"]


def gen_greek(add):
    for i in range(len(_GREEK) - 1):
        _emit(add, "General", f"Which Greek letter comes immediately after {_GREEK[i]}?",
              _GREEK[i + 1], [g for g in _GREEK if g != _GREEK[i + 1] and g != _GREEK[i]])


def gen_chemistry(add):
    compounds = {"H2O": "Water", "CO2": "Carbon dioxide", "NaCl": "Table salt", "O2": "Oxygen",
                 "CH4": "Methane", "NH3": "Ammonia", "CO": "Carbon monoxide", "O3": "Ozone",
                 "H2O2": "Hydrogen peroxide", "NaOH": "Sodium hydroxide", "HCl": "Hydrochloric acid",
                 "N2": "Nitrogen gas", "CaCO3": "Calcium carbonate", "H2SO4": "Sulfuric acid",
                 "C6H12O6": "Glucose"}
    names = list(compounds.values())
    formulas = list(compounds.keys())
    for f, name in compounds.items():
        _emit(add, "Science", f"What common substance has the chemical formula {f}?", name,
              [n for n in names if n != name])
        _emit(add, "Science", f"What is the chemical formula for {name.lower()}?", f,
              [x for x in formulas if x != f])
    groups = [
        ("Which of these is a noble gas?", "Neon", ["Sodium", "Iron", "Oxygen"]),
        ("Which of these is an alkali metal?", "Potassium", ["Calcium", "Sulfur", "Argon"]),
        ("Which of these is a halogen?", "Chlorine", ["Helium", "Copper", "Carbon"]),
        ("Which element is a liquid metal at room temperature?", "Mercury",
         ["Lead", "Sodium", "Tin"]),
        ("Which gas is most abundant in Earth's atmosphere?", "Nitrogen",
         ["Oxygen", "Carbon dioxide", "Argon"]),
    ]
    for q, correct, distractors in groups:
        _emit(add, "Science", q, correct, distractors)


def gen_mesh_rf(add):
    # Meshtastic LoRa preset table verified vs meshtastic.org radio-settings (2026-07-06):
    # ShortTurbo SF7/500, ShortFast SF7/250, ShortSlow SF8/250, MediumFast SF9/250,
    # MediumSlow SF10/250, LongTurbo SF11/500, LongFast SF11/250, LongModerate SF11/125,
    # LongSlow SF12/125. Coding rate 4/5 on the "fast" presets, 4/8 on Turbo/Moderate/Slow.
    facts = [
        ("Short Turbo preset spreading factor?", "SF7", ["SF9", "SF11", "SF12"]),
        ("Medium Slow preset spreading factor?", "SF10", ["SF8", "SF11", "SF12"]),
        ("Long Turbo preset spreading factor?", "SF11", ["SF7", "SF9", "SF12"]),
        ("Long Moderate preset bandwidth?", "125 kHz", ["250 kHz", "500 kHz", "62 kHz"]),
        ("Medium Fast preset bandwidth?", "250 kHz", ["125 kHz", "500 kHz", "62 kHz"]),
        ("Which preset uses SF12?", "Long Slow", ["Long Fast", "Medium Slow", "Short Slow"]),
        ("Which preset uses 500 kHz bandwidth and SF7?", "Short Turbo",
         ["Short Fast", "Long Fast", "Medium Fast"]),
        ("Coding rate on the Long Fast preset?", "4/5", ["4/8", "1/2", "7/8"]),
        ("Meshtastic firmware targets mainly which MCU families?", "ESP32 and nRF52",
         ["AVR and PIC", "x86 and ARM64", "MSP430 and STM8"]),
        ("What does LoRa stand for?", "Long Range", ["Low Radio", "Local Relay", "Long Radio"]),
        ("The unit of radio frequency is the?", "Hertz", ["Watt", "Volt", "Decibel"]),
        ("Wavelength multiplied by frequency equals?", "Speed of light",
         ["Bandwidth", "Amplitude", "Impedance"]),
        ("A higher radio frequency generally means a shorter?", "Wavelength",
         ["Antenna gain", "Bit rate", "Battery life"]),
        ("VHF stands for?", "Very High Frequency",
         ["Variable High Frequency", "Vertical Hertz Field", "Voice Hz Format"]),
        ("UHF stands for?", "Ultra High Frequency",
         ["Universal Hertz Field", "Upper Hz Frame", "Ultra Hertz Flux"]),
        ("Amateur (ham) radio Q-code 'QTH' refers to your?", "Location",
         ["Callsign", "Signal report", "Frequency"]),
        ("Ham radio Q-code 'QRZ?' asks?", "Who is calling me?",
         ["What is your name?", "Where are you?", "Can you repeat?"]),
        ("In radio, '73' is shorthand for?", "Best regards",
         ["Say again", "Emergency", "Over and out"]),
        ("Antenna gain is expressed in?", "dBi", ["Hertz", "Ohms", "Watts"]),
        ("Impedance of most ham/LoRa coax and antennas is?", "50 ohms",
         ["75 ohms", "100 ohms", "600 ohms"]),
    ]
    for q, correct, distractors in facts:
        _emit(add, "Mesh", q, correct, distractors)


# --------------------------------------------------------------------------------------
# orchestrator
# --------------------------------------------------------------------------------------
def generate(add):
    """Run every generator, emitting through ``add`` (which de-dupes). Caps chosen so the
    ambient (med+hard) pool clears ~9,000 after de-dupe — well over the 8,760 literal-year line.
    """
    # fact tables first (highest value; guaranteed-correct rows)
    gen_elements(add)
    gen_capitals(add)
    gen_currencies(add)
    gen_us_states(add)
    gen_landmarks(add)
    gen_geo_superlatives(add)
    gen_planets(add)
    gen_nato(add)
    gen_greek(add)
    gen_chemistry(add)
    gen_mesh_rf(add)
    # computed math (bulk of the volume; correct by construction)
    gen_multiplication(add, 2500)
    gen_division(add, 1100)
    gen_addsub(add, 1100)
    gen_percent(add, 950)
    gen_roman(add, 720)
    gen_binary(add, 520)
    gen_hex(add, 320)
    gen_squares(add, 99)
    gen_cubes(add, 39)
    gen_roots(add, 99)
    gen_powers(add, 60)
    gen_primes(add, 320)
    gen_polygons(add, 60)
    gen_factorials(add, 12)
    gen_gcd_lcm(add, 220)
    gen_misc_math(add)


if __name__ == "__main__":
    _preview = []
    generate(lambda c, d, q, o, a: _preview.append((c, d, q, o, a)))
    print(f"generated {len(_preview)} questions (pre-dedupe/validation)")
