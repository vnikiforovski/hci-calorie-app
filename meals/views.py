import calendar
import os
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone

from .forms import (AccountDetailsForm, DeleteAccountForm, MealItemForm, MealPhotoForm, MealSlotForm, MealTimeForm,
                    MealTitleForm, PersonalDetailsForm,
                    PhotoMealForm, PreferencesForm, ProfileDetailsForm, SignUpForm, TextMealForm,
                    ZalakPasswordChangeForm)
from .models import Meal, MealItem, Profile, slot_for_time
from .services.ai import AnalysisError, analyze_photo, analyze_text, correct_meal, estimate_item, is_lighter
from .units import (BOWL_SIZES, COUNT_LADDER, GRAMS_PER_UNIT, MAX_GRAMS, MEASURED_STEPS, MIN_GRAMS,
                    NO_PLURAL, UNIT_TABS, WEIGHT_UNITS, format_amount, round_to, stepper_label)


def home(request):
    """The landing page. A guest gets Welcome; a signed-in user gets Home:
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
    # To finish (docs/05, T5): drafts checked but never logged or thrown away. Never counted.
    # "Create your own meal" drafts are left out: they are not meals eaten.
    day_drafts = list(Meal.objects.filter(user=request.user, status='draft', deleted_at__isnull=True,
                                          for_my_meals=False, eaten_at__date=day)
                      .order_by('eaten_at'))

    # One queryset per slot, like the exam's index grouped by specialty
    slots = []
    for value, label, icon in SLOT_OPTIONS:
        meals = list(day_meals.filter(slot=value))
        slots.append({
            'value': value,
            'label': label,
            'icon': icon,
            'meals': meals,
            'drafts': [{'id': draft.id, 'label': draft_label(draft)} for draft in day_drafts if draft.slot == value],
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

    # Desktop only (Figma "Desktop · Home"): the Statistics week chart for the week on screen
    monday, sunday = period_bounds('week', day)
    week_meals = list(logged.filter(eaten_at__date__range=(monday, sunday))
                      .prefetch_related('items').order_by('eaten_at'))

    month, calendar_open = parse_month(request.GET.get('month'), day)
    context = {
        'day': day,
        'is_today': day == today,
        'week_chart': period_stats(week_meals, monday, sunday, 'week'),
        'week_empty': empty_period_text('week', monday),
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
        # The Add meal sheet logs to the day on screen; today needs nothing
        'add_day': day if day != today else None,
    }
    return render(request, 'meals/home.html', context)


# ---------- Home helpers ----------

WEEKDAY_SHORT = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
# No page goes back further than this: a hand-typed ?date=0001-01-01 used to overflow
FIRST_DAY = date(2020, 1, 1)


def parse_day(value):
    """A day from ?date= or ?day= (2026-11-02) that is today or earlier, else None.
    The future is never shown or logged to (docs/05, constraints)."""
    try:
        day = date.fromisoformat(value or '')
    except ValueError:
        return None
    return day if FIRST_DAY <= day <= timezone.localdate() else None


def parse_month(value, day):
    """The month the calendar sheet shows: ?month=2026-10 after its ‹ › arrows (the sheet then
    opens by itself), otherwise the selected day's month. Never after this month."""
    this_month = timezone.localdate().replace(day=1)
    try:
        year, month = (int(part) for part in (value or '').split('-'))
        first = date(year, month, 1)
    except ValueError:
        return day.replace(day=1), False
    return max(min(first, this_month), FIRST_DAY), True


def day_url(view_name, day=None, month=None):
    """A page for a day (and a calendar month). Today needs no ?date=, so the URL stays clean."""
    params = {}
    if day and day != timezone.localdate():
        params['date'] = day.isoformat()
    if month:
        params['month'] = month.strftime('%Y-%m')
    url = reverse(view_name)
    return f'{url}?{urlencode(params)}' if params else url


def home_url(day=None, month=None):
    return day_url('home', day, month)


def diary_url(day=None, month=None):
    return day_url('diary', day, month)


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


def draft_label(meal):
    """The words after "To finish ·": Zalak's name for it, else the typed words, else "Photo meal"."""
    if meal.title:
        return meal.title
    words = ' '.join(meal.text.split())
    if words:
        return words if len(words) <= 40 else words[:39].rstrip() + '…'
    return 'Photo meal'


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


def calendar_month(logged, first, selected, url_for=home_url):
    """The "Jump to a date" month (Figma): weeks from Monday, None outside the month,
    a dot on days with logged meals, future days not links. url_for makes the links:
    home_url on Home, diary_url in the Diary."""
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
                'url': url_for(this),
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
        'prev_url': url_for(selected, previous),
        'prev_month': previous,
        'next_url': url_for(selected, following) if following <= today else None,
        'next_month': following,
        'today_url': url_for(),
    }


# ---------- Accounts. Sign in and Sign out are Django's LoginView / LogoutView (urls.py). ----------

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
    profile = own_profile(request)

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
    """One URL for a meal: a draft shows Result (Log / Just checking), a logged meal shows
    Meal detail. So every item change, which comes back here, works for both."""
    meal = get_own_meal(request, meal_id)
    if meal.status == 'logged':
        return render_meal_detail(request, meal)
    if meal.status == 'mine':
        # A My meal lives on its Saved meal page; item changes come back here, so they
        # land there too (the browser keeps the #item-… part of the address over the redirect)
        return redirect('saved_meal', meal_id=meal.id)
    if not meal.items.exists():
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
        'ask_questions': asks_questions(request),   # Profile · Preferences
        **tell_zalak_context(request),
        # "Create your own meal": Save to My meals instead of Log
        'is_mine': is_mine_draft(request, meal),
        'lighter_idea': lighter_idea_for(request, meal),
    }
    return render(request, 'meals/result.html', context)


def lighter_idea_for(request, meal):
    """The lighter idea card on Result (FR17), or None. Only on a draft the user is just checking
    (never a logged meal or a "Create your own meal" draft), not after its ×, not when Preferences
    turned it off (guests always see it), and only while it is still clearly lighter than the meal
    as it is now (the user may have removed items since Zalak answered)."""
    if meal.status != 'draft' or meal.hide_lighter_idea or is_mine_draft(request, meal):
        return None
    idea = meal.ai_response.get('lighter_idea') if isinstance(meal.ai_response, dict) else None
    if not isinstance(idea, dict):
        return None
    if request.user.is_authenticated and not own_profile(request).show_lighter_ideas:
        return None
    return idea if is_lighter(idea, meal.kcal_min, meal.kcal_max) else None


@require_POST
def hide_lighter_idea(request, meal_id):
    """The × on the lighter idea card: hidden for this meal for good. lighter_idea.js sends it with
    fetch and gets a 204 (the card just goes); without JavaScript the form posts and comes back."""
    meal = get_own_draft(request, meal_id)
    meal.hide_lighter_idea = True
    meal.save(update_fields=['hide_lighter_idea'])
    if request.headers.get('X-Requested-With') == 'fetch':
        return HttpResponse(status=204)
    return redirect('result', meal_id=meal.id)


