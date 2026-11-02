import calendar
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone

from .forms import MealItemForm, PhotoMealForm, ProfileDetailsForm, SignUpForm, TextMealForm
from .models import Meal, MealItem, Profile, slot_for_time
from .services.ai import AnalysisError, analyze_photo, analyze_text, estimate_item
from .units import (BOWL_SIZES, COUNT_LADDER, GRAMS_PER_UNIT, MAX_GRAMS, MEASURED_STEPS, MIN_GRAMS,
                    NO_PLURAL, UNIT_TABS, WEIGHT_UNITS, format_amount, stepper_label)


def home(request):
    """The landing page. A guest gets Welcome (chunk 12); a signed-in user gets Home (chunk 14):
    the week strip, what was eaten that day, and the four meal slots. ?date= picks the day."""
    if not request.user.is_authenticated:
        return render(request, 'meals/welcome.html')
    kept = pop_kept_meal(request)
    if kept:
        # Signed in from "Keep this meal?": the guest's meal is logged (signals.keep_guest_meal)
        request.session['toast'] = logged_toast(kept)

    today = timezone.localdate()
    day = parse_day(request.GET.get('date')) or today
    logged = Meal.objects.filter(user=request.user, status='logged', deleted_at__isnull=True)
    day_meals = logged.filter(eaten_at__date=day).prefetch_related('items').order_by('eaten_at')

    # One queryset per slot, like the exam's index grouped by specialty
    slots = []
    for value, label, icon in SLOT_OPTIONS:
        meals = list(day_meals.filter(slot=value))
        slots.append({
            'value': value,
            'label': label,
            'icon': icon,
            'meals': meals,
            'summary': slot_summary(meals),
            'kcal_min': sum(meal.kcal_min for meal in meals),
            'kcal_max': sum(meal.kcal_max for meal in meals),
        })

    all_meals = [meal for slot in slots for meal in slot['meals']]
    totals = {name: sum(getattr(meal, name) for meal in all_meals)
              for name in ['kcal_min', 'kcal_max', 'protein_min', 'protein_max',
                           'carbs_min', 'carbs_max', 'fat_min', 'fat_max']}
    macros = [
        {'key': 'protein', 'name': 'Protein', 'min': totals['protein_min'], 'max': totals['protein_max']},
        {'key': 'carbs', 'name': 'Carbs', 'min': totals['carbs_min'], 'max': totals['carbs_max']},
        {'key': 'fat', 'name': 'Fat', 'min': totals['fat_min'], 'max': totals['fat_max']},
    ]
    # The bar in the Eaten card: one part per slot that has meals, as wide as its share
    # of the day (the middle of each range), with the legend in words beside it
    bar = [{'value': slot['value'], 'label': slot['label'],
            'share': (slot['kcal_min'] + slot['kcal_max']) // 2}
           for slot in slots if slot['kcal_max']]

    month, calendar_open = parse_month(request.GET.get('month'), day)
    context = {
        'day': day,
        'is_today': day == today,
        'eaten_label': eaten_label(day, today),
        'greeting': greeting(),
        'week': week_strip(day),
        'calendar': calendar_month(logged, month, day),
        'calendar_open': calendar_open,
        'slots': slots,
        'totals': totals,
        'macros': macros,
        'bar': bar,
        # Figma "Home · First day": until the very first meal is logged
        'first_day': not logged.exists(),
        # The Add meal sheet logs to the day on screen (decided 2 Nov); today needs nothing
        'add_day': day if day != today else None,
    }
    return render(request, 'meals/home.html', context)


# ---------- Home helpers (chunk 14) ----------

WEEKDAY_SHORT = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']


def parse_day(value):
    """A day from ?date= or ?day= (2026-11-02) that is today or earlier, else None.
    The future is never shown or logged to (docs/05, constraints)."""
    try:
        day = date.fromisoformat(value or '')
    except ValueError:
        return None
    return day if day <= timezone.localdate() else None


def parse_month(value, day):
    """The month the calendar sheet shows: ?month=2026-10 after its ‹ › arrows (the sheet then
    opens by itself), otherwise the selected day's month. Never after this month."""
    this_month = timezone.localdate().replace(day=1)
    try:
        year, month = (int(part) for part in (value or '').split('-'))
        first = date(year, month, 1)
    except ValueError:
        return day.replace(day=1), False
    return min(first, this_month), True


def home_url(day=None, month=None):
    """Home for a day (and a calendar month). Today is plain "/", so the URL stays clean."""
    params = {}
    if day and day != timezone.localdate():
        params['date'] = day.isoformat()
    if month:
        params['month'] = month.strftime('%Y-%m')
    url = reverse('home')
    return f'{url}?{urlencode(params)}' if params else url


def greeting():
    """ "Good afternoon" on the desktop Home, from the local hour."""
    hour = timezone.localtime().hour
    if hour < 12:
        return 'Good morning'
    if hour < 18:
        return 'Good afternoon'
    return 'Good evening'


def eaten_label(day, today):
    """The Eaten card's label: always "eaten", never "left" (docs/06)."""
    if day == today:
        return 'Eaten today'
    if day == today - timedelta(days=1):
        return 'Eaten yesterday'
    return f'Eaten on {day:%a} {day.day}'


def slot_summary(meals):
    """The line under a slot's name: "Nothing yet", the meal's title, or "2 meals · A, B"."""
    titles = [meal.title or 'Meal' for meal in meals]
    if not titles:
        return 'Nothing yet'
    if len(titles) == 1:
        return titles[0]
    return f'{len(titles)} meals · ' + ', '.join(titles)


def week_strip(day):
    """Mo–Su of the selected day's week. Future days are not links. ‹ goes a week back
    (same weekday); › goes a week forward but never past today, and is gone on this week."""
    today = timezone.localdate()
    monday = day - timedelta(days=day.weekday())
    days = []
    for offset in range(7):
        this = monday + timedelta(days=offset)
        days.append({
            'date': this,
            'short': WEEKDAY_SHORT[offset],
            'url': home_url(this),
            'is_selected': this == day,
            'is_future': this > today,
        })
    sunday = monday + timedelta(days=6)
    return {
        'days': days,
        'prev_url': home_url(day - timedelta(days=7)),
        'next_url': home_url(min(day + timedelta(days=7), today)) if sunday < today else None,
    }


def calendar_month(logged, first, selected):
    """The "Jump to a date" month (Figma): weeks from Monday, None outside the month,
    a dot on days with logged meals, future days not links."""
    today = timezone.localdate()
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month)
    times = logged.filter(eaten_at__date__range=(weeks[0][0], weeks[-1][-1])).values_list('eaten_at', flat=True)
    meal_days = {timezone.localtime(eaten_at).date() for eaten_at in times}

    rows = []
    for week in weeks:
        row = []
        for this in week:
            if this.month != first.month:
                row.append(None)
                continue
            row.append({
                'date': this,
                'url': home_url(this),
                'has_meals': this in meal_days,
                'is_selected': this == selected,
                'is_today': this == today,
                'is_future': this > today,
            })
        rows.append(row)

    previous = (first - timedelta(days=1)).replace(day=1)
    following = (first + timedelta(days=31)).replace(day=1)
    return {
        'first': first,
        'weeks': rows,
        'prev_url': home_url(selected, previous),
        'prev_month': previous,
        'next_url': home_url(selected, following) if following <= today else None,
        'next_month': following,
    }


