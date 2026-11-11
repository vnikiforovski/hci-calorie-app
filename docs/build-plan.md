# Zalak: build plan

Agreed 25 Oct 2026. **Finish by Sun 1 Nov, demo on 4 or 5 Nov**, hard deadline 15 Nov. One chunk at a time, in order. Each chunk is reviewable in ~30–45 min and ends with `python manage.py check` plus a browser test at 390 px and 1440 px. Tick the box when the chunk is committed.

## Decisions

**Docs vs Figma**
- **Landing.** Welcome is the landing page (Create account / Sign in / "Try it without an account"). "Try it" opens Add meal as a guest.
- **Sign-up** has 2 steps, as in Figma: name, e-mail, password and the "estimates, not medical advice" checkbox; then height, weight and activity, which can be skipped. "What brings you here" is dropped. The uncertainty and food preferences live in Profile · Preferences, with the uncertainty default "Ask me".
- **Guests** see "Log to lunch" too. The overlay keeps its own wording ("Keep this meal?" / "Not now, I was just checking").
- **Clarifying question** is inline on the unsure item only. The A little / About that / A lot chips scale that item ×0.5 / ×1 / ×1.5. "Ask me" shows the question, "Best guess" hides it.
- **Edit item** is a full screen, as in Figma.
- **Water** is left out of Home until later (Could).
- **Errors built:** Connection lost / AI failure (error page with Retry and "Type it instead") and No food found. True offline is Could.

**Data and logic**
- **Drafts.** Every analysis creates a `Meal` row with status `draft`. Only `logged` meals count anywhere. Just checking deletes the draft. A guest's draft has no user and is tied to the session key.
- **Guest draft cleanup.** Whenever a new draft is created, guest drafts older than 24 h are deleted (one line in the draft-creating helper in `views.py`).
- **Scaling.** Each item stores the AI's kcal/macros per 100 g, with `grams` as the single source. Weight/volume units convert exactly. Portion units (slice, bowl S/M/L, plate, serving…) use a default-grams table in `units.py`.
- **Rename vs re-estimate.** Renaming keeps the numbers. "Re-estimate" and "Add item" make one small AI call for that single item.
- **Deferred features.** "Tell Zalak" is Should; "How it was cooked" is Could.
- **Camera** (changed in chunk 8b): a live viewfinder (`getUserMedia`, rear camera) on phones over https or localhost; the native `<input type="file" accept="image/*" capture="environment">` as the fallback when there's no camera access; a drop zone (drag, choose, Ctrl+V) on desktop.
- **Delete** is a soft delete (`deleted_at`), so Undo is one update.
- **Slots and catalog.** 4 fixed meal slots. No `Food` model. Totals are computed with `@property`, not stored.
- **The `meals_logged` counter lives in one place:** the `pre_save` signal on Meal (draft → logged). It fires for the admin, the views and the guest sign-up alike. Admin `save_model` only sets the owner.
- **Navigation never breaks.** Diary and Statistics show a simple "Coming soon" page until their chunk is built.

**Tech**
- Django 5.2 LTS. Packages: Django, Pillow, anthropic, python-dotenv.
- Bootstrap 5, Bootstrap Icons and the Fraunces/Figtree fonts are self-hosted in `static/`.
- AI model: Claude Haiku 5.5 (`claude-haiku-5-5`, chosen in Chunk 5), set in settings as `ZALAK_AI_MODEL`. Structured output via `output_config` with a JSON schema (structured outputs; forced tool calls are no longer supported on newer models), then our own validation. `ZALAK_AI_FAKE=1` in `.env` uses a fixed fake answer; `ZALAK_AI_FAKE_DELAY=4` makes it wait 4 s, to check the Analyzing overlay. The overlay's bites come at 0, 0.6 and 1.2 s to fit Haiku's 1–2 s answers.

## Data model (app `meals`)

```python
class Profile(models.Model):                       # ⟶ Doctor.user OneToOne
    ACTIVITY_CHOICES = [('low','Low'), ('medium','Medium'), ('high','High')]
    UNCERTAINTY_CHOICES = [('ask','Ask me'), ('guess','Best guess')]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    height_cm = models.PositiveIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)   # 78.4 (chunk 18)
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)                   # chunk 18
    activity_level = models.CharField(max_length=10, choices=ACTIVITY_CHOICES, blank=True)
    uncertainty = models.CharField(max_length=10, choices=UNCERTAINTY_CHOICES, default='ask')
    food_preferences = models.CharField(max_length=200, blank=True)   # sent to the AI (FR38)
    show_lighter_ideas = models.BooleanField(default=True)
    seen_photo_tips = models.BooleanField(default=False)
    meals_logged = models.PositiveIntegerField(default=0)             # ⟶ completed_appointments; set only by the signal

class Meal(models.Model):                          # ⟶ Appointment
    SLOT_CHOICES = [('breakfast','Breakfast'), ('lunch','Lunch'), ('snack','Snack'), ('dinner','Dinner')]
    INPUT_CHOICES = [('text','Text'), ('photo','Photo'), ('voice','Voice')]
    STATUS_CHOICES = [('draft','Draft'), ('logged','Logged')]
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='meals')
    session_key = models.CharField(max_length=40, blank=True)       # owner while a guest
    slot = models.CharField(max_length=10, choices=SLOT_CHOICES, blank=True)   # empty → set from time (signal)
    input_method = models.CharField(max_length=10, choices=INPUT_CHOICES)
    text = models.TextField(blank=True)             # typed/dictated text, or the photo note
    photo = models.ImageField(upload_to='meals/', null=True, blank=True)
    title = models.CharField(max_length=120, blank=True)
    description = models.CharField(max_length=200, blank=True)      # neutral line (FR15)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    eaten_at = models.DateTimeField(default=timezone.now)
    is_favorite = models.BooleanField(default=False)
    ai_response = models.JSONField(null=True, blank=True)           # validated AI output, for "Reset"
    deleted_at = models.DateTimeField(null=True, blank=True)        # soft delete for Undo
    created_at = models.DateTimeField(auto_now_add=True)
    # @property kcal_min / kcal_max / protein_min ... = sums over items

class MealItem(models.Model):
    CONFIDENCE_CHOICES = [('sure','Sure'), ('likely','Likely'), ('unsure','Unsure')]
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    unit = models.CharField(max_length=20)           # choices from units.py; bowl S/M/L = bowl_s / bowl_m / bowl_l
    grams = models.PositiveIntegerField()
    kcal_min_100g / kcal_max_100g                    # PositiveIntegerField
    protein_min_100g / protein_max_100g / carbs_… / fat_…   # DecimalField(5,1)
    confidence = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES)
    reason = models.CharField(max_length=150, blank=True)     # required when unsure
    question = models.CharField(max_length=150, blank=True)
    edited_by_user = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)
    # @property kcal_min = round to 10 of kcal_min_100g * grams / 100; macros the same but round to 1 g
```

