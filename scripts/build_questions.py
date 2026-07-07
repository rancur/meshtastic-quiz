#!/usr/bin/env python3
"""Generate / validate the Meshtastic Quiz question bank.

The questions are authored here (curated, single-correct, 4 short options) and written to
``meshquiz/data/questions.json``. Every rendered question+options is byte-budget validated
before writing; anything over budget is reported and the build fails.

Monthly refresh: edit/extend the QUESTIONS list (or append a new month's batch), then run
``python scripts/build_questions.py`` again. CI / the deploy step re-runs validation.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from meshquiz.questions import Question, validate_bank  # noqa: E402

# Each entry: (category, difficulty, question, [opt1,opt2,opt3,opt4], answer_index)
# Keep questions + options SHORT — they must render within 200 UTF-8 bytes.
Q = []
_SEEN = set()  # normalized question texts already added (global de-dupe: hand + generated)


def add(cat, diff, q, opts, ans):
    # De-dupe by normalized question text so hand-authored and PROGRAMMATICALLY-generated
    # questions never collide (the generator relies on this to skip repeats). Same key the
    # bank's duplicate check + the no-repeat history use.
    key = q.strip().lower()
    if key in _SEEN:
        return
    _SEEN.add(key)
    Q.append({"category": cat, "difficulty": diff, "question": q, "options": opts, "answer": ans})


# ---------------- SCIENCE ----------------
add("Science", "easy", "What gas do plants absorb?", ["Oxygen", "CO2", "Nitrogen", "Helium"], 1)
add("Science", "easy", "What is H2O?", ["Salt", "Water", "Acid", "Sugar"], 1)
add("Science", "easy", "How many bones in adult human body?", ["106", "206", "306", "150"], 1)
add("Science", "easy", "What planet is the Red Planet?", ["Venus", "Mars", "Jupiter", "Saturn"], 1)
add("Science", "med", "Speed of light approx (km/s)?", ["3k", "30k", "300k", "3M"], 2)
add("Science", "med", "What organ pumps blood?", ["Liver", "Lung", "Heart", "Kidney"], 2)
add("Science", "med", "Chemical symbol for gold?", ["Go", "Gd", "Au", "Ag"], 2)
add("Science", "med", "Powerhouse of the cell?", ["Nucleus", "Ribosome", "Mitochondria", "Golgi"], 2)
add("Science", "hard", "Who proposed general relativity?", ["Newton", "Einstein", "Bohr", "Hawking"], 1)
add("Science", "hard", "Hardest natural substance?", ["Iron", "Quartz", "Diamond", "Titanium"], 2)
add("Science", "easy", "What do bees make?", ["Milk", "Honey", "Silk", "Wax only"], 1)
add("Science", "med", "Closest star to Earth?", ["Sirius", "Sun", "Vega", "Polaris"], 1)
add("Science", "med", "What is frozen water?", ["Steam", "Ice", "Mist", "Snow only"], 1)
add("Science", "hard", "Number of elements (approx)?", ["88", "98", "118", "150"], 2)
add("Science", "med", "Gas most abundant in air?", ["Oxygen", "CO2", "Nitrogen", "Argon"], 2)
add("Science", "easy", "Largest planet?", ["Earth", "Mars", "Jupiter", "Neptune"], 2)
add("Science", "med", "What measures earthquakes?", ["Barometer", "Richter", "Thermo", "Geiger"], 1)
add("Science", "hard", "DNA stands for?", ["Deoxyribo NA", "Di-Nitro A", "Double NA", "Dyna NA"], 0)
add("Science", "easy", "Animals that lay eggs and fly?", ["Fish", "Birds", "Cats", "Snakes"], 1)
add("Science", "med", "Light from Sun takes ~? to Earth", ["8 sec", "8 min", "8 hr", "8 day"], 1)

# ---------------- HISTORY ----------------
add("History", "easy", "Who was first US president?", ["Lincoln", "Washington", "Adams", "Jefferson"], 1)
add("History", "med", "WWII ended in what year?", ["1918", "1939", "1945", "1950"], 2)
add("History", "med", "Great Wall is in?", ["India", "China", "Japan", "Korea"], 1)
add("History", "hard", "Who painted the Mona Lisa?", ["Raphael", "Da Vinci", "Monet", "Picasso"], 1)
add("History", "med", "Ancient pyramids built by?", ["Romans", "Greeks", "Egyptians", "Aztecs"], 2)
add("History", "hard", "Year man first walked on Moon?", ["1959", "1969", "1979", "1989"], 1)
add("History", "med", "Titanic sank in?", ["1905", "1912", "1920", "1931"], 1)
add("History", "easy", "Statue of Liberty gifted by?", ["UK", "France", "Spain", "Italy"], 1)
add("History", "hard", "Who discovered America 1492?", ["Magellan", "Columbus", "Cook", "Drake"], 1)
add("History", "med", "Roman numeral for 50?", ["V", "X", "L", "C"], 2)
add("History", "med", "First man in space?", ["Glenn", "Gagarin", "Armstrong", "Aldrin"], 1)
add("History", "hard", "Berlin Wall fell in?", ["1979", "1985", "1989", "1991"], 2)
add("History", "easy", "Knights wore?", ["Silk", "Armor", "Robes", "Furs"], 1)
add("History", "med", "Declaration of Indep. year?", ["1492", "1776", "1812", "1865"], 1)
add("History", "hard", "Who was Egyptian boy king?", ["Ramses", "Tut", "Nefer", "Khufu"], 1)

# ---------------- GEOGRAPHY ----------------
add("Geography", "easy", "Largest ocean?", ["Atlantic", "Indian", "Pacific", "Arctic"], 2)
add("Geography", "easy", "Capital of France?", ["Lyon", "Paris", "Nice", "Rome"], 1)
add("Geography", "med", "Longest river?", ["Amazon", "Nile", "Yangtze", "Congo"], 1)
add("Geography", "med", "Tallest mountain?", ["K2", "Everest", "Denali", "Alps"], 1)
add("Geography", "hard", "Smallest country?", ["Monaco", "Nauru", "Vatican", "Malta"], 2)
add("Geography", "easy", "Capital of Japan?", ["Osaka", "Tokyo", "Kyoto", "Seoul"], 1)
add("Geography", "med", "Largest desert?", ["Gobi", "Sahara", "Arctic", "Mojave"], 1)
add("Geography", "med", "How many continents?", ["5", "6", "7", "8"], 2)
add("Geography", "hard", "Country with most people?", ["USA", "India", "China", "Brazil"], 1)
add("Geography", "easy", "Capital of England?", ["Leeds", "London", "York", "Bath"], 1)
add("Geography", "med", "Sahara is on which continent?", ["Asia", "Africa", "Europe", "S.Am"], 1)
add("Geography", "hard", "Which is a US state?", ["Ontario", "Alberta", "Texas", "Sonora"], 2)
add("Geography", "easy", "Capital of Italy?", ["Milan", "Rome", "Turin", "Pisa"], 1)
add("Geography", "med", "Which is an island nation?", ["Peru", "Chad", "Japan", "Mali"], 2)
add("Geography", "hard", "Great Barrier Reef is near?", ["Brazil", "Australia", "Kenya", "India"], 1)

# ---------------- TECH ----------------
add("Tech", "easy", "What does CPU stand for?", ["Central Proc Unit", "Core Pwr U", "Comp Pers U", "Ctrl Proc U"], 0)
add("Tech", "med", "Who founded Microsoft?", ["Jobs", "Gates", "Musk", "Bezos"], 1)
add("Tech", "med", "HTML is used for?", ["Math", "Web pages", "Music", "3D"], 1)
add("Tech", "hard", "What year iPhone launched?", ["2005", "2007", "2009", "2011"], 1)
add("Tech", "easy", "What stores files on a PC?", ["RAM", "Disk", "GPU", "PSU"], 1)
add("Tech", "med", "Python is a?", ["Snake only", "Language", "Game", "Browser"], 1)
add("Tech", "hard", "What does HTTP stand for start?", ["HyperText", "HighThru", "HostText", "HotTrans"], 0)
add("Tech", "med", "Founder of Tesla/SpaceX?", ["Gates", "Musk", "Page", "Cook"], 1)
add("Tech", "easy", "What connects to WiFi?", ["Router", "Toaster", "Mouse only", "Cable only"], 0)
add("Tech", "hard", "Binary uses which digits?", ["0-9", "0 and 1", "1-2", "A-F"], 1)
add("Tech", "med", "What is LoRa used for?", ["Cooking", "Long radio", "Photos", "Gaming"], 1)
add("Tech", "med", "Open-source mesh radio project?", ["Meshtastic", "Bluetooth", "Zigbee", "NFC"], 0)
add("Tech", "easy", "Which is a search engine?", ["Excel", "Google", "Word", "Paint"], 1)
add("Tech", "hard", "RAM stands for?", ["Random Acc Mem", "Read All Mem", "Rapid Mem", "Run App Mem"], 0)
add("Tech", "med", "GPU is best at?", ["Storage", "Graphics", "Cooling", "Audio"], 1)

# ---------------- POP CULTURE ----------------
add("Pop", "easy", "Wizard boy with a scar?", ["Frodo", "Harry P", "Percy", "Luke"], 1)
add("Pop", "med", "Who sang Thriller?", ["Prince", "Jackson", "Bowie", "Sting"], 1)
add("Pop", "easy", "Yellow cartoon family?", ["Griffins", "Simpsons", "Belchers", "Smiths"], 1)
add("Pop", "med", "Star Wars hero with lightsaber?", ["Han", "Luke", "Yoda", "Leia"], 1)
add("Pop", "hard", "Director of Titanic film?", ["Spielberg", "Cameron", "Nolan", "Scott"], 1)
add("Pop", "easy", "Mickey is a?", ["Dog", "Mouse", "Duck", "Bear"], 1)
add("Pop", "med", "Friends was set in?", ["LA", "NYC", "Chicago", "Boston"], 1)
add("Pop", "hard", "Who plays Iron Man?", ["Evans", "Downey Jr", "Hemsworth", "Ruffalo"], 1)
add("Pop", "easy", "Spongebob lives in a?", ["Tree", "Pineapple", "Cave", "Boat"], 1)
add("Pop", "med", "Frozen princess who sings Let It Go?", ["Anna", "Elsa", "Belle", "Moana"], 1)
add("Pop", "med", "Band with Hey Jude?", ["Stones", "Beatles", "Queen", "U2"], 1)
add("Pop", "hard", "Game of Thrones house with wolf?", ["Lannister", "Stark", "Targ", "Bolton"], 1)
add("Pop", "easy", "Batman's city?", ["Metropolis", "Gotham", "Star City", "Central"], 1)
add("Pop", "med", "Pikachu is from?", ["Digimon", "Pokemon", "Yugioh", "Mario"], 1)
add("Pop", "hard", "Who wrote Harry Potter?", ["Tolkien", "Rowling", "Martin", "Lewis"], 1)

# ---------------- SPORTS ----------------
add("Sports", "easy", "How many players on soccer team?", ["9", "10", "11", "12"], 2)
add("Sports", "med", "Sport with home runs?", ["Soccer", "Baseball", "Tennis", "Golf"], 1)
add("Sports", "med", "Olympics held every ? years", ["2", "3", "4", "5"], 2)
add("Sports", "hard", "Most NBA points all-time (career)?", ["Jordan", "James", "Kobe", "Magic"], 1)
add("Sports", "easy", "Sport with rackets and a net?", ["Boxing", "Tennis", "Rugby", "Sumo"], 1)
add("Sports", "med", "Tour de France is what sport?", ["Run", "Cycling", "Swim", "Row"], 1)
add("Sports", "hard", "How many rings in Olympic logo?", ["3", "4", "5", "6"], 2)
add("Sports", "easy", "Goal of golf: ? strokes", ["Most", "Fewest", "Even", "Random"], 1)
add("Sports", "med", "Super Bowl is in which sport?", ["NBA", "NFL", "MLB", "NHL"], 1)
add("Sports", "hard", "Country that invented sumo?", ["China", "Japan", "Korea", "Thai"], 1)
add("Sports", "easy", "How many holes in golf round?", ["9", "12", "18", "24"], 2)
add("Sports", "med", "Wimbledon is played on?", ["Clay", "Grass", "Hard", "Sand"], 1)

# ---------------- NATURE / ANIMALS ----------------
add("Nature", "easy", "Largest land animal?", ["Lion", "Elephant", "Horse", "Bear"], 1)
add("Nature", "easy", "Fastest land animal?", ["Lion", "Cheetah", "Horse", "Wolf"], 1)
add("Nature", "med", "King of the jungle?", ["Tiger", "Lion", "Bear", "Wolf"], 1)
add("Nature", "med", "Animal known for changing color?", ["Frog", "Chameleon", "Snake", "Owl"], 1)
add("Nature", "hard", "Largest living animal ever?", ["Elephant", "Blue whale", "Shark", "Dino"], 1)
add("Nature", "easy", "Baby dog is called?", ["Kit", "Puppy", "Cub", "Calf"], 1)
add("Nature", "med", "Bird that cannot fly?", ["Eagle", "Penguin", "Crow", "Hawk"], 1)
add("Nature", "hard", "How many legs does a spider have?", ["6", "8", "10", "12"], 1)
add("Nature", "easy", "Bees live in a?", ["Den", "Hive", "Nest only", "Cave"], 1)
add("Nature", "med", "Tallest animal?", ["Elephant", "Giraffe", "Horse", "Camel"], 1)
add("Nature", "med", "What do caterpillars become?", ["Bees", "Butterflies", "Ants", "Moths only"], 1)
add("Nature", "hard", "Group of lions is a?", ["Pack", "Pride", "Herd", "Flock"], 1)

# ---------------- FOOD ----------------
add("Food", "easy", "Main ingredient in guacamole?", ["Tomato", "Avocado", "Lime", "Onion"], 1)
add("Food", "med", "Sushi comes from?", ["China", "Japan", "Korea", "Thai"], 1)
add("Food", "easy", "Pizza originated in?", ["France", "Italy", "Spain", "Greece"], 1)
add("Food", "med", "What bean makes chocolate?", ["Soy", "Cacao", "Coffee", "Vanilla"], 1)
add("Food", "hard", "Saffron comes from a?", ["Root", "Flower", "Leaf", "Seed"], 1)
add("Food", "easy", "What fruit is dried into raisins?", ["Plum", "Grape", "Fig", "Date"], 1)
add("Food", "med", "Espresso is a type of?", ["Tea", "Coffee", "Juice", "Soda"], 1)
add("Food", "hard", "Wasabi is typically what color?", ["Red", "Green", "Yellow", "Brown"], 1)
add("Food", "easy", "Cheese is made from?", ["Milk", "Soy", "Eggs", "Flour"], 0)
add("Food", "med", "Which is a citrus fruit?", ["Apple", "Lemon", "Pear", "Plum"], 1)

# ---------------- MUSIC ----------------
add("Music", "easy", "How many strings on a guitar?", ["4", "5", "6", "7"], 2)
add("Music", "med", "Beethoven was famously?", ["Blind", "Deaf", "Mute", "Lame"], 1)
add("Music", "med", "Instrument with 88 keys?", ["Guitar", "Piano", "Harp", "Drum"], 1)
add("Music", "hard", "Queen's lead singer?", ["Bowie", "Mercury", "Plant", "Daltrey"], 1)
add("Music", "easy", "A drum is what type of instrument?", ["String", "Percussion", "Wind", "Brass"], 1)
add("Music", "med", "Genre of Bob Marley?", ["Jazz", "Reggae", "Rock", "Pop"], 1)
add("Music", "hard", "How many notes in an octave?", ["6", "7", "8", "12"], 2)
add("Music", "easy", "Which is a brass instrument?", ["Violin", "Trumpet", "Flute", "Piano"], 1)

# ---------------- MATH / LOGIC ----------------
add("Math", "easy", "What is 7 x 8?", ["54", "56", "58", "64"], 1)
add("Math", "easy", "What is 100 / 4?", ["20", "25", "30", "40"], 1)
add("Math", "med", "What is 12 squared?", ["124", "144", "154", "121"], 1)
add("Math", "med", "Pi is approximately?", ["2.14", "3.14", "4.13", "1.62"], 1)
add("Math", "hard", "Sum of angles in a triangle?", ["90", "180", "270", "360"], 1)
add("Math", "easy", "How many sides on a hexagon?", ["5", "6", "7", "8"], 1)
add("Math", "med", "What is 15% of 200?", ["20", "30", "40", "50"], 1)
add("Math", "hard", "Next prime after 7?", ["8", "9", "11", "13"], 2)

# ---------------- GENERAL ----------------
add("General", "easy", "How many days in a week?", ["5", "6", "7", "8"], 2)
add("General", "easy", "What color is the sky on a clear day?", ["Green", "Blue", "Red", "Gray"], 1)
add("General", "med", "How many colors in a rainbow?", ["5", "6", "7", "8"], 2)
add("General", "med", "How many minutes in an hour?", ["30", "60", "90", "100"], 1)
add("General", "easy", "What shape has 4 equal sides?", ["Circle", "Square", "Triangle", "Oval"], 1)
add("General", "hard", "How many cards in a deck?", ["48", "50", "52", "54"], 2)
add("General", "easy", "What do you read?", ["Music only", "Book", "Air", "Light"], 1)
add("General", "med", "How many legs on a tripod?", ["2", "3", "4", "5"], 1)
add("General", "med", "Frozen rain is called?", ["Mist", "Hail", "Dew", "Fog"], 1)
add("General", "hard", "Roman numeral for 1000?", ["D", "M", "C", "L"], 1)

# ================= BATCH 2 (expansion) =================
# SCIENCE 2
add("Science", "easy", "What do we breathe to live?", ["CO2", "Oxygen", "Helium", "Neon"], 1)
add("Science", "easy", "What is the center of an atom?", ["Shell", "Nucleus", "Orbit", "Field"], 1)
add("Science", "med", "What force pulls us down?", ["Magnet", "Gravity", "Friction", "Drag"], 1)
add("Science", "med", "Boiling point of water (C)?", ["50", "90", "100", "120"], 2)
add("Science", "med", "Freezing point of water (C)?", ["0", "10", "-10", "32"], 0)
add("Science", "hard", "What is the smallest unit of life?", ["Atom", "Cell", "Molecule", "Tissue"], 1)
add("Science", "hard", "Element with symbol Fe?", ["Lead", "Iron", "Fluor", "Tin"], 1)
add("Science", "med", "What scientist defined gravity laws?", ["Bohr", "Newton", "Curie", "Tesla"], 1)
add("Science", "easy", "What do you call frozen rain crystals?", ["Rain", "Snow", "Mist", "Dew"], 1)
add("Science", "hard", "How many planets in our system?", ["7", "8", "9", "10"], 1)
add("Science", "med", "What part of the eye senses light?", ["Iris", "Retina", "Lens", "Pupil"], 1)
add("Science", "hard", "Half of 0 K is roughly?", ["0 K", "150 K", "-273 C", "Cold"], 0)

# HISTORY 2
add("History", "easy", "Pharaohs ruled which land?", ["Greece", "Egypt", "Rome", "Persia"], 1)
add("History", "med", "Who was Queen of England long est. recent?", ["Anne", "Elizabeth II", "Victoria", "Mary"], 1)
add("History", "med", "The Renaissance began in?", ["France", "Italy", "Spain", "England"], 1)
add("History", "hard", "Who led nonviolent India indep.?", ["Nehru", "Gandhi", "Bose", "Patel"], 1)
add("History", "easy", "Cavemen used tools made of?", ["Plastic", "Stone", "Steel", "Glass"], 1)
add("History", "med", "Vikings came from?", ["Spain", "Scandinavia", "Egypt", "India"], 1)
add("History", "hard", "First woman to win a Nobel?", ["Curie", "Franklin", "Meitner", "Lovelace"], 0)
add("History", "med", "Cold War was between US and?", ["China", "USSR", "Japan", "Cuba"], 1)
add("History", "easy", "Castles were homes for?", ["Farmers", "Royals", "Sailors", "Monks"], 1)
add("History", "hard", "Year the US declared independence?", ["1492", "1607", "1776", "1865"], 2)

# GEOGRAPHY 2
add("Geography", "easy", "Capital of the USA?", ["NYC", "DC", "LA", "Chicago"], 1)
add("Geography", "med", "Which country has the Eiffel Tower?", ["Italy", "France", "Spain", "UK"], 1)
add("Geography", "med", "The Amazon rainforest is mostly in?", ["Peru", "Brazil", "Chile", "Cuba"], 1)
add("Geography", "hard", "Which is the largest country by area?", ["China", "Russia", "USA", "Canada"], 1)
add("Geography", "easy", "Capital of Canada?", ["Toronto", "Ottawa", "Quebec", "Calgary"], 1)
add("Geography", "med", "Which sea is the saltiest famous one?", ["Red Sea", "Dead Sea", "Black Sea", "Aral"], 1)
add("Geography", "hard", "Which country spans most time zones?", ["USA", "Russia", "China", "Brazil"], 1)
add("Geography", "easy", "Capital of Spain?", ["Madrid", "Barcelona", "Seville", "Bilbao"], 0)
add("Geography", "med", "Mount Fuji is in?", ["China", "Japan", "Korea", "Nepal"], 1)
add("Geography", "hard", "Which is a landlocked country?", ["Cuba", "Chad", "Japan", "Italy"], 1)

# TECH 2
add("Tech", "easy", "What do you click on a screen with?", ["Pen", "Mouse", "Fork", "Key only"], 1)
add("Tech", "med", "Who co-founded Apple with Wozniak?", ["Gates", "Jobs", "Dell", "Cook"], 1)
add("Tech", "med", "What does WWW stand for start?", ["World Wide", "Web Wave", "Wide Work", "Wired W"], 0)
add("Tech", "hard", "What language is known for indentation?", ["Java", "Python", "C", "Ruby"], 1)
add("Tech", "easy", "What protects against viruses?", ["Antivirus", "Toaster", "Modem", "Cable"], 0)
add("Tech", "med", "USB is used to?", ["Cool", "Connect", "Cook", "Charge only"], 1)
add("Tech", "hard", "What is the brain of a computer?", ["GPU", "CPU", "RAM", "SSD"], 1)
add("Tech", "med", "Bluetooth is for?", ["Wired net", "Wireless link", "Power", "Cooling"], 1)
add("Tech", "easy", "Which company makes Android?", ["Apple", "Google", "Sony", "IBM"], 1)
add("Tech", "hard", "What does GPS stand for start?", ["Global Pos", "Grid Pwr", "Geo Path", "Gen Pos"], 0)

# POP 2
add("Pop", "easy", "Superman is from planet?", ["Mars", "Krypton", "Vulcan", "Tatooine"], 1)
add("Pop", "med", "Who is Mario's brother?", ["Wario", "Luigi", "Yoshi", "Toad"], 1)
add("Pop", "med", "What movie has 'May the Force'?", ["Trek", "Star Wars", "Avatar", "Dune"], 1)
add("Pop", "hard", "Who directed Jurassic Park?", ["Lucas", "Spielberg", "Cameron", "Nolan"], 1)
add("Pop", "easy", "SpongeBob's best friend?", ["Squid", "Patrick", "Krabs", "Sandy"], 1)
add("Pop", "med", "Which is a Marvel hero?", ["Joker", "Thor", "Bane", "Riddler"], 1)
add("Pop", "hard", "Singer known as Queen of Pop?", ["Cher", "Madonna", "Adele", "Sia"], 1)
add("Pop", "easy", "Scooby-Doo is a?", ["Cat", "Dog", "Fox", "Wolf"], 1)
add("Pop", "med", "Hogwarts is from which series?", ["Narnia", "Harry P", "LOTR", "Percy J"], 1)
add("Pop", "hard", "Who voices many Pixar shorts? Studio is?", ["Pixar", "DreamWorks", "Ghibli", "Sony"], 0)

# SPORTS 2
add("Sports", "easy", "Sport played at Wimbledon?", ["Golf", "Tennis", "Polo", "Darts"], 1)
add("Sports", "med", "How many bases in baseball?", ["3", "4", "5", "6"], 1)
add("Sports", "med", "A hat-trick is 3 of what?", ["Fouls", "Goals", "Cards", "Subs"], 1)
add("Sports", "hard", "Country that hosts the Tour de France?", ["Italy", "France", "Spain", "Belgium"], 1)
add("Sports", "easy", "What sport uses a puck?", ["Soccer", "Hockey", "Rugby", "Polo"], 1)
add("Sports", "med", "A marathon is about how many miles?", ["13", "20", "26", "31"], 2)
add("Sports", "hard", "How many players on a basketball court (per team)?", ["4", "5", "6", "7"], 1)
add("Sports", "easy", "A 'strike' is a term in?", ["Bowling", "Chess", "Swim", "Golf"], 0)

# NATURE 2
add("Nature", "easy", "What animal says 'moo'?", ["Pig", "Cow", "Dog", "Cat"], 1)
add("Nature", "med", "Largest big cat?", ["Lion", "Tiger", "Jaguar", "Puma"], 1)
add("Nature", "med", "What do pandas mainly eat?", ["Meat", "Bamboo", "Fish", "Fruit"], 1)
add("Nature", "hard", "A baby kangaroo is a?", ["Cub", "Joey", "Kit", "Calf"], 1)
add("Nature", "easy", "Which animal has a trunk?", ["Horse", "Elephant", "Lion", "Zebra"], 1)
add("Nature", "med", "Owls are mostly active at?", ["Noon", "Night", "Dawn", "Dusk only"], 1)
add("Nature", "hard", "What gas do plants release in day?", ["CO2", "Oxygen", "Methane", "Argon"], 1)
add("Nature", "easy", "Fish breathe using?", ["Lungs", "Gills", "Skin", "Nose"], 1)

# FOOD 2
add("Food", "easy", "What is the main grain in bread?", ["Rice", "Wheat", "Corn", "Oat"], 1)
add("Food", "med", "Which country is famous for pasta?", ["France", "Italy", "Spain", "Greece"], 1)
add("Food", "med", "What is tofu made from?", ["Milk", "Soy", "Egg", "Wheat"], 1)
add("Food", "hard", "Which spice is the most expensive?", ["Pepper", "Saffron", "Cumin", "Salt"], 1)
add("Food", "easy", "Which is a breakfast food?", ["Steak", "Pancakes", "Soup", "Salad"], 1)
add("Food", "med", "Sourdough is a type of?", ["Soup", "Bread", "Cheese", "Sauce"], 1)

# MUSIC 2
add("Music", "easy", "Which is a string instrument?", ["Drum", "Violin", "Flute", "Horn"], 1)
add("Music", "med", "A song's words are called?", ["Beat", "Lyrics", "Tempo", "Key"], 1)
add("Music", "hard", "How many lines in a music staff?", ["4", "5", "6", "7"], 1)
add("Music", "easy", "DJ stands for disc?", ["Jumper", "Jockey", "Joiner", "Judge"], 1)

# MATH 2
add("Math", "easy", "What is 9 + 6?", ["13", "15", "16", "18"], 1)
add("Math", "easy", "What is half of 50?", ["20", "25", "30", "15"], 1)
add("Math", "med", "What is 6 x 7?", ["36", "42", "48", "49"], 1)
add("Math", "hard", "What is 2 to the power of 5?", ["16", "25", "32", "64"], 2)
add("Math", "med", "How many degrees in a circle?", ["180", "270", "360", "400"], 2)
add("Math", "hard", "Which number is prime?", ["9", "15", "17", "21"], 2)

# GENERAL 2
add("General", "easy", "How many months in a year?", ["10", "11", "12", "13"], 2)
add("General", "easy", "What do you use to tell time?", ["Map", "Clock", "Book", "Cup"], 1)
add("General", "med", "How many hours in a day?", ["12", "20", "24", "30"], 2)
add("General", "med", "A decade is how many years?", ["5", "10", "20", "100"], 1)
add("General", "hard", "A century is how many years?", ["10", "50", "100", "1000"], 2)
add("General", "easy", "What season comes after winter?", ["Fall", "Spring", "Summer", "None"], 1)
add("General", "med", "How many sides on a stop sign?", ["6", "7", "8", "9"], 2)
add("General", "hard", "Primary colors are red, blue and?", ["Green", "Yellow", "Orange", "Purple"], 1)


# ================= BATCH 3: MESHTASTIC / LoRa DEEP CUT =================
# Fact-checked 2026-06-05 against the official docs at meshtastic.org (radio-settings,
# channels, device roles, mqtt, lora, mesh-algo). These power the MEDIUM and HARD tiers so
# "harder" means real mesh knowledge, not just obscure trivia. Keep them FUN + tight (<200B).

# ---- Mesh basics (medium) ----
add("Mesh", "med", "Meshtastic radios talk over which tech?", ["WiFi", "LoRa", "5G", "Zigbee"], 1)
add("Mesh", "med", "Default Meshtastic modem preset?", ["ShortFast", "LongFast", "LongSlow", "MediumFast"], 1)
add("Mesh", "med", "Default hop limit on a fresh node?", ["1", "3", "5", "7"], 1)
add("Mesh", "med", "Max hop limit Meshtastic allows?", ["3", "5", "7", "10"], 2)
add("Mesh", "med", "US Meshtastic runs in which ISM band?", ["433 MHz", "868 MHz", "915 MHz", "2.4 GHz"], 2)
add("Mesh", "med", "Default device role on a new node?", ["ROUTER", "CLIENT", "REPEATER", "SENSOR"], 1)
add("Mesh", "med", "Meshtastic answers and tapbacks ride on?", ["Bluetooth", "LoRa", "NFC", "IR"], 1)
add("Mesh", "med", "What app monitors a mesh via REST?", ["MeshMonitor", "Wireshark", "Grafana", "Pi-hole"], 0)
add("Mesh", "med", "A LoRa text packet caps around how many bytes?", ["50", "100", "200", "500"], 2)
add("Mesh", "med", "Higher spreading factor mainly gives more?", ["Speed", "Range", "Battery", "Color"], 1)
add("Mesh", "med", "Which preset is FASTEST but shortest range?", ["LongSlow", "LongFast", "ShortTurbo", "MediumSlow"], 2)
add("Mesh", "med", "Meshtastic firmware is built mostly for which chips?", ["ESP32/nRF52", "x86", "AVR", "PIC"], 0)
add("Mesh", "med", "What does PSK protect on a channel?", ["Speed", "Encryption", "Battery", "GPS"], 1)
add("Mesh", "med", "Default public MQTT broker host?", ["mqtt.meshtastic.org", "broker.mqtt.io", "mesh.local", "iot.aws"], 0)
add("Mesh", "med", "Sharing a channel needs matching what?", ["Color", "PSK", "Name only", "Hop limit"], 1)
add("Mesh", "med", "Region setting mainly controls the?", ["Color", "Frequency", "Hop limit", "Name"], 1)
add("Mesh", "med", "What does MQTT bridge a mesh to?", ["A printer", "The internet", "GPS sats", "A modem"], 1)
add("Mesh", "med", "Antenna gain is measured in?", ["Volts", "dBi", "Hertz", "Amps"], 1)
add("Mesh", "med", "A handheld Meshtastic node usually connects to a phone via?", ["WiFi", "Bluetooth", "USB only", "Cellular"], 1)
add("Mesh", "med", "Lower SNR distant nodes rebroadcast?", ["Never", "Sooner", "Later", "Twice"], 1)

# ---- LoRa presets + RF (hard) ----
add("Mesh", "hard", "LongFast uses which spreading factor?", ["SF7", "SF9", "SF11", "SF12"], 2)
add("Mesh", "hard", "ShortFast bandwidth is?", ["125 kHz", "250 kHz", "500 kHz", "62 kHz"], 1)
add("Mesh", "hard", "Each step up in SF roughly does what to airtime?", ["Halves", "Doubles", "No change", "Triples"], 1)
add("Mesh", "hard", "Slowest/longest-range default preset?", ["LongFast", "LongSlow", "MediumSlow", "ShortSlow"], 1)
add("Mesh", "hard", "LongSlow spreading factor?", ["SF9", "SF10", "SF11", "SF12"], 3)
add("Mesh", "hard", "ShortTurbo bandwidth?", ["250 kHz", "500 kHz", "125 kHz", "1 MHz"], 1)
add("Mesh", "hard", "US 915 ISM band spans roughly?", ["902-928", "863-870", "433-435", "920-925"], 0)
add("Mesh", "hard", "Default NA frequency slot after reset?", ["Slot 0", "Slot 20", "Slot 52", "Slot 7"], 1)
add("Mesh", "hard", "Higher SF adds about how much link budget per step?", ["0.5 dB", "2.5 dB", "10 dB", "25 dB"], 1)
add("Mesh", "hard", "Coding rate on most default presets?", ["4/5", "4/8", "1/2", "7/8"], 0)

# ---- Routing / flooding (hard) ----
add("Mesh", "hard", "Meshtastic routing model is called?", ["Mesh OSPF", "Managed flood", "BGP mesh", "Star route"], 1)
add("Mesh", "hard", "On rebroadcast, a node does what to hop limit?", ["Increments", "Decrements", "Resets", "Ignores"], 1)
add("Mesh", "hard", "Before rebroadcasting a node first?", ["Sleeps", "Listens", "Reboots", "Pings GPS"], 1)
add("Mesh", "hard", "Rebroadcast stops when hop limit hits?", ["1", "0", "-1", "7"], 1)
add("Mesh", "hard", "Contention window size keys off which metric?", ["GPS", "SNR", "Battery", "Clock"], 1)
add("Mesh", "hard", "v2.6+ direct messages prefer what over flooding?", ["Broadcast", "Next-hop", "MQTT", "Random"], 1)

# ---- Channels / encryption (hard) ----
add("Mesh", "hard", "Max channels you can configure (indices 0-7)?", ["4", "6", "8", "16"], 2)
add("Mesh", "hard", "Valid PSK sizes are 0, 16, or how many bytes?", ["24", "32", "48", "64"], 1)
add("Mesh", "hard", "A 32-byte PSK selects which cipher?", ["AES128", "AES256", "DES", "RSA"], 1)
add("Mesh", "hard", "The default primary channel name is?", ["LongFast", "Empty", "Public", "Default1"], 1)
add("Mesh", "hard", "Default channel's PSK is the single byte?", ["0x00", "0x01", "0xFF", "0x42"], 1)
add("Mesh", "hard", "A 0-byte PSK means?", ["AES256", "No crypto", "AES128", "Error"], 1)

# ---- Roles (hard) ----
add("Mesh", "hard", "Which role is HIDDEN from the nodes list?", ["CLIENT", "ROUTER", "REPEATER", "TRACKER"], 2)
add("Mesh", "hard", "ROUTER vs REPEATER: ROUTER is?", ["Hidden", "Visible", "Muted", "Mobile"], 1)
add("Mesh", "hard", "Role that does NOT forward others' packets?", ["CLIENT", "ROUTER", "CLIENT_MUTE", "REPEATER"], 2)
add("Mesh", "hard", "Role that broadcasts GPS as priority?", ["SENSOR", "TRACKER", "CLIENT", "TAK"], 1)
add("Mesh", "hard", "Role broadcasting telemetry as priority?", ["TRACKER", "SENSOR", "ROUTER", "CLIENT"], 1)
add("Mesh", "hard", "ROUTER_LATE rebroadcasts when?", ["First", "After others", "Never", "Twice"], 1)

# ---- MQTT (hard) ----
add("Mesh", "hard", "MQTT 'uplink' sends packets which way?", ["To broker", "From broker", "Both", "Neither"], 0)
add("Mesh", "hard", "If MQTT encryption is off, packets go to broker?", ["Encrypted", "Unencrypted", "Not at all", "Compressed"], 1)


# ================= BATCH 4: BROAD EXPANSION (v1.4.0, hard-skewed) =================
# Will (2026-06-05): "Add even more questions. Not just about meshtastic." + keep the harder
# skew. Authored across the existing non-Mesh categories with a deliberate lean to med/hard.
# Every non-common-knowledge fact WebSearch-verified 2026-06-05 (see process doc Tests note):
# AZ symbols/geo (azgovernor.gov, statesymbolsusa), Grand Canyon (nps.gov), London Bridge
# (Wikipedia), Space (NASA science.nasa.gov, Wikipedia), Canberra/Ankara/Baikal/Kilimanjaro,
# skin=largest organ, H=element 1, Curie's two Nobels. FUN wording, <200B worst-case.

# ---- SCIENCE (skew hard) ----
add("Science", "med", "What blood cells fight infection?", ["Red", "White", "Plasma", "Platelet"], 1)
add("Science", "hard", "Largest human internal organ?", ["Heart", "Liver", "Lung", "Brain"], 1)
add("Science", "hard", "Element number 1 on the table?", ["Helium", "Hydrogen", "Carbon", "Oxygen"], 1)
add("Science", "hard", "Atomic number of oxygen?", ["6", "7", "8", "16"], 2)
add("Science", "med", "What pigment makes plants green?", ["Keratin", "Chlorophyll", "Melanin", "Hemo"], 1)
add("Science", "hard", "Only metal liquid at room temp?", ["Lead", "Mercury", "Sodium", "Tin"], 1)
add("Science", "med", "Sound cannot travel through a?", ["Solid", "Liquid", "Gas", "Vacuum"], 3)
add("Science", "hard", "pH of pure water is about?", ["1", "7", "10", "14"], 1)
add("Science", "med", "Largest organ of the human body?", ["Liver", "Skin", "Heart", "Lung"], 1)
add("Science", "hard", "Element with chemical symbol Na?", ["Nickel", "Sodium", "Neon", "Nitro"], 1)

# ---- HISTORY (skew hard) ----
add("History", "med", "Who wrote the US Declaration mainly?", ["Adams", "Jefferson", "Franklin", "Hancock"], 1)
add("History", "hard", "Empire ruled by Julius Caesar?", ["Greek", "Roman", "Persian", "Ottoman"], 1)
add("History", "hard", "Ship the Pilgrims sailed on 1620?", ["Beagle", "Mayflower", "Santa Maria", "Endeavour"], 1)
add("History", "med", "Civil War split the US North and?", ["East", "South", "West", "Coast"], 1)
add("History", "hard", "First woman with two Nobel Prizes?", ["Franklin", "Curie", "Meitner", "Hodgkin"], 1)
add("History", "med", "The pyramids of Giza are near which river?", ["Tigris", "Nile", "Amazon", "Ganges"], 1)
add("History", "hard", "Who was the British PM in WWII?", ["Chamberlain", "Churchill", "Attlee", "Eden"], 1)

# ---- GEOGRAPHY (skew hard) ----
add("Geography", "hard", "Capital of Australia?", ["Sydney", "Canberra", "Melbourne", "Perth"], 1)
add("Geography", "hard", "Capital of Turkey?", ["Istanbul", "Ankara", "Izmir", "Bursa"], 1)
add("Geography", "hard", "Deepest lake on Earth?", ["Superior", "Baikal", "Tahoe", "Victoria"], 1)
add("Geography", "med", "Highest mountain in Africa?", ["Atlas", "Kilimanjaro", "Kenya", "Meru"], 1)
add("Geography", "med", "Which US state is the Grand Canyon in?", ["Utah", "Arizona", "Nevada", "Colorado"], 1)
add("Geography", "hard", "Strait between Europe and Africa?", ["Bering", "Gibraltar", "Hormuz", "Malacca"], 1)
add("Geography", "med", "Which continent is the Sahara on?", ["Asia", "Africa", "Australia", "Europe"], 1)

# ---- TECH (skew hard) ----
add("Tech", "med", "What does 'URL' point you to?", ["A file", "A web address", "A song", "A photo"], 1)
add("Tech", "hard", "What company created the iPhone?", ["Samsung", "Apple", "Nokia", "HTC"], 1)
add("Tech", "hard", "What does 'AI' stand for?", ["Auto Input", "Artificial Intel", "App Index", "Alt Icon"], 1)
add("Tech", "med", "A QR code is scanned with a?", ["Printer", "Camera", "Speaker", "Mic"], 1)
add("Tech", "hard", "Which is an open-source OS kernel?", ["Windows", "Linux", "macOS", "iOS"], 1)
add("Tech", "med", "Email '@' separates user and?", ["Password", "Domain", "Subject", "Folder"], 1)

# ---- POP / MOVIES (skew hard) ----
add("Pop", "med", "Which movie features the ship Titanic sinking?", ["Avatar", "Titanic", "Speed", "Jaws"], 1)
add("Pop", "hard", "Which film has the line 'I'll be back'?", ["Rambo", "Terminator", "Rocky", "Predator"], 1)
add("Pop", "med", "Toy cowboy in Toy Story is named?", ["Buzz", "Woody", "Rex", "Slinky"], 1)
add("Pop", "hard", "Wizard school in Harry Potter is?", ["Camelot", "Hogwarts", "Xavier's", "Narnia"], 1)
add("Pop", "med", "Green ogre in a swamp movie?", ["Hulk", "Shrek", "Grinch", "Yoda"], 1)
add("Pop", "hard", "Which superhero is the 'Caped Crusader'?", ["Superman", "Batman", "Flash", "Robin"], 1)
add("Pop", "hard", "Movie with a clownfish named Nemo?", ["Shark Tale", "Finding Nemo", "Moana", "Luca"], 1)

# ---- SPORTS (skew hard) ----
add("Sports", "med", "How many points is a touchdown worth?", ["3", "6", "7", "2"], 1)
add("Sports", "hard", "How long is an Olympic pool (m)?", ["25", "50", "100", "200"], 1)
add("Sports", "med", "What sport uses a shuttlecock?", ["Tennis", "Badminton", "Squash", "Ping pong"], 1)
add("Sports", "hard", "Boxing match max pro rounds usually?", ["5", "10", "12", "15"], 2)
add("Sports", "med", "Which sport has a quarterback?", ["Soccer", "Football", "Rugby", "Cricket"], 1)
add("Sports", "hard", "Country where rugby's World Cup began?", ["England", "NZ/Aus", "Wales", "France"], 1)

# ---- NATURE (skew hard) ----
add("Nature", "med", "Largest species of shark?", ["Great white", "Whale shark", "Tiger", "Hammer"], 1)
add("Nature", "hard", "Only mammal that can truly fly?", ["Squirrel", "Bat", "Sugar glider", "Lemur"], 1)
add("Nature", "med", "A group of wolves is called a?", ["Herd", "Pack", "Pride", "Flock"], 1)
add("Nature", "hard", "What animal has the largest eyes?", ["Whale", "Giant squid", "Owl", "Horse"], 1)
add("Nature", "med", "Honeybees communicate by a?", ["Song", "Dance", "Whistle", "Glow"], 1)
add("Nature", "hard", "Fastest bird in a dive?", ["Eagle", "Falcon", "Hawk", "Swift"], 1)

# ---- FOOD (skew hard) ----
add("Food", "med", "Which nut is in classic pesto?", ["Almond", "Pine nut", "Cashew", "Walnut"], 1)
add("Food", "hard", "Country where the croissant is iconic?", ["Italy", "France", "Spain", "Belgium"], 1)
add("Food", "med", "Hummus is mainly made from?", ["Lentil", "Chickpea", "Bean", "Pea"], 1)
add("Food", "hard", "What gives paprika its red color base?", ["Chili", "Pepper", "Beet", "Tomato"], 1)
add("Food", "med", "Which is a fermented soybean paste?", ["Miso", "Roux", "Pesto", "Aioli"], 0)

# ---- MUSIC (skew hard) ----
add("Music", "med", "How many keys total on a full piano?", ["66", "76", "88", "98"], 2)
add("Music", "hard", "Composer of the Fifth Symphony 'da-da-da-dum'?", ["Mozart", "Beethoven", "Bach", "Chopin"], 1)
add("Music", "med", "A capella means singing with no?", ["Words", "Instruments", "Audience", "Mic"], 1)
add("Music", "hard", "Which instrument has pedals, strings, no frets, 88 keys?", ["Harp", "Piano", "Cello", "Organ"], 1)

# ---- MATH (skew hard) ----
add("Math", "med", "What is 13 x 3?", ["36", "39", "42", "33"], 1)
add("Math", "hard", "Square root of 144?", ["10", "12", "14", "16"], 1)
add("Math", "med", "How many sides does an octagon have?", ["6", "7", "8", "10"], 2)
add("Math", "hard", "What is 7 factorial's first digit (5040)?", ["4", "5", "6", "7"], 1)
add("Math", "med", "What is 25% of 80?", ["15", "20", "25", "30"], 1)

# ---- GENERAL (skew hard) ----
add("General", "med", "How many continents touch the equator?", ["1", "2", "3", "4"], 2)
add("General", "hard", "Roman numeral for the year 2000?", ["MM", "MC", "DD", "CM"], 0)
add("General", "med", "How many zeros in one million?", ["4", "5", "6", "7"], 2)
add("General", "hard", "Which is NOT a primary color of light?", ["Red", "Green", "Blue", "Yellow"], 3)


# ================= BATCH 5: NEW CATEGORIES (Space + AZ/Southwest) =================
# Two new categories that suit the AZ mesh crowd (dark skies, desert, local pride). All
# AZ facts WebSearch-verified 2026-06-05 (azgovernor.gov Arizona Facts, statesymbolsusa,
# nps.gov Grand Canyon, Wikipedia London Bridge). Space facts verified via NASA science.nasa.gov.

# ---- SPACE (skew med/hard) ----
add("Space", "easy", "Which planet do we live on?", ["Mars", "Earth", "Venus", "Jupiter"], 1)
add("Space", "easy", "What lights up the daytime sky?", ["Moon", "Sun", "Mars", "A star"], 1)
add("Space", "med", "Closest planet to the Sun?", ["Venus", "Mercury", "Earth", "Mars"], 1)
add("Space", "med", "Hottest planet in our solar system?", ["Mercury", "Venus", "Mars", "Jupiter"], 1)
add("Space", "med", "How many moons does Earth have?", ["0", "1", "2", "4"], 1)
add("Space", "med", "Planet famous for its bright rings?", ["Mars", "Saturn", "Venus", "Earth"], 1)
add("Space", "hard", "Largest moon in our solar system?", ["Titan", "Ganymede", "Luna", "Europa"], 1)
add("Space", "hard", "Tallest volcano in the solar system?", ["Mauna Kea", "Olympus Mons", "Etna", "Fuji"], 1)
add("Space", "med", "Sunlight takes about how long to reach Earth?", ["8 sec", "8 min", "8 hr", "1 day"], 1)
add("Space", "hard", "First artificial satellite, launched 1957?", ["Apollo", "Sputnik", "Hubble", "Voyager"], 1)
add("Space", "hard", "Farthest human-made object from Earth?", ["Hubble", "Voyager 1", "ISS", "Cassini"], 1)
add("Space", "hard", "Halley's Comet returns roughly every?", ["12 yr", "50 yr", "76 yr", "100 yr"], 2)
add("Space", "med", "What telescope launched into orbit in 1990?", ["Webb", "Hubble", "Kepler", "Spitzer"], 1)
add("Space", "hard", "NASA rover that landed on Mars in 2021?", ["Spirit", "Perseverance", "Curiosity", "Opportunity"], 1)
add("Space", "med", "The ISS orbits Earth about every?", ["90 min", "6 hr", "12 hr", "24 hr"], 0)
add("Space", "hard", "Galaxy that contains our solar system?", ["Andromeda", "Milky Way", "Sombrero", "Whirlpool"], 1)

# ---- AZ / SOUTHWEST (local flavor, skew med/hard) ----
add("AZ", "easy", "Capital of Arizona?", ["Tucson", "Phoenix", "Mesa", "Flagstaff"], 1)
add("AZ", "easy", "Arizona's famous mile-deep canyon?", ["Bryce", "Grand Canyon", "Zion", "Antelope"], 1)
add("AZ", "med", "Arizona's state nickname?", ["Copper State", "Grand Canyon State", "Sun State", "Cactus State"], 1)
add("AZ", "med", "Tall cactus with arms, symbol of AZ?", ["Cholla", "Saguaro", "Prickly pear", "Barrel"], 1)
add("AZ", "med", "River that carved the Grand Canyon?", ["Gila", "Colorado", "Salt", "Verde"], 1)
add("AZ", "hard", "Arizona's state bird?", ["Roadrunner", "Cactus wren", "Quail", "Condor"], 1)
add("AZ", "hard", "Arizona's state flower?", ["Poppy", "Saguaro blossom", "Desert rose", "Marigold"], 1)
add("AZ", "med", "AZ city that bought the real London Bridge?", ["Sedona", "Lake Havasu City", "Yuma", "Bisbee"], 1)
add("AZ", "hard", "Which is one of Arizona's '5 C's'?", ["Coffee", "Copper", "Coal", "Corn"], 1)
add("AZ", "med", "AZ red-rock tourist town north of Phoenix?", ["Tempe", "Sedona", "Chandler", "Gilbert"], 1)
add("AZ", "hard", "Arizona does NOT observe which time change?", ["Leap year", "Daylight saving", "New Year", "Solstice"], 1)
add("AZ", "med", "Largest city in Arizona?", ["Tucson", "Phoenix", "Mesa", "Glendale"], 1)
add("AZ", "hard", "Year Arizona became a US state (1912)?", ["1850", "1912", "1945", "1976"], 1)
add("AZ", "hard", "AZ desert that shares a name with a saguaro park?", ["Mojave", "Sonoran", "Chihuahuan", "Painted"], 1)


# ================= BATCH 6: BIG NO-REPEAT EXPANSION (v1.5.0, hard-skewed) =================
# Will (2026-07-06): "there is repeating questions. Need more questions ... Make the questions
# harder too." This batch roughly doubles the med+hard tiers (the tiers the 24/7 ambient
# channel draws from) so the new 365-day no-repeat window has a deep pool to cycle through.
# Every fact is canonical + stable or WebSearch/official-doc verified 2026-07-06:
#  - Meshtastic/LoRa specifics verified against meshtastic.org radio-settings + channels docs
#    (LongFast=SF11, LongSlow=SF12/125kHz, Medium Fast=SF9, Short Slow=SF8, Long Turbo=500kHz,
#     default PSK byte 0x01 -> Base64 "AQ==", PSK sizes 0/16/32 bytes = none/AES128/AES256).
#  - All other facts are stable canonical knowledge (capitals, elements, dates, records) with
#    one unambiguous answer and three clearly-wrong distractors. Debatable/volatile facts
#    (current record-holders, contested "fastest", exact heights) were deliberately excluded.
# Options kept SHORT so every question renders under the 200B worst-case (with 🧠 lead).

# ---- SCIENCE (skew hard) ----
add("Science", "med", "Speed of sound in air is about (m/s)?", ["143", "243", "343", "443"], 2)
add("Science", "hard", "Metal with the highest melting point?", ["Iron", "Tungsten", "Gold", "Lead"], 1)
add("Science", "med", "Chemical formula of table salt?", ["NaCl", "KCl", "H2O", "CO2"], 0)
add("Science", "hard", "How many hearts does an octopus have?", ["1", "2", "3", "4"], 2)
add("Science", "hard", "Element with the symbol K?", ["Krypton", "Potassium", "Calcium", "Carbon"], 1)
add("Science", "hard", "Element with the symbol Pb?", ["Lead", "Tin", "Zinc", "Iron"], 0)
add("Science", "med", "Chemical symbol for silver?", ["Ag", "Au", "Si", "Sn"], 0)
add("Science", "hard", "Which planet rotates on its side (extreme tilt)?", ["Uranus", "Venus", "Mars", "Saturn"], 0)
add("Science", "hard", "Which planet rotates backwards (retrograde)?", ["Venus", "Mars", "Jupiter", "Earth"], 0)
add("Science", "hard", "Most abundant element in the universe?", ["Oxygen", "Helium", "Hydrogen", "Carbon"], 2)
add("Science", "hard", "Which blood type is the universal donor?", ["A", "B", "AB", "O-"], 3)
add("Science", "med", "How many chambers are in the human heart?", ["2", "3", "4", "5"], 2)
add("Science", "hard", "The study of fungi is called?", ["Botany", "Mycology", "Zoology", "Ecology"], 1)
add("Science", "hard", "Most reactive halogen element?", ["Fluorine", "Chlorine", "Bromine", "Iodine"], 0)
add("Science", "med", "Diamond is a crystalline form of which element?", ["Carbon", "Silicon", "Boron", "Sulfur"], 0)
add("Science", "med", "Sunlight helps the body make which vitamin?", ["A", "B12", "C", "D"], 3)
add("Science", "med", "Longest bone in the human body?", ["Femur", "Tibia", "Skull", "Ulna"], 0)
add("Science", "hard", "Smallest bone in the human body?", ["Stapes", "Femur", "Rib", "Ulna"], 0)
add("Science", "med", "SI unit of force?", ["Joule", "Newton", "Watt", "Pascal"], 1)
add("Science", "med", "SI unit of electric current?", ["Volt", "Ampere", "Ohm", "Watt"], 1)
add("Science", "med", "What gives soda its fizz?", ["Oxygen", "CO2", "Helium", "Nitrogen"], 1)
add("Science", "med", "How many teeth does a typical adult have?", ["28", "30", "32", "36"], 2)
add("Science", "hard", "Which noble gas glows red-orange in signs?", ["Neon", "Helium", "Argon", "Radon"], 0)
add("Science", "hard", "Absolute zero is about how many degrees C?", ["-100", "-200", "-273", "-373"], 2)
add("Science", "med", "Liquid turning into gas is called?", ["Melting", "Evaporation", "Condensation", "Freezing"], 1)
add("Science", "med", "Most of a cell's DNA is stored in the?", ["Nucleus", "Wall", "Membrane", "Cytoplasm"], 0)
add("Science", "hard", "What color is an octopus's blood?", ["Red", "Blue", "Green", "Clear"], 1)
add("Science", "med", "Force opposing motion between two surfaces?", ["Gravity", "Friction", "Magnetism", "Tension"], 1)

# ---- HISTORY (skew hard) ----
add("History", "hard", "First Emperor of Rome?", ["Julius Caesar", "Augustus", "Nero", "Caligula"], 1)
add("History", "hard", "The French Revolution began in?", ["1689", "1789", "1815", "1848"], 1)
add("History", "hard", "Who co-wrote the Communist Manifesto with Engels?", ["Lenin", "Marx", "Stalin", "Trotsky"], 1)
add("History", "hard", "Only ancient Wonder still standing today?", ["Great Pyramid", "Colossus", "Lighthouse", "Hanging Gardens"], 0)
add("History", "hard", "The Magna Carta was signed in?", ["1066", "1215", "1492", "1607"], 1)
add("History", "hard", "Whose expedition first sailed around the world?", ["Columbus", "Magellan", "Drake", "Cook"], 1)
add("History", "hard", "Which empire built Machu Picchu?", ["Aztec", "Maya", "Inca", "Olmec"], 2)
add("History", "hard", "Who discovered penicillin?", ["Fleming", "Pasteur", "Curie", "Salk"], 0)
add("History", "hard", "The Wright brothers first flew in?", ["1893", "1903", "1913", "1927"], 1)
add("History", "hard", "Whose 1914 assassination helped spark WWI?", ["Franz Ferdinand", "Bismarck", "Wilhelm", "Tito"], 0)
add("History", "hard", "Roman city buried by Vesuvius in 79 AD?", ["Athens", "Pompeii", "Carthage", "Troy"], 1)
add("History", "hard", "The Rosetta Stone helped decode ancient?", ["Latin", "Hieroglyphs", "Runes", "Cuneiform"], 1)
add("History", "med", "The Hundred Years' War was England versus?", ["Spain", "France", "Germany", "Italy"], 1)
add("History", "hard", "Who painted the Sistine Chapel ceiling?", ["Da Vinci", "Michelangelo", "Raphael", "Donatello"], 1)
add("History", "hard", "First woman to fly solo across the Atlantic?", ["Earhart", "Coleman", "Quimby", "Johnson"], 0)
add("History", "med", "The Black Death was a pandemic of the?", ["Cholera", "Plague", "Flu", "Smallpox"], 1)
add("History", "med", "Inventor credited with the telephone?", ["Edison", "Bell", "Tesla", "Morse"], 1)
add("History", "med", "In which year did WWI begin?", ["1901", "1914", "1918", "1929"], 1)
add("History", "hard", "Which US president led during the Civil War?", ["Washington", "Lincoln", "Grant", "Adams"], 1)

# ---- GEOGRAPHY (skew hard) ----
add("Geography", "med", "Capital of Germany?", ["Munich", "Berlin", "Hamburg", "Bonn"], 1)
add("Geography", "med", "Capital of Russia?", ["St Petersburg", "Moscow", "Kiev", "Minsk"], 1)
add("Geography", "med", "Capital of Egypt?", ["Cairo", "Alexandria", "Giza", "Luxor"], 0)
add("Geography", "hard", "Capital of Brazil?", ["Rio", "Brasilia", "Sao Paulo", "Salvador"], 1)
add("Geography", "med", "Capital of Greece?", ["Athens", "Sparta", "Corinth", "Crete"], 0)
add("Geography", "med", "Capital of South Korea?", ["Busan", "Seoul", "Incheon", "Daegu"], 1)
add("Geography", "hard", "Country with the most natural lakes?", ["USA", "Canada", "Russia", "Finland"], 1)
add("Geography", "hard", "The Nile empties into which sea?", ["Red", "Mediterranean", "Black", "Arabian"], 1)
add("Geography", "hard", "African nation famed for resisting colonization?", ["Kenya", "Ethiopia", "Ghana", "Egypt"], 1)
add("Geography", "hard", "Largest island in the world?", ["Greenland", "Madagascar", "Borneo", "Iceland"], 0)
add("Geography", "hard", "Largest US state by area?", ["Texas", "California", "Alaska", "Montana"], 2)
add("Geography", "hard", "Smallest of Earth's oceans?", ["Arctic", "Indian", "Atlantic", "Southern"], 0)
add("Geography", "med", "Mount Kilimanjaro is in which country?", ["Kenya", "Tanzania", "Uganda", "Ethiopia"], 1)
add("Geography", "med", "Which river flows through London?", ["Seine", "Thames", "Danube", "Rhine"], 1)
add("Geography", "med", "Which river flows through Paris?", ["Thames", "Seine", "Rhine", "Po"], 1)
add("Geography", "hard", "Most populous country in Africa?", ["Egypt", "Nigeria", "Ethiopia", "Kenya"], 1)
add("Geography", "hard", "Mountain range dividing Europe and Asia?", ["Alps", "Urals", "Andes", "Atlas"], 1)
add("Geography", "hard", "World's longest international border is between?", ["US-Mexico", "US-Canada", "Russia-China", "India-China"], 1)
add("Geography", "hard", "Which sea has no land coastline?", ["Sargasso", "Coral", "Baltic", "Caspian"], 0)
add("Geography", "med", "Capital of Portugal?", ["Lisbon", "Porto", "Madrid", "Faro"], 0)
add("Geography", "hard", "Constitutional capital of the Netherlands?", ["Rotterdam", "Amsterdam", "The Hague", "Utrecht"], 1)
add("Geography", "hard", "Everest sits on the border of Nepal and?", ["India", "China", "Bhutan", "Pakistan"], 1)

# ---- TECH (skew hard) ----
add("Tech", "med", "RAM loses what when the power is cut?", ["Nothing", "Its data", "Its case", "Speed"], 1)
add("Tech", "med", "What does 'SSD' stand for (start)?", ["Solid State", "Super Speed", "Single Sys", "Serial Store"], 0)
add("Tech", "hard", "Who is regarded as the first computer programmer?", ["Ada Lovelace", "Turing", "Babbage", "Hopper"], 0)
add("Tech", "med", "The 'S' in HTTPS mainly adds?", ["Speed", "Security", "Storage", "Style"], 1)
add("Tech", "med", "Which company owns YouTube?", ["Meta", "Google", "Amazon", "Apple"], 1)
add("Tech", "med", "What does 'VPN' stand for (start)?", ["Virtual Private", "Very Powerful", "Verified Pub", "Viral Peer"], 0)
add("Tech", "hard", "Binary 1010 equals which decimal number?", ["8", "10", "12", "20"], 1)
add("Tech", "hard", "Who is credited with inventing the World Wide Web?", ["Gates", "Berners-Lee", "Jobs", "Torvalds"], 1)
add("Tech", "hard", "A Wi-Fi network's broadcast name is its?", ["IP", "SSID", "MAC", "DNS"], 1)
add("Tech", "hard", "Who created the Linux kernel?", ["Gates", "Torvalds", "Jobs", "Ritchie"], 1)
add("Tech", "med", "An HTTP '404' error means?", ["Server down", "Not found", "Forbidden", "Timeout"], 1)
add("Tech", "hard", "What does 'IoT' stand for (start)?", ["Internet of", "Input on", "Index of", "Image of"], 0)
add("Tech", "med", "CPU clock speed is measured in?", ["Volts", "Hertz", "Bytes", "Amps"], 1)
add("Tech", "med", "One kilobyte is about how many bytes?", ["10", "100", "1000", "1M"], 2)

# ---- POP / CULTURE (skew hard) ----
add("Pop", "med", "Who wrote 'Romeo and Juliet'?", ["Dickens", "Shakespeare", "Austen", "Poe"], 1)
add("Pop", "med", "Author of 'The Lord of the Rings'?", ["Lewis", "Tolkien", "Rowling", "Martin"], 1)
add("Pop", "med", "Which band recorded 'Bohemian Rhapsody'?", ["Beatles", "Queen", "U2", "Oasis"], 1)
add("Pop", "hard", "Who directed 'Pulp Fiction'?", ["Scorsese", "Tarantino", "Coen", "Fincher"], 1)
add("Pop", "med", "Spider-Man's real name?", ["Bruce Wayne", "Peter Parker", "Clark Kent", "Tony Stark"], 1)
add("Pop", "med", "Batman's real name?", ["Clark Kent", "Bruce Wayne", "Tony Stark", "Barry Allen"], 1)
add("Pop", "hard", "Who painted 'The Starry Night'?", ["Monet", "Van Gogh", "Picasso", "Dali"], 1)
add("Pop", "hard", "Which artist famously cut off part of his ear?", ["Picasso", "Van Gogh", "Dali", "Monet"], 1)
add("Pop", "med", "The Beatles formed in which city?", ["London", "Liverpool", "Manchester", "Leeds"], 1)
add("Pop", "hard", "Who wrote 'Pride and Prejudice'?", ["Bronte", "Austen", "Eliot", "Woolf"], 1)
add("Pop", "med", "In which game do you buy and trade properties?", ["Clue", "Monopoly", "Risk", "Sorry"], 1)
add("Pop", "hard", "How many squares on a chessboard?", ["36", "49", "64", "81"], 2)
add("Pop", "hard", "Which chess piece moves only diagonally?", ["Rook", "Bishop", "Knight", "Pawn"], 1)
add("Pop", "med", "Which superhero is 'The Caped Crusader'?", ["Superman", "Batman", "Flash", "Robin"], 1)

# ---- SPORTS (skew hard) ----
add("Sports", "med", "How many players field a baseball team?", ["7", "9", "11", "10"], 1)
add("Sports", "med", "A field goal in American football is worth?", ["2", "3", "6", "1"], 1)
add("Sports", "hard", "The ancient Olympics were first held in?", ["Rome", "Greece", "Egypt", "Persia"], 1)
add("Sports", "med", "How many players are on a volleyball court per side?", ["5", "6", "7", "9"], 1)
add("Sports", "med", "A standard soccer match lasts how many minutes?", ["60", "80", "90", "120"], 2)
add("Sports", "hard", "Which country has won the most FIFA World Cups?", ["Germany", "Brazil", "Italy", "Argentina"], 1)
add("Sports", "med", "In tennis, a score of zero is called?", ["Love", "Nil", "Duck", "Naught"], 0)
add("Sports", "hard", "How many players on a rugby union team?", ["11", "13", "15", "7"], 2)
add("Sports", "hard", "The 'Ashes' is a rivalry in which sport?", ["Cricket", "Rugby", "Golf", "Rowing"], 0)
add("Sports", "hard", "A 'birdie' in golf is how many under par?", ["1", "2", "3", "Even"], 0)
add("Sports", "hard", "Which martial art's name means 'gentle way'?", ["Karate", "Judo", "Taekwondo", "Boxing"], 1)
add("Sports", "med", "How many periods in an ice hockey game?", ["2", "3", "4", "5"], 1)
add("Sports", "med", "Which sport uses a 'slam dunk'?", ["Volleyball", "Basketball", "Tennis", "Golf"], 1)
add("Sports", "med", "A red card in soccer means a player is?", ["Warned", "Sent off", "Subbed", "Captain"], 1)

# ---- NATURE (skew hard) ----
add("Nature", "hard", "What is a group of crows called?", ["Pack", "Murder", "Herd", "School"], 1)
add("Nature", "med", "Largest bird in the world?", ["Eagle", "Ostrich", "Condor", "Albatross"], 1)
add("Nature", "easy", "Which bird is a common symbol of peace?", ["Crow", "Dove", "Owl", "Hawk"], 1)
add("Nature", "med", "How many legs does an insect have?", ["4", "6", "8", "10"], 1)
add("Nature", "med", "An animal that eats only plants is a?", ["Carnivore", "Herbivore", "Omnivore", "Predator"], 1)
add("Nature", "hard", "Largest species of penguin?", ["King", "Emperor", "Gentoo", "Adelie"], 1)
add("Nature", "med", "A frog begins life as a?", ["Chick", "Tadpole", "Larva", "Nymph"], 1)
add("Nature", "med", "Which animal is called the 'ship of the desert'?", ["Horse", "Camel", "Donkey", "Llama"], 1)
add("Nature", "hard", "Tallest type of grass in the world?", ["Wheat", "Bamboo", "Corn", "Reed"], 1)
add("Nature", "hard", "Largest land carnivore on Earth?", ["Lion", "Polar bear", "Tiger", "Grizzly"], 1)
add("Nature", "med", "A baby horse is called a?", ["Calf", "Foal", "Cub", "Kid"], 1)
add("Nature", "med", "Bees make honey primarily from?", ["Water", "Nectar", "Pollen", "Sap"], 1)
add("Nature", "med", "A spider is classified as an?", ["Insect", "Arachnid", "Reptile", "Crustacean"], 1)
add("Nature", "hard", "A group of lions is called a?", ["Pack", "Pride", "Colony", "Troop"], 1)

# ---- FOOD (skew hard) ----
add("Food", "hard", "Which fruit carries its seeds on the outside?", ["Apple", "Strawberry", "Grape", "Cherry"], 1)
add("Food", "med", "Sushi rice is seasoned with?", ["Sugar", "Vinegar", "Soy", "Oil"], 1)
add("Food", "med", "Which country is the origin of tea drinking?", ["India", "China", "Japan", "England"], 1)
add("Food", "med", "Cheese traditionally on a Margherita pizza?", ["Cheddar", "Mozzarella", "Brie", "Feta"], 1)
add("Food", "hard", "Champagne must legally come from which country?", ["Italy", "France", "Spain", "Germany"], 1)
add("Food", "med", "A dried plum is called a?", ["Raisin", "Prune", "Date", "Fig"], 1)
add("Food", "hard", "Tequila is distilled from which plant?", ["Cactus", "Agave", "Corn", "Grape"], 1)
add("Food", "med", "Which vitamin is abundant in citrus fruit?", ["A", "B", "C", "D"], 2)
add("Food", "hard", "Balsamic vinegar traditionally comes from?", ["France", "Italy", "Greece", "Spain"], 1)
add("Food", "med", "Which grain is used to make risotto?", ["Wheat", "Rice", "Barley", "Oat"], 1)

# ---- MUSIC (skew hard) ----
add("Music", "med", "How many musicians are in a quartet?", ["2", "3", "4", "5"], 2)
add("Music", "med", "In music, 'forte' means to play?", ["Soft", "Loud", "Fast", "Slow"], 1)
add("Music", "med", "As a dynamic, 'piano' means to play?", ["Loud", "Soft", "Fast", "High"], 1)
add("Music", "hard", "Who is called the 'King of Rock and Roll'?", ["Elvis", "Chuck Berry", "L. Richard", "B. Holly"], 0)
add("Music", "med", "How many strings on a standard violin?", ["4", "5", "6", "7"], 0)
add("Music", "hard", "Composer of 'The Four Seasons'?", ["Bach", "Vivaldi", "Mozart", "Handel"], 1)
add("Music", "med", "A group of three musicians is a?", ["Duo", "Trio", "Quartet", "Solo"], 1)

# ---- MATH (skew hard) ----
add("Math", "med", "What is 8 x 9?", ["63", "72", "81", "74"], 1)
add("Math", "hard", "Square root of 169?", ["11", "12", "13", "14"], 2)
add("Math", "med", "What is 3 cubed?", ["6", "9", "27", "81"], 2)
add("Math", "med", "How many degrees in a right angle?", ["45", "90", "180", "360"], 1)
add("Math", "med", "What is 11 x 11?", ["111", "121", "131", "144"], 1)
add("Math", "med", "A polygon with 5 sides is a?", ["Square", "Pentagon", "Hexagon", "Octagon"], 1)
add("Math", "med", "What is 20% of 150?", ["20", "25", "30", "35"], 2)
add("Math", "hard", "Smallest positive integer that's neither prime nor composite?", ["0", "1", "2", "3"], 1)
add("Math", "hard", "Sum of the first three prime numbers?", ["8", "9", "10", "11"], 2)
add("Math", "hard", "How many sides does a dodecagon have?", ["10", "11", "12", "14"], 2)
add("Math", "med", "A triangle with all sides equal is?", ["Scalene", "Isosceles", "Equilateral", "Right"], 2)

# ---- GENERAL (skew med/hard) ----
add("General", "med", "Water boils at what temperature in Fahrenheit?", ["180", "212", "232", "100"], 1)
add("General", "hard", "Most spoken native language in the world?", ["English", "Mandarin", "Spanish", "Hindi"], 1)
add("General", "hard", "Roman numeral for 500?", ["C", "D", "M", "L"], 1)
add("General", "med", "Water freezes at what temperature in Fahrenheit?", ["0", "32", "100", "212"], 1)
add("General", "med", "The currency of Japan is the?", ["Won", "Yen", "Yuan", "Baht"], 1)
add("General", "med", "The currency of the United Kingdom is the?", ["Euro", "Pound", "Franc", "Krona"], 1)
add("General", "med", "The currency of India is the?", ["Rupee", "Ringgit", "Rupiah", "Taka"], 0)
add("General", "med", "How many stripes are on the US flag?", ["12", "13", "14", "50"], 1)
add("General", "easy", "How many letters are in the English alphabet?", ["24", "25", "26", "27"], 2)
add("General", "hard", "How many minutes are in a full day?", ["1200", "1440", "2400", "960"], 1)
add("General", "med", "The study of weather is called?", ["Geology", "Meteorology", "Astronomy", "Biology"], 1)
add("General", "med", "The study of living things is called?", ["Biology", "Chemistry", "Physics", "Geology"], 0)
add("General", "med", "How many US states are there?", ["48", "50", "52", "51"], 1)

# ---- SPACE (skew med/hard) ----
add("Space", "med", "Which planet is called the 'Morning Star'?", ["Mars", "Venus", "Mercury", "Jupiter"], 1)
add("Space", "hard", "The Sun is composed mostly of?", ["Oxygen", "Hydrogen", "Iron", "Carbon"], 1)
add("Space", "med", "Pluto is now classified as a?", ["Planet", "Dwarf planet", "Moon", "Comet"], 1)
add("Space", "hard", "A light-year is a measure of?", ["Time", "Distance", "Speed", "Brightness"], 1)
add("Space", "med", "Which planet hosts the Great Red Spot?", ["Mars", "Jupiter", "Saturn", "Neptune"], 1)
add("Space", "med", "The Moon's gravity mainly causes Earth's?", ["Winds", "Tides", "Seasons", "Quakes"], 1)
add("Space", "hard", "How many planets in our system have rings?", ["1", "2", "4", "8"], 2)
add("Space", "med", "A space rock that lands on Earth is a?", ["Meteor", "Meteorite", "Asteroid", "Comet"], 1)
add("Space", "hard", "Mars looks red mainly due to?", ["Iron oxide", "Lava", "Ice", "Copper"], 0)
add("Space", "hard", "Which planet is the least dense (floats in water)?", ["Saturn", "Jupiter", "Neptune", "Earth"], 0)

# ---- MESHTASTIC / LoRa (hard; verified 2026-07-06 vs official docs) ----
add("Mesh", "hard", "Default channel key shown in Base64 as?", ["AQ==", "MQ==", "AA==", "ZZ=="], 0)
add("Mesh", "hard", "Medium Fast preset uses which spreading factor?", ["SF7", "SF9", "SF10", "SF11"], 1)
add("Mesh", "hard", "Short Slow preset spreading factor?", ["SF7", "SF8", "SF9", "SF10"], 1)
add("Mesh", "hard", "Long Slow preset bandwidth?", ["62 kHz", "125 kHz", "250 kHz", "500 kHz"], 1)
add("Mesh", "hard", "A 16-byte PSK selects which cipher?", ["AES128", "AES256", "DES", "None"], 0)
add("Mesh", "hard", "Long Turbo preset bandwidth?", ["125 kHz", "250 kHz", "500 kHz", "62 kHz"], 2)
add("Mesh", "hard", "Meshtastic serializes packets using?", ["JSON", "Protobuf", "XML", "YAML"], 1)


# ================= BATCH 7: PROGRAMMATIC MASS GENERATION (v1.6.0) =================
# Correctness-by-construction generators (math answers COMPUTED, fact tables from vetted
# canonical data) scale the ambient (med+hard) pool past 8,760 for a LITERAL 365-day no-repeat.
# All emitted as difficulty "hard" so the curated MEDIUM tier (the live game) stays untouched.
import gen_bank  # noqa: E402

gen_bank.generate(add)


def main():
    questions = [Question(**q) for q in Q]
    problems = validate_bank(questions, max_bytes=200)
    if problems:
        print("VALIDATION FAILED:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        sys.exit(1)
    out_path = os.path.join(ROOT, "meshquiz", "data", "questions.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(Q, f, ensure_ascii=False, indent=2)
    # stats
    cats = {}
    maxb = 0
    for q in questions:
        cats[q.category] = cats.get(q.category, 0) + 1
        maxb = max(maxb, q.byte_len())
    print(f"OK: wrote {len(Q)} questions to {out_path}")
    print(f"max rendered size: {maxb} bytes (budget 200)")
    print("by category: " + ", ".join(f"{k}={v}" for k, v in sorted(cats.items())))


if __name__ == "__main__":
    main()
