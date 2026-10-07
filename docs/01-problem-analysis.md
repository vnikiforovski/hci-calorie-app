# Zalak: Problem Analysis

Zalak (залак, Macedonian for "a bite") helps people estimate the calories and macronutrients of a meal from a photo, a text description or a voice note, and lets them correct the estimate. Per the assignment, the focus is interaction design, not the accuracy of the nutritional model.

The four core problems from the assignment, which every decision below is checked against:

1. **Input:** what is the easiest way to enter a meal?
2. **Uncertainty:** how does the system communicate that an estimate is uncertain?
3. **Correction:** how does the user fix misidentified food or wrong portions?
4. **Wellbeing:** how do we avoid guilt and obsessive calorie counting, while staying useful, simple and unobtrusive?

## 0. Design goals

These are condensed from the brainstorm on the intro lecture.

- **G1 Fast:** logging a meal must feel quicker than not logging it.
- **G2 Honest:** the AI proposes and the user decides (human-in-the-loop). Estimates are shown as ranges, and the AI's limits are visible.
- **G3 Forgiving:** every action can be undone or edited. Nothing is final without confirmation.
- **G4 Calm:** the app supports awareness without guilt. Food is never judged as "good" or "bad".
- **G5 Inclusive:** the app is accessible (WCAG 2.1 AA) and works for both beginners and experienced trackers.
- **G6 Value-checked:** every feature must serve the core loop (*capture a meal → review the estimate → correct → save*). If it doesn't, it waits.

### How AI is used in the design process

- **Analysis:** expanding user groups and contexts, and finding blind spots (as the PACT lecture suggests).
- **Ideas:** scenarios, user stories, user journeys, feature alternatives.
- **Design:** generating alternative layouts and visual variations in Figma tools, and test scenarios.
- **Development:** code (Django, Python, HTML/CSS/JS, Bootstrap).
- **Rule:** AI output is a starting point that we critically review. It does not replace real users, real testing or our own judgment.

## 1. PACT Analysis

### 1.1 People

The users are a **heterogeneous** group:
- people losing or maintaining weight
- fitness and athletes
- casual "just curious" users
- older users
- people with health conditions (diabetes, allergies, intolerances)

**Indirect stakeholders** are people who don't use the app but are affected by it: family members who cook the meals, and trainers or dietitians the user might show their log to.

**Primary target (proposed):** young adults and students who want awareness of what they eat without becoming obsessive. Fitness users are secondary. Clinical use, such as insulin dosing or allergy management, is not a target, but the app must stay safe for those users (see 1.2).

The lecture's key question applies to every decision: *could this design decision eliminate part of the population as possible users?*

**Physical differences**
- **Vision:** nearsightedness, low vision, and color blindness (about 8% of men, per the lecture). Nutrition information must never rely on color alone, and text must be resizable and high-contrast.
- **Touch and motor:** finger size versus small on-screen buttons. Users are often holding food, a fork or a drink, so they operate the phone one-handed.
- **Hearing:** audio cannot be the only feedback channel.
- **Age-related changes:** reduced vision and dexterity in older users.
- **Body metrics:** height, weight, age and activity level differ widely. They change a person's energy needs but not the interaction. They matter only if the user chooses to set a goal.
- **Health conditions:** diabetes, food allergies and intolerances. These are physical differences with safety consequences (see 1.2 Safety-critical).

**Psychological differences**
- **Memory:** people quickly forget what and how much they ate, and "people recognize something more easily than they remember it" (lecture). Logging hours later is unreliable without memory cues.
- **Words vs numbers:** some users understand "≈650 kcal", while others understand "a filling, protein-rich lunch" better.
- **Emotional reaction to numbers:** for some people calorie numbers motivate. For others they cause guilt, anxiety or obsessive tracking. People with a history of disordered eating are a vulnerable group.
- **Short-term states:** hunger, stress, fatigue and distraction at mealtimes lower attention.
- **Motivation changes over time:** it is high in the first days and drops after a few weeks. Engagement must not depend on pressure.
- **Trust in AI varies:** some users over-trust and accept wrong estimates. Others under-trust and stop using the app after one bad guess. The design must calibrate trust.

