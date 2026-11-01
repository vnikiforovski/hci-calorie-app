from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.urls import reverse
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

# The steps the Analyzing overlay shows for a typed meal (the photo has its own in chunk 8)
TEXT_STEPS = ['Reading your meal', 'Finding the foods', 'Estimating portions']


def result(request, meal_id):
    meal = get_own_meal(request, meal_id)
    if meal.status == 'draft' and not meal.items.exists():
        # A draft without items has no Result yet: show the way forward instead
        if (meal.ai_response or {}).get('status') == 'no_food':
            return redirect('no_food', meal_id=meal.id)
        return redirect('analysis_error', meal_id=meal.id)
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


def analyze_meal(meal):
    """Ask the AI about a saved draft and redirect to what comes next:
    Result, No food found, or the error page. Used by Analyze and Try again."""
    try:
        data = analyze_text(meal.text)
    except AnalysisError as error:
        # The draft and its input stay saved, so nothing is lost (FR29)
        return redirect(reverse('analysis_error', args=[meal.id]) + f'?why={error.kind}')

    if data['status'] == 'no_food':
        meal.ai_response = data
        meal.save()
        meal.items.all().delete()
        return redirect('no_food', meal_id=meal.id)

    apply_analysis(meal, data)
    return redirect('result', meal_id=meal.id)


def get_own_draft(request, meal_id):
    """Like get_own_meal, but only a draft: logged meals are edited from meal detail (chunk 15)."""
    meal = get_own_meal(request, meal_id)
    if meal.status != 'draft':
        raise Http404
    return meal


def text_input(request, meal_id=None):
    """Text and voice. Without meal_id it starts a new draft; with one ("Edit the text")
    it edits that draft, so a corrected meal doesn't leave a second draft behind."""
    meal = get_own_draft(request, meal_id) if meal_id else None

    if request.method == 'POST':
        form = TextMealForm(request.POST, instance=meal)
        if form.is_valid():
            meal = form.save(commit=False)   # input_method (text or voice) comes from the form
            if not meal.slot:
                meal.slot = slot_for_time(timezone.now())
            if meal_id is None:
                set_owner(request, meal)
            # The draft is saved first, so the input is kept even if the AI fails (FR29)
            meal.save()
            return analyze_meal(meal)
    elif meal:
        form = TextMealForm(instance=meal)
    else:
        slot = request.GET.get('slot')
        if slot not in SLOT_ICONS:
            slot = slot_for_time(timezone.now())
        form = TextMealForm(initial={'slot': slot})

    context = {
        'form': form,
        'slot': form['slot'].value(),
        'steps': TEXT_STEPS,
    }
    return render(request, 'meals/text_input.html', context)


def retry(request, meal_id):
    """Try again on the error page: the same draft goes to the AI again."""
    meal = get_own_draft(request, meal_id)
    if request.method != 'POST':
        # A retry costs an AI call, so only a button press (POST) starts one
        return redirect('analysis_error', meal_id=meal.id)
    return analyze_meal(meal)


def analysis_error(request, meal_id):
    meal = get_own_draft(request, meal_id)
    why = request.GET.get('why')
    if why != 'connection':
        why = 'failed'
    context = {
        'meal': meal,
        'why': why,
        'steps': TEXT_STEPS,
    }
    return render(request, 'meals/error.html', context)


def no_food(request, meal_id):
    meal = get_own_draft(request, meal_id)
    reason = (meal.ai_response or {}).get('no_food_reason', '')
    context = {
        'meal': meal,
        'reason': reason,
    }
    return render(request, 'meals/no_food.html', context)


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
