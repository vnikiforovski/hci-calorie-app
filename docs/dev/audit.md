# Zalak: audit (Phase 1)

Written 11 Nov 2026, read-only. Nothing in the project was changed except this file.

**What was checked:** `CLAUDE.md`, `docs/01`–`06`, `build-plan.md`, `demo-script.md`, the exam-mapping doc, all of `meals/` and `zalak/`, every template, every file in `static/js/`, `zalak.css` (by script), the tests, and the git history.

**State today**
- `manage.py check`: no issues. `makemigrations --check`: no changes. `manage.py test meals`: **309 tests, all pass** (108 s).
- No secrets in git history (`.env`, the databases and `media/` were never committed; the only `django-insecure` key is the one in `../reference`).
- Every meal view goes through `get_own_meal` / `get_own_draft` / `get_own_logged_meal`, every state change is a POST with `{% csrf_token %}`, and the three `fetch` calls send the token. **No ownership or CSRF hole was found.**
- Findings marked **(confirmed)** were reproduced with Django's test client in a throwaway test file outside the repo.

**Not checked:** `.env` and `.env.example` (reading them is blocked in this session; what is said about `.env.example` comes from its size and its first commit), the Figma file (the Figma connection failed), and real browsers (the HCI section is an expert review of the templates, CSS and JS, not a test with users).

**How to read it:** each finding has an id (H = High, M = Medium, L = Low), the file, why it matters, and the fix. Phase 2 works through H and M.

| | High | Medium | Low |
|---|---|---|---|
| 1 Bugs and edge cases | 2 | 7 | 6 |
| 2 Robustness and security | 2 | 3 | 4 |
| 3 Code quality | 0 | 2 | 7 |
| 5 Tests | 0 | 1 | 0 |
| 6 HCI (new ones; it also re-lists H2, M7, M9, M10) | 0 | 4 | 5 |
| 7 Docs | 1 | 2 | 2 |

In total 5 High (H1–H5), 19 Medium (M1–M19) and 24 Low (L1–L24).

---

## 1. Bugs and edge cases

### High

**H1. A double tap on Log, Just checking, Delete or Undo ends on a 404 (confirmed)**
- File: `meals/views.py` (`log_meal`, `just_checking`, `delete_meal`, `undo_delete_meal`, `undo_log`, `undo_log_again`); `result.html`, `meal_detail.html`, `_toast.html` (the buttons are never disabled).
- Why: the first POST changes the meal, so the second one no longer finds "a draft" / "a not-deleted meal" and raises `Http404`. The browser shows the answer to the *last* request, so the user sees an error page although the action worked. On a phone a double tap is common, and with `DEBUG = True` the page is Django's yellow debug page (see H3).
- Fix: make the views idempotent (an already-logged meal → redirect to Home on its day; an already-deleted one → redirect back) and send each of these forms once (the small "send once" script from `auth.js`). One test per view: the second POST redirects.

**H2. A guest can only type: there is no way to the photo input, and no way to switch input on the input pages (confirmed)**
- File: `templates/meals/welcome.html` ("Try it without an account" → `add_meal` → always `text_input`), `text_input.html`, `photo_input.html`; `views.add_meal`.
- Why: the Add meal sheet with the three ways in exists only for signed-in users. A guest lands on Text and voice, and no page links to `/add/photo/` (which works for a guest if typed by hand). This breaks D1 (three inputs), D14 (the checker works without an account), the build-plan decision "Try it opens Add meal as a guest", and docs/03 "text is always next to the camera". The demo's first step is the guest flow.
- Fix: one link on each input page, carrying `slot`, `day` and `mine`: "Use a photo instead" on Text and voice, "Type it instead" on Photo. That also gives signed-in users the missing fallback. Test: a guest's text page links to the photo page and back.

### Medium

**M1. A "Create your own meal" draft turns into a normal draft after sign-out (confirmed)**
- File: `meals/views.py` (`remember_mine_draft`, `is_mine_draft`, `home`).
- Why: "this draft is for My meals" lives only in `session['mine_drafts']`. Sign out (or a new browser) and the draft shows on Home under **To finish**, and its Result offers **Log** instead of **Save to My meals**.
- Fix: keep it on the meal, not in the session: a `BooleanField` such as `Meal.for_my_meals` (one migration), set where `remember_mine_draft` is called. Test: sign out and in, the draft is still not under To finish.

**M2. The AI answer has no upper limits, and NaN crashes (confirmed)**
- File: `meals/services/ai.py` (`_validate_item`, `_number`).
- Why: `validate()` checks `>= 0` and `min <= max` only. An answer with `grams: 250000`, `amount: 12345678` or 90,000 kcal for one item is saved and shown. `NaN` passes `_number` and then fails in the database (500). CLAUDE.md: "treat a bad response like a failure".
- Fix: in `_number` reject non-finite values; in `_validate_item` raise `AnalysisError` when grams > `MAX_GRAMS` (5,000, already in `units.py`), amount > 1,000, or kcal per 100 g > 900 (pure fat). Tests for each.