**Social differences**
- **Experience with technology:** ranges from first-time app users to experienced tracker users.
- **Nutrition knowledge:** beginners may not know what macros are, while experienced users want detail.
- **Food culture:** local and home-cooked dishes (for example ajvar, burek, tavče gravče, sarma, shopska salad) are harder for AI to recognize than packaged or fast food. Portions in home cooking are not standardized.
- **Dietary patterns:** vegetarian and vegan diets, religious fasting periods, cultural restrictions.
- **Language:** the interface is in English first. Macedonian is a possible later addition, since test users will be local.

### 1.2 Activities

**Purpose:** there are two different purposes:
1. **Journal (after eating):** documenting what was eaten during the day.
2. **Check (before eating):** "how much is this?" when ordering at a restaurant or choosing takeaway.

The core activity is the same for both: *capture a meal → get an estimate → review and correct → save*.

**Time aspects**
1. **Frequency:** 3–6 times a day, every day. Frequent tasks must be extremely simple. Rare tasks (profile setup, goals) only need to be easy to remember (lecture).
2. **Time pressure:** high before eating (the food is getting cold, people are waiting, the waiter is at the table). Low when logging calmly at the end of the day.
3. **Continuous vs intermittent:** logging is often interrupted when the food arrives or a conversation starts. Users must be able to capture quickly now and finish the details later, without losing anything.
4. **Response speed:** people expect a response to a click in about 1 second (lecture). An AI analysis will take several seconds, which exceeds that expectation, so the waiting time needs immediate acknowledgement and visible progress.

**Cooperation**
- Logging is mostly an individual activity.
- Shared meals add a group aspect. When one dish is eaten by several people, the user must be able to log "my share".
- Sharing the log with a trainer or dietitian is a possible secondary activity (see Scope).

**Complexity**
- **Well-defined:** logging a meal follows a linear flow (capture → review → save), so a step-by-step design fits.
- **Less well-defined:** correcting an estimate. The user has to work out whether the wrong part is the food, the portion, or a missing item, which needs flexible editing rather than a fixed sequence.
- **Less well-defined:** browsing history and spotting patterns, which needs free navigation.

**Safety-critical aspects**

For most users, a wrong estimate is a small error. But there are three serious risks:
- **Diabetes:** a user may use a carbohydrate estimate to decide an insulin dose. An estimate shown as precise could cause harm.
- **Allergens:** allergens cannot be reliably detected from a photo (nuts in a sauce, butter in a dish). A message like "no allergens found" would create a false sense of safety.
- **Psychological harm:** guilt, shame, or reinforcement of disordered eating. This is the "avoid guilt" requirement from the assignment.

**Errors and recovery**
- **AI errors:** wrong food identified, wrong portion, missed items, hidden ingredients (oil, butter, sugar in drinks).
- **User errors:** wrong photo, typo, meal logged twice, wrong day or meal slot, accidental delete.
- **Recovery:** every error must be fixable in place, with undo for destructive actions.

**Nature of content**
- **Required data:**
  - Input: a meal photo, a short free-text description (e.g. "two eggs, a slice of bread, hummus and yogurt"), or speech converted to text.
  - System data: a list of food items with portions, a calorie range, and macronutrients (protein, carbohydrates, fat).
  - History over time.
  - This is personal and sensitive data (photos, eating habits).
- **Display media:**
  - The meal photo, which is the strongest memory cue in history.
  - Numbers with ranges.
  - Short text descriptions.
  - Simple charts for a day or week.

### 1.3 Context

**Physical**
- **Home** (table, kitchen, couch): calm, good light, time available.
- **Restaurants and cafés:** dim or warm light (worse photos), a small table, time pressure.
- **On the move** (street food, campus, office desk, after the gym): one hand, standing, screen glare, noise (worse voice input).
- Because light and noise directly affect photo and voice quality, every input mode needs a fallback.

