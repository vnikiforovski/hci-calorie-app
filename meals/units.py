from decimal import Decimal, ROUND_HALF_UP

# Grouped choices: Django shows each group as an <optgroup> in forms and the admin.
UNIT_CHOICES = [
    ('Weight', [
        ('g', 'g'),
        ('kg', 'kg'),
        ('oz', 'oz'),
        ('lb', 'lb'),
    ]),
    ('Volume', [
        ('ml', 'ml'),
        ('l', 'l'),
        ('cup', 'cup'),
        ('fl_oz', 'fl oz'),
    ]),
    ('Kitchen', [
        ('tsp', 'tsp'),
        ('tbsp', 'tbsp'),
        ('handful', 'handful'),
        ('pinch', 'pinch'),
    ]),
    ('Portion', [
        ('piece', 'piece'),
        ('slice', 'slice'),
        ('bowl_s', 'small bowl'),
        ('bowl_m', 'bowl'),
        ('bowl_l', 'large bowl'),
        ('plate', 'plate'),
        ('serving', 'serving'),
    ]),
]

# Grams in one unit. Weight is exact; volume assumes 1 ml = 1 g;
# kitchen and portion units are typical defaults the user can correct.
GRAMS_PER_UNIT = {
    'g': Decimal('1'),
    'kg': Decimal('1000'),
    'oz': Decimal('28.35'),
    'lb': Decimal('453.6'),
    'ml': Decimal('1'),
    'l': Decimal('1000'),
    'cup': Decimal('240'),
    'fl_oz': Decimal('29.6'),
    'tsp': Decimal('5'),
    'tbsp': Decimal('15'),
    'handful': Decimal('30'),
    'pinch': Decimal('0.5'),
    'piece': Decimal('100'),
    'slice': Decimal('30'),
    'bowl_s': Decimal('200'),
    'bowl_m': Decimal('300'),
    'bowl_l': Decimal('450'),
    'plate': Decimal('400'),
    'serving': Decimal('150'),
}


def round_to(value, step):
    """Round a number to the nearest step (10 for kcal, 5 for grams, 1 for macros)."""
    steps = (Decimal(value) / step).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return int(steps * step)


def to_grams(amount, unit):
    """Convert an amount in a unit to grams, rounded to 5."""
    return round_to(Decimal(amount) * GRAMS_PER_UNIT[unit], 5)
