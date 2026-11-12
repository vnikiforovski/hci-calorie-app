# Zalak: 5-minute demo script

Two people in the story:

- **Viktor**, a guest who checks a meal before he has an account, and signs up live.
- **Ana**, the demo account with nine days of meals (`meals/fixtures/demo.json`): `ana@zalak.demo`, password `zalak-demo-2026`.

## Setup (the day before, and again right before the demo)

1. **Move Ana's week next to the demo day.** Her meals have fixed dates. In `meals/fixtures/build_demo.py` set `FIRST_DAY` to the **Monday of the week before the demo** (demo on Thu 19 Nov → `date(2026, 11, 9)`), then rebuild the fixture (needs the original photos in `demo_photos_src/`):

   ```powershell
   python manage.py shell -c "exec(open('meals/fixtures/build_demo.py', encoding='utf-8').read())"
   ```

   Her nine days then end on the Tuesday of the demo week: Home, the Diary and Statistics show a full last week and a started one.
2. **`.env`:** `ZALAK_DB=demo.sqlite3`, `ZALAK_AI_FAKE=0` and your `ANTHROPIC_API_KEY`. Leave `DJANGO_DEBUG` out, so the app runs as submitted. Your own `db.sqlite3` is not touched.
3. **A fresh demo database** (PowerShell, in the project folder, with `.venv` active):

   ```powershell
   Remove-Item demo.sqlite3 -ErrorAction SilentlyContinue
   python manage.py migrate
   python manage.py loaddata demo
   New-Item -ItemType Directory -Force media\meals\demo | Out-Null
   Copy-Item meals\fixtures\demo_photos\* media\meals\demo\
   python manage.py runserver --insecure
   ```

   Run it again right before the demo: it frees Viktor's e-mail and removes meals logged in rehearsal.
4. **A photo for step 5** on the desktop, e.g. a copy of `meals\fixtures\demo_photos\pasta.jpg`.
5. **Chrome, two windows** at http://127.0.0.1:8000:
   - **Incognito** for Viktor (the guest): DevTools → device toolbar → 390 × 844.
   - **A normal window** for Ana, signed out: full width (1440) for Home, Diary and Statistics, the device toolbar (390) for the checker.
   - Voice needs Chrome and the microphone allowed for `127.0.0.1`.
6. **Backup if the internet fails:** `ZALAK_AI_FAKE=1` in `.env`, restart `runserver`. Every meal then gets the same tavče gravče answer; skip step 11.

## The 5 minutes

1. **0:00 · Incognito, 390 · Welcome → "Try it without an account" → Text and voice.**
   Say: "Zalak works without an account, for checking a meal before you order. Photo or text, your choice."
2. **0:15 · Tap the mic, say "tavče gravče with bread and a shopska salad" → Analyze.**
   Point at the cookie losing bites. Say: "Voice for when one hand is busy, and you always see that it's working."
3. **0:30 · Result:** the total range, Sure / Likely / Unsure, the oil's reason. Tap **How to read this estimate**, then Got it.
   Say: "Calories are a range, and Zalak says how sure it is. Every number is explained."
4. **0:50 · Under the oil: A lot** → the total changes. Then **Log to lunch → Keep this meal? → Create a free account** → name **Viktor**, `viktor@zalak.demo`, a password, the box → Continue → **Skip for now**.
   Say: "When it's unsure it asks one quick question. Nothing is saved until you tap Log, and the meal you checked as a guest is kept."
5. **1:30 · Normal window, 390 · Sign in as Ana → + → Photo → drop the photo → note "cooked in butter" → Analyze.**
   Say: "A photo and a note are analysed together."
6. **1:55 · Tap an item's pencil → Edit item:** tap the big number, type **200**, Enter: the kcal follows → **Save changes**.
   Say: "Every item can be corrected: rename, portion, unit, remove, add, or just tell Zalak what was wrong."
7. **2:15 · Log to lunch** → the toast "Logged to lunch · Undo" stays.
   Say: "Undo waits until you're done with it."
8. **2:30 · 1440 · Home:** the week strip, Eaten, the macro cards, the four slots, the week's chart. ‹ to last week.
   Say: "Always 'eaten', never 'left'. No targets, no red or green, no streaks."
9. **2:50 · Diary:** the open book, ‹ back a few days, the calendar, then the **Your meals** tab. Open a meal → **Meal detail**: change the time → Done → "Saved".
   Say: "The diary is a book. Logged meals stay editable, and every change saves at once."
10. **3:30 · Statistics:** last week (days logged, the average range, macros, Most logged) → **Month**.
    Say: "Patterns, not judgement."
11. **3:55 · 390 · + → Text → "my shoe" → Analyze** → the overlay marks *No food found*, then the page explains.
    Say: "Calm errors, always with a way forward. If the internet drops, the text is kept as a draft."
12. **4:20 · Profile → Preferences → Best guess** (saves at once) → **Help and about** → "Where your meals go".
    Say: "Some people don't want questions. And Zalak is open about what it sends to the AI."
13. **4:45 · Point at "Estimate, not medical advice".**
    Say: "Zalak estimates. It doesn't judge, and it isn't medical advice."

## If something goes wrong

- **The AI is slow or fails:** use **Try again**. If the internet is down, switch to the fake AI (Setup 6).
- **"There is already an account with this e-mail"** for Viktor: the database wasn't reloaded. Use another e-mail, e.g. `viktor2@zalak.demo`.
- **Ana's photos are missing:** the `Copy-Item` step was skipped.
- **The page has no styling:** `runserver` was started without `--insecure` while DEBUG is off.

## Back to your own database after the demo

1. Stop `runserver` (Ctrl+C).
2. In `.env`, remove `ZALAK_DB=demo.sqlite3` (or set it to `db.sqlite3`), and set `ZALAK_AI_FAKE` and `DJANGO_DEBUG` back to what you use for development.
3. If you ever set a variable in the terminal (`$env:ZALAK_DB = ...`), clear it there too: `Remove-Item Env:ZALAK_DB`. A terminal value wins over `.env`.