GUEST_DRAFT_HOURS = 24
DELETED_MEAL_HOURS = 24   # how long a deleted meal waits after its Undo toast before it really goes
USER_DRAFT_DAYS = 7       # a signed-in user's draft that was never finished


def delete_old_guest_drafts():
    """The clean-up, run whenever a new draft is made. A queryset delete still sends post_delete
    for each meal, so signals.remove_photo_file removes their photos too.
    - Guest drafts nobody came back to for a day.
    - Meals deleted more than a day ago: "Delete meal" is a soft delete so Undo works,
      but once Undo is long gone the meal and its photo should not stay on the server.
    - A signed-in user's drafts older than a week: To finish is for today's interrupted meals."""
    now = timezone.now()
    Meal.objects.filter(user=None, status='draft',
                        created_at__lt=now - timedelta(hours=GUEST_DRAFT_HOURS)).delete()
    Meal.objects.filter(deleted_at__lt=now - timedelta(hours=DELETED_MEAL_HOURS)).delete()
    Meal.objects.filter(user__isnull=False, status='draft',
                        created_at__lt=now - timedelta(days=USER_DRAFT_DAYS)).delete()


# ---------- Meal detail: a logged meal's slot, time, name and photo; delete with Undo ----------

def day_name(day):
    """ "Today", "Yesterday" or "Sun 1": for the time pill and the time sheet."""
    today = timezone.localdate()
    if day == today:
        return 'Today'
    if day == today - timedelta(days=1):
        return 'Yesterday'
    return f'{day:%a} {day.day}'


def get_own_logged_meal(request, meal_id):
    meal = get_own_meal(request, meal_id)
    if meal.status != 'logged':
        raise Http404   # a draft is still on Result
    return meal


# Where Meal detail goes back to (its back arrow, Save changes, Delete and Undo)
MEAL_PAGES = {'home': home_url, 'diary': diary_url,
              # "Edit meal" on a favorite's Saved meal page: back to Your meals
              'your_meals': lambda day: your_meals_url('favorites')}


def meal_back_url(request, meal):
    """Meal detail goes back to the page it was opened from, Home or the Diary, on the meal's day.
    The links say which with ?from=…; the session keeps it for this meal, so coming back from
    Edit item (or Save, Delete and Undo, which are POSTs) still knows."""
    came_from = request.GET.get('from')
    if came_from in MEAL_PAGES:
        request.session['meal_from'] = {'id': meal.id, 'page': came_from}
    saved = request.session.get('meal_from') or {}
    page = saved['page'] if saved.get('id') == meal.id else 'home'
    return MEAL_PAGES[page](timezone.localdate(meal.eaten_at))


def render_meal_detail(request, meal, error=''):
    """Figma "Meal detail". Each change saves at once: the slot, the time (on the meal's
    own day), the name and the photo each have their own small form posting to save_meal.
    error: what went wrong with the last change, when it came without JavaScript."""
    eaten = timezone.localtime(meal.eaten_at)
    logged = timezone.localtime(meal.created_at)
    minutes = sorted(set(range(0, 60, 5)) | {eaten.minute, logged.minute})
    back_url = meal_back_url(request, meal)
    context = {
        'meal': meal,
        'rename_form': MealTitleForm(instance=meal),
        'error': error,
        'items': meal.items_with_bars,
        'slot': meal.slot,
        'slot_icon': SLOT_ICONS[meal.slot],
        'slot_options': SLOT_OPTIONS,
        'add_item_error': request.session.pop('add_item_error', None),
        'ask_questions': asks_questions(request),
        **tell_zalak_context(request),
        'eaten': eaten,
        'day_label': day_name(eaten.date()),
        'time_label': f'{day_name(eaten.date())}, {eaten:%H:%M}',
        'hours': [f'{hour:02d}' for hour in range(24)],
        'minutes': [f'{minute:02d}' for minute in minutes],
        'logged_at': logged,
        # "Use the time it was logged" only makes sense on the day it was logged
        'show_logged_time': logged.date() == eaten.date(),
        'now': timezone.localtime(),
        'back_url': back_url,
        'back_label': back_label(back_url),
    }
    return render(request, 'meals/meal_detail.html', context)


def back_label(url):
    """The words of Meal detail's back arrow. Your meals is checked first: its URL starts with /diary/."""
    if url.startswith(reverse('your_meals')):
        return 'Back to Your meals'
    if url.startswith(reverse('diary')):
        return 'Back to the Diary'
    return 'Back to Home'


# What the toast says after each change on Meal detail without JavaScript
SAVED_WORDS = {'slot': 'Slot saved', 'time': 'Time saved', 'title': 'Name saved',
               'photo': 'Photo saved', 'remove_photo': 'Photo removed'}


@require_POST
def save_meal(request, meal_id):
    """One change on Meal detail, saved at once (FR25): the slot, the time, the name, a new
    photo, or removing the photo, named by the posted "field". meal_detail.js sends the slot, time and
    name with fetch: it gets a 204 (the name: 200 with the name as saved) or a 400 with the calm message,
    and the page stays. The photo forms post normally and come back to Meal detail with a toast."""
    meal = get_own_logged_meal(request, meal_id)
    field = request.POST.get('field')
    if field not in SAVED_WORDS:
        return HttpResponse(status=400)
    by_fetch = request.headers.get('X-Requested-With') == 'fetch'
    old_photo = meal.photo.name if meal.photo else ''

    form = None
    if field == 'slot':
        form = MealSlotForm(request.POST, instance=meal)
    elif field == 'title':
        form = MealTitleForm(request.POST, instance=meal)
    elif field == 'photo':
        form = MealPhotoForm(request.POST, request.FILES, instance=meal)
    elif field == 'time':
        form = MealTimeForm(meal, request.POST)

    if form is not None and not form.is_valid():
        errors = form.non_field_errors() or [error for errors in form.errors.values() for error in errors]
        message = errors[0]
        if by_fetch:
            return HttpResponse(message, status=400, content_type='text/plain; charset=utf-8')
        # A fresh copy for the page: is_valid() already put the posted values on `meal`
        return render_meal_detail(request, get_own_logged_meal(request, meal_id), error=message)

    if field == 'time':
        meal.eaten_at = form.cleaned_data['eaten_at']
    elif field == 'remove_photo':
        meal.photo = None
    else:
        meal = form.save(commit=False)
        if field == 'title':
            meal.title = meal.title.strip() or meal.zalak_title   # an emptied name gives back Zalak's
    meal.save()
    if old_photo and old_photo != (meal.photo.name if meal.photo else ''):
        Meal._meta.get_field('photo').storage.delete(old_photo)   # replaced or removed: the file goes

    if by_fetch:
        if field == 'title':
            return HttpResponse(meal.title, content_type='text/plain; charset=utf-8')
        return HttpResponse(status=204)
    request.session['toast'] = {'text': SAVED_WORDS[field]}
    return redirect('result', meal_id=meal.id)


