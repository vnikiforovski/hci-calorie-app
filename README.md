# Zalak

Zalak (залак, Macedonian for "a bite") is an AI meal calorie checker. You photograph, type or say what you ate; Zalak estimates the calories and macros **as ranges** (650–850 kcal), says how sure it is about each food (sure, likely, unsure), and you correct anything wrong before you log it. Nothing is saved until you tap **Log**, and **Just checking** throws the estimate away.

A project for the course Design of Human-Computer Interaction (ДИЧК) at FINKI, Skopje, 2026. The design work is in [`docs/`](docs/); the Figma prototype is [here](https://www.figma.com/design/TAkknAZ98WZRCS6eSG2ULW/Zalak-Prototype).

**What it does**
- **Three ways in:** a photo with an optional note, typed text, or voice (Chrome). A guest can try it without an account.
- **Honest estimates:** ranges, a confidence word and icon per food, a short reason and one quick question when Zalak is unsure.
- **Correction:** rename an item, change its amount and unit (live totals), add or remove items, or tell Zalak what was wrong in your own words. Undo after every change.
- **A calm diary:** Home with the week and four meal slots, a Diary that reads like a book, Statistics for a week or a month, favorites and your own meals. No targets, no red or green, no streaks.

## Run it

Needs Python 3.12 (Windows commands shown; on macOS or Linux use `source .venv/bin/activate`).

```powershell
git clone <this repository>
cd hci-calorie-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# make the .env file (next section), then:
python manage.py migrate
python manage.py runserver
```

Open **http://127.0.0.1:8000**. To get an admin account: `python manage.py createsuperuser`, then http://127.0.0.1:8000/admin/.

### The `.env` file

Settings and secrets live in a file called `.env` in the project folder (it is gitignored). A working one for a first run:

```ini
DJANGO_SECRET_KEY=change-me-to-a-long-random-string
DJANGO_DEBUG=1
ZALAK_AI_FAKE=1
```

| Variable | What it does |
|---|---|
| `DJANGO_SECRET_KEY` | **Required.** Any long random text: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `1` while developing. Without it Zalak shows its own error pages, and `runserver` needs `--insecure` to serve the CSS and JavaScript. |
| `ZALAK_AI_FAKE` | `1`: every meal gets the same fixed answer (tavče gravče with bread and salad). No API key, no cost, works offline. |
| `ZALAK_AI_FAKE_DELAY` | Seconds the fake AI waits, to see the Analyzing screen (default `0`). |
| `ANTHROPIC_API_KEY` | The real AI (Claude Haiku 5.5). Needed when `ZALAK_AI_FAKE` is not `1`. |
| `ZALAK_DB` | Another database file, e.g. `demo.sqlite3` for the demo. Default `db.sqlite3`. |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | Extra hosts, comma-separated: your laptop's IP to open Zalak from a phone on the same Wi-Fi, or an https tunnel. |

### Demo data

A demo account with a week of meals (Ana, `ana@zalak.demo` / `zalak-demo-2026`):

```powershell
python manage.py loaddata demo
New-Item -ItemType Directory -Force media\meals\demo | Out-Null
Copy-Item meals\fixtures\demo_photos\* media\meals\demo\
```

The 5-minute demo walkthrough is in [`docs/dev/demo-script.md`](docs/dev/demo-script.md).

### Running it like the submission (DEBUG off)

Leave `DJANGO_DEBUG` out of `.env`, then:

```powershell
python manage.py runserver --insecure
```

`--insecure` lets the development server serve `static/` with DEBUG off. Photos in `media/` are served by Zalak itself.

### Opening it from a phone

`python manage.py runserver 0.0.0.0:8000` listens on every network card. `0.0.0.0` is not an address you can open: on the phone use `http://<your laptop's IP>:8000` and put that IP in `DJANGO_ALLOWED_HOSTS`. The live camera and voice need https (or localhost), so on a phone over plain http Zalak falls back to the phone's own camera and hides the microphone.

### Tests and checks

```powershell
python manage.py check
python manage.py makemigrations --check
python manage.py test meals
```

The tests never call the real AI (it is patched) and keep uploaded photos in a temporary folder.

## How it is built

One Django project with one app, in the course's style: function views, `ModelForm`s, admin customisations, signals, and templates with `{% extends %}` and Bootstrap 5. Plain JavaScript only where an interaction needs it; no build step. SQLite.

```
zalak/                 project settings and the top-level URLs (admin, sign in/out, photos)
meals/
  models.py            Profile, Meal (draft / logged / my meal), MealItem (numbers per 100 g)
  views.py             every page (function views)
  urls.py              the app's URLs, included by zalak/urls.py
  forms.py             ModelForms for the inputs, items, meal detail and accounts; photo checks
  admin.py             list_display, an item inline, get_queryset, has_*_permission, save_model
  signals.py           slot from the time, the logged-meals counter, photo cleanup, Profile on
                       sign-up, the guest's meal logged after sign-up
  units.py             units, grams per unit, rounding (portion.js does the same maths)
  context_processors.py  the Add meal sheet and the one-time toast on every page
  services/ai.py       the only code that talks to the AI: prompts, JSON schema, validation, fake mode
  fixtures/            the demo data and how it was built
  tests.py             the tests
templates/             base.html, the error pages, meals/ (pages and _partials), registration/
static/                css/zalak.css (the Sage & caramel theme over Bootstrap), js/, fonts, Bootstrap
docs/                  the HCI design documents 01–06 and the Figma export
  dev/                 the build plan, the audit, the demo script, the Django exam notes
reference/             the course's official exam solution (the style followed)
```

**How a meal moves:** the input page saves a **draft** first (so nothing is lost if the AI fails), `services/ai.py` asks Claude for structured JSON and validates it, and the draft's items are saved per 100 g with `grams` as the one source, so changing a portion rescales everything. **Log** turns the draft into a **logged** meal; **Just checking** deletes it. A guest's draft belongs to their session and is logged once they sign up.

## Known limits

- The AI estimates; it is not medical advice, and Zalak makes no allergen claims.
- Voice uses the browser's speech recognition (Chrome, Edge, Safari; not Firefox) in English, so local dish names are often misheard. The text can always be edited.
- Photos are reachable by anyone who has their (random) address.
- There is no password reset (Zalak sends no e-mail); the admin can set a new password.
- No limit on how often a guest can call the AI.
- Built and tested with the development server, not for a public deployment.
