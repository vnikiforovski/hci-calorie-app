"""Builds meals/fixtures/demo.json: the demo account Ana and her week of meals (chunk 20).

Run it from the project folder:
    python manage.py shell -c "exec(open('meals/fixtures/build_demo.py', encoding='utf-8').read())"
Then load it into a database with the built-in command:
    python manage.py loaddata demo

It works inside a transaction that is rolled back, so the database it runs on is never changed.
The meals go through the app's own code: services.ai.validate() checks each answer like a real AI
answer, and views.apply_analysis() turns it into items (per 100 g) and keeps ai_response, so Reset
and Re-estimate work on demo meals too. The photos in demo_photos_src/ (not in git) are shrunk with
forms.shrink_photo into meals/fixtures/demo_photos/, which loaddata's meals point at as media/meals/demo/.
To move the demo week, change FIRST_DAY and run it again.
"""
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core import serializers
from django.db import transaction
from django.utils import timezone

from meals.forms import shrink_photo
from meals.models import Meal, Profile
from meals.services.ai import validate
from meals.views import apply_analysis

FIRST_DAY = date(2026, 10, 26)          # a Monday: a full week, then Mon 2 and Tue 3 Nov (9 days)
EMAIL = 'ana@zalak.demo'
PASSWORD = 'zalak-demo-2026'            # written in docs/dev/demo-script.md
USER_ID = 900                           # high ids, so loading never overwrites someone's own rows
FIRST_MEAL_ID = 9001
FIRST_ITEM_ID = 90001

FIXTURES = Path(settings.BASE_DIR) / 'meals' / 'fixtures'
SOURCE = Path(settings.BASE_DIR) / 'demo_photos_src'
PHOTOS = FIXTURES / 'demo_photos'


def food(name, amount, unit, grams, kcal, protein, carbs, fat, confidence='likely', reason='', question=''):
    """One item as the AI would answer it: totals for the portion, as ranges."""
    return {'name': name, 'amount': amount, 'unit': unit, 'grams': grams,
            'kcal_min': kcal[0], 'kcal_max': kcal[1], 'protein_min': protein[0], 'protein_max': protein[1],
            'carbs_min': carbs[0], 'carbs_max': carbs[1], 'fat_min': fat[0], 'fat_max': fat[1],
            'confidence': confidence, 'reason': reason, 'question': question}


OIL = food('Cooking oil', 1, 'tbsp', 10, (20, 60), (0, 0), (0, 0), (2, 7), 'unsure',
           'Oil is hard to see in a dish.', 'How much was there?')
BREAD = food('White bread', 2, 'slice', 60, (150, 170), (5, 6), (28, 32), (1, 2), 'sure')
WHITE_CHEESE = food('White cheese', 1, 'handful', 40, (100, 120), (6, 7), (1, 2), (8, 10), 'likely')