@require_POST
def delete_meal(request, meal_id):
    """Delete meal (FR25): a soft delete, so Undo is one update. Back to Home or the Diary."""
    if request.user.is_authenticated:
        # A second tap: the first one already deleted it, so go where that one went (not a 404)
        deleted = Meal.objects.filter(id=meal_id, user=request.user, deleted_at__isnull=False).first()
        if deleted:
            return redirect(meal_back_url(request, deleted))
    meal = get_own_logged_meal(request, meal_id)
    meal.deleted_at = timezone.now()
    meal.save()
    request.session['toast'] = {
        'text': 'Meal deleted',
        'undo_url': reverse('undo_delete_meal', args=[meal.id]),
    }
    return redirect(meal_back_url(request, meal))


@require_POST
def undo_delete_meal(request, meal_id):
    """Undo in the "Meal deleted" toast. get_own_meal skips deleted meals, so this looks itself."""
    if not request.user.is_authenticated:
        raise Http404
    meal = get_object_or_404(Meal, id=meal_id, user=request.user)
    if meal.deleted_at is not None:   # a second tap finds it already back: nothing to do
        meal.deleted_at = None
        meal.save()
    return redirect(meal_back_url(request, meal))


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


@transaction.atomic
def apply_analysis(meal, data):
    """Save a validated AI answer on the draft: title, description and the items. All or nothing,
    so a crash halfway never leaves a meal without items."""
    meal.title = data['title']
    meal.description = data['description']
    meal.ai_response = data
    meal.save()

    meal.items.all().delete()   # a Retry or Tell Zalak replaces the old items
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


def read_photo(meal):
    """The bytes of the meal's photo. A file that is gone from media/ is an AnalysisError of the
    kind 'photo', so the user gets the calm error page instead of a server error."""
    try:
        with meal.photo.open('rb') as photo:
            return photo.read()
    except OSError as error:
        raise AnalysisError('The photo file is missing.', kind='photo') from error


def analyze_meal(meal):
    """Ask the AI about a saved draft and redirect to what comes next:
    Result, No food found, or the error page. Used by Analyze and Try again."""
    try:
        if meal.photo:
            data = analyze_photo(read_photo(meal), meal.text)
        else:
            data = analyze_text(meal.text)
    except AnalysisError as error:
        # The draft and its input stay saved, so nothing is lost (FR29)
        # fresh=1: the page opens with the overlay showing the failed step first
        return redirect(reverse('analysis_error', args=[meal.id]) + f'?why={error.kind}&fresh=1')

    if data['status'] == 'no_food':
        meal.ai_response = data
        meal.save()
        meal.items.all().delete()
        return redirect(reverse('no_food', args=[meal.id]) + '?fresh=1')

    apply_analysis(meal, data)
    return redirect('result', meal_id=meal.id)


def get_own_draft(request, meal_id):
    """Like get_own_meal, but only a draft: logged meals are edited from meal detail."""
    meal = get_own_meal(request, meal_id)
    if meal.status != 'draft':
        raise Http404
    return meal


def picked_day(request, meal_id):
    """The past day a new meal goes to: Home on Mon 12 sends day=… with "+".
    None means now: today, an edited draft, or a missing, odd or future day."""
    if meal_id is not None:
        return None
    day = parse_day(request.POST.get('day') if request.method == 'POST' else request.GET.get('day'))
    return day if day and day != timezone.localdate() else None


def eaten_on(day):
    """The current clock time on a past day."""
    now = timezone.localtime()
    return now.replace(year=day.year, month=day.month, day=day.day)


def checker_back(request, mine, meal):
    """Where the input pages' back / close button goes: Home, or Your meals for "Create your own meal"."""
    if mine or is_mine_draft(request, meal):
        return {'back_url': your_meals_url('mine'), 'back_to': 'Your meals'}
    return {'back_url': reverse('home'), 'back_to': 'Home'}


def switch_input_url(view_name, edit_name, meal, slot, day, mine):
    """The other input page, for "Use a photo instead" and "Type it instead": a draft
    keeps its own URL (so no second draft is made); a new meal keeps its slot, day and mine=1."""
    if meal:
        return reverse(edit_name, args=[meal.id])
    params = {'slot': slot}
    if day:
        params['day'] = day.isoformat()
    if mine:
        params['mine'] = '1'
    return f'{reverse(view_name)}?{urlencode(params)}'


def text_input(request, meal_id=None):
    """Text and voice. Without meal_id it starts a new draft; with one ("Edit the text")
    it edits that draft, so a corrected meal doesn't leave a second draft behind."""
    meal = get_own_draft(request, meal_id) if meal_id else None
    mine = wants_mine(request, meal_id)
    day = None if mine else picked_day(request, meal_id)

    if request.method == 'POST':
        reused = None
        if meal is None:
            # Cancel during Analyzing only stops the browser waiting: the server kept the draft
            # (and may have finished it). The same words again use that draft, not a second one.
            reused = recent_same_draft(request, request.POST.get('text', ''))
            meal = reused
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
            if mine:
                remember_mine_draft(request, meal)
            elif reused:
                forget_mine_draft(request, meal)   # checked normally this time
            if reused and meal.items.exists():
                return redirect('result', meal_id=meal.id)   # Zalak already answered: no second call
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
        'mine': mine,
        **checker_back(request, mine, meal),
        'steps': TEXT_STEPS,
        'photo_url': switch_input_url('photo_input', 'edit_photo', meal, form['slot'].value(), day, mine),
    }
    return render(request, 'meals/text_input.html', context)


REUSE_MINUTES = 15


def recent_same_draft(request, text):
    """The visitor's text draft with the same words (spaces and case aside) from the last 15 minutes,
    or None. Photos are not matched: two photos can't be compared cheaply."""
    words = ' '.join(text.split()).casefold()
    if not words:
        return None
    since = timezone.now() - timedelta(minutes=REUSE_MINUTES)
    drafts = Meal.objects.filter(status='draft', deleted_at__isnull=True, created_at__gte=since)
    if request.user.is_authenticated:
        drafts = drafts.filter(user=request.user)
    elif request.session.session_key:
        drafts = drafts.filter(user=None, session_key=request.session.session_key)
    else:
        return None
    for draft in drafts.order_by('-created_at'):
        if not draft.photo and ' '.join(draft.text.split()).casefold() == words:
            return draft
    return None


def photo_input(request, meal_id=None):
    """Photo + note. Without meal_id it starts a new draft; with one ("Take another photo")
    it gives that draft a new photo, so a retake doesn't leave a second draft behind."""
    meal = get_own_draft(request, meal_id) if meal_id else None
    old_photo = meal.photo.name if meal and meal.photo else ''
    mine = wants_mine(request, meal_id)
    day = None if mine else picked_day(request, meal_id)

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
            if mine:
                remember_mine_draft(request, meal)
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
        'mine': mine,
        **checker_back(request, mine, meal),
        'steps': PHOTO_STEPS,
        'text_url': switch_input_url('text_input', 'edit_text', meal, slot, day, mine),
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
        profile = own_profile(request)
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