**Where the course patterns are practiced:**
- **Models:** `choices` + `get_*_display`, `ImageField` + MEDIA, `related_name`.
- **Admin:** `list_display`, an inline for items, `get_queryset` (own meals only), `has_change_permission(obj)`, `has_delete_permission` (no deleting logged meals), `save_model` (sets the owner only).
- **Signals:** `pre_save` Meal (empty slot ← hour; draft → logged increments `meals_logged`), `post_delete` Meal (removes the photo file), `post_save` User (creates the Profile).
- **Forms and views:** `ModelForm` + `exclude` + `commit=False`, `get_object_or_404` with an ownership check, Post/Redirect/Get, Home grouped by slot ⟶ index grouped by specialty.

## AI response (validated in `services/ai.py`)

```json
{
  "status": "ok",
  "no_food_reason": "",
  "seen": [],
  "title": "Tavče gravče with bread and salad",
  "description": "A filling lunch with good protein and fibre.",
  "items": [
    {"name": "Cooking oil", "amount": 1, "unit": "tbsp", "grams": 10,
     "kcal_min": 20, "kcal_max": 60,
     "protein_min": 0, "protein_max": 0, "carbs_min": 0, "carbs_max": 0,
     "fat_min": 2, "fat_max": 7,
     "confidence": "unsure", "reason": "Oil is hard to see in a photo.",
     "question": "How much was there?"}
  ],
  "lighter_idea": null
}
```

**Validation rules** (anything that fails raises `AnalysisError`, handled like an AI failure):
- `status` is `ok` or `no_food`; `ok` needs 1–20 items
- every number is ≥ 0 and min ≤ max
- `confidence` is sure / likely / unsure, and `reason` is required when unsure
- strings are trimmed and length-capped
- grams are rounded to 5; per-100 g values are derived from the totals

`estimate_item(name, amount, unit)` returns one item in the same shape.

---

## Chunks

### Phase A: core checker, including voice (26–29 Oct, ~3 chunks a day)

- [x] **0. Project setup** (26 Oct)
  - Work: `.venv`, the 4 packages, `startproject zalak`, app `meals`; settings (TEMPLATES DIRS, STATIC, MEDIA, `.env` via python-dotenv); `media/` added to `.gitignore`; a placeholder page.
  - Files: `zalak/settings.py`, `zalak/urls.py`, `meals/apps.py`, `meals/views.py`, `templates/base.html`, `requirements.txt`, `.gitignore`
  - Pattern: settings.py, urls.py + `static()`
  - Test: runserver shows the placeholder; `/admin` loads.
- [x] **1. Theme + layout shell** (26 Oct)
  - Work: Bootstrap, Icons and fonts in `static/`; `zalak.css` (tokens overriding `--bs-*`, pill buttons, cards, confidence badge); `base.html` with the mobile bottom bar / desktop sidebar and a guest header; a "Coming soon" page for Diary and Statistics; a temporary style page.
  - Files: `static/…`, `static/css/zalak.css`, `templates/base.html`, `templates/coming_soon.html`, `templates/style.html`, `views.py`, `urls.py`
  - Pattern: base.html + `{% extends %}`
  - Test: the style page at 390 and 1440; every nav link opens a page.
- [x] **2. Models + admin** (26 Oct)
  - Work: Profile, Meal, MealItem, `units.py`, total properties; admin with `list_display`, the item inline, `get_queryset`, the permissions, `save_model` (owner only).
  - Files: `meals/models.py`, `meals/units.py`, `meals/admin.py`
  - Pattern: models.py, admin.py
  - Test: make a meal with 3 items in /admin; a second non-superuser sees only their own.
- [x] **3. Result page (read-only)** (27 Oct)
  - Work: total range, description, macro bar, item cards with confidence badges, slot dropdown, sticky Just checking / Log (inactive), "Estimate, not medical advice".
  - Files: `views.py`, `urls.py`, `templates/meals/result.html`, `templates/meals/_item_card.html`
  - Pattern: doctor_detail + `{% include %}`
  - Test: `/meal/<id>/` for the admin-made meal, compared with Figma Result; someone else's meal gives a 404.