**Social**
- Eating is highly social: family meals, friends, dates, business lunches.
- Photographing your plate or saying your meal out loud in front of others can feel awkward or invite comments. The lecture notes that privacy matters when other people are present, and that social norms decide whether a design is accepted (e.g. sound output in a shared space).
- People may not want others to know they track food. The app should be discreet.
- Shared dishes, common in local meals (shared salads, meze, a family pot), make individual portions hard to estimate.
- No expert is present when the user logs a meal, so the app must explain itself. Help and tips have to be inside the app.

**Organizational**
- This is primarily personal use, and no organization imposes rules or workflows.
- Possible organizational settings, such as gym or coaching programs, dietitian follow-up and workplace canteens, are out of scope for this project.

**Other context** (from the intro lecture)
- **Temporal:** fixed mealtimes, late-night logging, weekends vs weekdays.
- **Cognitive:** hungry, tired, multitasking.
- **Technological:** phone vs laptop, weak mobile data indoors in restaurants.

### 1.4 Technologies

**Platform:** one responsive web app (Django + Bootstrap), designed mobile-first. On the phone it is used for quick capture, and on the laptop for reviewing history and uploading photos.

**Input**
- **Camera:** on mobile, a photo upload field can open the camera directly. Users can also upload from the gallery or the computer.
- **Text:** keyboard input in a single free-text field.
- **Voice:** microphone plus browser speech recognition (Web Speech API; works in Chrome, Edge and Safari, but not Firefox). Speech is turned into text, which the user sees and can edit before sending.
- **Touch:** steppers and sliders for adjusting portions.

**Output**
- **Screen:** the phone is primary and the laptop secondary.
- **Visual feedback:** every action gets one (loading, success, error, saved).
- **Sound:** optional and off by default, because of the social context.
- **Haptics:** the web Vibration API works on Android browsers but not on iPhone, so it can only be an optional extra and never the only feedback.

**Communication**
- The data flows browser ↔ Django server ↔ Claude API, which requires an internet connection.
- The API key stays on the server (`.env`) and is never sent to the browser.
- An analysis takes several seconds and can fail (timeout, no connection, unrecognizable photo). The system must always respond with a clear message, a retry option, and a manual-entry fallback.

**Content**
- Meal records: photo, items, portions, nutrition ranges, time, meal slot.
- Recent and favorite meals.
- An optional user profile and goals.
- Nutrition values are generated by Claude as structured data: items, portions, calorie range, macros, and confidence per item.

### 1.5 Key design implications

Each implication is traced back to the PACT findings above.