# The meals: title, the neutral line, the items. Same title = the same meal for "Most logged".
MEALS = {
    'yogurt': ('Yogurt with honey and walnuts', 'A light breakfast with protein and good fats.', [
        food('Greek yogurt', 1, 'bowl_s', 200, (190, 240), (16, 20), (8, 10), (10, 14), 'likely'),
        food('Honey', 1, 'tbsp', 20, (60, 65), (0, 0), (16, 17), (0, 0), 'sure'),
        food('Walnuts', 1, 'handful', 30, (190, 200), (4, 5), (4, 4), (18, 20), 'likely'),
    ]),
    'tavce': ('Tavče gravče with bread', 'A filling lunch with good protein and fibre.', [
        food('Tavče gravče', 1, 'bowl_m', 300, (390, 480), (18, 24), (50, 60), (12, 18), 'likely'),
        BREAD,
        OIL,
    ]),
    'coffee': ('Coffee with milk', 'A small drink between meals.', [
        food('Coffee with milk', 1, 'cup', 240, (60, 90), (3, 4), (5, 6), (3, 4), 'likely'),
    ]),
    'chicken': ('Chicken with rice and salad', 'A balanced plate with lots of protein.', [
        food('Grilled chicken breast', 150, 'g', 150, (230, 260), (42, 47), (0, 0), (5, 6), 'sure'),
        food('White rice', 1, 'serving', 150, (190, 210), (4, 4), (42, 45), (0, 1), 'likely'),
        food('Green salad', 1, 'bowl_s', 120, (20, 30), (1, 2), (3, 4), (0, 1), 'sure'),
    ]),
    'eggs': ('Scrambled eggs and toast', 'A warm breakfast with protein.', [
        food('Scrambled eggs', 2, 'piece', 100, (140, 170), (12, 13), (1, 1), (10, 12), 'likely'),
        food('Toast', 2, 'slice', 60, (150, 170), (5, 6), (28, 32), (1, 2), 'sure'),
        food('Butter', 1, 'tsp', 5, (30, 40), (0, 0), (0, 0), (4, 4), 'unsure',
             'Butter melts into the eggs, so it is hard to see.', 'How much butter did you use?'),
    ]),
    'burek': ('Meat burek with yogurt', 'A big, warm pastry; a filling meal.', [
        food('Meat burek', 1, 'piece', 250, (650, 800), (22, 28), (55, 65), (38, 50), 'likely'),
        food('Yogurt drink', 1, 'cup', 240, (140, 160), (8, 9), (11, 12), (7, 8), 'sure'),
    ]),
    'apple': ('Apple and almonds', 'A small snack with fibre.', [
        food('Apple', 1, 'piece', 180, (90, 100), (0, 1), (23, 25), (0, 0), 'sure'),
        food('Almonds', 1, 'handful', 30, (170, 180), (6, 6), (6, 6), (14, 15), 'likely'),
    ]),
    'shopska': ('Shopska salad with bread', 'A fresh dinner with vegetables.', [
        food('Tomato, cucumber and pepper', 1, 'bowl_m', 300, (60, 80), (3, 4), (12, 14), (1, 1), 'sure'),
        WHITE_CHEESE,
        BREAD,
        OIL,
    ]),
    'lentils': ('Lentil soup with bread', 'A warm, filling soup with plant protein.', [
        food('Lentil soup', 1, 'bowl_m', 300, (210, 260), (13, 16), (32, 38), (4, 7), 'likely'),
        food('White bread', 1, 'slice', 30, (75, 85), (2, 3), (14, 16), (0, 1), 'sure'),
    ]),
    'banana': ('Banana', 'A quick snack.', [
        food('Banana', 1, 'piece', 120, (100, 110), (1, 1), (25, 27), (0, 0), 'sure'),
    ]),
    'pasta': ('Spaghetti with tomato sauce', 'A comforting plate of pasta.', [
        food('Spaghetti', 1, 'plate', 250, (390, 430), (14, 15), (75, 80), (2, 3), 'likely'),
        food('Tomato sauce', 1, 'serving', 150, (60, 90), (2, 3), (9, 12), (2, 4), 'likely'),
        food('White cheese', 1, 'handful', 30, (75, 90), (4, 5), (1, 1), (6, 7), 'likely'),
        food('Olive oil', 1, 'tbsp', 10, (40, 90), (0, 0), (0, 0), (5, 10), 'unsure',
             'Some oil shines on the pasta; the amount is a guess.', 'How much oil was on it?'),
    ]),
    'ajvar': ('Toast with ajvar and cheese', 'A quick breakfast with vegetables.', [
        food('Toast', 2, 'slice', 60, (150, 170), (5, 6), (28, 32), (1, 2), 'sure'),
        food('Ajvar', 2, 'tbsp', 30, (30, 45), (0, 1), (3, 4), (2, 3), 'likely'),
        WHITE_CHEESE,
    ]),
    'kebapi': ('Kebapi with onion and bread', 'A hearty grilled dinner.', [
        food('Kebapi', 5, 'piece', 200, (480, 560), (30, 34), (2, 4), (36, 42), 'likely'),
        food('Raw onion', 1, 'handful', 40, (15, 20), (0, 1), (3, 4), (0, 0), 'sure'),
        BREAD,
    ]),
    'sandwich': ('Ham and cheese sandwich', 'A simple lunch on the go.', [
        food('Ham and cheese sandwich', 1, 'piece', 180, (380, 460), (20, 24), (38, 44), (14, 20), 'likely'),
    ]),
    'chocolate': ('Milk chocolate', 'A small sweet.', [
        food('Milk chocolate', 4, 'piece', 25, (130, 140), (2, 2), (14, 15), (7, 8), 'sure'),
    ]),
    'pizza': ('Pizza margherita', 'Two slices from the pizzeria.', [
        food('Pizza margherita', 2, 'slice', 220, (500, 600), (20, 24), (64, 72), (16, 22), 'likely'),
    ]),
}