- [x] **4. Text input → fake AI** (27 Oct)
  - Work: the Text and voice page (TextMealForm, detail chips); POST creates a draft (`commit=False`, slot from time); `services/ai.py` returns a fixed fake JSON; the validator turns it into items; redirect to Result.
  - Files: `forms.py`, `views.py`, `services/ai.py`, `templates/meals/text_input.html`, `static/js/chips.js`
  - Pattern: ModelForm + exclude, `commit=False`, PRG
  - Test: type a meal → Result with the fake items; Analyze is disabled while the field is empty.
- [x] **5. Real AI (text)** (27 Oct)
  - Work: the model proposal, then an Anthropic call with structured outputs (JSON schema); the prompt (ranges, the three confidence words, calm tone, no allergen claims); full validation; `AnalysisError`.
  - Files: `services/ai.py`, `settings.py`
  - Pattern: beyond the exam (a service module)
  - Test: "tavče gravče, bread, shopska salad" gives plausible ranges and an unsure item with a reason.
- [x] **6. Analyzing + errors** (28 Oct)
  - Work: an overlay shown instantly on submit with step messages + Cancel (plain JS), where the cookie loses a bite per step (Figma "Cookie (bites = progress)"); the error page "Couldn't analyze this" with Try again (same draft) / Edit the text; the No food found page. Figma has only the photo versions of the error pages, so the text versions are an adaptation; the exact Figma match is checked in chunk 19.
  - Files: `templates/meals/_analyzing.html`, `templates/meals/_input_card.html`, `static/js/analyzing.js`, `views.py`, `urls.py`, `services/ai.py`, `templates/meals/error.html`, `templates/meals/no_food.html`, `zalak.css` (the cookie reuses `img/logo.svg`)
  - Pattern: PRG, `get_object_or_404`
  - Test: a wrong API key → error page with the input kept, and Retry works; "my shoe" → No food found.
- [x] **7. Voice input (FR7, Must)** (28 Oct)
  - Work: Web Speech API in the text field; idle / listening (pulsing, live words) / done (editable) states; `input_method='voice'`; the mic is hidden when unsupported.
  - Files: `static/js/voice.js`, `templates/meals/text_input.html`, `forms.py`
  - Pattern: JS only where the interaction needs it
  - Test: in Chrome, dictate → edit → Analyze; in Firefox there's no mic and the field still works.
- [x] **8. Photo + note** (28 Oct)
  - Work: PhotoMealForm (`multipart`); the native camera input with a preview; the note + chips; a Tips button placeholder; the image sent to the AI; the photo shown on Result.
  - Files: `forms.py`, `views.py`, `services/ai.py`, `templates/meals/photo_input.html`, `static/js/photo_preview.js`
  - Pattern: ImageField + `request.FILES`
  - Test: a plate photo with "cooked in butter"; a phone on the LAN (`runserver 0.0.0.0:8000`) opens the camera.
- [x] **8b. Photo + voice polish** (1 Nov, added after phone tests through the https tunnel)
  - Work: voice state machine for Android Chrome (every SpeechRecognition event, start/stop watchdogs, `[voice]` console logs, one phrase per tap on Android); waves that follow speech; swipeable photo tips (Figma Tips 1–3) with "Don't show again" in `Profile.seen_photo_tips` or the session; a live camera on phones with the native camera as fallback; a desktop drop zone + two columns; the bigger note-step preview; `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` extras from `.env`.
  - Files: `static/js/voice.js`, `static/js/photo.js`, `static/js/photo_tips.js`, `templates/meals/photo_input.html`, `_photo_tips.html`, `_meal_drawing.html`, `views.py`, `urls.py`, `settings.py`, `zalak.css`
  - Pattern: `@require_POST` + session / Profile, beyond the exam (getUserMedia, DataTransfer)
  - Test: voice on Android through the tunnel stops every time; live camera → note; tips "Don't show again" survives a reload; desktop drag / paste.
- [x] **9. Log / Just checking + signals** (29 Oct)
  - Work: Log → `logged`, toast "Logged to lunch · Undo"; Just checking deletes the draft; signals for the slot from time, the counter (draft → logged) and removing the photo file.
  - Files: `views.py`, `signals.py`, `apps.py`, `templates/meals/_toast.html`, a temporary `home.html` list
  - Pattern: signals.py + `ready()`
  - Test: log a meal → the counter goes up once (also when logged from the admin); Undo works; after Just checking the photo is gone from `media/`.
- [x] **10. Edit item: amount** (29 Oct)
  - Work: MealItemForm with the name, a stepper + quick fractions, the unit picker (offcanvas-bottom with 4 tabs), the "≈ g" line, a live kcal/macro preview, and Save changes / Reset / Delete item.
  - Adapted from Figma (agreed 1 Nov): the stepper walks the fractions itself (¼ ½ ¾ 1 1½ 2 2½ 3, then whole numbers; measured units step evenly), no separate chips; no "How it was cooked" row (Could), no fibre/salt, no name suggestions; Delete works now (Undo in chunk 11) but not on the last item; logged meals' items can be edited too (reused in chunk 15). Same unit → scale by the item's own grams per unit; a new unit → the `units.py` table.
  - Changed 2 Nov (after review, also adapted from Figma): no Details card / Unit row (the chip under the number opens the Unit sheet); Nutrition is always open (three tiles, no toggle); Reset is a tinted pill with an icon; the buttons are Re-estimate | Save changes in one row, with Delete item on its own below.
  - Files: `units.py`, `models.py`, `forms.py`, `views.py`, `urls.py`, `templates/meals/edit_item.html`, `_unit_sheet.html`, `_item_card.html`, `static/js/portion.js`, `zalak.css`
  - Pattern: ModelForm with `instance`
  - Test: chicken 150 g → 200 g, and protein updates live and on Result (T2, NFR7).