# ---------- Accounts (chunk 12). Sign in and Sign out are Django's LoginView / LogoutView (urls.py). ----------

def signup(request):
    """Create account, step 1. The account is made here and signed in, so step 2 only
    fills in the Profile (and the password never waits in the session)."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.email             # Zalak signs in with the e-mail
            user.set_password(form.cleaned_data['password'])   # stored hashed (NFR18)
            user.save()                            # the post_save signal creates the Profile
            login(request, user)
            return redirect('signup_details')
    else:
        form = SignUpForm()
    context = {
        'form': form,
        # The e-mail already has an account: offer "Sign in instead" under the message
        'email_taken': form.has_error('email', 'taken'),
    }
    return render(request, 'meals/signup_1.html', context)


@login_required
def signup_details(request):
    """Create account, step 2 ("A bit about you"): height, weight and activity, all optional.
    Finish saves them; "Skip for now" saves nothing. Both end on Home with a welcome toast."""
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        if 'skip' in request.POST:
            return welcome_home(request)
        form = ProfileDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return welcome_home(request)
    else:
        form = ProfileDetailsForm(instance=profile)
    return render(request, 'meals/signup_2.html', {'form': form})


def welcome_home(request):
    """The end of sign-up: Home, with a one-time "Welcome to Zalak, Ana" toast.
    After a guest's Log it also says where the kept meal went, with Undo."""
    name = request.user.first_name
    text = f'Welcome to Zalak, {name}' if name else 'Welcome to Zalak'
    kept = pop_kept_meal(request)
    if kept:
        toast = logged_toast(kept)
        toast['text'] = f'{text} · {toast["text"]}'
    else:
        toast = {'text': text}
    request.session['toast'] = toast
    return redirect('home')


