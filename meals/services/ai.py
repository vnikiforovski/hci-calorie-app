"""The only place that talks to the AI. Views call analyze_text() and get back
validated data, or an AnalysisError that they handle like any AI failure.

Chunk 4: the answer is a fixed fake. Chunk 5 replaces it with the Anthropic call."""

from ..units import GRAMS_PER_UNIT, round_to

CONFIDENCES = ('sure', 'likely', 'unsure')
RANGES = ('kcal', 'protein', 'carbs', 'fat')


class AnalysisError(Exception):
    """The AI failed or answered something we can't use."""


FAKE_RESPONSE = {
    'status': 'ok',
    'no_food_reason': '',
    'title': 'Tavče gravče with bread and salad',
    'description': 'A filling lunch with good protein and fibre.',
    'items': [
        {'name': 'Tavče gravče', 'amount': 1, 'unit': 'bowl_m', 'grams': 300,
         'kcal_min': 390, 'kcal_max': 480, 'protein_min': 18, 'protein_max': 24,
         'carbs_min': 50, 'carbs_max': 60, 'fat_min': 12, 'fat_max': 18,
         'confidence': 'likely', 'reason': '', 'question': ''},
        {'name': 'White bread', 'amount': 2, 'unit': 'slice', 'grams': 60,
         'kcal_min': 150, 'kcal_max': 170, 'protein_min': 5, 'protein_max': 6,
         'carbs_min': 28, 'carbs_max': 32, 'fat_min': 1, 'fat_max': 2,
         'confidence': 'sure', 'reason': '', 'question': ''},
        {'name': 'Shopska salad', 'amount': 1, 'unit': 'bowl_s', 'grams': 150,
         'kcal_min': 60, 'kcal_max': 100, 'protein_min': 4, 'protein_max': 6,
         'carbs_min': 6, 'carbs_max': 8, 'fat_min': 4, 'fat_max': 8,
         'confidence': 'likely', 'reason': '', 'question': ''},
        {'name': 'Cooking oil', 'amount': 1, 'unit': 'tbsp', 'grams': 10,
         'kcal_min': 20, 'kcal_max': 60, 'protein_min': 0, 'protein_max': 0,
         'carbs_min': 0, 'carbs_max': 0, 'fat_min': 2, 'fat_max': 7,
         'confidence': 'unsure', 'reason': 'Oil is hard to see in a dish.',
         'question': 'How much was there?'},
    ],
}


def analyze_text(text):
    """Estimate a typed or dictated meal. Returns validated data (see validate)."""
    return validate(FAKE_RESPONSE)


def validate(data):
    """Check the AI answer against the rules in docs/build-plan.md and clean it.
    Returns {'status', 'no_food_reason', 'title', 'description', 'items'}."""
    if not isinstance(data, dict):
        raise AnalysisError('The answer is not an object.')

    status = data.get('status')
    if status == 'no_food':
        return {'status': 'no_food', 'no_food_reason': _text(data.get('no_food_reason'), 200),
                'title': '', 'description': '', 'items': []}
    if status != 'ok':
        raise AnalysisError(f'Unknown status: {status!r}')

    items = data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 20:
        raise AnalysisError('An ok answer needs 1 to 20 items.')

    return {
        'status': 'ok',
        'no_food_reason': '',
        'title': _text(data.get('title'), 120),
        'description': _text(data.get('description'), 200),
        'items': [_validate_item(item) for item in items],
    }


def _validate_item(item):
    if not isinstance(item, dict):
        raise AnalysisError('An item is not an object.')

    name = _text(item.get('name'), 100)
    if not name:
        raise AnalysisError('An item has no name.')

    amount = _number(item.get('amount', 1))
    unit = item.get('unit')
    if unit not in GRAMS_PER_UNIT:
        unit = 'serving'   # a unit we don't know still reads as one portion

    confidence = item.get('confidence')
    if confidence not in CONFIDENCES:
        raise AnalysisError(f'{name}: unknown confidence {confidence!r}')
    reason = _text(item.get('reason'), 150)
    if confidence == 'unsure' and not reason:
        raise AnalysisError(f'{name}: unsure needs a reason.')

    clean = {
        'name': name,
        'amount': amount or 1,
        'unit': unit,
        'grams': max(5, round_to(_number(item.get('grams')), 5)),
        'confidence': confidence,
        'reason': reason,
        'question': _text(item.get('question'), 150),
    }
    for key in RANGES:
        low, high = _number(item.get(f'{key}_min')), _number(item.get(f'{key}_max'))
        if low > high:
            raise AnalysisError(f'{name}: {key}_min is bigger than {key}_max.')
        clean[f'{key}_min'], clean[f'{key}_max'] = low, high
    return clean


def _number(value):
    """A number >= 0 (True/False and text are rejected)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise AnalysisError(f'Not a number >= 0: {value!r}')
    return value


def _text(value, limit):
    """Trimmed text, cut to the field length. Missing text becomes ''."""
    return str(value or '').strip()[:limit]