**M3. Anything unexpected during an AI call is a 500, not the calm error page (confirmed for a missing photo file)**
- File: `meals/views.py` (`analyze_meal`, `tell_zalak`: `meal.photo.open()`), `meals/services/ai.py` (`_ask_model` catches `APIConnectionError` and `APIError` only).
- Why: a photo missing from `media/` (the demo DB without the `Copy-Item` step, a cleaned folder) raises `FileNotFoundError` on Try again and Tell Zalak. Any other exception from the SDK or from reading the response does the same. FR29 promises "the input is kept, the problem explained".
- Fix: catch `OSError` around the photo read and treat it as a failed analysis with its own words ("The photo is missing. Take another one."); in `_ask_model` add a last `except Exception` that logs and raises `AnalysisError`. Tests for both.

**M4. A hand-edited date crashes Home, the Diary and Statistics (confirmed)**
- File: `meals/views.py` (`parse_day`, `parse_month`, then `week_strip`, `calendar_month`, `diary`, `period_bounds`).
- Why: `?date=0001-01-01` and `?month=1-1` are valid dates, and "a week earlier" overflows (`OverflowError`, 500).
- Fix: `parse_day` and `parse_month` return `None` for anything before a floor (e.g. 1 Jan 2020). Test with both URLs on the three pages.

**M5. A draft without items can be logged (confirmed)**
- File: `meals/views.py` (`log_meal`, `save_my_meal`).
- Why: a draft whose analysis failed has no items and no title. No button offers it, but a POST to `/meal/<id>/log/` logs an empty "0–0 kcal" meal that then sits on Home, in the Diary and in the day counts.
- Fix: both views redirect to `result` (which already routes to the error or No food page) when `meal.items` is empty. One test each.

**M6. "Delete" never really deletes, and drafts pile up**
- File: `meals/views.py` (`delete_meal`, `remove_saved`, `delete_old_guest_drafts`).
- Why: a soft-deleted meal keeps its row, items and photo for ever once the 5 s Undo toast is gone; nothing in the app can reach it again. Signed-in drafts are never cleaned either: a draft the user never opens again stays under To finish on its day. For an app that says "personal, sensitive data" (docs/01) and shows "Delete meal", the photo should go.
- Fix: in the same helper that cleans guest drafts, hard-delete meals with `deleted_at` older than a day (the `post_delete` signal removes the photo). For old signed-in drafts decide: keep them (To finish is the feature) or delete after e.g. 7 days. **Decision for you.** Tests with backdated rows, like `GuestDraftCleanupTests`.

**M7. Meal detail has two save rules on one page, and the slower one loses changes silently**
- File: `templates/meals/meal_detail.html`, `static/js/meal_detail.js`, `views.toggle_favorite`, `log_again`, `save_as_my_meal`.
- Why: slot, time, name and photo wait for **Save changes**; items, the heart, Log again, "Save a copy to My meals" and Tell Zalak each post at once and reload the page. Change the time, then tap an item's pencil or the heart: the new time is gone, with no warning. The build plan notes it for the heart only. It is a bug for the user and a consistency problem (Norman, docs/05: "the same thing works the same everywhere").
- Fix (smallest): while there are unsaved changes, show one line above the buttons ("You have unsaved changes") and ask before leaving the page (`beforeunload`, plus a confirm on the item links). Better, and closer to Figma's toggles: save slot and time the moment they are picked, like Preferences does. **Decision for you**; see HCI idea 2.

### Low