def pop_kept_meal(request):
    """The guest meal that signals.keep_guest_meal logged at sign-up or sign-in, once, or None."""
    meal_id = request.session.pop('kept_meal_id', None)
    if meal_id is None:
        return None
    return Meal.objects.filter(id=meal_id, user=request.user, status='logged',
                               deleted_at__isnull=True).first()


def logged_toast(meal):
    """ "Logged to lunch · Undo", after Log and after a guest's meal was kept."""
    return {
        'text': f'Logged to {meal.slot}',
        'undo_url': reverse('undo_log', args=[meal.id]),
    }


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
        # Set by add_item when Zalak couldn't add the item: the name comes back with a message
        'add_item_error': request.session.pop('add_item_error', None),
    }
    return render(request, 'meals/result.html', context)


GUEST_DRAFT_HOURS = 24


def delete_old_guest_drafts():
    """Guest drafts nobody came back to for a day are deleted. A queryset delete still sends
    post_delete for each meal, so signals.remove_photo_file removes their photos too."""
    cutoff = timezone.now() - timedelta(hours=GUEST_DRAFT_HOURS)
    Meal.objects.filter(user=None, status='draft', created_at__lt=cutoff).delete()


def set_owner(request, meal):
    """A signed-in user owns the meal; a guest owns it through their session (FR2).
    Called for every new draft, which is when old guest drafts are cleaned up."""
    delete_old_guest_drafts()
    if request.user.is_authenticated:
        meal.user = request.user
    else:
        if not request.session.session_key:
            request.session.create()
        meal.session_key = request.session.session_key


def item_fields(ai_item):
    """The MealItem fields for one validated AI item. The AI gives totals for the portion;
    we store them per 100 g (grams is the single source). Used by Analyze, Add and Re-estimate."""
    grams = ai_item['grams']
    return {
        'name': ai_item['name'],
        'amount': ai_item['amount'],
        'unit': ai_item['unit'],
        'grams': grams,
        'kcal_min_100g': round(ai_item['kcal_min'] * 100 / grams),
        'kcal_max_100g': round(ai_item['kcal_max'] * 100 / grams),
        'protein_min_100g': round(ai_item['protein_min'] * 100 / grams, 1),
        'protein_max_100g': round(ai_item['protein_max'] * 100 / grams, 1),
        'carbs_min_100g': round(ai_item['carbs_min'] * 100 / grams, 1),
        'carbs_max_100g': round(ai_item['carbs_max'] * 100 / grams, 1),
        'fat_min_100g': round(ai_item['fat_min'] * 100 / grams, 1),
        'fat_max_100g': round(ai_item['fat_max'] * 100 / grams, 1),
        'confidence': ai_item['confidence'],
        'reason': ai_item['reason'],
        'question': ai_item['question'],
    }


def apply_analysis(meal, data):
    """Save a validated AI answer on the draft: title, description and the items."""
    meal.title = data['title']
    meal.description = data['description']
    meal.ai_response = data
    meal.save()

    meal.items.all().delete()   # a Retry (chunk 6) replaces the old items
    for position, ai_item in enumerate(data['items']):
        MealItem.objects.create(meal=meal, position=position, **item_fields(ai_item))


def remember_ai_item(meal, position, ai_item):
    """Keep Zalak's answer for an item in meal.ai_response['items'][position], where Reset and
    the grams rule look for it (MealItem.ai_estimate). position is always the item's index there."""
    answer = meal.ai_response if isinstance(meal.ai_response, dict) else {'status': 'ok'}
    items = list(answer.get('items') or [])
    while len(items) <= position:
        items.append(None)   # a gap (e.g. items made in the admin) keeps the positions apart
    items[position] = ai_item
    answer['items'] = items
    meal.ai_response = answer
    meal.save(update_fields=['ai_response'])


def next_position(meal):
    """Where an added item goes: after every item and every AI answer, so nothing collides."""
    last_item = max(meal.items.values_list('position', flat=True), default=-1)
    ai_items = []
    if isinstance(meal.ai_response, dict):
        ai_items = meal.ai_response.get('items') or []
    return max(last_item + 1, len(ai_items))