# Why an analysis failed (AnalysisError.kind) -> the step the overlay marks and its words
ERROR_STEPS = {
    'connection': (0, 'Connection lost'),
    'photo': (0, 'Photo not found'),
    'failed': (1, 'Something went wrong'),
}


def analysis_error(request, meal_id):
    meal = get_own_draft(request, meal_id)
    why = request.GET.get('why')
    if why not in ERROR_STEPS:
        why = 'failed'
    index, words = ERROR_STEPS[why]
    context = {
        'meal': meal,
        'why': why,
        'steps': steps_for(meal),
        'failed': failed_step(request, index, words),
    }
    return render(request, 'meals/error.html', context)


# How far the progress bar had got, per failed step (Figma "Analyzing · Connection lost": 28 %,
# "Analyzing · No food": 60 %)
FAILED_BAR = [28, 60, 90]


def failed_step(request, index, words):
    """Figma "Analyzing · Connection lost / No food": straight after a failed analysis (?fresh=1)
    the page opens with the overlay still up, the steps before done and this one marked "!" with
    its words; analyzing.js then fades it to the page. None on a later visit or a reload."""
    if request.GET.get('fresh') != '1':
        return None
    return {'index': index, 'words': words, 'bar': FAILED_BAR[index]}


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
    Works for a draft and for a logged meal (meal detail reuses it)."""
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


def item_snapshot(item):
    """Everything Undo needs to make the item again. The session holds JSON only, so the Decimal
    fields are kept as text."""
    copy = {}
    for field in ITEM_FIELDS:
        value = getattr(item, field)
        copy[field] = str(value) if isinstance(value, Decimal) else value
    return copy


@require_POST
def delete_item(request, meal_id, item_id):
    """Delete item on Edit item (FR21). The last item stays, so Result is never empty:
    Just checking drops the whole meal. A copy waits in the session for Undo."""
    meal = get_own_meal(request, meal_id)
    item = get_object_or_404(MealItem, id=item_id, meal=meal)
    if meal.items.count() <= 1:
        return redirect('edit_item', meal_id=meal.id, item_id=item.id)

    request.session['removed_item'] = {'meal_id': meal.id, 'fields': item_snapshot(item)}

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


# ---------- Tell Zalak (FR18-FR22): correct the whole meal in your own words ----------

# The Analyzing overlay's steps while Zalak reads a correction
CORRECTION_STEPS = ['Reading what you said', 'Updating the foods', 'Estimating portions']
NO_FOOD_CORRECTION = "Zalak couldn't use that. Try saying what changed."


def tell_zalak_context(request):
    """For Result, Meal detail and Saved meal: a failed correction (its words and a calm message,
    shown once) and the overlay's steps."""
    return {
        'tell_error': request.session.pop('tell_error', None),
        'correction_steps': CORRECTION_STEPS,
    }


@require_POST
def tell_zalak(request, meal_id):
    """"Something else wrong? Tell Zalak": one AI call with the meal, its items as they are now and
    the correction. Zalak's answer replaces the items (a name the user gave the meal stays); the old
    meal waits in the session for Undo. If Zalak can't answer, nothing changes and the words come back."""
    meal = get_own_meal(request, meal_id)
    back = reverse('result', args=[meal.id])
    correction = ' '.join(request.POST.get('correction', '').split())[:300]
    if not correction:
        return redirect(back)

    items = list(meal.items.all())
    current = [{'name': item.name, 'amount': format_amount(item.amount), 'unit': item.unit,
                'grams': item.grams, 'kcal_min': item.kcal_min, 'kcal_max': item.kcal_max}
               for item in items]
    try:
        photo = None
        if meal.photo:
            try:
                photo = read_photo(meal)
            except AnalysisError:
                pass   # the file is gone: Zalak corrects from the note and the items alone
        data = correct_meal(meal.text, current, correction, photo)
    except AnalysisError as error:
        request.session['tell_error'] = {'text': correction, 'message': ai_problem(error)}
        return redirect(back + '#tell-zalak')
    if data['status'] == 'no_food':
        request.session['tell_error'] = {'text': correction, 'message': NO_FOOD_CORRECTION}
        return redirect(back + '#tell-zalak')

    old_answer = meal.ai_response if isinstance(meal.ai_response, dict) else {}
    request.session['corrected_meal'] = {
        'meal_id': meal.id,
        'title': meal.title,
        'description': meal.description,
        'ai_response': meal.ai_response,
        'items': [item_snapshot(item) for item in items],
    }
    renamed = bool(meal.title) and meal.title != old_answer.get('title', '')
    title = meal.title
    apply_analysis(meal, data)   # the new items, description and answer (so Reset means this one)
    removed = request.session.get('removed_item')
    if removed and removed['meal_id'] == meal.id:
        del request.session['removed_item']   # its place in the list now belongs to another item
    if renamed:
        meal.title = title
        meal.save(update_fields=['title'])
    request.session['toast'] = {
        'text': 'Zalak updated the meal',
        'undo_url': reverse('undo_tell_zalak', args=[meal.id]),
    }
    return redirect(back)


@require_POST
def undo_tell_zalak(request, meal_id):
    """Undo in "Zalak updated the meal": the meal as it was before, items and all. Works once."""
    meal = get_own_meal(request, meal_id)
    saved = request.session.get('corrected_meal')
    if not saved or saved['meal_id'] != meal.id:
        raise Http404
    del request.session['corrected_meal']
    with transaction.atomic():   # all or nothing, as in apply_analysis
        meal.title = saved['title']
        meal.description = saved['description']
        meal.ai_response = saved['ai_response']
        meal.save()
        meal.items.all().delete()
        for fields in saved['items']:
            MealItem.objects.create(meal=meal, **fields)
    return redirect('result', meal_id=meal.id)


@require_POST
def log_meal(request, meal_id):
    """Log on Result: the draft becomes a logged meal in the chosen slot (FR23).
    The pre_save signal counts it in Profile.meals_logged.
    A guest gets here from "Keep this meal?" (FR2, T7): the draft waits for the account."""
    meal = get_own_meal(request, meal_id)
    if meal.status == 'logged':
        # A second tap on Log: the first one already logged it, so go where that one went (not a 404)
        return redirect(home_url(timezone.localdate(meal.eaten_at)))
    if meal.status != 'draft':
        raise Http404
    if not meal.items.exists():
        # A draft whose analysis failed has nothing to log: back to its error or No food page
        return redirect('result', meal_id=meal.id)

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
    if meal.status == 'logged':   # a second tap finds a draft already: straight to its Result
        meal.status = 'draft'
        meal.save()   # the signal takes the meal off the counter again
    elif meal.status != 'draft':
        raise Http404
    return redirect('result', meal_id=meal.id)