| # | Implication | From |
|---|---|---|
| D1 | **Three input modes, one pipeline.** Photo, text and voice all produce the same editable list of food items on one review screen. | P, C, T |
| D2 | **Quick capture, finish later.** One tap captures a meal as a *draft*, and the details can be completed later. Nothing is lost if the user is interrupted. | A: time 2–3 |
| D3 | **Review before save (human-in-the-loop).** The AI proposes and the user confirms. Nothing enters the journal without confirmation. | A: safety, T |
| D4 | **Show uncertainty honestly.** Calories are shown as a range (e.g. 550–700 kcal), uncertain items are marked, and a plain-language note explains *why* the system is unsure (e.g. "cooking oil not visible"). | A: safety, P: trust |
| D5 | **Correction is a first-class action.** Tap an item to replace it, change a portion with steppers or visual sizes, add a missed item, or remove one. Totals update instantly. | A: errors, complexity |
| D6 | **Feedback during waiting.** The app acknowledges immediately, shows progress during the analysis, and lets the user leave and come back to the result. | A: time 4 |
| D7 | **Calm, non-judgmental presentation.** No red/green "good/bad" food and no "over the limit" alarms. Numbers are paired with short descriptions. Healthier alternatives are offered as optional ideas, not corrections. | P: psychological, assignment |
| D8 | **Recognition over recall.** Recent and favorite meals allow one-tap logging, and photo thumbnails appear in the history. | P: memory |
| D9 | **Accessible by default.** WCAG 2.1 AA contrast, resizable text, color never the only cue, and touch targets of about 44–48 px. The most frequent actions are large and within thumb reach (Fitts' law). Checked with the WAVE tool. | P: physical |
| D10 | **Discreet by default.** Sound is off, text input is always available, and there is no social sharing. | C: social |
| D11 | **Safe boundaries.** No allergen-safety claims, a short note that estimates are not medical advice, and no extreme goals. | A: safety |
| D12 | **Progressive disclosure.** A simple summary comes first, with macro details on tap. Learning tips are optional, depending on experience. | P: social |
| D13 | **Graceful failure.** If the AI fails or isn't sure, the app asks the user or falls back to text or manual entry, and never hits a dead end. | T: communication |
| D14 | **Two display modes, chosen per profile.** *Standard* shows calorie ranges and macro grams. *Numbers-light* shows a short description ("a filling, balanced lunch") and macro proportions without grams, with exact numbers one tap away. Standard is the default for every new user; numbers-light is a display preference in the profile settings that can be switched anytime. | P: psychological, assignment (guilt) |

### 1.6 Scope decisions

**Core (must be in the app)**
- Photo, text and voice input feeding one review screen (D1)
- Calorie and macro estimate shown as ranges, with uncertainty markers (D4)
- Item correction and portion adjustment (D5)
- Draft meals (D2)
- Today view and a history with a calendar
- Recent and favorite meals (D8)
- Optional, gentle healthier-alternative suggestions (D7)
- Standard and numbers-light display modes, chosen per profile (D14)
- Accessibility basics (D9)
- Responsive layout for phone and laptop

**Only if time allows (after the core works)**
- Weekly trends dashboard
- Optional profile and goals (age, height, weight, activity)
- Learning tips and nutrition facts (can be toggled)
- Water and drink tracking
- Short onboarding tutorial
- Macedonian language

**Out of scope, with reasons**
- **Separate native mobile and desktop apps:** one responsive web app covers both, and the course stack is Django.
- **Micronutrients (vitamins, minerals):** the assignment asks for macronutrients, and micronutrients are unreliable from a photo and add clutter.
- **Allergen warnings:** they can't be reliable from a photo and would create false safety. Replaced by the D11 note.
- **Trainer or doctor access to the account:** privacy and account-sharing complexity, and not part of the assignment.
- **Push notifications and reminders:** complex for a web app, and reminders can feel like nagging (D7).
- **Haptics as a feature:** not supported in iPhone browsers.
- **Different interface based on the user's sex:** no user need for it, and a risk of stereotyping.
- **Streaks that "break":** they create pressure and guilt (D7). If anything, a neutral "days logged" count.
- **Monetization (ads, subscription):** not part of the course, and ads conflict with "unobtrusive". It will only be noted in the competitor analysis.

### 1.7 Open questions

**Answered**
- **Mobile, desktop or both?** One responsive web app, mobile-first.
- **How are calories and macros computed?**
  - We use the Claude API: vision for photos, text for descriptions.
  - It returns structured data (items, portions, calorie range, macros, confidence).
  - The course grades interaction, not accuracy, so this is enough.
  - Possible extra: checking against a nutrition database (e.g. USDA FoodData Central).
- **How are the three input modes implemented?**
  - Photo: an upload field that opens the camera on mobile.
  - Text: a single text field.
  - Voice: browser speech recognition that produces editable text.
  - All three lead to the same review screen.
- **Haptic feedback?** Only as an optional extra (see 1.4).
- **Personalized interface?** Recent and favorite meals plus optional goals, and nothing more for now.
- **LLM suggestions?** Yes. One optional healthier swap per meal, phrased as an idea.
- **Human-in-the-loop and trust calibration?** Adopted as core principles (D3, D4, D5).
- **Can an LLM do the PACT analysis?** It can support it but not replace it (lecture). This analysis was written first by us and then reviewed with AI.
- **Output as a range?** Yes (D4).
- **Primary target group?** Confirmed: young adults and students who want awareness without obsession; fitness users secondary.
- **Show numbers or a "numbers-light" mode?** Both (D14). Standard (calorie ranges and grams) is the default; numbers-light is a preference in the profile settings, with no extra step at sign-up.
- **App name?** **Zalak** (залак, "a bite"). Forkcast was the runner-up.

**Still open**