# The week: (day number from FIRST_DAY, "HH:MM", slot, meal, how it was entered, photo or None).
# Typed and dictated meals keep the words; a photo meal keeps its note.
WEEK = [
    (0, '08:10', 'breakfast', 'yogurt', 'photo', 'yogurt-honey-walnuts.jpg'),
    (0, '13:20', 'lunch', 'tavce', 'photo', 'tavce-gravce.jpg'),
    (0, '16:30', 'snack', 'coffee', 'text', None),
    (0, '20:00', 'dinner', 'chicken', 'text', None),
    (1, '08:30', 'breakfast', 'eggs', 'text', None),
    (1, '12:50', 'lunch', 'burek', 'photo', 'burek.jpg'),
    (1, '17:00', 'snack', 'apple', 'text', None),
    (1, '19:40', 'dinner', 'shopska', 'photo', 'shopska.jpg'),
    (2, '08:00', 'breakfast', 'yogurt', 'text', None),
    (2, '13:10', 'lunch', 'lentils', 'voice', None),
    (2, '16:15', 'snack', 'coffee', 'text', None),
    (2, '16:45', 'snack', 'banana', 'text', None),          # two snacks: the "2 meals" sheet
    (2, '20:30', 'dinner', 'pasta', 'photo', 'pasta.jpg'),
    (3, '09:00', 'breakfast', 'ajvar', 'text', None),
    (3, '13:30', 'lunch', 'tavce', 'text', None),
    (3, '20:10', 'dinner', 'kebapi', 'voice', None),
    (4, '08:20', 'breakfast', 'yogurt', 'photo', 'yogurt-honey-walnuts.jpg'),
    (4, '12:40', 'lunch', 'sandwich', 'text', None),
    (4, '17:20', 'snack', 'chocolate', 'text', None),
    (4, '21:00', 'dinner', 'pizza', 'text', None),
    (5, '10:30', 'breakfast', 'eggs', 'text', None),
    (5, '14:00', 'lunch', 'chicken', 'text', None),
    (5, '17:30', 'snack', 'coffee', 'voice', None),
    (5, '20:30', 'dinner', 'shopska', 'photo', 'shopska.jpg'),
    (6, '10:00', 'breakfast', 'yogurt', 'text', None),
    (6, '14:30', 'lunch', 'lentils', 'text', None),
    (6, '19:30', 'dinner', 'sandwich', 'text', None),
    (7, '08:15', 'breakfast', 'ajvar', 'text', None),
    (7, '13:00', 'lunch', 'chicken', 'voice', None),
    (7, '17:10', 'snack', 'apple', 'text', None),
    (8, '08:30', 'breakfast', 'eggs', 'text', None),
    (8, '13:15', 'lunch', 'burek', 'photo', 'burek.jpg'),
    (8, '16:40', 'snack', 'coffee', 'text', None),
]