@require_POST
def just_checking(request, meal_id):
    """Just checking on Result: the draft is thrown away (FR34). Nothing was logged.
    The post_delete signal removes the photo file."""
    if not Meal.objects.filter(id=meal_id).exists():
        return redirect('home')   # a second tap: the first one already threw it away (not a 404)
    meal = get_own_draft(request, meal_id)
    waiting = request.session.get('guest_meal')
    if waiting and waiting['id'] == meal.id:
        del request.session['guest_meal']   # nothing is waiting for an account any more
    mine = is_mine_draft(request, meal)
    meal.delete()
    if mine:
        return redirect(your_meals_url('mine'))   # Cancel on "Create your own meal"
    return redirect('home')


def no_food(request, meal_id):
    meal = get_own_draft(request, meal_id)
    answer = meal.ai_response or {}
    context = {
        'meal': meal,
        'reason': answer.get('no_food_reason', ''),
        'seen': answer.get('seen', []),
        'steps': steps_for(meal),
        'failed': failed_step(request, 1, 'No food found in the photo' if meal.photo else 'No food found in what you wrote'),
    }
    return render(request, 'meals/no_food.html', context)


# The Diary, Statistics, Your meals and Profile are personal pages: @login_required sends a guest
# to Sign in first (LOGIN_URL in settings).

@login_required
def diary(request):
    """The Diary (FR26): one page per day, like a book; ?date= picks the day.
    Phones show that page; the desktop shows the day before beside it (Figma "Desktop · Diary").
    The arrows go one day on phones and two on the desktop, back as far as you like, never past today."""
    today = timezone.localdate()
    day = parse_day(request.GET.get('date')) or today
    logged = Meal.objects.filter(user=request.user, status='logged', deleted_at__isnull=True)
    first_day = first_logged_day(logged)

    left_day = day - timedelta(days=1)
    month, calendar_open = parse_month(request.GET.get('month'), day)

    # Phones: one day back or on. Desktop: the spread before or after this one, two days away.
    # Back always works, like turning back the pages of a paper diary. Forward stops at today.
    phone_next = desk_next = None
    if day < today:
        phone_next = nav_link(day + timedelta(days=1))
        desk_next = nav_link(min(day + timedelta(days=2), today), spread=True)

    context = {
        'day': day,
        # Not 'page': base.html already uses that name for the current URL
        'right_page': diary_page(logged, day, first_day),
        # The desktop's left page: always the day before
        'left_page': diary_page(logged, left_day, first_day),
        'spread_name': f'{day_name(left_day)} – {day_name(day)}',
        'phone_prev': nav_link(left_day),
        'phone_next': phone_next,
        'desk_prev': nav_link(day - timedelta(days=2), spread=True),
        'desk_next': desk_next,
        'calendar': calendar_month(logged, month, day, diary_url),
        'calendar_open': calendar_open,
        # The corner "+" adds to the day on screen, as on Home
        'add_day': day if day != today else None,
    }
    return render(request, 'meals/diary.html', context)


def nav_link(day, spread=False):
    """A Diary arrow: the URL and its words, "Wed 14" or, for the desktop spread, "Mon 12 – Tue 13"."""
    label = day_name(day)
    if spread:
        label = f'{day_name(day - timedelta(days=1))} – {label}'
    return {'url': diary_url(day), 'label': label}


def first_logged_day(logged):
    """The day of the first logged meal (today for a new account): its page says "First page"."""
    first = logged.order_by('eaten_at').values_list('eaten_at', flat=True).first()
    return timezone.localtime(first).date() if first else timezone.localdate()


def diary_page(logged, day, first_day):
    """One Diary page: the day's logged meals in time order (one queryset per page), its words
    and its total. Today also lists the slots that are still empty, to add to them."""
    today = timezone.localdate()
    meals = list(logged.filter(eaten_at__date=day).prefetch_related('items').order_by('eaten_at'))

    if day == today:
        kicker = f'{day:%A} · Today'
    elif day == today - timedelta(days=1):
        kicker = f'{day:%A} · Yesterday'
    elif day == first_day:
        kicker = f'{day:%A} · First page'
    else:
        kicker = f'{day:%A}'

    count = f'{len(meals)} meal{"s" if len(meals) != 1 else ""}'
    if day == today:
        count = f'{count} so far' if meals else 'Nothing yet today'
    elif not meals:
        count = 'Nothing logged'
    elif day == first_day:
        count = f'{count} · your first day with Zalak'

    used = {meal.slot for meal in meals}
    return {
        'date': day,
        'is_today': day == today,
        'is_first': day == first_day,
        'kicker': kicker,
        'count': count,
        'meals': meals,
        'empty_slots': [(value, label) for value, label, icon in SLOT_OPTIONS if value not in used]
                       if day == today else [],
        'kcal_min': sum(meal.kcal_min for meal in meals),
        'kcal_max': sum(meal.kcal_max for meal in meals),
        'name': day_name(day),
    }


# ---------- Statistics (Figma "Statistics", "Statistics · Last week") ----------

STATS_PERIODS = ['week', 'month']
# kcal in a gram of each macro: for the share of the day's energy (Figma "Protein · 20%")
KCAL_PER_GRAM = {'protein': 4, 'carbs': 4, 'fat': 9}
MACRO_NAMES = [('protein', 'Protein'), ('carbs', 'Carbs'), ('fat', 'Fat')]
# A month's chart names only these days under its bars, so the labels fit at 390 px
MONTH_AXIS_DAYS = {1, 8, 15, 22, 29}
MOST_LOGGED_COUNT = 3


@login_required
def statistics(request):
    """Statistics (FR28, the default of FR41): a Mo–Su week (as on Home's week strip) or a calendar month.
    ?period=month switches, ?date= picks the period that holds that day. Only logged meals count,
    and the averages are over the days with a logged meal (a day not logged isn't a day of eating nothing)."""
    today = timezone.localdate()
    period = request.GET.get('period')
    if period not in STATS_PERIODS:
        period = 'week'
    day = parse_day(request.GET.get('date')) or today
    first, last = period_bounds(period, day)

    logged = Meal.objects.filter(user=request.user, status='logged', deleted_at__isnull=True)
    meals = list(logged.filter(eaten_at__date__range=(first, last))
                 .prefetch_related('items').order_by('eaten_at'))

    # ‹ always goes back (as in the Diary); › stops at the period that holds today
    previous = first - timedelta(days=1)
    words = period_words(period, first)
    context = {
        'period': period,
        'words': words,
        'label': period_label(period, first, last),
        'week_url': stats_url('week', day),
        'month_url': stats_url('month', day),
        'prev_url': stats_url(period, period_bounds(period, previous)[0]),
        'next_url': stats_url(period, last + timedelta(days=1)) if last < today else None,
        'stats': period_stats(meals, first, last, period),
        'empty_text': empty_period_text(period, first),
    }
    return render(request, 'meals/statistics.html', context)


def period_bounds(period, day):
    """The first and last day of the Mo–Su week or the calendar month that holds day."""
    if period == 'month':
        first = day.replace(day=1)
        return first, first.replace(day=calendar.monthrange(first.year, first.month)[1])
    first = day - timedelta(days=day.weekday())
    return first, first + timedelta(days=6)