- [x] **11. Add / remove / re-estimate / inline question** (29 Oct)
  - Work: "Add something Zalak missed" and "Re-estimate" via `estimate_item`; remove with Undo; the A little / About that / A lot chips on unsure items.
  - Done early (1 Nov, with chunk 10): remove with Undo. Delete item keeps a copy of the item in the session; Undo in the toast recreates it with its numbers and position (no soft delete, so no `meal.items` filtering).
  - Add item works on logged meals too (Meal detail reuses the item list in chunk 15). If `estimate_item` fails (decided 1 Nov): keep the typed name and show a calm message inline on Result, the button becomes "Try again". No typing calories by hand.
  - Decided 1 Nov: "Re-estimate" is a button on Edit item (not in Figma); it keeps the user's amount and unit. `item.position` is the item's index in `ai_response['items']`, so Reset and the chips always find Zalak's estimate.
  - Changed 2 Nov: Re-estimate sits next to Save changes (see chunk 10). An answered question disappears: the item becomes "likely" (an unsure item always shows its reason), and the amount can still be changed on Edit item. Replaces the 1 Nov "chip stays pressed".  - Files: `services/ai.py`, `models.py`, `views.py`, `urls.py`, `templates/meals/result.html`, `_item_card.html`, `edit_item.html`, `static/js/add_item.js`, `portion.js`, `zalak.css`
  - Pattern: POST + redirect
  - Test: add "coffee with milk", remove the bread + Undo, tap "A lot" on the oil; with a wrong API key, Add shows the error with the name kept, and Retry works.

### Phase B: accounts, guest flow, Home, meal detail, Diary (30 Oct – 1 Nov)

- [x] **12. Welcome, sign up (2 steps), sign in/out** (30 Oct)
  - Work: e-mail as the username; Profile via a `post_save` signal; LoginView/LogoutView; `@login_required`.
  - Decided 2 Nov: the account is made and signed in at step 1 (the password never waits in the session), so step 2 has no back arrow and "Skip for now" is the way out. No "Forgot password?" (no e-mail sending). Name is required. Sign out sits on the Profile placeholder until chunk 18. `/` shows Welcome to guests and Home to users; Diary, Statistics and Profile send a guest to Sign in.
  - Added beyond Figma: show/hide password, a live "At least 8 characters" tick, calm password messages that say what to do, errors that clear once the field is changed, a wrong password keeps the e-mail and focuses the password, "Sign in instead" under a taken e-mail, a short hint under each activity level, a "Welcome to Zalak, Ana" toast on Home, and a centered card at 1440.
  - Files: `forms.py`, `views.py`, `signals.py`, `urls.py`, `settings.py`, `templates/base.html`, `templates/registration/login.html`, `welcome.html`, `signup_1.html`, `signup_2.html`, `_field.html`, `home.html`, `coming_soon.html`, `static/js/auth.js`, `zalak.css`
  - Pattern: ModelForm, signals
  - Test: create an account, Skip step 2, sign out, sign in.
- [x] **13. Guest flow (T7) + guest draft cleanup** (30 Oct)
  - Work: a guest's draft is tied to the session; Log → the "Keep this meal?" sheet → sign-up → the draft is assigned and logged; guest drafts older than 24 h are deleted on each new draft.
  - Note from chunk 12: Django's `login()` gives the session a new key, so read the guest's `session_key` (or keep the meal id in the session) *before* signing in, or the draft can't be found afterwards. Same for Sign in from the sheet.
  - Decided 2 Nov: the guest's Log opens the sheet; "Create a free account" submits the Log form (so the slot goes along) and `log_meal` keeps the draft's id + session key in `session['guest_meal']`. A `user_logged_in` signal in `signals.py` logs it after any sign-in (sign-up step 1, Sign in, "Sign in instead"), so the meal is safe before step 2. The toast is "Welcome to Zalak, Ana · Logged to lunch" after sign-up and "Logged to lunch" after sign-in, both with Undo. "Not now, I was just checking" is Just checking.
  - Added beyond Figma: "Already have an account? Sign in" on the sheet, and "Your meal will be logged to lunch once you're in." on Sign up and Sign in while a meal waits.
  - Files: `views.py`, `signals.py`, `templates/meals/result.html`, `_guest_sheet.html`, `_keep_note.html`, `signup_1.html`, `registration/login.html`, `zalak.css`
  - Pattern: `commit=False`, session, signals
  - Test: in a private window, check → Log → create an account → the meal is on Home and the counter is 1; an old guest draft (backdated in admin) disappears.
