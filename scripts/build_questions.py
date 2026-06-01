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

from meshquiz.questions import Question, validate_bank  # noqa: E402

# Each entry: (category, difficulty, question, [opt1,opt2,opt3,opt4], answer_index)
# Keep questions + options SHORT — they must render within 200 UTF-8 bytes.
Q = []


def add(cat, diff, q, opts, ans):
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