def stats_url(period, day):
    """A Statistics page. This week needs no parameters, so the nav link stays clean."""
    params = {}
    if period != 'week':
        params['period'] = period
    if period_bounds(period, day)[0] != period_bounds(period, timezone.localdate())[0]:
        params['date'] = day.isoformat()
    url = reverse('statistics')
    return f'{url}?{urlencode(params)}' if params else url


def period_words(period, first):
    """ "this week", "last week" or "that week" (and the same for months): under the KPI numbers
    and in "Most logged this week" (Figma)."""
    this_first = period_bounds(period, timezone.localdate())[0]
    if first == this_first:
        return f'this {period}'
    if first == period_bounds(period, this_first - timedelta(days=1))[0]:
        return f'last {period}'
    return f'that {period}'


def empty_period_text(period, first):
    """ "Nothing logged this week yet." or "Nothing logged last week." for an empty chart."""
    words = period_words(period, first)
    return f'Nothing logged {words}{" yet" if words.startswith("this") else ""}.'


def period_label(period, first, last):
    """ "12–18 October", "27 October – 2 November" or "October 2026"."""
    if period == 'month':
        return f'{first:%B %Y}'
    if first.month == last.month:
        return f'{first.day}–{last.day} {last:%B}'
    return f'{first.day} {first:%B} – {last.day} {last:%B}'


def period_stats(meals, first, last, period):
    """Everything the Statistics cards show, from the period's logged meals (plain loops)."""
    today = timezone.localdate()
    by_day = {}
    for meal in meals:
        by_day.setdefault(timezone.localdate(meal.eaten_at), []).append(meal)
    days_logged = len(by_day)

    # The chart's top: a little above the highest day, and never under 1,000, so a light day
    # doesn't fill the card. Grid lines at every 1,000 below it (Figma: 1,000 and 2,000).
    highest = max((sum(meal.kcal_max for meal in day_meals) for day_meals in by_day.values()), default=0)
    top = max(1000, highest) * 1.1

    days = []
    this = first
    while this <= last:
        day_meals = by_day.get(this, [])
        kcal_min = sum(meal.kcal_min for meal in day_meals)
        kcal_max = sum(meal.kcal_max for meal in day_meals)
        if this > today:
            said = 'not yet'
        elif day_meals:
            said = f'{kcal_min:,}–{kcal_max:,} kcal'
        else:
            said = 'nothing logged'
        if period == 'week':
            axis = WEEKDAY_SHORT[this.weekday()]
        else:
            axis = str(this.day) if this.day in MONTH_AXIS_DAYS else ''
        days.append({
            'date': this,
            'axis': axis,
            'spoken': f'{this:%A} {this.day} {this:%B}: {said}',
            'has_meals': bool(day_meals),
            'is_future': this > today,
            # One bar up to the highest estimate (in % of the chart), its top part the lighter
            # "Possible range" (in % of the bar), the rest the solid "Lowest estimate"
            'bar_pct': f'{kcal_max / top * 100:.1f}',
            'range_pct': f'{(kcal_max - kcal_min) / kcal_max * 100:.1f}' if kcal_max else '0',
        })
        this += timedelta(days=1)

    grid = [{'value': value, 'pct': f'{value / top * 100:.1f}'}
            for value in range(1000, int(top) + 1, 1000)]

    stats = {
        'days': days,
        'grid': grid,
        'days_logged': days_logged,
        'days_total': len(days),
        'meal_count': len(meals),
        'kcal_min': 0,
        'kcal_max': 0,
        'macros': [],
        'most_logged': most_logged(meals),
    }
    if not days_logged:
        return stats

    # Averages a day, over the days with a logged meal: kcal rounded to 10, grams to 5
    stats['kcal_min'] = round_to(sum(meal.kcal_min for meal in meals) / days_logged, 10)
    stats['kcal_max'] = round_to(sum(meal.kcal_max for meal in meals) / days_logged, 10)
    macros = []
    for key, name in MACRO_NAMES:
        grams_min = sum(getattr(meal, f'{key}_min') for meal in meals) / days_logged
        grams_max = sum(getattr(meal, f'{key}_max') for meal in meals) / days_logged
        macros.append({
            'key': key,
            'name': name,
            'min': round_to(grams_min, 5),
            'max': round_to(grams_max, 5),
            # the middle of the range, in kcal, for the share
            'energy': (grams_min + grams_max) / 2 * KCAL_PER_GRAM[key],
        })
    stats['macros'] = macro_shares(macros)
    return stats


def macro_shares(macros):
    """Each macro's share of the energy in whole %, adding up to 100 (the last one takes the rest).
    With 65–75 / 155–175 / 50–60 g this gives Figma's 20 / 46 / 34."""
    energy = sum(macro['energy'] for macro in macros)
    used = 0
    for macro in macros:
        if not energy:
            macro['pct'] = 0
        elif macro is macros[-1]:
            macro['pct'] = 100 - used
        else:
            macro['pct'] = round(macro['energy'] / energy * 100)
            used += macro['pct']
    return macros


def most_logged(meals):
    """Figma "Most logged this week": meal names logged at least twice (case doesn't matter),
    the most often first, then the latest. Each shows its latest photo, else its slot's pastel."""
    groups = {}
    for meal in meals:   # in time order, so the last meal of a group is its latest
        name = (meal.title or '').strip()
        if name:
            groups.setdefault(name.casefold(), []).append(meal)

    rows = []
    for same in groups.values():
        if len(same) < 2:
            continue
        latest = same[-1]
        photos = [meal.photo for meal in same if meal.photo]
        rows.append({
            'title': latest.title.strip(),
            'count': len(same),
            'photo': photos[-1] if photos else None,
            'tint': latest.tint,
            'latest': latest.eaten_at,
        })
    rows.sort(key=lambda row: (row['count'], row['latest']), reverse=True)
    return rows[:MOST_LOGGED_COUNT]


# ---------- Profile (Figma "Profile", "Profile · Personal details / Preferences / Account and privacy") ----------

def own_profile(request):
    """The signed-in user's Profile. get_or_create: the post_save signal makes one for every new
    user, but an account made before that signal existed may have none."""
    profile, created = Profile.objects.get_or_create(user=request.user)
    return profile


def asks_questions(request):
    """Show the inline question on an unsure item (FR16)? "Ask me" yes, "Best guess" no (FR37).
    A guest has no Profile, so a guest is always asked."""
    if not request.user.is_authenticated:
        return True
    return own_profile(request).uncertainty == 'ask'


@login_required
def profile(request):
    """The Profile hub: who is signed in, the rows to the subpages, and Sign out (red)."""
    context = {
        'profile': own_profile(request),
        'saved_count': saved_meals(request.user).count(),   # "Your meals · 4 saved"
    }
    return render(request, 'meals/profile.html', context)


