# Zalak: instructions for Claude Code

Zalak ("a bite" in Macedonian) is an AI meal calorie checker: the user photographs, types or dictates a meal, the AI estimates calories and macros as ranges, the user corrects anything wrong and logs it. It is the project for the HCI course ДИЧК (Design of Human-Computer Interaction) at FINKI, Skopje. It is graded mostly on the working app and its interaction design, not on nutritional accuracy.

**Target: finish by Sunday 1 November 2026 and demo to the professor on 4 or 5 November.** The hard deadline is 15 November; the days after the demo are a buffer for the professor's feedback and leftover Should features. Scope to what can be built and tested well by the target.

## How I want to work (most important)

I am a student learning Django through this project. I approve every plan and review every chunk.

- **One chunk at a time**, from `docs/dev/build-plan.md`. Never start the next chunk on your own.
- **Plan first.** Before editing, list the files you will touch and what changes in each. Wait for my approval.
- **Whole chunk at once, after the plan is approved.** Implement all files of the chunk in one go, in Django order (models → admin → forms → views → urls → templates → static).
- **Check your own work before handing over.** Run `python manage.py check`, `makemigrations --check` when models changed, and `python manage.py test meals`; request the chunk's pages with Django's test client; fix anything that fails. Add or update small tests for the chunk's logic (ownership 404s, signals, scaling maths).
- **Then explain the chunk**: per file, 2-4 sentences on what it does, why, and which course pattern it uses (point to the matching file in `docs/reference` when there is one). End with browser test steps at 390 and 1440 px and a suggested commit message.
- **Course-minimum Django style.** Function-based views, `ModelForm`, admin customizations (`list_display`, `has_*_permission`, `save_model`, `get_queryset`), signals in `signals.py` imported in `apps.py ready()`, Django templates with `{% extends %}` and Bootstrap. Go beyond this only when the feature needs it, and tell me why first. No class-based views, DRF, React, HTMX or other frameworks unless I agree.
- **JavaScript only where the interaction needs it** (voice input, live total updates while editing portions, bottom sheets). Plain JS, no build step.
- **No new packages without asking.** Say what it is for and whether a built-in option exists.
- **Don't commit or push.** At the end of a chunk, tell me how to test it in the browser and suggest a commit message. I commit myself.
- **Don't edit `docs/`** except `docs/dev/build-plan.md`, unless I ask.
- If something in the docs is unclear or contradicts itself, ask me instead of guessing.

## Where things are

- `docs/01-problem-analysis.md`: principles, PACT, design implications **D1-D15**, scope (what is out)
- `docs/02-user-research-and-requirements.md`: personas, functional requirements **FR1-FR41** with MoSCoW priority, NFRs
- `docs/03-task-analysis.md`: tasks T1-T7, scenarios, mental models
- `docs/04-competitors.md`: what we adopt and avoid from 20 apps
- `docs/05-structure-and-interaction.md`: content objects, sitemap, navigation, user flows, labels, key interactions, error messages
- `docs/06-visual-design-and-prototype.md`: colors, fonts, numbers, spacing, components, prototype screens
- `docs/figma-prototype.pdf`: export of the final Figma screens
- Figma file (use the Figma tools to inspect frames): https://www.figma.com/design/TAkknAZ98WZRCS6eSG2ULW/Zalak-Prototype
- `docs/dev/django-exam-pattern.md`: the course's Django exam pattern and how it maps to Zalak
- `docs/reference`: an official course exam solution. This is the style and minimum level to follow.
- `docs/dev/build-plan.md`: the agreed build plan, chunk by chunk (created in the first session)
- `docs/dev/audit.md`: the audit of 11 Nov 2026 and what was fixed; `docs/dev/demo-script.md`: the demo walkthrough

Read the relevant doc before building a screen. The research docs win over the model sketch in the exam-mapping doc where they differ (e.g. ranges, the confidence words sure/likely/unsure, the statuses draft/logged).

## Product rules that affect the code

- **Calories are ranges** (`650–850 kcal`), stored as min and max. Calories rounded to 10, grams to 5. Always "eaten", never "left" or "remaining".
- **The AI proposes, the user decides.** Nothing is saved until the user taps Log (FR23). "Just checking" discards.
- **Confidence per food item**: sure / likely / unsure, with a short reason when unsure. Always an icon plus a word, never color alone.
- **Correction is first-class**: rename, replace, change portion, add, remove an item; totals update instantly (FR18-FR22).
- **Calm tone**: no good/bad food, no red/green for food or days, no streaks, no scores. Red only for delete or sign-out actions.
- **Graceful failure**: if the AI call fails, keep the input, explain, offer Retry or "Type it instead" (FR29, FR30).
- **Guest checker**: the checker works without an account; Log asks a guest to sign up and then logs the kept meal (FR2, D14).
- **Meal slot** (breakfast, lunch, snack, dinner) is suggested from the time of day and can be changed (FR8). A slot can hold several meals.
- **Labels are fixed**: Home, Diary, Statistics, Your meals, Just checking, Log, To finish, Tips. Use exactly these words.
- "Estimate, not medical advice" is shown on Result and in Profile. No allergen claims.

## Priorities

1. **Core checker flow** (Must): text input, voice input (FR7), photo + note input, Analyzing state, Result with items and ranges, Edit item, Log / Just checking, errors.
2. **Accounts and Home** (Must): sign up, sign in, Home with week strip, dashboards and meal slots; edit/delete a logged meal.
3. **Should**: Diary, Your meals (favorites, custom meals), drafts, uncertainty preference, profile preferences.
4. **Could**: water, statistics, lighter-idea card, dark mode, book-style diary.

Build the core flow well before widening.

## Tech

- Python + Django, one project, SQLite. Windows 11, PyCharm, virtual environment in `.venv`.
- Bootstrap 5 + Bootstrap Icons served from `static/`. The Sage & caramel theme lives in one CSS file that overrides Bootstrap's CSS variables (colors and fonts from `docs/06`). Fonts: Fraunces (headings, big numbers) and Figtree (everything else).
- Mobile-first responsive web app: designed at 390 × 844 and 1440 wide.
- AI: the Anthropic Python SDK, called only from one module (e.g. `services/ai.py`), never from templates or JS. The browser never talks to the API.
- Secrets: `ANTHROPIC_API_KEY` in `.env` (already gitignored), never in code or settings. Uploaded photos go to `media/`, which must be gitignored too.
- The AI must return structured JSON (items with name, portion, unit, grams, kcal_min, kcal_max, macros, confidence, reason). Validate it before saving; treat a bad response like a failure.

## Commands

- `python manage.py runserver`: run the app at http://127.0.0.1:8000
- `python manage.py makemigrations` then `python manage.py migrate` after model changes
- `python manage.py createsuperuser` for the admin
- `python manage.py check` before telling me a chunk is done
