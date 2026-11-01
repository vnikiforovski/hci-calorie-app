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
    weight_kg = models.PositiveIntegerField(null=True, blank=True)
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
- [ ] **10. Edit item: amount** (29 Oct)
  - Work: MealItemForm with the name, a stepper + quick fractions, the unit picker (offcanvas-bottom with 4 tabs), the "≈ g" line, a live kcal/macro preview, and Save changes / Reset / Delete item.
  - Adapted from Figma (agreed 1 Nov): the stepper walks the fractions itself (¼ ½ ¾ 1 1½ 2 2½ 3, then whole numbers; measured units step evenly), no separate chips; no "How it was cooked" row (Could), no fibre/salt, no name suggestions; Delete works now (Undo in chunk 11) but not on the last item; logged meals' items can be edited too (reused in chunk 15). Same unit → scale by the item's own grams per unit; a new unit → the `units.py` table.
  - Files: `units.py`, `models.py`, `forms.py`, `views.py`, `urls.py`, `templates/meals/edit_item.html`, `_unit_sheet.html`, `_item_card.html`, `static/js/portion.js`, `zalak.css`
  - Pattern: ModelForm with `instance`
  - Test: chicken 150 g → 200 g, and protein updates live and on Result (T2, NFR7).
- [ ] **11. Add / remove / re-estimate / inline question** (29 Oct)
  - Work: "Add something Zalak missed" and "Re-estimate" via `estimate_item`; remove with Undo; the A little / About that / A lot chips on unsure items.
  - Done early (1 Nov, with chunk 10): remove with Undo. Delete item keeps a copy of the item in the session; Undo in the toast recreates it with its numbers and position (no soft delete, so no `meal.items` filtering).
  - Files: `views.py`, `services/ai.py`, `templates/meals/result.html`, `templates/meals/_item_card.html`
  - Pattern: POST + redirect
  - Test: add "coffee with milk", remove the bread + Undo, tap "A lot" on the oil.

### Phase B: accounts, guest flow, Home, meal detail, Diary (30 Oct – 1 Nov)

- [ ] **12. Welcome, sign up (2 steps), sign in/out** (30 Oct)
  - Work: e-mail as the username; Profile via a `post_save` signal; LoginView/LogoutView; `@login_required`.
  - Files: `forms.py`, `views.py`, `signals.py`, `urls.py`, `templates/registration/*`, `welcome.html`, `signup_1.html`, `signup_2.html`
  - Pattern: ModelForm, signals
  - Test: create an account, Skip step 2, sign out, sign in.
- [ ] **13. Guest flow (T7) + guest draft cleanup** (30 Oct)
  - Work: a guest's draft is tied to the session; Log → the "Keep this meal?" sheet → sign-up → the draft is assigned and logged; guest drafts older than 24 h are deleted on each new draft.
  - Files: `views.py`, `templates/meals/result.html`, `templates/meals/_guest_sheet.html`
  - Pattern: `commit=False`, session
  - Test: in a private window, check → Log → create an account → the meal is on Home and the counter is 1; an old guest draft (backdated in admin) disappears.
- [ ] **14. Home** (31 Oct)
  - Work: the week strip (`?date=`, arrows, date picker); the Eaten today card (range, bar by slot); macro cards; four slots (one queryset per slot) with an "N meals" sheet; "+" per slot and the corner "+" → the Add meal sheet (offcanvas-bottom); the first-day empty state.
  - Files: `views.py`, `templates/meals/home.html`, `_add_meal_sheet.html`, `_slot.html`
  - Pattern: index grouped by specialty, `__date` lookups
  - Test: log 3 meals in different slots; switch days; check a new account's empty state.
- [ ] **15. Meal detail: edit + delete with Undo** (31 Oct)
  - Work: change the slot and time; edit items (reusing Edit item); soft delete + Undo toast.
  - Files: `views.py`, `forms.py`, `templates/meals/meal_detail.html`
  - Pattern: `has_delete_permission`, PRG
  - Test: change the time, then delete + Undo (FR25).
