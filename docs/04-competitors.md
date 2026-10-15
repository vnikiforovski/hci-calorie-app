# Zalak: Competitor Analysis

A short review of 20 calorie and nutrition apps: what they offer, what works, what doesn't, and what Zalak takes from them. The focus is on the calorie-checking flow (input → result → correction); the rest of each app is noted briefly. Screenshots of the parts we liked are in `img/`.

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

## Design wants

The direction for Zalak, based on the review. Details are designed in the design phase.

**General**
- Simple UI.
- Works on mobile and desktop; the desktop version shows more detail.
- Calories and macros come from the AI only; no nutrition database.
- Logo: the name plus a food item with a bite taken out, since Zalak means "a bite". A cookie is the favorite (decided later); not an apple, which is too close to Apple's logo.
- Priorities: the checker first; then the home page, sign-up and diary; water, goals, BMI, the book style and customizable statistics last.

**First use and account**
- No account needed at first: Zalak opens as an AI calorie checker.
- An account unlocks logging, the diary, custom meals, water and goals. When a guest taps Log, they are asked to sign up, and the meal is then logged.
- Sign-up with e-mail and password (no Google or Apple), as a short step-by-step form of 4–5 steps, where everything except e-mail and password can be skipped:
  - name
  - height, weight, activity level
  - how Zalak should handle calorie uncertainty (the Amy idea)
  - a few quick preferences for the AI (e.g. diet, usual cuisine)

**Home page**
- Logo and name at the top, with a profile icon that opens the profile.
- The 7 days of the week at the top; tapping a day changes the dashboards. Arrows change the week, and a small calendar jumps to any date.
- Dashboards below: calories as the main one, then macros and water.
- Breakfast, lunch, dinner and snack below the dashboards, each with a "+" for quick input. Meal sections can be renamed, added or removed.

**Meal input (the checker)**
- One "+" button with three ways in:
  - **Text and voice:** one text field with a microphone that fills it; the text can be edited.
  - **Photo:** always with an optional text field to help the analysis; a tutorial as swipeable cards from the bottom the first time (with "Don't show again"), then a "Tips" button next to the camera.
  - **Your meals:** favorites and custom meals.
- Two goals: **just check** the calories and macros, or **log** the meal to breakfast, lunch, dinner or snack.
- When only checking, Zalak offers a **healthier option** as a small, dismissible card under the result, worded as an idea ("A lighter idea: chicken wrap, ~550 kcal"). Only when a meaningfully lighter option exists; can be turned off. Not a pop-up.
- Each food item shows the AI's confidence (sure / likely / unsure, with a reason).

**Analysis and editing**
- A loading animation while the AI works; other animations where they help.
- When the result arrives you can:
  - edit the whole meal
  - open each food item and change it, its portion or its weight, in many different measurements
  - add and delete items
- Then log it.

**Diary**
- Looks like a real diary book: swipe between days like pages, with meal photos; tap a meal to see and edit details.
- A bookmark section for favorite meals and recipes.
- A quick calendar to jump between days.
- Fallback if the book is too hard: a normal diary with photos.

**Profile**
- Requires sign-in.
- Edit personal data and preferences: dashboard style, calorie uncertainty handling.
- Calculated BMI and recommended daily calories and macros, only if the user wants them (handled carefully to avoid guilt; decided later).
- Optional goals to follow and track.
- Custom meals: "Save as my meal" from an analyzed meal, or created in a form.
- Water intake: tap-to-fill glasses, editable daily amount.

**Statistics**
- A default design that works well for everyone, customizable per user; macro targets if the user chooses them.

## Idea parking lot (decisions)

**In**
- uncertainty preference at sign-up and in the profile
- personal preferences in the AI prompt
- usable without an account
- diary with photos
- custom meals
- water intake
- healthier option when checking
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

**Uncertainty, split in two:** the *preference* ("ask me" or "best guess") is set at sign-up and in the profile; the per-item *confidence* (sure / likely / unsure, with a reason) is always on the result screen.
