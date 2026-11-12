# Zalak: 5-minute demo script

For the demo to the professor on 4 or 5 November 2026. Two people in the story:

- **Viktor**, a guest who checks a meal before he has an account, and signs up live.
- **Ana**, the demo account, with a week of meals from Mon 26 Oct to Tue 3 Nov
  (`meals/fixtures/demo.json`): `ana@zalak.demo`, password `zalak-demo-2026`.

## Setup (the day before, and again right before the demo)

1. In `.env`: `ZALAK_DB=demo.sqlite3`, `ZALAK_AI_FAKE=0` and the `ANTHROPIC_API_KEY`.
   Your normal `db.sqlite3` is not touched.
2. A fresh demo database (PowerShell, in the project folder, with `.venv` active):

   ```powershell
   Remove-Item demo.sqlite3 -ErrorAction SilentlyContinue
   python manage.py migrate
   python manage.py loaddata demo
   New-Item -ItemType Directory -Force media\meals\demo | Out-Null
   Copy-Item meals\fixtures\demo_photos\* media\meals\demo\
   python manage.py runserver
   ```

   Run it again before the demo: it frees Viktor's e-mail and removes the meals logged in rehearsal.
3. Put one meal photo on the desktop for step 3, e.g. a copy of `meals\fixtures\demo_photos\pasta.jpg`.
4. Chrome, two windows:
   - **Incognito** for Viktor (the guest). DevTools → device toolbar → 390 × 844.
   - **A normal window** for Ana, signed out. Full width (1440) for Home, Diary and Statistics, and
     the device toolbar (390) for the checker steps.
   - Voice input needs Chrome and the microphone allowed for `127.0.0.1`.
5. **Backup if the room's internet fails:** set `ZALAK_AI_FAKE=1` in `.env` and restart
   `runserver`. Every meal then gives the same tavče gravče answer, and step 7's errors can't be shown.

## The 5 minutes

| Time | Where | Do | Say |
|---|---|---|---|
| 0:00 | Incognito, 390 | Welcome → **Try it without an account** → Text and voice | "Zalak works without an account, for checking a meal before you order." |
| 0:15 | | Tap the mic and say *"tavče gravče with bread and a shopska salad"* → **Analyze** | "Voice, for when one hand is busy." |
| 0:30 | Result | Point at the total range, Sure / Likely / Unsure, and the oil's reason | "Calories are a range, and Zalak says how sure it is, with a reason." |
| 0:45 | | Under the oil: **A lot** → the total changes | "When it's unsure, it asks one quick question instead of guessing." |
| 1:00 | | **Log to lunch** → *Keep this meal?* → **Create a free account** | "Nothing is saved until you tap Log." |
| 1:10 | Sign-up | Name **Viktor**, e-mail `viktor@zalak.demo`, a password, tick the box → Continue → **Skip for now** | "Two short steps; everything after the e-mail can be skipped." |
| 1:25 | Home | The first-day Home with his lunch and *Welcome to Zalak, Viktor · Logged to lunch* | "The meal he checked as a guest is kept." |
| 1:35 | Normal window, 1440 | **Sign in** as `ana@zalak.demo` / `zalak-demo-2026` → Home | "Ana has used Zalak for a week." |
| 1:45 | Home | The week strip, *Eaten today* (still empty), the macro cards, the four slots, the week chart; ‹ to last week, tap a day | "Always 'eaten', never 'left'. No targets, no red or green." |
| 2:05 | 390 | **+** → **Photo** → drop the photo from the desktop → note *"cooked in butter"* → **Analyze** | "A photo and a note are analysed together." |
| 2:25 | Result | Tap an item's pencil → **Edit item**: + / − on the amount, the kcal follows live → **Save changes** | "Every item can be corrected: rename, portion, unit, remove, add." |
| 2:45 | | **Log to lunch** → toast *Logged to lunch · Undo* | |
| 3:00 | Diary, 1440 | Today's page → ‹ back a few days (the open book) → the calendar icon → pick Tue 27 Oct | "The diary is a book: one page per day." |
| 3:15 | | Open the burek → **Meal detail**: change the time → **Done** ("Saved" appears) | "Logged meals stay editable, and every change saves at once." |
| 3:30 | Statistics | This week → ‹ **last week** (7 of 7 days, the average range, macros, *Most logged*) → **Month** | "Patterns, not judgement." |
| 4:00 | Profile | **Preferences** → **Best guess** (saves at once) | "Some people don't want questions." |
| 4:10 | 390 | **+** → Text → *"a piece of homemade pita"* → Analyze | The unsure item shows its reason, with no question. Switch back to **Ask me** afterwards. |
| 4:30 | | Text → *"my shoe"* → Analyze | The overlay marks *No food found*, then the page explains. "Calm errors with a way forward." |
| 4:45 | | Turn **Wi-Fi off** → **+** → Text → any meal → Analyze → *Connection lost*, the text is kept → Wi-Fi on → **Try again** | "Nothing typed is ever lost." |
| 5:00 | Result / Profile | Point at *Estimate, not medical advice* | "Zalak estimates; it doesn't judge and it isn't medical advice." |

## If something goes wrong

- **The AI is slow or fails:** use **Try again**. If the internet is down, switch to the fake AI
  (Setup 5) and skip the Wi-Fi step.
- **"There is already an account with this e-mail"** for Viktor: the database wasn't reloaded.
  Use another e-mail, e.g. `viktor2@zalak.demo`.
- **Ana's photos are missing:** the `Copy-Item` step in Setup 2 was skipped.
- **The demo moves to a later date:** change `FIRST_DAY` in `meals/fixtures/build_demo.py`, then run
  `python manage.py shell -c "exec(open('meals/fixtures/build_demo.py', encoding='utf-8').read())"`
  (needs the original photos in `demo_photos_src/`), then repeat Setup 2.

## Back to your own database after the demo

The demo never touches `db.sqlite3`; only `.env` decides which database the app uses.

1. Stop `runserver` (Ctrl+C).
2. In `.env`, delete the line `ZALAK_DB=demo.sqlite3`, or change it to `ZALAK_DB=db.sqlite3`
   (no line at all also means `db.sqlite3`).
3. Set `ZALAK_AI_FAKE` back to what you use for development (`1` for the free fake answer, `0` for
   the real AI).
4. If you ever set it in the terminal instead (`$env:ZALAK_DB = ...`), clear it there too:
   `Remove-Item Env:ZALAK_DB`. A terminal value wins over `.env`.
5. Start `python manage.py runserver` again and sign in with your usual account: your own meals are back.

Optional tidy-up (both can be made again with Setup 2):

```powershell
Remove-Item demo.sqlite3
Remove-Item media\meals\demo -Recurse
```

Switching back for another demo is the same in reverse: set `ZALAK_DB=demo.sqlite3` and `ZALAK_AI_FAKE=0`,
then repeat Setup 2 for a clean start.
