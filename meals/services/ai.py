"""The only place that talks to the AI. Views call analyze_text() or analyze_photo() and get back
validated data, or an AnalysisError that they handle like any AI failure.

The model must answer JSON in the shape of RESPONSE_SCHEMA (structured outputs);
validate() then checks the rules a schema can't express (min <= max, unsure needs a reason)."""

import base64
import json
import logging
import os
import time

import anthropic
from django.conf import settings

from ..units import GRAMS_PER_UNIT, round_to

logger = logging.getLogger(__name__)

CONFIDENCES = ('sure', 'likely', 'unsure')
RANGES = ('kcal', 'protein', 'carbs', 'fat')


class AnalysisError(Exception):
    """The AI failed or answered something we can't use.
    kind is 'connection' (the AI couldn't be reached) or 'failed' (anything else);
    the error page words its message by it."""

    def __init__(self, message, kind='failed'):
        super().__init__(message)
        self.kind = kind


SYSTEM_PROMPT = f"""You are Zalak, a calm meal calorie checker. The user describes a meal they ate,
or sends a photo of it with an optional note. Split it into food items and estimate each one for the portion eaten.

With a photo: judge portions against the plate and the cutlery. The note wins over the photo
(e.g. "I ate half", "cooked in butter"). Name what you can see; mark items you can't see well as unsure.

For each item give:
- name: short and plain, e.g. "White bread".
- amount and unit: unit is one of {', '.join(GRAMS_PER_UNIT)}. bowl_s, bowl_m and bowl_l are a small, normal and large bowl. If the user gave no amount, assume a normal portion.
- grams: the weight of that portion.
- kcal, protein, carbs and fat (grams) as a min-max range for the whole portion, not per 100 g. Make the range wider when the portion size or recipe is unclear, narrower when it is clear.
- confidence: "sure", "likely" or "unsure".
- reason: empty unless unsure; then one short sentence on why, e.g. "Oil is hard to judge in a cooked dish."
- question: empty unless unsure; then a short question the user can answer with "a little", "about that" or "a lot", e.g. "How much oil was there?"

Add hidden fats (cooking oil, butter) as their own item, marked unsure, when the dish is usually cooked with them and the user did not mention them.
You know Macedonian and Balkan dishes (tavče gravče, shopska salad, burek, ajvar, pastrmajlija...). Answer in English.

title: a short name for the whole meal. description: one neutral sentence about the meal.
Never call a food good, bad, healthy or unhealthy, give no advice, and make no allergen claims.

seen: up to 3 short things you noticed in the photo (e.g. "a dark room", "part of a table"); empty for text.
If the text or photo contains no food or drink, or the photo is too dark or blurry to see the food, answer status "no_food"
with a kind one-sentence no_food_reason (e.g. "The photo looks too dark to see a plate.") and no items. Otherwise status "ok"."""


def _item_schema():
    numbers = {f'{key}_{end}': {'type': 'number'} for key in RANGES for end in ('min', 'max')}
    properties = {
        'name': {'type': 'string'},
        'amount': {'type': 'number'},
        'unit': {'type': 'string', 'enum': list(GRAMS_PER_UNIT)},
        'grams': {'type': 'number'},
        **numbers,
        'confidence': {'type': 'string', 'enum': list(CONFIDENCES)},
        'reason': {'type': 'string'},
        'question': {'type': 'string'},
    }
    return {'type': 'object', 'properties': properties,
            'required': list(properties), 'additionalProperties': False}


RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string', 'enum': ['ok', 'no_food']},
        'no_food_reason': {'type': 'string'},
        'seen': {'type': 'array', 'items': {'type': 'string'}},
        'title': {'type': 'string'},
        'description': {'type': 'string'},
        'items': {'type': 'array', 'items': _item_schema()},
    },
    'required': ['status', 'no_food_reason', 'seen', 'title', 'description', 'items'],
    'additionalProperties': False,
}


