from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone

from .forms import PhotoMealForm, TextMealForm
from .models import Meal, MealItem, Profile, slot_for_time
from .services.ai import AnalysisError, analyze_photo, analyze_text


def home(request):
    """Temporary Home (chunk 9): a plain list of the logged meals. Chunk 14 builds the real one."""
    meals = []
    if request.user.is_authenticated:
        meals = (Meal.objects
                 .filter(user=request.user, status='logged', deleted_at__isnull=True)
                 .prefetch_related('items')[:20])
    return render(request, 'meals/home.html', {'meals': meals})


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

# The steps the Analyzing overlay shows, for a typed / dictated meal and for a photo
TEXT_STEPS = ['Reading your meal', 'Finding the foods', 'Estimating portions']
PHOTO_STEPS = ['Looking at your photo', 'Finding the foods', 'Estimating portions']


def steps_for(meal):
    return PHOTO_STEPS if meal and meal.photo else TEXT_STEPS


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
        if meal.photo:
            with meal.photo.open('rb') as photo:
                data = analyze_photo(photo.read(), meal.text)
        else:
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
            if meal.photo:
                # "Describe it instead" on a photo draft: it becomes a text meal, still one draft
                meal.photo.delete(save=False)
            # An empty slot is filled from the time by the pre_save signal (signals.py)
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


def photo_input(request, meal_id=None):
    """Photo + note. Without meal_id it starts a new draft; with one ("Take another photo")
    it gives that draft a new photo, so a retake doesn't leave a second draft behind."""
    meal = get_own_draft(request, meal_id) if meal_id else None
    old_photo = meal.photo.name if meal and meal.photo else ''

    if request.method == 'POST':
        form = PhotoMealForm(request.POST, request.FILES, instance=meal)
        if form.is_valid():
            meal = form.save(commit=False)
            meal.input_method = 'photo'
            # An empty slot is filled from the time by the pre_save signal (signals.py)
            if meal_id is None:
                set_owner(request, meal)
            # Saved first, so the photo and note are kept even if the AI fails (FR29)
            meal.save()
            if old_photo and old_photo != meal.photo.name:
                meal.photo.storage.delete(old_photo)   # the retaken photo replaces the old file
            return analyze_meal(meal)
    elif meal:
        form = PhotoMealForm(instance=meal)
    else:
        slot = request.GET.get('slot')
        if slot not in SLOT_ICONS:
            slot = slot_for_time(timezone.now())
        form = PhotoMealForm(initial={'slot': slot})

    slot = form['slot'].value() or slot_for_time(timezone.now())
    context = {
        'form': form,
        'slot': slot,
        'steps': PHOTO_STEPS,
        'show_tips': not tips_seen(request),   # the tips open by themselves until "Don't show again"
    }
    return render(request, 'meals/photo_input.html', context)


def tips_seen(request):
    """True after "Don't show these tips again": kept in the Profile, or in the session for a guest."""
    if request.user.is_authenticated:
        return Profile.objects.filter(user=request.user, seen_photo_tips=True).exists()
    return request.session.get('seen_photo_tips', False)


@require_POST
def photo_tips_seen(request):
    """Sent by photo_tips.js when the tips close with "Don't show these tips again" ticked."""
    if request.user.is_authenticated:
        # get_or_create: the Profile signal for new users only arrives in chunk 12
        profile, created = Profile.objects.get_or_create(user=request.user)
        profile.seen_photo_tips = True
        profile.save()
    else:
        request.session['seen_photo_tips'] = True
    return HttpResponse(status=204)


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
        'steps': steps_for(meal),
    }
    return render(request, 'meals/error.html', context)


@require_POST
def log_meal(request, meal_id):
    """Log on Result: the draft becomes a logged meal in the chosen slot (FR23).
    The pre_save signal counts it in Profile.meals_logged."""
    if not request.user.is_authenticated:
        raise Http404   # until chunk 13, where a guest's Log opens "Keep this meal?"
    meal = get_own_draft(request, meal_id)

    slot = request.POST.get('slot')
    if slot in SLOT_ICONS:
        meal.slot = slot
    meal.status = 'logged'
    meal.save()

    # Shown once on the next page by the toast context processor
    request.session['toast'] = {
        'text': f'Logged to {meal.slot}',
        'undo_url': reverse('undo_log', args=[meal.id]),
    }
    return redirect('home')


@require_POST
def undo_log(request, meal_id):
    """Undo in the "Logged to lunch" toast: the meal is a draft again, back on its Result."""
    meal = get_own_meal(request, meal_id)
    if meal.status != 'logged':
        raise Http404
    meal.status = 'draft'
    meal.save()   # the signal takes the meal off the counter again
    return redirect('result', meal_id=meal.id)


@require_POST
def just_checking(request, meal_id):
    """Just checking on Result: the draft is thrown away (FR34). Nothing was logged.
    The post_delete signal removes the photo file."""
    meal = get_own_draft(request, meal_id)
    meal.delete()
    return redirect('home')


def no_food(request, meal_id):
    meal = get_own_draft(request, meal_id)
    answer = meal.ai_response or {}
    context = {
        'meal': meal,
        'reason': answer.get('no_food_reason', ''),
        'seen': answer.get('seen', []),
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