def item_url(meal, item):
    """Result, scrolled to one item's card (its id="item-<id>")."""
    return reverse('result', args=[meal.id]) + f'#item-{item.id}'


NO_FOOD_ITEM = "Zalak couldn't find a food or drink in that."


def ai_problem(error):
    """The calm words for an AI failure on Add or Re-estimate."""
    if error.kind == 'connection':
        return 'Connection lost. Check your internet and try again.'
    return "Zalak couldn't estimate that just now. Try again."


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


def picked_day(request, meal_id):
    """The past day a new meal goes to: Home on Mon 12 sends day=… with "+" (decided 2 Nov).
    None means now: today, an edited draft, or a missing, odd or future day."""
    if meal_id is not None:
        return None
    day = parse_day(request.POST.get('day') if request.method == 'POST' else request.GET.get('day'))
    return day if day and day != timezone.localdate() else None


def eaten_on(day):
    """The current clock time on a past day."""
    now = timezone.localtime()
    return now.replace(year=day.year, month=day.month, day=day.day)


def text_input(request, meal_id=None):
    """Text and voice. Without meal_id it starts a new draft; with one ("Edit the text")
    it edits that draft, so a corrected meal doesn't leave a second draft behind."""
    meal = get_own_draft(request, meal_id) if meal_id else None
    day = picked_day(request, meal_id)

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
                if day:
                    meal.eaten_at = eaten_on(day)
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
        'day': day,
        'steps': TEXT_STEPS,
    }
    return render(request, 'meals/text_input.html', context)


def photo_input(request, meal_id=None):
    """Photo + note. Without meal_id it starts a new draft; with one ("Take another photo")
    it gives that draft a new photo, so a retake doesn't leave a second draft behind."""
    meal = get_own_draft(request, meal_id) if meal_id else None
    old_photo = meal.photo.name if meal and meal.photo else ''
    day = picked_day(request, meal_id)

    if request.method == 'POST':
        form = PhotoMealForm(request.POST, request.FILES, instance=meal)
        if form.is_valid():
            meal = form.save(commit=False)
            meal.input_method = 'photo'
            # An empty slot is filled from the time by the pre_save signal (signals.py)
            if meal_id is None:
                set_owner(request, meal)
                if day:
                    meal.eaten_at = eaten_on(day)
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
        'day': day,
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


def portion_data(item):
    """Everything portion.js needs for the live preview on Edit item, read from the saved
    item (before a form changes it). Passed to the page with the json_script filter."""
    ai = item.ai_estimate
    per_100g = ['kcal_min', 'kcal_max', 'protein_min', 'protein_max',
                'carbs_min', 'carbs_max', 'fat_min', 'fat_max']
    return {
        'known': [[float(amount), unit, grams] for amount, unit, grams in item.known_portions],
        'saved': {'amount': float(item.amount), 'unit': item.unit,
                  'kcalMin': item.kcal_min, 'kcalMax': item.kcal_max},
        'ai': {'name': ai['name'], 'amount': ai['amount'], 'unit': ai['unit']} if ai else None,
        'per100': {name: float(getattr(item, f'{name}_100g')) for name in per_100g},
        'gramsPerUnit': {unit: float(grams) for unit, grams in GRAMS_PER_UNIT.items()},
        'labels': {unit: stepper_label(unit, 1) for unit in GRAMS_PER_UNIT},
        'steps': {unit: float(step) for unit, step in MEASURED_STEPS.items()},
        'ladder': [float(value) for value in COUNT_LADDER],
        'noPlural': sorted(NO_PLURAL),
        'weightUnits': sorted(WEIGHT_UNITS),
        'minGrams': MIN_GRAMS,
        'maxGrams': MAX_GRAMS,
    }


def edit_item(request, meal_id, item_id):
    """Edit item (FR18, FR19): rename it or change its amount and unit, with a live preview.
    Works for a draft and for a logged meal (meal detail reuses it in chunk 15)."""
    meal = get_own_meal(request, meal_id)
    item = get_object_or_404(MealItem, id=item_id, meal=meal)   # the item must be in this meal
    data = portion_data(item)   # before the form changes the instance

    if request.method == 'POST':
        form = MealItemForm(request.POST, instance=item)
        if form.is_valid():
            item = form.save(commit=False)
            item.grams = form.cleaned_data['grams']   # from units.grams_for, never from the browser
            item.edited_by_user = True
            item.save()
            request.session['toast'] = {'text': 'Changes saved'}
            return redirect(item_url(meal, item))
    else:
        form = MealItemForm(instance=item)
    return render_edit_item(request, meal, item, form, data)


