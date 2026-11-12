# Zalak: Competitor Analysis

A short review of 20 calorie and nutrition apps: what they offer, what works, what doesn't, and what Zalak takes from them. The focus is on the calorie-checking flow (input → result → correction); the rest of each app is noted briefly. Screenshots of the parts we liked are in `competitor screenshots/`.

## Apps

**Cronometer**
- Good: very detailed nutrition (macros and micronutrients); custom foods and recipes; flexible serving units; tap-to-fill water glasses.
- Bad: crowded, messy UI; too many dashboards and options; key features behind a paid tier.
- For Zalak: phone for adding meals, desktop for details. Nine input methods behind one "+" is too many.

**Fitia**
- Good: the best input structure (text, voice, camera, gallery in 2–3 taps); meal sections that are easy to add to or remove; a week calendar that expands to a month; customizable stats cards.
- Bad: very long onboarding; hard-to-avoid paywall; social features and constant notifications; voice input can't be edited.
- For Zalak: main design reference for input, meal sections and calendar. Voice must stay editable.

**MyFitnessPal**
- Good: simple, uncrowded design; calendar; progress charts.
- Bad: much hidden behind Premium; the input flow feels odd.
- For Zalak: reference for a calm layout. Its database-search input is the slow model Zalak replaces.

**Noom**
- Good: voice and text in one input field; a short tutorial on first use of photo and voice.
- Bad: long sign-up; face scan for age; news content; weak statistics.
- For Zalak: one combined text + voice field; a first-use tutorial.

**MacroFactor**
- Good: the best overall feel; the app we'd most likely use; good input methods.
- Bad: some screens crowded or oversized.
- For Zalak: reference for overall feel.

**Yazio**
- Good: solid but unremarkable.
- Bad: very long introduction.
- For Zalak: most apps are alike, so Zalak should stand out through the assignment's four problems, not more features.

**Simple**
- Good: some interesting input design.
- Bad: a virtual "buddy" and chatbot; weight-loss-only goals with deadlines; too-simple meal editing.
- For Zalak: no buddy, no deadline goals; correction must be strong.

**Cal AI**
- Good: the fastest app; a simple home page; does calorie checking very well; good animations.
- Bad: only a 3-day free trial; few features beyond the checker.
- For Zalak: main reference for the checker itself (input, result, animations).

**Amy**
- Good: asks at sign-up *"How should Amy handle calorie uncertainty?"*; nice loading animations.
- Bad: too simple; odd journaling.
- For Zalak: let the user choose how uncertainty is handled.

**Welling AI**
- Good: an AI chatbot coach; decent inputs and statistics.
- Bad: paid after 7 days; basic.
- For Zalak: a few personal preferences at sign-up passed to the AI; a short introduction.

**PlateLens**
- Good: some interesting layouts.
- Bad: UI not appealing; a few seconds of waiting.
- For Zalak: the wait is unavoidable, so the analyzing state matters.

**MyNetDiary**
- Good: good editing of logged meals.
- Bad: constant Premium upselling; average UI.
- For Zalak: reference for editing saved meals.

**Foodvisor**
- Good: some nice UI elements.
- Bad: cartoonish style; quests; an intro that moves too fast.
- For Zalak: no gamification.

**Lose It!**
- Bad: long sign-up with too much text; unappealing feel.
- For Zalak: the checker should work immediately; profile and diary optional.

**SnapCalorie**
- Good: an interesting diary; free version.
- Bad: weak charts.
- For Zalak: a photo diary, like a real food journal.

**Lifesum**
- Good: quick sign-up; decent UI.
- Bad: the free version only allows logging by food name.

**Nutrola**
- Good: quick sign-up; simple, effective first impression.
- Bad: weak diary.

**Kalo**
- Good: no profile setup at the start; details can be added later.
- Bad: glitches; overall weak.

**Calorie Mama**
- Good: short sign-up; interesting meal plan and dashboard.
- Bad: not appealing overall.

**CalorieAI**
- Good: clean, consistent, Apple-like design; a *Today · Yesterday · Tue · Mon* day strip.
- Bad: colorless palette; no full calendar; the text field only patches the photo, with no guidance.
- For Zalak: the day strip; a photo note that explains what to write.

