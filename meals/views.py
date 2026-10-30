from django.shortcuts import render, get_object_or_404
from django.http import Http404

from .models import Meal, slot_for_time


def home(request):
    return render(request, 'base.html')


def get_own_meal(request, meal_id):
    """Return the visitor's own, not-deleted meal, or raise 404. Used by every meal view."""
    if request.user.is_authenticated:
        return get_object_or_404(Meal, id=meal_id, user=request.user, deleted_at__isnull=True)

    session_key = request.session.session_key

    if not session_key:
        raise Http404

    return get_object_or_404(
        Meal, id=meal_id, user=None, session_key=session_key, deleted_at__isnull=True
    )


# Options of the slot select: value, label, icon
SLOT_OPTIONS = [
    ('breakfast', 'Breakfast', 'bi-cup-hot'),
    ('lunch', 'Lunch', 'bi-egg-fried'),
    ('snack', 'Snack', 'bi-cookie'),
    ('dinner', 'Dinner', 'bi-fork-knife'),
]
SLOT_ICONS = {value: icon for value, label, icon in SLOT_OPTIONS}


def result(request, meal_id):
    meal = get_own_meal(request, meal_id)
    slot = meal.slot or slot_for_time(meal.eaten_at)
    context = {
        'meal': meal,
        'items': meal.items_with_bars,
        'slot': slot,
        'slot_icon': SLOT_ICONS[slot],
        'slot_options': SLOT_OPTIONS,
    }
    return render(request, 'meals/result.html', context)


# Placeholders until their chunk is built, so the navigation never breaks.

def diary(request):
    return render(request, 'coming_soon.html', {'title': 'Diary'})


def statistics(request):
    return render(request, 'coming_soon.html', {'title': 'Statistics'})


def profile(request):
    return render(request, 'coming_soon.html', {'title': 'Profile'})


def add_meal(request):
    return render(request, 'coming_soon.html', {'title': 'Add meal'})


# Temporary style page (remove in chunk 19).

def style(request):
    swatches = ['bg', 'card', 'tint', 'line', 'accent', 'ink', 'muted',
                'water', 'protein', 'carbs', 'fat',
                'peach', 'butter', 'lilac', 'sky', 'danger', 'danger-bg']
    return render(request, 'style.html', {'swatches': swatches})