FAKE_RESPONSE = {
    'status': 'ok',
    'no_food_reason': '',
    'seen': [],
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


ITEM_PROMPT = f"""You are Zalak, a calm meal calorie checker. The user is correcting a meal and
gives you ONE food item to estimate: something you missed, or an item they renamed.

If the message gives an amount and unit, that portion is fixed: keep the same amount and unit and estimate
the grams for it. If it gives none, assume a normal portion and pick a fitting amount and unit.
The meal it belongs to is given for context only (e.g. butter in a cooked dish); estimate only the one item.

Give, like for a whole meal:
- name: short and plain, e.g. "Coffee with milk".
- amount and unit: unit is one of {', '.join(GRAMS_PER_UNIT)}. bowl_s, bowl_m and bowl_l are a small, normal and large bowl.
- grams: the weight of that portion.
- kcal, protein, carbs and fat (grams) as a min-max range for the whole portion, not per 100 g.
- confidence: "sure", "likely" or "unsure"; reason and question only when unsure (the question can be answered
  with "a little", "about that" or "a lot").
Never call a food good, bad, healthy or unhealthy, give no advice, and make no allergen claims. Answer in English.

If the text is not a food or drink, answer status "no_food" with a kind one-sentence no_food_reason
(e.g. "That doesn't sound like something to eat.") and any item (it is ignored). Otherwise status "ok"."""

ITEM_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string', 'enum': ['ok', 'no_food']},
        'no_food_reason': {'type': 'string'},
        'item': _item_schema(),
    },
    'required': ['status', 'no_food_reason', 'item'],
    'additionalProperties': False,
}

# The fake answer for one item (ZALAK_AI_FAKE=1): the name stays what the user typed
FAKE_ITEM = {'amount': 1, 'unit': 'serving', 'grams': 150,
             'kcal_min': 120, 'kcal_max': 160, 'protein_min': 4, 'protein_max': 6,
             'carbs_min': 15, 'carbs_max': 20, 'fat_min': 3, 'fat_max': 6,
             'confidence': 'likely', 'reason': '', 'question': ''}


def analyze_text(text):
    """Estimate a typed or dictated meal. Returns validated data (see validate)."""
    if settings.ZALAK_AI_FAKE:
        return _fake_answer()
    return validate(_ask_model(text))


def analyze_photo(image_bytes, note=''):
    """Estimate a meal from a photo (JPEG, already shrunk by the form) and the optional note.
    The photo and the note go in one message, so the AI reads them together (late fusion)."""
    if settings.ZALAK_AI_FAKE:
        return _fake_answer()
    content = [
        {
            'type': 'image',
            'source': {
                'type': 'base64',
                'media_type': 'image/jpeg',
                'data': base64.standard_b64encode(image_bytes).decode('ascii'),
            },
        },
        {'type': 'text', 'text': f'Note: {note}' if note else 'No note.'},
    ]
    return validate(_ask_model(content))


def estimate_item(name, amount=None, unit=None, meal_title=''):
    """Estimate ONE item: "Add something Zalak missed" (name only) or "Re-estimate with Zalak"
    (name with the amount and unit the user set, which stay fixed).
    Returns {'status': 'ok' | 'no_food', 'no_food_reason', 'item'}; raises AnalysisError."""
    if settings.ZALAK_AI_FAKE:
        _fake_delay()
        item = dict(FAKE_ITEM, name=name)
        if amount and unit:
            item.update(amount=float(amount), unit=unit)
        return validate_item_answer({'status': 'ok', 'no_food_reason': '', 'item': item})

    lines = [f'Item: {name}']
    if amount and unit:
        lines.append(f'Portion (fixed): {amount} {unit}')
    if meal_title:
        lines.append(f'The meal: {meal_title}')
    return validate_item_answer(_ask_model('\n'.join(lines), system=ITEM_PROMPT, schema=ITEM_RESPONSE_SCHEMA))