- [x] **14. Home** (31 Oct)
  - Work: the week strip (`?date=`, arrows, date picker); the Eaten today card (range, bar by slot); macro cards; four slots (one queryset per slot) with an "N meals" sheet; "+" per slot and the corner "+" → the Add meal sheet (offcanvas-bottom); the first-day empty state.
  - Decided 2 Nov: "+" on a past day logs to that day (the Add sheet carries `day=`; the input pages keep it in a hidden field; the draft gets that day at the current clock time; Log returns to `?date=` of that day). Jump to a date is the Figma calendar sheet, built in Python with the `calendar` module (dots on days with meals, no future days, months by `?month=`), reused by the Diary.
  - Adapted from Figma: arrows at the ends of the week strip (docs/05; Figma has none); the date beside "Meals" opens the calendar; the Add meal sheet is on every signed-in page (the corner "+" and the sidebar's "Add a meal"), a GET form, so slot and day work without JS. Left out: water, the desktop "On average" chart (chunk 17), "Your meals" and Recent in the sheet (chunk 22). One meal in a slot opens Result until chunk 15 brings Meal detail. `django.contrib.humanize` for `1,230`.
  - Files: `settings.py`, `context_processors.py`, `views.py`, `templates/base.html`, `templates/meals/home.html`, `_slot.html`, `_slot_body.html`, `_slot_sheet.html`, `_add_meal_sheet.html`, `_date_sheet.html`, `text_input.html`, `photo_input.html`, `static/js/add_meal_sheet.js`, `static/js/home.js`, `zalak.css`
  - Pattern: index grouped by specialty, `__date` lookups
  - Test: log 3 meals in different slots; switch days; check a new account's empty state.
- [x] **15. Meal detail: edit + delete with Undo** (31 Oct)
  - Work: change the slot and time; rename the meal title; add, replace or remove the photo; edit items (reusing Edit item); soft delete + Undo toast.
  - Title (adaptation beyond Figma, decided 1 Nov): a small field in the same ModelForm as slot and time, saved with Save changes; an emptied title falls back to the AI's (`ai_response['title']`), so a meal is never untitled. The description line stays the AI's.
  - Photo (adaptation beyond Figma, decided 1 Nov): add a photo to a typed meal, replace it, or remove it, without asking the AI again (the numbers stay). Reuses `shrink_photo` from `forms.py`; the old file is deleted from `media/` on replace and remove.
  - Decided 2 Nov: Meal detail lives at the same URL as Result (`/meal/<id>/` shows Result for a draft and Meal detail once logged), so Edit item, Add item, Delete item and the question chips come back to it unchanged. Result and Meal detail share `_slot_dropdown.html`, `_meal_summary.html` and `_meal_items.html`. Save changes goes to Home on the meal's day with "Changes saved"; Delete meal is a soft delete with "Meal deleted · Undo" on that Home. Item changes still save on their own.
  - Time sheet (Figma "Overlay · Time"): the hour : minute wheel as in Figma (changed 2 Nov from two native selects): scroll-snap columns, 5 rows visible, minutes in 5-minute steps, one row per mouse-wheel notch, arrow keys (each column is a spinbutton); no day switch (removed 2 Nov: the sheet only changes the time on the meal's own day); "Use the time it was logged" uses `created_at`. Done fills hidden fields, so an untouched time is saved exactly. A future time is refused.
  - Left out for now: the heart and Log again (chunk 22), Tell Zalak (chunk 24); the slot stays Result's dropdown, not the Figma sheet. Delete doesn't lower `meals_logged` (it counts Log actions).
  - Files: `forms.py`, `views.py`, `urls.py`, `templates/meals/meal_detail.html`, `_time_sheet.html`, `_slot_dropdown.html`, `_meal_summary.html`, `_meal_items.html`, `result.html`, `static/js/meal_detail.js`, `slot_select.js`, `zalak.css`
  - Pattern: `has_delete_permission`, PRG, ImageField + `request.FILES`
  - Test: change the time, rename the title (shows on Meal detail and Home), add a photo to a typed meal, replace it (the old file is gone from `media/`), remove it, then delete + Undo (FR25).
- [x] **16. Simple Diary** (1 Nov)
  - Work: one page per day with meal photos, time, name and range, plus the day total; arrows and a date jump; meal → meal detail. Replaces the "Coming soon" page. No book animation.
  - Decided 2 Nov: the arrows step through every calendar day (an empty past day says "Nothing logged this day" with "Add a meal to this day"); back always works (changed 2 Nov: no "Start" at the first logged meal, whose page is only labelled "First page"); nothing after today. The desktop is Figma's two-page spread (the day before | the chosen day), its arrows two days at a time. Meal detail goes back where it was opened from (Home or the Diary, `?from=` kept in the session per meal), also after Save, Delete and Undo. Today's page lists its empty slots at the end ("Nothing yet · Tap to add it"). The calendar sheet is shared with Home (`calendar_month(..., url_for)`), and the Add meal sheet takes the day from the button that opens it (`data-day`).
  - Left out: the "Your meals" tab and button (chunk 22), the page dots, the book animation (Could). Thumbnails without a photo are a pastel square with a small CSS plate. The page keeps a fixed minimum size (phones: the screen between header and arrows, at least 32rem; desktop book: at least 38rem); a busy day grows longer.
  - Files: `views.py`, `templates/meals/diary.html`, `_diary_page.html`, `_diary_nav.html`, `_date_sheet.html`, `_add_meal_sheet.html`, `home.html`, `static/js/date_sheet.js` (was `home.js`), `add_meal_sheet.js`, `zalak.css`
  - Pattern: date filters
  - Test: browse back a week and open a meal.

### Phase C: demo prep (2–3 Nov)

- [x] **17. Statistics page** (2 Nov)
  - Work: the last 7 days, with the average kcal range per day and the average macro split; no target line, no red/green. Replaces "Coming soon".
  - Decided 2 Nov: Figma's **Mo–Su weeks** (as on Home's week strip) instead of "the last 7 days", plus a **Month** view through Figma's Week / Month switch (`?period=month`, `?date=` picks the week or month; ‹ always goes back, › stops at the period holding today). Averages are over the **days with a logged meal** (a day not logged isn't a day of eating nothing): kcal rounded to 10, grams to 5. Each bar is solid up to the lowest estimate and lighter up to the highest; the chart's top is 1.1 × the highest day (at least 1,000), with grid lines every 1,000. Macro shares come from the middle of each range × 4/4/9 kcal per g and add up to 100 (Figma's 20/46/34). Also built from Figma: the Days logged and Meals cards, and "Most logged this week" (names logged at least twice, case-insensitive, top 3, with the latest photo or the slot's pastel).
  - Adapted from Figma: left out Customize (FR41, Could), the Water card (water not built), Weight and BMI (no weight history; BMI is out of scope), so two KPI cards. The Month view and the desktop layout have no Figma frame: a month has thin bars with the day number on 1, 8, 15, 22, 29; at 1440 the switch and the range share a row and the chart sits beside Macros + Most logged. Empty and future days draw no bar; an empty period says "Nothing logged this week yet." and hides Macros and Most logged. The Week / Month options are 44 px high (Figma 38). Still left out: the desktop Home "On average" card.
  - Files: `views.py`, `templates/meals/statistics.html`, `zalak.css`, `settings.py` (`STATIC_VERSION`), `tests.py`
  - Pattern: loops over querysets
  - Test: the numbers match the logged meals by hand.
- [x] **18. Small Profile page** (2 Nov)
  - Work: personal details (name, height, weight, activity) via a ProfileForm with `instance`; the "When Zalak is unsure" switch (Ask me / Best guess) saved to `Profile.uncertainty`, and Result's inline question follows it (guests always get Ask me); a red Sign out button; "Estimate, not medical advice". The Profile link in the nav opens it.
  - Decided 2 Nov: Figma's hub + subpages instead of one page. `/profile/` (card with the initial, Edit details, menu rows, red Sign out), Personal details (name, e-mail, height, weight with one decimal, year of birth, activity: two ModelForms in one form; a new e-mail is the new sign-in name), Preferences ("When Zalak is unsure", saved on tap with `fetch`, a 204 back, a `<noscript>` Save button otherwise), Account and privacy (Change password with Django's `PasswordChangeForm` + `update_session_auth_hash`; Delete account and all data, FR3, on a confirm page that asks for the password once), and Help and about. Best guess hides the question and the chips but keeps the unsure badge and its reason; guests are always asked. Profile URL names all start with `profile`, so the sidebar row is marked on every subpage. `coming_soon.html` is removed (nothing uses it).
  - Adapted from Figma: left out the Goals and targets, Water and Your meals rows; Food preferences (chunk 23), Show lighter ideas (chunk 25), Dark mode and Meal slots in Preferences; "Download my data" and "Photos · Kept for 30 days" in Account. Sub-lines say what is built ("When unsure: Ask me", "Password, delete account", "Choose a new one any time"). The Preferences line follows the choice. Personal details keeps sign-up's activity hints. Switch options are 44 px (Figma 38). No Figma frame for Change password, the delete confirm, Help and about or the desktop (one 560 px column in the middle).
  - Files: `models.py` + migration `0002`, `forms.py`, `views.py`, `urls.py`, `base.html`, `templates/meals/profile.html`, `profile_details.html`, `profile_preferences.html`, `account_privacy.html`, `change_password.html`, `delete_account.html`, `help_about.html`, `_profile_head.html`, `_profile_row.html`, `_activity_field.html` (from `signup_2.html`), `_item_card.html`, `static/js/preferences.js`, `zalak.css`, `settings.py`, `tests.py`
  - Pattern: ModelForm with `instance`, `@login_required`, PRG
  - Test: switch to Best guess → a new analysis shows no question on the unsure item; switch back; edit the weight; sign out.