@login_required
def profile_details(request):
    """Personal details: name and e-mail (the User) plus height, weight, year and activity
    (the Profile). Two ModelForms in one <form>; both must be valid before anything is saved."""
    profile = own_profile(request)
    if request.method == 'POST':
        account_form = AccountDetailsForm(request.POST, instance=request.user)
        details_form = PersonalDetailsForm(request.POST, instance=profile)
        if account_form.is_valid() and details_form.is_valid():
            account_form.save()   # a new e-mail is the new sign-in name too
            details_form.save()
            request.session['toast'] = {'text': 'Changes saved'}
            return redirect('profile')
    else:
        account_form = AccountDetailsForm(instance=request.user)
        details_form = PersonalDetailsForm(instance=profile)
    context = {
        'account_form': account_form,
        'details_form': details_form,
    }
    return render(request, 'meals/profile_details.html', context)


@login_required
def profile_preferences(request):
    """Preferences: "When Zalak is unsure" and "Show lighter ideas". preferences.js saves a tap straight away with fetch
    (it gets a 204, so the page and the focus stay); without JavaScript the Save button posts and comes back."""
    profile = own_profile(request)
    if request.method == 'POST':
        form = PreferencesForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'fetch':
                return HttpResponse(status=204)
            request.session['toast'] = {'text': 'Preferences saved'}
            return redirect('profile_preferences')
        if request.headers.get('X-Requested-With') == 'fetch':
            return HttpResponse(status=400)
    else:
        form = PreferencesForm(instance=profile)
    return render(request, 'meals/profile_preferences.html', {'form': form, 'profile': profile})


@login_required
def account_privacy(request):
    """Account and privacy: Change password, and Delete account and all data (red)."""
    return render(request, 'meals/account_privacy.html')


@login_required
def change_password(request):
    """Change password: Django's PasswordChangeForm with calmer words. update_session_auth_hash
    keeps this browser signed in (a new password otherwise signs every session out)."""
    if request.method == 'POST':
        form = ZalakPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            request.session['toast'] = {'text': 'Password changed'}
            return redirect('profile_account')
    else:
        form = ZalakPasswordChangeForm(request.user)
    return render(request, 'meals/change_password.html', {'form': form})


@login_required
def delete_account(request):
    """Delete account and all data (FR3). The page says what goes and asks for the password once.
    user.delete() cascades to the Profile, every meal and its items; the post_delete signal on Meal
    removes each photo file (signals.remove_photo_file). Then the visitor is a guest on Welcome."""
    if request.method == 'POST':
        form = DeleteAccountForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            logout(request)   # first: logout() empties the session, the toast goes into the new one
            user.delete()
            request.session['toast'] = {'text': 'Your account and meals are deleted'}
            return redirect('home')
    else:
        form = DeleteAccountForm(request.user)
    context = {
        'form': form,
        'meal_count': Meal.objects.filter(user=request.user, status='logged', deleted_at__isnull=True).count(),
    }
    return render(request, 'meals/delete_account.html', context)


@login_required
def help_about(request):
    """Help and about: what Zalak does, the three confidence words, and "estimates, not medical advice"."""
    return render(request, 'meals/help_about.html')


# ---------- Your meals (Figma "Diary · Your meals", "Saved meal", "Add meal") ----------
# Favorites are logged meals with the heart (is_favorite). My meals are templates with status "mine":
# never counted, never on Home, the Diary or Statistics. Logging either one again makes a copy.

YOUR_MEALS_TABS = ['favorites', 'mine']
RECENT_COUNT = 5


def your_meals_url(tab='favorites'):
    url = reverse('your_meals')
    return f'{url}?tab=mine' if tab == 'mine' else url


def saved_meals(user):
    """Everything under Your meals: the hearted logged meals and the My meals."""
    own = Meal.objects.filter(user=user, deleted_at__isnull=True)
    return own.filter(status='logged', is_favorite=True) | own.filter(status='mine')


def copy_meal(source, slot, eaten_at, status):
    """A new meal like `source`: its words, Zalak's answer (so Reset still works) and every item with
    its numbers and position. The photo is copied to a new file, so deleting one meal (whose
    post_delete signal removes its photo) never takes the other's photo with it. The heart is not
    copied: a meal logged again from Favorites doesn't show up there twice."""
    meal = Meal(user=source.user, slot=slot, input_method=source.input_method, text=source.text,
                title=source.title, description=source.description, status=status,
                eaten_at=eaten_at, ai_response=deepcopy(source.ai_response))
    if source.photo:
        try:
            with source.photo.open('rb') as photo:
                content = ContentFile(photo.read())
            meal.photo.save(os.path.basename(source.photo.name), content, save=False)
        except OSError:
            pass   # the file is gone from media/: the copy simply has no photo
    meal.save()   # with status "logged" the pre_save signal counts it, like any Log
    for item in source.items.all():
        MealItem.objects.create(meal=meal, **{field: getattr(item, field) for field in ITEM_FIELDS})
    return meal


def logged_times(meal):
    """ "Logged 12 times" on Saved meal: logged meals with the same name, case aside (as Most logged)."""
    name = (meal.title or '').strip().casefold()
    if not name:
        return 0
    titles = Meal.objects.filter(user=meal.user, status='logged', deleted_at__isnull=True) \
        .values_list('title', flat=True)
    return sum(1 for title in titles if (title or '').strip().casefold() == name)


def recent_meals(user):
    """Recent in the Add meal sheet: the last 5 logged meals with different names, newest first."""
    logged = Meal.objects.filter(user=user, status='logged', deleted_at__isnull=True)
    seen, ids = set(), []
    for meal_id, title in logged.order_by('-eaten_at').values_list('id', 'title')[:100]:
        name = (title or '').strip().casefold()
        if name in seen:
            continue
        seen.add(name)
        ids.append(meal_id)
        if len(ids) == RECENT_COUNT:
            break
    meals = {meal.id: meal for meal in logged.filter(id__in=ids).prefetch_related('items')}
    return [meals[meal_id] for meal_id in ids]


# "Create your own meal": the normal checker, whose draft is marked for_my_meals so its Result
# shows Save to My meals instead of Log. Only signed-in users have Your meals.

def wants_mine(request, meal_id):
    if meal_id is not None or not request.user.is_authenticated:
        return False
    data = request.POST if request.method == 'POST' else request.GET
    return data.get('mine') == '1'


def remember_mine_draft(request, meal):
    if not meal.for_my_meals:
        meal.for_my_meals = True
        meal.save(update_fields=['for_my_meals'])


def forget_mine_draft(request, meal):
    if meal.for_my_meals:
        meal.for_my_meals = False
        meal.save(update_fields=['for_my_meals'])


def is_mine_draft(request, meal):
    return bool(meal and meal.status == 'draft' and meal.for_my_meals)