## Findings

- **Most apps are alike:** photo, text and voice input, a diary, charts. Having three inputs is not unique; doing them well is.
- **Long sign-ups and paywalls** are the most common frustrations. The apps with short sign-ups made the best first impression.
- **Clean beats crowded:** Cal AI and CalorieAI felt best; Cronometer and parts of MacroFactor felt overwhelming.
- **Extras add noise:** social features, quests, buddies and notifications don't help the core task.
- **AI analysis takes a few seconds everywhere,** so the waiting state needs care. Cal AI and Amy handle it best.
- **Uncertainty is rarely addressed;** only Amy asks the user about it. This is where Zalak can stand out.

## Adopt / Avoid

**Adopt**
- A checker that does one job fast and well (Cal AI)
- One combined, editable text + voice input (Noom)
- First-use tutorial for photo and voice (Noom)
- User's choice of how uncertainty is handled (Amy)
- Usable immediately, profile optional and later (Lose It!, Kalo)
- Short sign-up (Lifesum, Nutrola)
- Meal sections and an expandable calendar (Fitia), with a day strip (CalorieAI)
- Photo diary (SnapCalorie)
- Loading animations (Cal AI, Amy)

**Avoid**
- Long onboarding and health questionnaires
- Paywalls and upselling
- Crowded dashboards
- Social features, quests, buddies, notifications
- Too many input options; non-editable voice
- A cartoonish or colorless style

## Design wants, and what became of them

The direction set after the review, and what the built app does with it.

**General**
- Simple UI that works on a phone and a laptop, with more detail on the laptop. *Done (390 and 1440 px layouts).*
- Calories and macros from the AI only; no nutrition database. *Done.*
- Logo: the name plus a food with a bite taken out ("zalak" means "a bite"). *Done: a golden cookie; it also loses bites on the Analyzing screen.*

**First use and account**
- No account needed at first: Zalak opens as a calorie checker; Log asks a guest to sign up and then logs the meal. *Done: Welcome offers "Try it without an account".*
- A short step-by-step sign-up with e-mail and password (no Google or Apple), everything else skippable. *Done in 2 steps; the uncertainty preference moved to Profile, and food preferences for the AI were dropped.*

**Home page**
- Logo and profile icon at the top; the week's 7 days with arrows and a calendar; calorie and macro dashboards; breakfast, lunch, snack and dinner, each with a "+". *Done. Water and renaming slots were left out.*

**Meal input (the checker)**
- One "+" with three ways in: Text and voice (one field, editable), Photo (with a note and first-time tips), Your meals. *Done; Recent meals sit under them.*
- Just check or log. *Done: Just checking and Log to [slot].*
- A small, dismissible lighter idea when only checking. *Done; it can be turned off.*
- Confidence per item (sure / likely / unsure, with a reason). *Done.*

**Analysis and editing**
- A loading animation; edit the whole meal, each item, its portion and unit; add and delete items. *Done, plus "Tell Zalak" to correct the whole meal in your own words.*

**Diary**
- A real diary book with meal photos, a bookmark section for favorite and own meals, and a quick calendar. *Done: pages turn with arrows (not swipes); "Your meals" is a tab on the edge of the book.*

**Profile and statistics**
- Personal data and the uncertainty preference. *Done.*
- Own meals. *Done ("Create your own meal").*
- BMI, recommended calories and macros, goals, water, customizable statistics. *Not built: Statistics has one default layout for everyone.*

## Idea parking lot (decisions)

**In, and built**
- uncertainty preference (in the profile)
- usable without an account
- diary with photos
- own meals and favorites
- a lighter idea when checking

**In, but not built** (time went to the core flow)
- personal preferences in the AI prompt
- water intake
- optional BMI, recommended calories, macro targets and goals
- customizable statistics

**Out**
- Google/Apple sign-in
- chatbot
- barcode scanning
- nutrition database
- separate food search
- structured text input as the main input
- numbers-free display mode (Zalak is a calorie checker)

**Uncertainty, split in two:** the *preference* ("Ask me" or "Best guess") is set in the profile; the per-item *confidence* (sure / likely / unsure, with a reason) is always on Result.