def render_edit_item(request, meal, item, form, data, problem=''):
    """The Edit item page; also shown again by re_estimate_item when Zalak couldn't answer."""
    context = {
        'meal': meal,
        'item': item,
        'form': form,
        'problem': problem,
        'portion_data': data,
        'unit_tabs': UNIT_TABS,
        'bowl_sizes': BOWL_SIZES,
        'can_delete': meal.items.count() > 1,
        # The first paint, before portion.js takes over (it uses the same numbers)
        'amount_text': format_amount(data['saved']['amount']),
        'unit_text': stepper_label(item.unit, item.amount),
    }
    return render(request, 'meals/edit_item.html', context)


# What Undo needs to put a removed item back exactly as it was (everything but id and meal)
ITEM_FIELDS = ['name', 'amount', 'unit', 'grams',
               'kcal_min_100g', 'kcal_max_100g', 'protein_min_100g', 'protein_max_100g',
               'carbs_min_100g', 'carbs_max_100g', 'fat_min_100g', 'fat_max_100g',
               'confidence', 'reason', 'question', 'edited_by_user', 'position']


@require_POST
def delete_item(request, meal_id, item_id):
    """Delete item on Edit item (FR21). The last item stays, so Result is never empty:
    Just checking drops the whole meal. A copy waits in the session for Undo."""
    meal = get_own_meal(request, meal_id)
    item = get_object_or_404(MealItem, id=item_id, meal=meal)
    if meal.items.count() <= 1:
        return redirect('edit_item', meal_id=meal.id, item_id=item.id)

    # The session holds JSON only, so the Decimal fields are kept as text
    copy = {}
    for field in ITEM_FIELDS:
        value = getattr(item, field)
        copy[field] = str(value) if isinstance(value, Decimal) else value
    request.session['removed_item'] = {'meal_id': meal.id, 'fields': copy}

    item.delete()
    request.session['toast'] = {
        'text': f'{item.name} removed',
        'undo_url': reverse('undo_remove_item', args=[meal.id]),
    }
    return redirect('result', meal_id=meal.id)


@require_POST
def undo_remove_item(request, meal_id):
    """Undo in the "Bread removed" toast: the item comes back with its numbers and its place
    in the list (position), so Reset still finds Zalak's original. Works once."""
    meal = get_own_meal(request, meal_id)
    removed = request.session.get('removed_item')
    if removed and removed['meal_id'] == meal.id:
        del request.session['removed_item']
        MealItem.objects.create(meal=meal, **removed['fields'])
    return redirect('result', meal_id=meal.id)


@require_POST
def add_item(request, meal_id):
    """"Add something Zalak missed" on Result (FR20): one small AI call for the typed item.
    If Zalak can't answer, the name comes back on Result with a calm message and Try again."""
    meal = get_own_meal(request, meal_id)
    name = request.POST.get('name', '').strip()[:100]
    if not name:
        return redirect('result', meal_id=meal.id)

    try:
        answer = estimate_item(name, meal_title=meal.title)
    except AnalysisError as error:
        request.session['add_item_error'] = {'name': name, 'message': ai_problem(error)}
        return redirect(reverse('result', args=[meal.id]) + '#add-item')

    if answer['status'] == 'no_food':
        message = answer['no_food_reason'] or NO_FOOD_ITEM
        request.session['add_item_error'] = {'name': name, 'message': message}
        return redirect(reverse('result', args=[meal.id]) + '#add-item')

    position = next_position(meal)
    item = MealItem.objects.create(meal=meal, position=position, **item_fields(answer['item']))
    remember_ai_item(meal, position, answer['item'])
    request.session['toast'] = {'text': f'{item.name} added'}
    return redirect(item_url(meal, item))