- [ ] **16. Simple Diary** (1 Nov)
  - Work: one page per day with meal photos, time, name and range, plus the day total; arrows and a date jump; meal → meal detail. Replaces the "Coming soon" page. No book animation.
  - Files: `views.py`, `templates/meals/diary.html`
  - Pattern: date filters
  - Test: browse back a week and open a meal.

### Phase C: demo prep (2–3 Nov)

- [ ] **17. Statistics page** (2 Nov)
  - Work: the last 7 days, with the average kcal range per day and the average macro split; no target line, no red/green. Replaces "Coming soon".
  - Files: `views.py`, `templates/meals/statistics.html`
  - Pattern: loops over querysets
  - Test: the numbers match the logged meals by hand.
- [ ] **18. Small Profile page** (2 Nov)
  - Work: personal details (name, height, weight, activity) via a ProfileForm with `instance`; the "When Zalak is unsure" switch (Ask me / Best guess) saved to `Profile.uncertainty`, and Result's inline question follows it (guests always get Ask me); a red Sign out button; "Estimate, not medical advice". The Profile link in the nav opens it.
  - Files: `forms.py`, `views.py`, `urls.py`, `templates/meals/profile.html`, `templates/meals/_item_card.html`
  - Pattern: ModelForm with `instance`, `@login_required`, PRG
  - Test: switch to Best guess → a new analysis shows no question on the unsure item; switch back; edit the weight; sign out.
- [ ] **19. 390 / 1440 + accessibility pass** (2 Nov)
  - Work: the desktop two-column Result and Home; check the Analyzing, error and No food pages against their Figma frames (spacing, font and button sizes, desktop layout); keyboard use; 44 px targets; contrast; WAVE with no errors.
  - Files: templates, `zalak.css`
  - Test: WAVE on Home, Result and Edit item; tab through the checker.
- [ ] **20. Demo data + demo script** (3 Nov)
  - Work: a fixture with a demo user and a week of logged meals (built-in `loaddata`); `docs/demo-script.md` with a 5-minute walkthrough: guest check → Log → sign-up, photo + correction, voice, Home, Diary, Statistics, Profile (Best guess), an error case.
  - Files: `meals/fixtures/demo.json`, `docs/demo-script.md`
  - Test: run the whole script on a fresh DB.

> **═══ DEMO SCOPE LINE (4/5 Nov) ═══** Chunks 0–20 must work at the demo: the full checker (text, voice, photo + note, Analyzing, Result, Edit / add / remove / re-estimate, Log / Just checking, errors), accounts, the guest flow, Home, meal detail, a simple Diary, Statistics, a small Profile page, a responsive and accessible layout, and the demo data. Everything below can wait until after the demo.

### Phase D: after the demo (6–15 Nov, buffer)

- [ ] **21. Professor's feedback**: fixes from the demo, planned once we have it.
- [ ] **22. Your meals**: a favorite heart, Your meals + Recent in the Add meal sheet, and "Log again" copies a meal (≤2 taps, NFR8).
- [ ] **23. Food preferences**: food preferences in Profile · Preferences, sent to the AI (FR38).
- [ ] **24. Drafts "To finish" + Tell Zalak**: Cancel during Analyzing keeps a To finish draft on Home; the correction text re-analyzes the meal.
- [ ] **25. Photo tips + lighter idea**: swipeable Tips cards with "Don't show again" (FR31); the dismissible lighter-idea card when Just checking (FR17).

### Cut order if we fall behind
- **Before the demo:** reduce Statistics (17) to the average kcal range only. Phases A and B and the Diary are never cut.
- **After the demo:** cut 24 first, then 25, then the remaining Statistics details.

## Every chunk ends with
- `python manage.py check`, plus `makemigrations` / `migrate` if the models changed
- bump `STATIC_VERSION` in `settings.py` if `zalak.css` or a file in `static/js/` changed
- the browser test at 390 px and 1440 px, including the error path
- a suggested commit message (I never commit)
