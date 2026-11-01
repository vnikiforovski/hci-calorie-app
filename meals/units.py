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


# The Unit sheet on Edit item (Figma "Unit picker"): 4 tabs, each unit with a hint.
# Bowl is one row; its size (bowl_s / bowl_m / bowl_l) is picked under the list.
UNIT_TABS = [
    ('portion', 'Portion', [
        ('piece', 'piece', 'one item, like a burek or an apple'),
        ('slice', 'slice', 'bread, pizza, cake'),
        ('bowl', 'bowl', 'soups, stews, salads'),
        ('plate', 'plate', 'a full plate'),
        ('serving', 'serving', 'one restaurant portion'),
    ]),
    ('weight', 'Weight', [
        ('g', 'grams (g)', ''),
        ('kg', 'kilograms (kg)', ''),
        ('oz', 'ounces (oz)', ''),
        ('lb', 'pounds (lb)', ''),
    ]),
    ('volume', 'Volume', [
        ('ml', 'millilitres (ml)', ''),
        ('l', 'litres (l)', ''),
        ('cup', 'cups', 'about 240 ml'),
        ('fl_oz', 'fluid ounces (fl oz)', ''),
    ]),
    ('kitchen', 'Kitchen', [
        ('tsp', 'teaspoon (tsp)', 'about 5 ml'),
        ('tbsp', 'tablespoon (tbsp)', 'about 15 ml'),
        ('handful', 'handful', 'nuts, berries, chips'),
        ('pinch', 'pinch', 'salt, spices'),
    ]),
]
BOWL_SIZES = [('bowl_s', 'Small'), ('bowl_m', 'Medium'), ('bowl_l', 'Large')]

# The name under the big number on Edit item ("medium bowl"), where it differs from UNIT_CHOICES
STEPPER_LABELS = {'bowl_s': 'small bowl', 'bowl_m': 'medium bowl', 'bowl_l': 'large bowl'}

# Units measured exactly: the stepper moves in even steps and the amount is shown as a decimal.
# Every other unit is counted (2 slices, 1½ bowls) and walks the fraction ladder.
MEASURED_STEPS = {
    'g': Decimal('10'), 'ml': Decimal('10'),
    'kg': Decimal('0.1'), 'l': Decimal('0.1'),
    'oz': Decimal('1'), 'fl_oz': Decimal('1'),
    'lb': Decimal('0.25'),
}
COUNT_LADDER = [Decimal(v) for v in ['0.25', '0.5', '0.75', '1', '1.5', '2', '2.5', '3']] + \
               [Decimal(n) for n in range(4, 21)]

# Exact by definition: grams_for never uses an item's own grams per unit for these
WEIGHT_UNITS = {'g', 'kg', 'oz', 'lb'}

# Units written without a plural: "2 tbsp", "300 ml"
NO_PLURAL = {'g', 'kg', 'oz', 'lb', 'ml', 'l', 'fl_oz', 'tsp', 'tbsp'}

MIN_GRAMS = 5        # the AI validator's minimum too
MAX_GRAMS = 5000

FRACTIONS = {Decimal('0.25'): '¼', Decimal('0.5'): '½', Decimal('0.75'): '¾'}


def round_to(value, step):
    """Round a number to the nearest step (10 for kcal, 5 for grams, 1 for macros)."""
    steps = (Decimal(value) / step).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return int(steps * step)


def to_grams(amount, unit):
    """Convert an amount in a unit to grams, rounded to 5."""
    return round_to(Decimal(amount) * GRAMS_PER_UNIT[unit], 5)


def grams_for(amount, unit, known=()):
    """Grams for an amount on Edit item. `known` holds portions we already know for this
    item as (amount, unit, grams): the AI's first, then the saved one. The first in the
    same unit gives the item's own grams per unit (the AI's "2 slices · 80 g" makes
    3 slices 120 g, not the table's 90 g); otherwise the table above is used.
    Weight units are exact, so they always use the table.
    Rounded to 5, at least 5. static/js/portion.js does exactly the same."""
    for base_amount, base_unit, base_grams in known:
        if base_unit == unit and base_amount and unit not in WEIGHT_UNITS:
            grams = round_to(Decimal(amount) * Decimal(base_grams) / Decimal(str(base_amount)), 5)
            break
    else:
        grams = to_grams(amount, unit)
    return max(grams, MIN_GRAMS)


UNIT_LABELS = {unit: label for group, units in UNIT_CHOICES for unit, label in units}


def stepper_label(unit, amount):
    """The unit under the big number on Edit item: 'medium bowl', '2 slices' -> 'slices', 'g'."""
    label = STEPPER_LABELS.get(unit, UNIT_LABELS[unit])
    if Decimal(str(amount)) > 1 and unit not in NO_PLURAL:
        label += 'es' if label.endswith('ch') else 's'
    return label


def format_amount(amount):
    """1.5 -> '1½', 0.25 -> '¼', 2 -> '2', 0.3 -> '0.3'."""
    amount = Decimal(amount)
    whole = int(amount)
    fraction = amount - whole
    if fraction in FRACTIONS:
        return f"{whole or ''}{FRACTIONS[fraction]}"
    return f"{amount.normalize():f}"