@login_required
def your_meals(request):
    """Your meals, the back of the Diary book (FR10, FR27): ?tab=favorites (the hearted meals) or ?tab=mine."""
    tab = request.GET.get('tab')
    if tab not in YOUR_MEALS_TABS:
        tab = 'favorites'
    own = Meal.objects.filter(user=request.user, deleted_at__isnull=True)
    if tab == 'mine':
        meals = own.filter(status='mine').order_by('-created_at')
    else:
        meals = own.filter(status='logged', is_favorite=True).order_by('-eaten_at')
    meals = list(meals.prefetch_related('items'))
    today = timezone.localdate()
    logged = own.filter(status='logged')
    month, calendar_open = parse_month(request.GET.get('month'), today)
    context = {
        'tab': tab,
        'meals': meals,
        # The Diary's "Jump to a date", as on every Diary page
        'calendar': calendar_month(logged, month, today, diary_url),
        'calendar_open': calendar_open,
        'favorites_url': your_meals_url('favorites'),
        'mine_url': your_meals_url('mine'),
    }
    return render(request, 'meals/your_meals.html', context)


def get_saved_meal(request, meal_id):
    """A meal under Your meals: the user's own hearted logged meal or My meal, else 404."""
    meal = get_own_meal(request, meal_id)
    if meal.status == 'mine' or (meal.status == 'logged' and meal.is_favorite):
        return meal
    raise Http404


@login_required
def saved_meal(request, meal_id):
    """Saved meal (Figma): log it again in 2 taps (NFR8), slot from the time unless changed.
    A favorite's items are read-only here ("Edit meal" opens its Meal detail), so a pencil never
    quietly changes a day in the Diary. A My meal is edited right here, and renamed in a small sheet."""
    meal = get_saved_meal(request, meal_id)
    is_mine = meal.status == 'mine'
    slot = slot_for_time(timezone.now())
    context = {
        'meal': meal,
        'is_mine': is_mine,
        'read_only': not is_mine,
        'items': meal.items_with_bars,
        'slot': slot,
        'slot_icon': SLOT_ICONS[slot],
        'slot_options': SLOT_OPTIONS,
        'logged_times': logged_times(meal),
        'back_url': your_meals_url(meal.status if is_mine else 'favorites'),
        'add_item_error': request.session.pop('add_item_error', None),
        'ask_questions': asks_questions(request),
        **tell_zalak_context(request),
        'title_form': MealTitleForm(instance=meal) if is_mine else None,
    }
    return render(request, 'meals/saved_meal.html', context)


@login_required
@require_POST
def rename_saved(request, meal_id):
    """The Rename sheet of a My meal. An emptied name gives back Zalak's, as on Meal detail."""
    meal = get_saved_meal(request, meal_id)
    if meal.status != 'mine':
        raise Http404
    form = MealTitleForm(request.POST, instance=meal)
    if form.is_valid():
        meal = form.save(commit=False)
        if not meal.title:
            meal.title = meal.zalak_title
        meal.save()
        request.session['toast'] = {'text': 'Changes saved'}
    return redirect('saved_meal', meal_id=meal.id)


@login_required
@require_POST
def toggle_favorite(request, meal_id):
    """The heart on Meal detail (FR10). Its Undo is the same toggle again."""
    meal = get_own_logged_meal(request, meal_id)
    meal.is_favorite = not meal.is_favorite
    meal.save(update_fields=['is_favorite'])
    if meal.is_favorite:
        request.session['toast'] = {'text': 'Saved to Your meals'}
    else:
        request.session['toast'] = {'text': 'Removed from Your meals',
                                    'undo_url': reverse('toggle_favorite', args=[meal.id])}
    return redirect('result', meal_id=meal.id)


@login_required
@require_POST
def log_again(request, meal_id):
    """Log again (FR27, NFR8) from Meal detail, Saved meal and Recent: a copy, logged now on
    today (or the Add sheet's day), in the posted slot or the one from the time."""
    source = get_own_meal(request, meal_id)
    if source.status not in ('logged', 'mine'):
        raise Http404
    slot = request.POST.get('slot')
    if slot not in SLOT_ICONS:
        slot = slot_for_time(timezone.now())
    day = parse_day(request.POST.get('day'))
    eaten_at = eaten_on(day) if day and day != timezone.localdate() else timezone.now()

    meal = copy_meal(source, slot, eaten_at, 'logged')
    request.session['logged_again'] = meal.id
    request.session['toast'] = {
        'text': f'Logged again to {slot}',
        'undo_url': reverse('undo_log_again', args=[meal.id]),
    }
    return redirect(home_url(timezone.localdate(meal.eaten_at)))


@login_required
@require_POST
def undo_log_again(request, meal_id):
    """Undo in "Logged again to lunch": the copy goes. Back to draft first, so the signal takes it
    off the counter again; deleting it then removes its photo file (post_delete)."""
    if request.session.get('logged_again') != meal_id:
        if not Meal.objects.filter(id=meal_id).exists():
            return redirect('home')   # a second tap: the first one already took the copy away
        raise Http404   # only the copy just made, never any other logged meal
    meal = get_own_logged_meal(request, meal_id)
    day = timezone.localdate(meal.eaten_at)
    meal.status = 'draft'
    meal.save()
    meal.delete()
    del request.session['logged_again']
    return redirect(home_url(day))


@login_required
@require_POST
def save_my_meal(request, meal_id):
    """Save to My meals on the Result of "Create your own meal" (FR39): the draft becomes a My meal."""
    meal = get_own_draft(request, meal_id)
    if not is_mine_draft(request, meal):
        raise Http404
    if not meal.items.exists():
        return redirect('result', meal_id=meal.id)   # a failed analysis: nothing to save yet
    slot = request.POST.get('slot')
    if slot in SLOT_ICONS:
        meal.slot = slot
    meal.status = 'mine'
    meal.for_my_meals = False   # no longer a draft waiting for Save
    meal.save()
    request.session['toast'] = {'text': 'Saved to Your meals'}
    return redirect(your_meals_url('mine'))


@login_required
@require_POST
def remove_saved(request, meal_id):
    """The red button and the heart on Saved meal: a favorite loses its heart (the meal stays in
    the Diary); a My meal is soft-deleted. Both with Undo."""
    meal = get_saved_meal(request, meal_id)
    if meal.status == 'mine':
        meal.deleted_at = timezone.now()
    else:
        meal.is_favorite = False
    meal.save()
    request.session['toast'] = {'text': 'Removed from Your meals',
                                'undo_url': reverse('undo_remove_saved', args=[meal.id])}
    return redirect(your_meals_url(meal.status))


@login_required
@require_POST
def undo_remove_saved(request, meal_id):
    """Undo in "Removed from Your meals": the heart, or the My meal, comes back."""
    meal = get_object_or_404(Meal, id=meal_id, user=request.user)
    if meal.status == 'mine':
        meal.deleted_at = None
    elif meal.status == 'logged' and meal.deleted_at is None:
        meal.is_favorite = True
    else:
        raise Http404
    meal.save()
    return redirect(your_meals_url(meal.status))


def add_meal(request):
    """/add/: "Try it without an account" on Welcome, and the "+" without JavaScript (with it, the
    "+" opens the Add meal sheet instead). Text and voice links to the photo input from there."""
    return redirect('text_input')