# What the user typed or said, per meal (a photo meal gets a short note instead)
WORDS = {
    'yogurt': 'greek yogurt with honey and walnuts',
    'tavce': 'tavče gravče and two slices of bread',
    'coffee': 'coffee with milk',
    'chicken': 'grilled chicken breast with rice and a green salad',
    'eggs': 'two scrambled eggs with butter and two toasts',
    'burek': 'a piece of meat burek and a yogurt drink',
    'apple': 'an apple and a handful of almonds',
    'shopska': 'shopska salad with two slices of bread',
    'lentils': 'a bowl of lentil soup with a slice of bread',
    'banana': 'a banana',
    'pasta': 'spaghetti with tomato sauce and white cheese',
    'ajvar': 'two toasts with ajvar and white cheese',
    'kebapi': 'five kebapi with onion and bread',
    'sandwich': 'ham and cheese sandwich',
    'chocolate': 'four pieces of milk chocolate',
    'pizza': 'two slices of pizza margherita',
}
NOTES = {'tavce': 'homemade, from the pot', 'burek': 'from the bakery', 'shopska': 'with oil'}


def shrink_photos():
    """Small copies of the photos for git (the originals stay in demo_photos_src/)."""
    PHOTOS.mkdir(exist_ok=True)
    for name in sorted({photo for *rest, photo in WEEK if photo}):
        with open(SOURCE / name, 'rb') as original:
            small = shrink_photo(original)
        (PHOTOS / name).write_bytes(small.read())


def build():
    objects = []
    when_joined = timezone.make_aware(datetime.combine(FIRST_DAY - timedelta(days=1), time(19, 0)))
    user = User(id=USER_ID, username=EMAIL, email=EMAIL, first_name='Ana', date_joined=when_joined,
                password=make_password(PASSWORD, salt='zalakdemo2026'))   # a fixed salt: the same file every run
    user.save()   # signals.create_profile makes her Profile
    profile = Profile.objects.get(user=user)
    profile.height_cm, profile.weight_kg, profile.birth_year = 168, '61.5', 2004
    profile.activity_level, profile.uncertainty, profile.seen_photo_tips = 'medium', 'ask', True
    profile.save()

    meals, items = [], []
    for number, (day, clock, slot, key, method, photo) in enumerate(WEEK):
        title, description, foods = MEALS[key]
        eaten = timezone.make_aware(datetime.combine(FIRST_DAY + timedelta(days=day),
                                                     time(*map(int, clock.split(':')))))
        meal = Meal(id=FIRST_MEAL_ID + number, user=user, slot=slot, input_method=method,
                    text=NOTES.get(key, '') if photo else WORDS[key],
                    photo=f'meals/demo/{photo}' if photo else None,
                    status='logged', eaten_at=eaten)
        meal.save()   # logged straight away: signals.count_logged_meals counts it
        apply_analysis(meal, validate({'status': 'ok', 'title': title, 'description': description,
                                       'seen': [], 'items': foods}))
        Meal.objects.filter(id=meal.id).update(created_at=eaten + timedelta(minutes=3))
        meal.refresh_from_db()
        meals.append(meal)
        items.extend(meal.items.order_by('position'))

    profile.refresh_from_db()   # meals_logged, set by the signal
    profile.pk = profile.id = USER_ID
    for number, item in enumerate(items):
        item.pk = item.id = FIRST_ITEM_ID + number
    objects = [user, profile] + meals + items
    return serializers.serialize('json', objects, indent=1, ensure_ascii=False), len(meals), profile.meals_logged


class Rollback(Exception):
    pass


shrink_photos()
try:
    with transaction.atomic():
        data, meal_count, counted = build()
        raise Rollback
except Rollback:
    pass
(FIXTURES / 'demo.json').write_text(data + '\n', encoding='utf-8')
print(f'demo.json: Ana, {meal_count} meals (meals_logged {counted}), photos in {PHOTOS}')