- [x] **19. 390 / 1440 + accessibility pass** (2 Nov)
  - Work: the desktop two-column Result and Home; check the Analyzing, error and No food pages against their Figma frames (spacing, font and button sizes, desktop layout); keyboard use; 44 px targets; contrast; WAVE with no errors.
  - Decided 2 Nov: Figma's failed-step moment (`Analyzing · Connection lost / No food`): after a failed analysis the redirect carries `?fresh=1`, and the error or No food page opens with the overlay showing the done steps, the failed one (peach "!", "Connection lost" / "No food found in the photo" / "Something went wrong") and the bites and progress so far; after 1.2 s it fades to the page (a tap or key skips it; `replaceState` drops `fresh`; aria-hidden + inert; not with reduced motion or without JS). Result and Meal detail have two columns at ≥ 992 px (photo, slot, totals left; What Zalak saw right); the left side is sticky on Result when it fits (≥ 820 px high), not on Meal detail (too tall); Meal detail's Save | Delete sit side by side on the desktop. The Statistics chart card is `_kcal_chart.html`, also on the desktop Home for the week on screen. The Analyzing overlay, error and No food pages follow the Figma measurements (310 px steps card and bar, 20 px title, 24 px gutter, 28 px titles, no line above the buttons, the photo note as a "Waiting" chip). Field edges use `--z-field-line` (#7E9486, 3:1). Targets to 44 px (logo, detail chips, unit chip, unit tabs, sign-up checkbox label, desktop week arrows); future days lose their 0.5 opacity (contrast); the week strip's future days use hidden text instead of `aria-label` on a span; the hidden photo inputs got a name. The activity `.z-segment` rule is scoped to `.z-activity`. The temporary style page is removed.
  - Checked with axe-core 4.10.2 (from the scratchpad, not in the project) and a small target/label/contrast script on 32 pages at 390 and 1440 px: no axe violations. Known exception: the phone week strip (day pills ~35 px wide, arrows 36 px), which passes WCAG 2.2 AA (24 px) but not NFR13's 44 px, because 7 days and 2 arrows don't fit at 390 otherwise.
  - Kept against Figma: "Saved as a draft" / "Connection lost" instead of "Saved on this phone" / "You're offline" (the draft is on the server), no "Analyze it when I'm back online" (true offline is Could), and the failed step's "!" in ink, not orange (red only for delete).
  - Files: `views.py`, `urls.py`, `forms.py`, `templates/meals/result.html`, `meal_detail.html`, `home.html`, `statistics.html`, `_kcal_chart.html` (new), `error.html`, `no_food.html`, `_analyzing.html`, `templates/style.html` (deleted), `static/js/analyzing.js`, `zalak.css`, `settings.py`, `tests.py`
  - Test: WAVE on Home, Result and Edit item; tab through the checker.
- [x] **20. Demo data + demo script** (3 Nov)
  - Work: a fixture with a demo user and a week of logged meals (built-in `loaddata`); `docs/demo-script.md` with a 5-minute walkthrough: guest check → Log → sign-up, photo + correction, voice, Home, Diary, Statistics, Profile (Best guess), an error case.
  - Decided 2 Nov: a fixture with fixed dates, built by `meals/fixtures/build_demo.py` (run in `manage.py shell`; a rolled-back transaction; meals go through `services.ai.validate()` and `views.apply_analysis()`, so Reset works; written with Django's serializer). Ana (`ana@zalak.demo` / `zalak-demo-2026`): 33 logged meals from Mon 26 Oct to Tue 3 Nov (changed from the plan's 27 Oct, which is a Tuesday), with high ids (user 900, meals 9001+, items 90001+) so loading never overwrites other rows. Five of your photos (`demo_photos_src/`, gitignored) are shrunk with `forms.shrink_photo` into `meals/fixtures/demo_photos/`, copied to `media/meals/demo/` in the setup. `ZALAK_DB` in `.env` picks the database file, so the demo runs on `demo.sqlite3`. The script: sign up live as Viktor (guest flow), then sign in as Ana; real AI with `ZALAK_AI_FAKE=1` as the backup.
  - Fixed on the way (from chunk 19): Meal detail on phones had a large gap above "What Zalak saw" (the old 13rem room for the buttons was on the wrong part after the two-column split).
  - Files: `meals/fixtures/build_demo.py`, `meals/fixtures/demo.json`, `meals/fixtures/demo_photos/`, `docs/demo-script.md`, `settings.py` (`ZALAK_DB`, `STATIC_VERSION`), `.gitignore`, `zalak.css`, `tests.py`
  - Test: run the whole script on a fresh DB.

> **═══ DEMO SCOPE LINE (4/5 Nov) ═══** Chunks 0–20 must work at the demo: the full checker (text, voice, photo + note, Analyzing, Result, Edit / add / remove / re-estimate, Log / Just checking, errors), accounts, the guest flow, Home, meal detail, a simple Diary, Statistics, a small Profile page, a responsive and accessible layout, and the demo data. Everything below can wait until after the demo.

### Phase D: after the demo (6–15 Nov, buffer)

- [ ] **21. Professor's feedback**: fixes from the demo, planned once we have it.
- [x] **22. Your meals: Favorites + My meals** (FR10, FR26, FR27, FR39, NFR8). Planned 2 Nov.
  - Work: a favorite heart and **Log again** on Meal detail; the **Your meals** page as the back of the Diary book (`/diary/your-meals/?tab=favorites|mine`, the ribbon tab on every Diary page, › on today's page goes there); the **Saved meal** page (heart, "Logged N times", slot dropdown, the items, Log to <slot>, Edit meal, red Remove from favorites / Delete from My meals with Undo); **My meals**: "Create your own meal" runs the normal checker with `mine=1` and its Result shows **Save to My meals**, plus **Save as my meal** on Meal detail; the Add meal sheet gets **Your meals** (lilac) and **Recent** (the last 5 different logged meals, one-tap **Log again** to the sheet's slot and day, "See all" → the Diary); the Profile row **Your meals · N saved**. Toasts: "Saved to Your meals", "Removed from Your meals · Undo", "Logged again to lunch · Undo".
  - Data: a new status `('mine', 'My meal')` (migration): a template that never counts. One helper `copy_meal(source, slot, eaten_at, status)` copies the fields, the items (`ITEM_FIELDS`) and `ai_response`, and copies a photo to a **new file** (so `remove_photo_file` deleting one never breaks the other). "Logged N times" counts logged meals with the same title (any case), as Most logged does.
  - Figma: `Add meal`, `Diary · Your meals`, `Diary · Your meals · My meals`, `Saved meal`, `Meal detail`, the three toasts.
  - Pattern: `commit=False` copies, PRG, `get_object_or_404` ownership, `@require_POST`
  - Decided 3 Nov (built): a favorite's items are read-only on Saved meal and "Edit meal" opens its Meal detail (`?from=your_meals`, back goes to Your meals), so a pencil never quietly changes a Diary day; a My meal is edited on Saved meal itself (`result` redirects a `mine` meal there, so Edit item / Add item / the chips come back to it) and "Edit meal" is a **Rename** sheet (`MealTitleForm`; empty → Zalak's name). Log again is always a copy now (today, or Recent's day), slot from the time unless picked; Undo sets the copy to draft (the signal lowers the counter), then deletes it, and only for the id in `session['logged_again']`. The heart is a POST form (unsaved Meal detail edits are lost if tapped first); its Undo is the same toggle. "Create your own meal" is a two-option sheet (Photo / Text and voice) with `mine=1`; the draft id waits in `session['mine_drafts']`; its Result shows Cancel | Save to My meals. Recent is in the `add_meal` context processor (one query per signed-in page); each card is its own POST form, `add_meal_sheet.js` copies the slot and day into it.
  - Adapted from Figma: "Save a copy to My meals" is a text button under Meal detail's items (not in Figma); the "♥ Your meals" tab is 36 px wide (WCAG 2.2's 24 px, not NFR13's 44 px, which would cover the page); the heart is ink, not red; empty-tab words; Your meals on the desktop is one 560 px page (no frame). Left out: the page dots. Meal detail's bar is Log again | Save changes with Delete meal below on phones, all three in a row on the desktop.
  - Files: `models.py` + migration `0003`, `forms.py`, `views.py`, `context_processors.py`, `zalak/urls.py`, `templates/meals/your_meals.html`, `saved_meal.html`, `_book_tab.html`, `_create_meal_sheet.html` (new), `meal_detail.html`, `result.html`, `_add_meal_sheet.html`, `_item_card.html`, `_meal_items.html`, `diary.html`, `_diary_nav.html`, `profile.html`, `text_input.html`, `photo_input.html`, `static/js/add_meal_sheet.js`, `zalak.css`, `settings.py` (`STATIC_VERSION` 27), `tests.py`
  - Test: heart a meal → it's under Favorites → open it → Log to lunch (2 taps) → today's Home has it; Log again from Recent; create a My meal by voice and log it the next day; delete the original and the copy's photo stays.
- [x] ~~**23. Food preferences**~~: dropped 2 Nov (FR38 not built). The unused `Profile.food_preferences` field is removed in the clean-up (a migration).
- [x] **24. Drafts "To finish" + Tell Zalak** (FR9, D2, FR18–FR22). Planned 2 Nov.
  - Work: Home lists that day's drafts in their slot as a dashed **To finish** row ("To finish · <title or the typed words>" ›; never counted), for any meal checked but not logged or thrown away (Cancel during Analyzing, an error / No food page left with ×, a Result left without Log); tapping opens where it stopped (the `result` view already routes drafts), Just checking removes it. Cancel says "Kept as a draft: find it on Home under To finish", and the same words analysed again within 15 minutes reuse that draft. **Tell Zalak** under Add item on Result and Meal detail ("Something else wrong? Tell Zalak", a field with a mic; `voice.js` becomes a small function any field can use): one AI call (`services.ai.correct_meal`: the original words or photo + note, the current items, the correction; the normal `RESPONSE_SCHEMA` and `validate()`) replaces the items, shows the Analyzing overlay, keeps a title the user renamed, and the toast "Zalak updated the meal · Undo" brings back the old items from the session. Failures keep the words with a calm message and Try again; "no food" → "Zalak couldn't use that. Try saying what changed."
  - Adapted: no Figma frame for the To finish row (docs/05 names it); it uses the dashed style of "Add something Zalak missed".
  - Decided 3 Nov (built): Cancel only calls `window.stop()`, so the server still saves (and may finish) the draft; that is what makes "Kept as a draft" true. The reuse matches **text only** (spaces and case aside, own drafts or the guest's session, 15 min, `REUSE_MINUTES`); a reused draft that already has items opens its Result with no new AI call. The To finish rows leave out "Create your own meal" drafts (`session['mine_drafts']`). Guests and My-meal pages get "Stopped. What you added is still here." (`_cancel_note.html`). Tell Zalak is in `_meal_items.html`, so it is on Result, Meal detail and a My meal's Saved page, never on a favorite's read-only page; it changes a logged meal straight away (like item edits). `services.ai.correct_meal(text, items, correction, image_bytes)` uses `CORRECTION_PROMPT` (the system prompt + "keep what the correction doesn't touch"); the old meal waits in `session['corrected_meal']` (`item_snapshot()`, now shared with `delete_item`). `voice.js` finds its parts by `data-voice-*` in each `form[data-voice]` (the state machine is unchanged); the Tell Zalak mic sits inside the field.
  - Files: `services/ai.py`, `forms.py`, `views.py`, `zalak/urls.py`, `templates/meals/_slot.html`, `_meal_items.html`, `_cancel_note.html` (new), `result.html`, `meal_detail.html`, `saved_meal.html`, `text_input.html`, `photo_input.html`, `static/js/voice.js`, `analyzing.js`, `zalak.css`, `settings.py` (`STATIC_VERSION` 28), `tests.py`
  - Pattern: querysets per slot, session Undo, the service module
  - Test: Cancel an analysis → To finish on Home → finish and Log; "it was turkey, not chicken" on a meal → items change → Undo; with a wrong API key the correction stays in the field.
- [x] **25. Lighter idea** (FR17). The photo tips were built in chunk 8b. Planned 2 Nov.
  - Work: `RESPONSE_SCHEMA` gets `lighter_idea` (null, or name + kcal_min/kcal_max); the prompt asks for one only when a clearly lighter version of the same kind of meal exists, in neutral words (never "healthier", "better", "good"); `validate()` drops it unless its middle is at least 25 % below the meal's; the fake answer gets one. A small card under the summary on a **draft's Result only** ("A lighter idea: bean salad with a slice of bread, ~300–380 kcal") with × (saved on the meal; fetch, or a form post without JS); never a pop-up, never on a logged meal. Preferences gets the Figma toggle **Show lighter ideas** (`Profile.show_lighter_ideas`, on by default), "On Result, before you log", saved on tap; guests always see them.
  - Pattern: the service module, `validate()`, ModelForm with `instance`
  - Test: check "a big plate of burek" → the card shows → × hides it; turn it off in Preferences → no card; a logged meal never shows it.

### Cut order if we fall behind
- **Before the demo:** reduce Statistics (17) to the average kcal range only. Phases A and B and the Diary are never cut.
- **After the demo:** cut 25 first, then Tell Zalak (24), then the To finish rows (24). 22 is kept.

## Every chunk ends with
- `python manage.py check`, plus `makemigrations` / `migrate` if the models changed
- bump `STATIC_VERSION` in `settings.py` if `zalak.css` or a file in `static/js/` changed
- the browser test at 390 px and 1440 px, including the error path
- a suggested commit message (I never commit)