@require_POST
def re_estimate_item(request, meal_id, item_id):
    """"Re-estimate with Zalak" on Edit item: new numbers for the name, amount and unit on the
    screen (e.g. after a rename). The user's amount and unit stay; Zalak gives the grams for them.
    Zalak's answer replaces its old one, so Reset afterwards means this estimate."""
    meal = get_own_meal(request, meal_id)
    item = get_object_or_404(MealItem, id=item_id, meal=meal)
    data = portion_data(item)
    form = MealItemForm(request.POST, instance=item)
    if not form.is_valid():
        return render_edit_item(request, meal, item, form, data)

    amount, unit = form.cleaned_data['amount'], form.cleaned_data['unit']
    # If Zalak can't answer, nothing is saved: the page comes back with what the user typed
    try:
        answer = estimate_item(form.cleaned_data['name'], amount, unit, meal.title)
    except AnalysisError as error:
        return render_edit_item(request, meal, item, form, data, problem=ai_problem(error))
    if answer['status'] == 'no_food':
        problem = answer['no_food_reason'] or NO_FOOD_ITEM
        return render_edit_item(request, meal, item, form, data, problem=problem)

    ai_item = dict(answer['item'], amount=float(amount), unit=unit)   # the user's portion stays
    fields = item_fields(ai_item)
    for name, value in fields.items():
        setattr(item, name, value)
    item.amount = amount
    item.edited_by_user = False   # the numbers are Zalak's again
    item.save()
    remember_ai_item(meal, item.position, ai_item)
    request.session['toast'] = {'text': f'{item.name} re-estimated'}
    return redirect(item_url(meal, item))


@require_POST
def answer_question(request, meal_id, item_id):
    """A little / About that / A lot under an unsure item's question: Zalak's portion
    ×0.5, ×1 or ×1.5, from Zalak's own portion. The user answered, so the item becomes "likely"
    and the question goes (an unsure item always shows its reason). Edit item can still change it."""
    meal = get_own_meal(request, meal_id)
    item = get_object_or_404(MealItem, id=item_id, meal=meal)
    if not item.can_ask:
        raise Http404
    factors = {value: factor for value, label, factor in MealItem.ANSWERS}
    factor = factors.get(request.POST.get('answer'))
    if factor is not None:
        item.amount, item.unit, item.grams = item.answer_portion(factor)
        item.confidence = 'likely'
        item.edited_by_user = True
        item.save()
    return redirect(item_url(meal, item))


@require_POST
def log_meal(request, meal_id):
    """Log on Result: the draft becomes a logged meal in the chosen slot (FR23).
    The pre_save signal counts it in Profile.meals_logged.
    A guest gets here from "Keep this meal?" (FR2, T7): the draft waits for the account."""
    meal = get_own_draft(request, meal_id)

    slot = request.POST.get('slot')
    if slot in SLOT_ICONS:
        meal.slot = slot

    if not request.user.is_authenticated:
        meal.save()   # still a draft, but in the slot the guest picked
        # login() will give the session a new key, so the draft's id and today's key are
        # kept in the session now; signals.keep_guest_meal logs the meal after sign-up / sign-in
        request.session['guest_meal'] = {
            'id': meal.id,
            'session_key': request.session.session_key,
            'slot': meal.slot,
        }
        if request.POST.get('then') == 'sign_in':
            return redirect('sign_in')
        return redirect('signup')

    meal.status = 'logged'
    meal.save()

    # Shown once on the next page by the toast context processor
    request.session['toast'] = logged_toast(meal)
    # Home opens on the meal's day, so a meal logged to Mon 12 is seen landing there
    return redirect(home_url(timezone.localdate(meal.eaten_at)))


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
    waiting = request.session.get('guest_meal')
    if waiting and waiting['id'] == meal.id:
        del request.session['guest_meal']   # nothing is waiting for an account any more
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
# They are personal pages, so a guest is sent to Sign in first (LOGIN_URL in settings).

@login_required
def diary(request):
    return render(request, 'coming_soon.html', {'title': 'Diary'})


@login_required
def statistics(request):
    return render(request, 'coming_soon.html', {'title': 'Statistics'})


@login_required
def profile(request):
    # Sign out lives here until chunk 18 builds the real Profile page
    return render(request, 'coming_soon.html', {'title': 'Profile', 'sign_out': True})


def add_meal(request):
    # Until the Add meal sheet (chunk 14), "+" goes straight to Text and voice
    return redirect('text_input')


# Temporary style page (remove in chunk 19).

def style(request):
    swatches = ['bg', 'card', 'tint', 'line', 'accent', 'ink', 'muted',
                'water', 'protein', 'carbs', 'fat',
                'peach', 'butter', 'lilac', 'sky', 'danger', 'danger-bg']
    return render(request, 'style.html', {'swatches': swatches})