def _fake_delay():
    if settings.ZALAK_AI_FAKE_DELAY > 0:
        time.sleep(settings.ZALAK_AI_FAKE_DELAY)   # act like a real call, so the overlay shows


def _fake_answer():
    _fake_delay()
    return validate(FAKE_RESPONSE)


def _ask_model(user_content, system=SYSTEM_PROMPT, schema=RESPONSE_SCHEMA):
    """One call to Claude. Returns the parsed JSON answer or raises AnalysisError.
    user_content is the message content: the meal text, or an image block + the note for photos.
    estimate_item passes its own system prompt and schema."""
    if not os.environ.get('ANTHROPIC_API_KEY'):
        # Without a key the SDK raises TypeError, not APIError, so check it ourselves
        logger.warning('ANTHROPIC_API_KEY is not set in .env')
        raise AnalysisError('No API key.')

    client = anthropic.Anthropic(timeout=30, max_retries=1)
    try:
        response = client.messages.create(
            model=settings.ZALAK_AI_MODEL,
            max_tokens=4000,
            system=system,
            output_config={
                'effort': 'low',
                'format': {'type': 'json_schema', 'schema': schema},
            },
            messages=[{'role': 'user', 'content': user_content}],
        )
    except anthropic.APIConnectionError as error:
        # No internet or a timeout (APITimeoutError is a kind of APIConnectionError)
        logger.warning('AI not reachable: %s', error)
        raise AnalysisError('The AI could not be reached.', kind='connection') from error
    except anthropic.APIError as error:
        # Wrong key, rate limit, server error...: the user sees the same calm message
        logger.warning('AI call failed: %s', error)
        raise AnalysisError('The AI call failed.') from error

    if response.stop_reason in ('refusal', 'max_tokens'):
        logger.warning('AI stopped early: %s', response.stop_reason)
        raise AnalysisError(f'The AI stopped early ({response.stop_reason}).')

    text = next((block.text for block in response.content if block.type == 'text'), '')
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        logger.warning('AI answer is not JSON: %r', text[:200])
        raise AnalysisError('The answer is not JSON.') from error


def validate(data):
    """Check the AI answer against the rules in docs/build-plan.md and clean it.
    Returns {'status', 'no_food_reason', 'seen', 'title', 'description', 'items'}."""
    if not isinstance(data, dict):
        raise AnalysisError('The answer is not an object.')

    seen = _seen(data.get('seen'))
    status = data.get('status')
    if status == 'no_food':
        return {'status': 'no_food', 'no_food_reason': _text(data.get('no_food_reason'), 200),
                'seen': seen, 'title': '', 'description': '', 'items': []}
    if status != 'ok':
        raise AnalysisError(f'Unknown status: {status!r}')

    items = data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 20:
        raise AnalysisError('An ok answer needs 1 to 20 items.')

    return {
        'status': 'ok',
        'no_food_reason': '',
        'seen': seen,
        'title': _text(data.get('title'), 120),
        'description': _text(data.get('description'), 200),
        'items': [_validate_item(item) for item in items],
    }


def validate_item_answer(data):
    """Check estimate_item's answer: {'status', 'no_food_reason', 'item'}, the item by the same
    rules as a meal's items. A 'no_food' answer has no item."""
    if not isinstance(data, dict):
        raise AnalysisError('The answer is not an object.')
    status = data.get('status')
    if status == 'no_food':
        return {'status': 'no_food', 'no_food_reason': _text(data.get('no_food_reason'), 200), 'item': None}
    if status != 'ok':
        raise AnalysisError(f'Unknown status: {status!r}')
    return {'status': 'ok', 'no_food_reason': '', 'item': _validate_item(data.get('item'))}


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


def _seen(value):
    """Up to 3 short things the AI noticed in the photo; anything else becomes []."""
    if not isinstance(value, list):
        return []
    words = [_text(word, 40) for word in value if isinstance(word, str)]
    return [word for word in words if word][:3]