- **L1. Edit item, the only item of a logged meal or a My meal** (`edit_item.html`): the note says "Use Just checking to drop the meal", but those pages have no Just checking (confirmed). Fix: word it by `meal.status` ("Use Delete meal" / "Delete from My meals").
- **L2. Undo "removed item" after Tell Zalak** (`views.undo_remove_item`): the snapshot in the session is put back into a meal whose items were replaced, at a position that may now belong to another item, so Reset shows the wrong estimate. Fix: `tell_zalak` clears `session['removed_item']` for that meal.
- **L3. Save changes accepts any past day** (`MealDetailForm.clean`): the time sheet only changes the time, but a posted `eaten_day` moves the meal to another day. Fix: the form ignores the day and keeps the meal's own, or checks it equals it.
- **L4. `apply_analysis` and `undo_tell_zalak` are not atomic** (`views.py`): they delete the items and create new ones in separate queries; a crash in between leaves a meal with no items. Fix: `transaction.atomic()` around both.
- **L5. Demo photos are shared between meals** (`meals/fixtures/demo.json`: 8 meals use 5 files): hard-deleting one (admin, or deleting Ana's account) removes a file the other still shows. Fix: `build_demo.py` writes one file per meal, or note it in the demo script.
- **L6. A guest's "Don't show these tips again" is lost at sign-up** (`views.tips_seen`): it is in the session, never copied to the Profile. Fix: copy it in `signals.keep_guest_meal`'s neighbour (a second `user_logged_in` receiver).

Checked and fine: ownership on every view (guest by session key, user by `user`), the guest → sign-up flow including "Sign in instead" and a discarded or expired draft, soft delete and Undo for meals and My meals, slot from the time, `eaten_at__date` in `Europe/Skopje`, a future time refused on the server, photo type and size (Pillow verification, 20 MB, re-encoded to JPEG with a random name), and the empty states of Home, Diary, Statistics and Your meals.

---

## 2. Robustness and security for submission

### High

**H3. `DEBUG = True` is hard-coded and there are no error pages**
- File: `zalak/settings.py:43`; `templates/` has no `404.html`, `500.html` or `403_csrf.html`.
- Why: every 404 (a stale link, Back after Just checking, H1) and every 500 (M2–M4) shows Django's technical page with the URL list, settings and stack trace: bad at a demo and the first thing a reviewer checks. Turning DEBUG off today would show bare "Not Found" pages and stop `runserver` serving `static/` and `media/`.
- Fix: `DEBUG = os.environ.get('DJANGO_DEBUG') == '1'` (on in your `.env`, off by default); calm `404.html`, `500.html` and `403_csrf.html` in Zalak's style ("This page isn't here any more" → Home); when DEBUG is off, serve `media/` with `django.views.static.serve` in `urls.py` and run with `runserver --insecure` (written down in the README). No new package. Test: an unknown URL with `DEBUG=False` renders the Zalak 404.

**H4. A fresh clone cannot be started without guessing**
- File: `README.md` (3 lines), `.env.example` (two keys), `zalak/settings.py:40`.
- Why: `SECRET_KEY = os.environ['DJANGO_SECRET_KEY']` dies with a bare `KeyError` when `.env` is missing. The settings read seven variables (`DJANGO_SECRET_KEY`, `ANTHROPIC_API_KEY`, `ZALAK_AI_FAKE`, `ZALAK_AI_FAKE_DELAY`, `ZALAK_DB`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`); the example lists two. The professor cannot run the project from the repository alone, and without `ZALAK_AI_FAKE=1` cannot run it without an API key.
- Fix: a full `.env.example` with a comment per line and `ZALAK_AI_FAKE=1` as the default; a clear `ImproperlyConfigured` message when the key is missing; the README (Phase 3) with the six commands from clone to `runserver`, plus `loaddata demo`.

### Medium

**M8. The text sent to the AI has no length limit, and guests can call the AI without limit (confirmed: 300,000 characters went through)**
- File: `meals/forms.py` (`TextMealForm`, `PhotoMealForm.text`); `meals/models.py` (`Meal.text` is a `TextField`).
- Why: cost and abuse once the app is reachable through the tunnel, and a very long input makes the wait long. Add item (100) and Tell Zalak (300) already have limits.
- Fix: `clean_text` cuts off at 1,000 characters with a calm message, and `maxlength` on the two textareas. Guest rate limiting is not worth building for the course; name it as a known limit in the README.

**M9. The AI call can run for a minute while the overlay says "a few seconds"**
- File: `meals/services/ai.py:282` (`timeout=30, max_retries=1`, `max_tokens=4000`), `templates/meals/_analyzing.html`, `static/js/analyzing.js`.
- Why: a timeout is retried once, so the worst case is about 60 s on a blocked `runserver` thread, against NFR3 (10 s text, 15 s photo). Haiku 5.5 thinks by default and thinking counts towards `max_tokens`, so 4,000 can cut a long meal off (`stop_reason: max_tokens` → the error page). The bar stops at 90 % and nothing else changes.
- Fix: `timeout=20, max_retries=0` (Try again is the retry, and the user sees it), `max_tokens=8000`; after 8 s the overlay's second line becomes "Still working. You can cancel: your meal is kept." (HCI idea 4).

**M10. Privacy: the app never says where the meal goes**
- File: `templates/meals/help_about.html`, `signup_1.html`, `profile_details.html` ("Never shared").
- Why: NFR20 "users are told meals go to an AI service" is not met (confirmed: Help has no such sentence). Photos and text go to Anthropic's API; dictated audio goes to the browser's speech service (Google in Chrome). "Never shared" on Personal details is true for height and weight but reads as a promise for everything.
- Fix: a short "Where your meals go" card in Help and about, one line under the sign-up checkbox, and one line in the Tips sheet or under the mic. Words only.

### Low

- **L7. Photos are public to anyone with the link** (`zalak/urls.py`, `static()`): fine for a course project because the names are random (`uuid4`), but NFR17 says "visible only to its owner". Fix: say so in the README's known limits; an owner-checked photo view is possible later.
- **L8. `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` always include `*.trycloudflare.com`** (`settings.py:47`): move them to `.env`, where the LAN IP already goes.
- **L9. No password reset** (decided in chunk 12: no e-mail sending): a forgotten password locks the user out; only the admin can help. Fix: say it on Sign in ("Forgot it? Ask the person who runs this Zalak") or in the README.
- **L10. `check --deploy` warnings** (HSTS, SSL redirect, secure cookies): not relevant for a local demo; mention in the README instead of setting them.

---

## 3. Code quality

### Medium

**M11. Left-overs from earlier chunks**
- `Profile.food_preferences` (`models.py:42`): unused since FR38 was dropped; the build plan already says "removed in the clean-up (a migration)". Also in `demo.json`.
- `views.add_meal` and its comment "Until the Add meal sheet (chunk 14)": the view is still used (Welcome, the no-JavaScript fallback), the comment is wrong.
- `views.py:1228` "Placeholders until their chunk is built…": sits above the finished Diary.
- `base.html:81–82` "Zalak is being built.": default content no page shows.
- `photo_tips_seen` and `own_profile` comments about "accounts from before chunk 12", and chunk numbers in almost every comment: history, not explanation. Phase 3 can turn them into plain comments.
- Build plan decision "Diary and Statistics show a 'Coming soon' page": stale.

**M12. `views.py` is 1,950 lines and mixes three kinds of code**
- Why: about half of it is not views: date helpers, the week strip and calendar, statistics maths, copy and Undo helpers. It is hard to find a view, and `context_processors.py` has to import from `views` inside a function to avoid a circle.
- Fix: section 4.

### Low

- **L11. Plain scripts share one global scope** (`toast.js`, `add_item.js`, `slot_select.js`, `portion.js`, `chips.js`): `analyzing.js` already records one bug from this (two `showStep`). `portion.js` alone defines `data`, `state`, `step`, `render`, `sheet`. Fix: wrap each file in the same `(function () { … })();` as the others, and use one of `var` / `const` throughout.
- **L12. Duplicated blocks**: the hero (back arrow, "AI estimate" chip, photo or text) is written three times (`result.html`, `meal_detail.html`, `saved_meal.html`); the Home `macros` list repeats `Meal.macro_rows`; "empty title → Zalak's title" is in `save_meal` and `rename_saved`; the image block for the AI is in `analyze_photo` and `correct_meal`; `SLOT_TINTS.get(meal.slot, 'sky')` is set in four views (a `Meal.tint` property would do). Fix: one include, one helper each.
- **L13. `zalak.css` is one 3,411-line file**: in good shape (529 classes, only 6 never used: `.btn-dark`, `.btn-sm`, `.form-select`, `.z-actions-pair`, `.z-heading`, `.z-label`), but about 60 hex colors are written outside `:root`, and 47 selectors are defined twice (most are the phone rule plus the desktop rule, which is fine). Fix: delete the 6, move repeated colors into variables; keep one file (the build plan wants one theme file) with a table of contents at the top.
- **L14. Queries on every page** (`context_processors.add_meal` → `recent_meals`): up to 100 rows plus a prefetch for the Recent list, also on pages that hide the sheet's trigger. `logged_times` reads every title. Fine at this size; note it, or skip the work on pages without the "+" later.
- **L15. `Profile.objects.get_or_create` in four places** (`own_profile`, `signup_details`, `photo_tips_seen`, the signal): use `own_profile` everywhere.
- **L16. `STATIC_VERSION` is bumped by hand** (`settings.py:157`): easy to forget. Leave it, but put it in the README's "when you change CSS or JS".
- **L17. `Meal.__str__` shows the time in UTC** (`models.py:93`): the admin list is an hour or two off. Fix: `timezone.localtime(self.eaten_at)`.

No JavaScript errors were found by reading: every script guards the elements it needs or is loaded only on its own page. The four `console.warn` / `console.debug` lines in `voice.js` and `photo.js` are deliberate (phone debugging) and can stay.

---

## 4. Structure: a proposal

The course style stays: function views, `ModelForm`, admin, signals in `signals.py`, templates with `{% extends %}`. No new packages. Two steps; the second is optional.

**Step A (recommended): move what is not a view out of `views.py`.** Same functions, new homes, imports updated.

```
meals/
  models.py  admin.py  forms.py  signals.py  apps.py  units.py   (as now)
  context_processors.py
  urls.py                 ← new: the meals routes; zalak/urls.py keeps admin, sign-in/out and include()
  views.py                ← only the views and their small request helpers (about 950 lines)
  helpers/
    dates.py              parse_day, parse_month, day_url, day_name, greeting, week_strip, calendar_month, period_bounds
    stats.py              period_stats, macro_shares, most_logged, period_label, period_words
    meals.py              SLOT_OPTIONS, item_fields, apply_analysis, copy_meal, item_snapshot, recent_meals, saved_meals, cleanup
  services/ai.py          (as now)
  fixtures/  migrations/  tests/
```

- `context_processors.py` then imports from `helpers/meals.py` at the top, like any module.
- `meals/urls.py` + `include()` is the standard Django pattern and makes `zalak/urls.py` ten lines. The reference exam keeps everything in the project `urls.py`, so this is one step beyond it: **your call**.

**Step B (optional): split `views.py` into a package by screen**, still plain functions: `views/checker.py` (inputs, result, items, log), `views/home.py`, `views/diary.py` (Diary, Your meals, Saved meal), `views/statistics.py`, `views/profile.py`, `views/accounts.py`, with `views/__init__.py` importing them so `views.home` still works in `urls.py`. Worth it only if Step A still feels too long; the exam pattern has one `views.py`.

**Tests:** `meals/tests.py` (3,008 lines, 46 classes) → a `meals/tests/` package with one file per area (`test_ai.py`, `test_checker.py`, `test_items.py`, `test_accounts.py`, `test_home.py`, `test_diary.py`, `test_statistics.py`, `test_profile.py`, `test_your_meals.py`). `manage.py test meals` finds them unchanged.

**Templates and static:** fine as they are. Two small moves: partials (`_*.html`) into `templates/meals/partials/` if you want the folder to list only pages (40 `include` paths to update, so only with your go-ahead), and `docs/` dev files to `docs/dev/` (Phase 4).

---

## 5. Tests: important behaviour without one

**M13.** 309 tests cover the AI validation, signals, the guest flow, ownership 404s (36 of them), units, Home, Diary, Statistics, Profile, Your meals, drafts, Tell Zalak and the lighter idea. Missing:

| Behaviour | Why it matters | Covered by fix |
|---|---|---|
| A second POST to Log / Just checking / Delete / Undo | the user sees a 404 | H1 |
| A guest can reach the photo input from the UI | the demo's first step | H2 |
| A My-meal draft after sign-out | leaks into To finish | M1 |
| AI numbers that are too big or NaN | saved, or a 500 | M2 |
| Try again / Tell Zalak with the photo file missing | 500 | M3 |
| `?date=0001-01-01`, `?month=1-1` | 500 | M4 |
| Logging a draft with no items | an empty logged meal | M5 |
| A photo over 20 MB, a file that is not an image | the two messages in `clean_uploaded_photo` are never asserted | new |
| A photo with EXIF rotation is turned upright | `shrink_photo`'s main job | new |
| `stop_reason` `max_tokens` and `refusal` | both branches of `_ask_model` | new |
| `rename_saved` (empty name → Zalak's, someone else's meal → 404) | no test names it | new |
| Custom 404 / 500 pages with `DEBUG=False` | H3 | H3 |
| A meal at 23:30 and one at 00:30 land on the right days | the time zone is the classic place for an off-by-one | new |

The JavaScript has no tests and no build step, which fits the project. `portion.js` repeats `units.grams_for` by hand; the pair stays honest only through the comment in both files. Worth one line in the README.

---

## 6. HCI: heuristic evaluation

Method: an expert review (lecture 009) of the built app against Nielsen's 10 heuristics and the project's own rules in docs/05 (Norman's principles, labels, key interactions) and docs/06 (color, type, numbers). Severity uses Nielsen's scale: 0 none, 1 cosmetic, 2 minor, 3 major, 4 catastrophe. It was done by reading the templates, CSS and JS and by requesting pages with the test client, so layout and touch behaviour still need a pass in a real browser at 390 and 1440 px.

### What the app does well (keep, and say so in docs/07)

- **Visibility of system status:** the Analyzing overlay appears on submit with named steps and Cancel; the failed step is shown before the error page; toasts confirm every change; Preferences says "Saving… / Saved".
- **Match with the real world:** "eaten", bowls and slices before grams, "What Zalak saw", sure / likely / unsure with icon, word and a three-dot meter.
- **User control:** Undo after Log, Delete, Remove item, Tell Zalak, Log again and Remove from Your meals; Reset on Edit item; Just checking; Cancel during Analyzing keeps the draft.
- **Error messages:** calm, in ink, never red, each with what to do next; a wrong password keeps the e-mail; a failed Add item or Tell Zalak brings the words back.
- **Calm tone:** no red or green for food or days, no streaks, "Days logged 5 of 7" without judgement, averages only over days that were logged.
- **Accessibility:** icon plus word everywhere, `aria-current`, `role="status"` and `role="alert"`, hidden text for chart bars, reduced-motion rules, a no-JavaScript path for sheets and preferences.

### Where it falls short

| Id | Heuristic | Problem | Where | Sev. |
|---|---|---|---|---|
| H2 | 7 Flexibility; 3 User control | A guest cannot choose Photo, and nobody can switch between Photo and Text without going back to Home (section 1). Docs/03: "text is always next to the camera". | Welcome, both input pages | 3 |
| M7 | 4 Consistency; 5 Error prevention | Meal detail: four fields wait for Save changes, everything else saves at once and reloads, so unsaved edits vanish (section 1). | Meal detail | 3 |
| M14 | 7 Flexibility and efficiency | A portion can only be stepped: grams move by 10, so 150 g → 200 g is five taps. NFR7 says ≤ 2 taps, and it is Marko's scenario and usability task 2. No way to type a number. | Edit item (`portion.js`) | 3 |
| M15 | 3 User control; accessibility | Undo lives in a toast for 5 s. The toast is the last element of the page, so a keyboard or screen-reader user must tab through everything to reach it in time, and a touch user cannot pause it (hover only). After that, a deleted meal cannot be brought back. WCAG 2.2.1 (timing adjustable). | `_toast.html`, `toast.js` | 3 |
| M9 | 1 Visibility of system status | The overlay promises "a few seconds" and then shows nothing new for up to a minute (section 2). | Analyzing | 2 |
| M10 | 10 Help; honesty (D4, NFR20) | Nowhere says that meals and photos go to an AI service (section 2). | Help, sign-up | 2 |
| M16 | 10 Help and documentation | "kcal" and "macros" are never explained (NFR24, Goran's scenario "kcal is explained the first time"). Help explains the confidence words only. | Help and about, Result | 2 |
| M17 | 4 Consistency (calm tone) | The model is told never to call food "good", and the lighter idea drops names with "good", yet the fake answer and the demo data say "good protein", "good fats", "a balanced plate". FR15's own example in docs/02 says "good protein". The docs contradict themselves; the app follows both. | `ai.py` (`FAKE_RESPONSE`), `build_demo.py`, docs/02 FR15, NFR23 | 2 |
| L18 | 6 Recognition over recall | Guests have no trace of a checked meal: leave Result and the draft is unreachable (no To finish without Home). | Result for guests | 2 |
| L19 | 4 Consistency | Labels drift: "Add a meal" (sidebar, "+"), "Add to lunch" (sheet), "Add meal" (docs); "Describe it instead" / "Edit the text" / "Describe it again" for the same link; "See all" beside Recent opens the Diary, not a list of recent meals. | `base.html`, error pages, `_add_meal_sheet.html` | 1 |
| L20 | 8 Minimalist design | Meal detail on a phone carries up to nine actions (heart, three photo buttons, slot, time, rename, items, Tell Zalak, Save a copy, Log again, Save, Delete). Docs/06 asks for progressive disclosure (the Edit item lesson). | Meal detail | 2 |
| L21 | Accessibility (NFR13) | The week strip's day pills (~35 px) and the "Your meals" book tab (36 px) are under 44 px. Both are noted in the build plan as known exceptions. | Home, Diary | 1 |
| L22 | 2 Match with the real world | Voice listens in `en-US` only; local dish names are misheard (docs/01 says so). The page does not say which language to speak. | `voice.js` | 1 |

### Where the app differs from its own design docs

These are not bugs; the docs describe an earlier plan. They matter because the docs are graded next to the app (section 7 lists the edits).

- **Not built:** water (FR40), goals and targets (FR4), "my share" ½ ⅓ ¼ (FR11; only a "Shared dish" chip), food preferences (FR38), renaming slots (FR8, the Should part), Customize statistics (FR41), dark mode, sound and vibration, PWA install, swiping between days, name suggestions on Edit item, "How it was cooked".
- **Built differently:** sign-up has 2 steps, not 5; the uncertainty preference is in Profile, not in sign-up; a guest lands on Welcome, not on the checker; Edit item is a page, not a bottom sheet; the clarifying question is three chips on the item, not a card with "Skip"; "Save as my meal" is on Meal detail, not in a menu on Result; dashboards do not open Statistics; sheets close with × or a tap outside, not a swipe; the error words are "Connection lost" and "Couldn't analyze this", not "You're offline"; Log is never disabled (it does not need to be: Result only exists once the answer is there).

### Up to five improvements

| # | Idea | Solves | Effort |
|---|---|---|---|
| 1 | **Switch input in place.** "Use a photo instead" / "Type it instead" on the two input pages, and the guest's "Try it" opens a small chooser (Photo / Text and voice). | H2 | S |
| 2 | **One save rule on Meal detail.** Slot and time save the moment they are picked (a small POST, a "Saved" line, like Preferences); the name saves from its own field; the photo keeps its explicit button. "Save changes" goes away, and the bar is Log again + Delete. | M7, L20 | M |
| 3 | **Type the amount.** Tapping the big number on Edit item turns it into a number field (decimal keyboard), with the stepper still beside it; the live kcal preview follows. 150 g → 200 g is tap, type, Save. | M14 (NFR7) | S–M |
| 4 | **An Undo that waits.** The toast stays until it is closed or the next action (a × button, focus moved to it for keyboard users), and Analyzing says "Still working…" after 8 s. Optional second step: a "Recently deleted" list in the Diary for a day. | M15, M9 | S (toast), M (list) |
| 5 | **"How to read this" in one place.** A small "?" on Result's total opens a sheet: why a range, what kcal and macros are, what the three confidence words mean, and that the meal is sent to an AI service to be estimated. The same text in Help and about. | M16, M10 | S |

---

## 7. Docs

### High

**H5. `docs/07-evaluation.md` is empty.**
- Why: lecture 009 (evaluation) is the last step of the process the other six docs follow, and docs/02 and 03 promise it ("the personas and requirements will be checked in usability testing", six test tasks, NFR5–NFR10 with numbers such as SUS ≥ 75). Docs/06 has one sentence: "friends tried the prototype… no changes were needed".
- What it should hold (short):
  1. **Heuristic evaluation**: section 6 of this audit, cut down to the table and the fixes made.
  2. **Usability test**: 3–5 people, the six tasks from docs/03 §7, per task: done / done with help / not done, time, what they said. Then SUS. **This needs real people before 15 November; I cannot produce it.** A template with the tasks and the SUS sheet can be ready in Phase 4.
  3. **Requirements check**: FR1–FR41 and NFR1–NFR24 as built / partly / not built, one line each.
  4. **Accessibility**: the axe-core result from chunk 19 (32 pages, no violations) and the known exceptions.
  5. **Professor's feedback** from the demo (chunk 21 is still unticked: what was it?) and what changed.
  6. **Limits and next steps.**

### Medium

**M18. Docs 01–06 describe the plan, not the app.** Per file:
- **01**: scope names "healthier option", water, goals, BMI, Macedonian language without saying what was built; "sound optional", "vibration"; "shared dishes need a my share option" (not built).
- **02**: FR36 (4–5 steps), FR37 ("set at sign-up"), FR38, FR11, FR4, FR40, FR41, FR8's Should part: mark each built / changed / not built. FR15's example contradicts NFR23 (M17). The method line still says the testing is to come.
- **03**: T4 "adjust the portion", T5, Lea's "my share: ¼" and Goran's "kcal is explained" describe features that are not there; test task 5 asks for "a quarter of the dish".
- **05**: sitemap (Checker as guest landing, 5-step sign-up, Custom meal form, Goals, Water settings), PWA, dashboards opening Statistics, swipe, Edit item as a sheet, the question card with Skip, "Save as my meal in a small menu", the three error texts, haptic and sound. The labels list is right; "Add meal" needs one spelling (L19).
- **06**: still called "v1"; dark mode; the Round 3 list mixes Figma-only screens (Goals and targets, water glasses, Customize) with built ones; the prompt appendix (80 lines) belongs in `docs/dev/`.
- **04** (competitors): not checked line by line; its "Idea parking lot (decisions)" should say which ideas were built.

**M19. The README does not describe the project** (H4): what Zalak is, how to run it, `.env`, the fake AI, the demo data, the structure, known limits. Phase 3.

### Low

- **L23. `build-plan.md`** is the best record of what was built and why, but its "Decisions" and data-model block are from 25 Oct (no `mine` status, no `hide_lighter_idea`, `lighter_idea: null`, "Coming soon" pages). It also has an uncommitted two-line change. Move to `docs/dev/` with `audit.md`, `demo-script.md` and the exam-mapping doc (Phase 4); fix the model block or point it at `models.py`.
- **L24. `docs/competitor screenshots/`** is 36 MB of the repository's 51 MB. Keep (docs/04 and 06 point at it), but the folder name has a space and docs/06 says the *AI tool* screenshots are there too: check that sentence.

---

## Phase 2 status (11 Nov)

Decisions taken: DEBUG from `.env`, off by default; deleted meals go after a day and unfinished drafts after a week; Meal detail gets a warning (the redesign is Phase 5); "good protein" is allowed in the neutral description (NFR23 gets the exception in Phase 4); `Meal.for_my_meals` added; `meals/urls.py` with `include()` in Phase 3, the helpers only if there is time; all five HCI ideas in Phase 5; no evaluation doc (`07-evaluation.md` deleted).

| Finding | Status |
|---|---|
| H1 double tap | Fixed: the views cope with a second POST, and `send_once.js` stops a second send |
| H2 guest photo | Fixed: "Use a photo instead" / "Type it instead" on both input pages |
| H3 DEBUG, error pages | Fixed: `DJANGO_DEBUG`, `404.html`, `500.html`, `403_csrf.html`, photos served with DEBUG off |
| H4 fresh clone | Partly: a clear message when `DJANGO_SECRET_KEY` is missing. `.env.example` and the README follow in Phase 3 |
| H5 evaluation doc | Dropped by decision; file deleted |
| M1 My-meal draft | Fixed (migration `0005`) |
| M2 AI limits, NaN | Fixed |
| M3 crashes in the AI call, missing photo | Fixed: any SDK error is a calm failure; a missing photo has its own page |
| M4 odd dates | Fixed: nothing before 1 Jan 2020 |
| M5 logging an empty draft | Fixed (also Save to My meals) |
| M6 clean-up | Fixed |
| M7 Meal detail | Fixed with the warning |
| M8 text length | Fixed: 1,000 characters |
| M9 slow AI | Partly: one try of 20 s, `max_tokens` 8,000. The "Still working" line is HCI idea 4 (Phase 5) |
| M10 privacy words | Fixed: Help, sign-up, Personal details |
| M11, M12 left-overs, structure | Phase 3 |
| M13 missing tests | Added (43 tests: 309 → 352) |
| M14–M16 HCI | Phase 5 (ideas 3, 4, 5) |
| M17 "good" | Allowed; docs in Phase 4 |
| M18, M19 docs, README | Phases 3 and 4 |

## Phase 3 status (12 Nov)

| Finding | Status |
|---|---|
| H4 fresh clone | Fixed in the README (every `.env` variable). `.env.example` itself is left to Viktor: the file is blocked for the assistant |
| M11 left-overs | Fixed: `Profile.food_preferences` removed (migration `0006`, demo data too), old chunk comments, the "being built" text |
| M12 structure | `meals/urls.py` with `include()`. `views.py` stays one file for now (decided); the helpers move only if there is time |
| M19 README | Written |
| L1, L2, L3, L4, L11, L12 (tint, Zalak's title), L13 (unused CSS), L15, L17 | Fixed |
| Also removed | "Save a copy to My meals" (asked for on 12 Nov) |

## Phase 4 status (12 Nov)

- `docs/01`–`06` describe the built app: built / changed / not built per requirement in `02`, the real sitemap, navigation, interactions and error texts in `05`, a "From prototype to app" section in `06`. NFR23 allows describing what a meal contains ("good protein").
- Moved to `docs/dev/`: `build-plan.md`, `audit.md`, `demo-script.md`, `django-exam-pattern.md`, and the AI design prompts from `06` (`ai-design-prompts.md`).

## Phase 5 status (12 Nov): the five HCI ideas

| Idea | Solves | What was built |
|---|---|---|
| 1 Switch input in place | H2 | The input pages link to each other (Phase 2); "Try it without an account" now opens a Photo / Text and voice chooser |
| 2 One save rule on Meal detail | M7, L20 | Slot, time, name and photo save the moment they change (fetch and "Saved"; a normal post without JavaScript). "Save changes" and the unsaved-changes warning are gone; the bar is Log again + Delete meal; removing a photo asks first |
| 3 Type the amount | M14 (NFR7) | Tap the big number on Edit item to type it; the preview follows; Enter or leaving the field goes back, Escape undoes |
| 4 An Undo that waits | M15, M9 | A toast with Undo stays until × or Escape and comes first for the Tab key; a plain confirmation still goes after 2.5 s. Analyzing says "Still working…" after 8 s. The optional "Recently deleted" list was not built |
| 5 How to read this | M16 (NFR24), M10 | "How to read this estimate" at the bottom of the summary card on Result, Meal detail and Saved meal opens a sheet (why a range, kcal, macros, the confidence words, where the estimate comes from); the same words in Help and about |

## Decisions I needed from you before Phase 2 (answered above)

1. **H3:** DEBUG from `.env` (off by default) with `runserver --insecure` for the submission, or keep `DEBUG = True` and only add the error pages?
2. **M6:** really delete soft-deleted meals after a day? And old signed-in drafts: keep, or delete after 7 days?
3. **M7:** the small fix (a warning) in Phase 2, or the full "save at once" change as HCI idea 2 in Phase 5?
4. **M17:** is "good protein" allowed in the neutral description (then docs NFR23 gets an exception), or should the fake answer, the demo data and FR15's example lose the word?
5. **M1:** a new field on `Meal` (one migration) is the clean fix. OK?
6. **Section 4:** Step A only, or A and B? `meals/urls.py` with `include()`, yes or no?
7. **Section 6:** which of the five HCI ideas go into Phase 5?
8. **H5:** can you run the six tasks with 3–5 people this week? And what was the professor's feedback at the demo?

## Suggested commit message

```
Add the Phase 1 audit (docs/audit.md)
```
