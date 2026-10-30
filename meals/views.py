from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.utils import timezone

from .forms import TextMealForm
from .models import Meal, MealItem, slot_for_time
from .services.ai import AnalysisError, analyze_text


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


def set_owner(request, meal):
    """A signed-in user owns the meal; a guest owns it through their session (FR2)."""
    if request.user.is_authenticated:
        meal.user = request.user
    else:
        if not request.session.session_key:
            request.session.create()
        meal.session_key = request.session.session_key


def apply_analysis(meal, data):
    """Save a validated AI answer on the draft: title, description and the items.
    The AI gives totals for the portion; we store them per 100 g (grams is the single source)."""
    meal.title = data['title']
    meal.description = data['description']
    meal.ai_response = data
    meal.save()

    meal.items.all().delete()   # a Retry (chunk 6) replaces the old items
    for position, item in enumerate(data['items']):
        grams = item['grams']
        MealItem.objects.create(
            meal=meal,
            position=position,
            name=item['name'],
            amount=item['amount'],
            unit=item['unit'],
            grams=grams,
            kcal_min_100g=round(item['kcal_min'] * 100 / grams),
            kcal_max_100g=round(item['kcal_max'] * 100 / grams),
            protein_min_100g=round(item['protein_min'] * 100 / grams, 1),
            protein_max_100g=round(item['protein_max'] * 100 / grams, 1),
            carbs_min_100g=round(item['carbs_min'] * 100 / grams, 1),
            carbs_max_100g=round(item['carbs_max'] * 100 / grams, 1),
            fat_min_100g=round(item['fat_min'] * 100 / grams, 1),
            fat_max_100g=round(item['fat_max'] * 100 / grams, 1),
            confidence=item['confidence'],
            reason=item['reason'],
            question=item['question'],
        )


def text_input(request):
    if request.method == 'POST':
        form = TextMealForm(request.POST)
        if form.is_valid():
            meal = form.save(commit=False)
            meal.input_method = 'text'
            if not meal.slot:
                meal.slot = slot_for_time(timezone.now())
            set_owner(request, meal)
            meal.save()

            # The draft is saved first, so the input is kept even if the AI fails (FR29)
            try:
                data = analyze_text(meal.text)
            except AnalysisError:
                form.add_error(None, "Zalak couldn't analyze this right now. Your text is kept, so try again.")
            else:
                if data['status'] == 'no_food':
                    form.add_error(None, data['no_food_reason'] or "Zalak couldn't find any food in this.")
                else:
                    apply_analysis(meal, data)
                    return redirect('result', meal_id=meal.id)
    else:
        slot = request.GET.get('slot')
        if slot not in SLOT_ICONS:
            slot = slot_for_time(timezone.now())
        form = TextMealForm(initial={'slot': slot})

    context = {
        'form': form,
        'slot': form['slot'].value(),
    }
    return render(request, 'meals/text_input.html', context)


# Placeholders until their chunk is built, so the navigation never breaks.

def diary(request):
    return render(request, 'coming_soon.html', {'title': 'Diary'})


def statistics(request):
    return render(request, 'coming_soon.html', {'title': 'Statistics'})


def profile(request):
    return render(request, 'coming_soon.html', {'title': 'Profile'})


def add_meal(request):
    # Until the Add meal sheet (chunk 14), "+" goes straight to Text and voice
    return redirect('text_input')


# Temporary style page (remove in chunk 19).

def style(request):
    swatches = ['bg', 'card', 'tint', 'line', 'accent', 'ink', 'muted',
                'water', 'protein', 'carbs', 'fat',
                'peach', 'butter', 'lilac', 'sky', 'danger', 'danger-bg']
    return render(request, 'style.html', {'swatches': swatches})
