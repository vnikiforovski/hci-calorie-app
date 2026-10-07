# Zalak: User Research and Requirements

User research is a systematic process of collecting and analyzing data about users in order to understand them (lecture 003). This document answers the lecture's five questions for Zalak:

- **Needs:** what do users need?
- **Goals:** what are they trying to achieve?
- **Behavior:** how do they currently solve the problem?
- **Problems:** what obstacles and frustrations do they have?
- **Context:** in what context would they use the system?

It builds on `01-problem-analysis.md` (PACT, design implications D1–D14).

**Method.** We used desk research: five published studies on food journaling, calorie-tracking apps and AI photo logging. From these and the PACT analysis we built six user personas. We did not run our own interviews or surveys; the personas and requirements will be checked in the usability tests of the prototype (lecture 009).

## 1. Desk research

**Rethinking the mobile food journal (Cordeiro et al., CHI 2015)**
A survey of 257 people, followed by a 4–8 week field study with 27 participants using a photo-based food journal.
- 54% forgot to journal, 40% skipped foods that were hard to enter, and 65% avoided journaling when unsure of the ingredients.
- 13% deliberately avoided logging unhealthy meals.
- Existing apps made packaged foods the easiest to log.
- With photo journaling, participants made about 3.5 entries per day, 88% with a photo, and 86% within 10 minutes of eating. Only 22% skipped entries because they were difficult, compared with 60% with their previous method.
- Photos worked as memory cues: who they ate with, where, how the food was made.
- 52% felt awkward photographing food in public, especially at restaurants, friends' homes and parties.

**Barriers and negative nudges (Cordeiro et al., CHI 2015)**
A survey of 141 current and former food journalers and over 5,500 forum posts. The authors recommend different journal designs for different goals, instead of one journal that tries to capture everything.

**Sustained use of a photo-based food app (Helander et al., JMIR 2014)**
Of 189,770 people who downloaded a free photo food app, only 2.58% used it for at least a week. Users who added a text description to their first photos were far more likely to keep going (about 53% of active users versus 18% of those who stopped).

**Calorie trackers and eating disorders (Levinson et al., 2017)**
Among 105 people recently treated for eating disorders, about 75% had used MyFitnessPal, and 73% of those felt it contributed to their disorder. This is a clinical group, not typical users, but it shows number-focused tracking can harm a vulnerable minority.

**User errors in an AI photo nutrition app (Vasiloglou et al., 2021)**
48 participants used an AI photo app for 24 hours. 12.8% of recordings were unusable because of capture mistakes, and 52% of participants made at least one. Clear instructions and automatic photo checks are needed.

**Key takeaways**
- People stop tracking because of **effort and uncertainty**, not lack of motivation.
- **Photos** are the lowest-effort input and a good memory cue, but are **awkward in public**.
- **Judgment** makes people log less honestly; exact numbers can harm some users.
- **AI capture fails** in predictable ways, so users need guidance and a way to correct it.

## 2. Personas

**Ana, 22, the curious student (primary)**
- **Goal:** a rough idea of whether she eats balanced, without a strict diet.
- **Today:** eats at the faculty canteen, at home, and burek on the way. Tried MyFitnessPal and quit after a few days.
- **Frustration:** finding home-cooked dishes in a database took too long.
- **Context:** phone always in hand, often eating with friends.

**Elena, 30, the former tracker (primary)**
- **Goal:** stay aware of what she eats without numbers taking over her day.
- **Today:** tracked strictly for months, then stopped because counting felt stressful.
- **Frustration:** exact numbers and daily limits made her feel guilty.
- **Context:** office lunches, cooking at home in the evening.
- **Why she matters:** numbers-light mode (D14) and calm presentation (D7).

**Ivan, 19, the first-year on a budget (primary)**
- **Goal:** check a meal *before* ordering ("is this a lot?"), and make slightly better choices.
- **Today:** fast food, delivery and canteen meals; never tracked anything.
- **Frustration:** calorie apps look like work; he won't type ingredients.
- **Context:** standing in a queue or scrolling a delivery app, one hand, in a hurry.
- **Why he matters:** speed, the "check before eating" purpose, and a good first experience.

**Marko, 26, the gym regular (secondary)**
- **Goal:** reach a daily protein and calorie target.
- **Today:** logs everything in a calorie app and knows grams and macros well.
- **Frustration:** home-cooked meals and eating out mean guessing every ingredient; it takes minutes.
- **Context:** meal prep at home, quick meals after training.
- **Why he matters:** detail on demand and fast correction of portions.

**Lea, 38, the parent who cooks (secondary)**
- **Goal:** know roughly what she and her family eat.
- **Today:** cooks traditional dishes (tavče gravče, sarma, stews) for everyone; doesn't track.
- **Frustration:** her meals don't exist in apps, and she eats from a shared pot, so portions are unclear.
- **Context:** family table, little free time, interrupted constantly.
- **Why she matters:** local dishes, "my share" of a shared dish, and finishing a log later.

**Goran, 55, the cautious newcomer (secondary)**
- **Goal:** follow his doctor's general advice to eat better.
- **Today:** uses his phone for calls, messages and news; has never used a food app.
- **Frustration:** small text, unclear buttons, unfamiliar terms like "macros".
- **Context:** at home, reading glasses, no one to ask for help.
- **Why he matters:** accessibility (D9), plain language, and not mistaking estimates for medical advice (D11).

## 3. The five research questions

**Needs**
- Logging that takes seconds, because it happens several times a day (Ivan, Ana).
- A way to log even when unsure of the ingredients (Ana, Lea).
- Home-cooked, local and shared dishes, not only packaged food (Lea, Marko).
- A discreet option when a photo or voice would be awkward (Ana, Elena).
- A result understandable at a glance, in numbers or in words (Marko, Elena).
- Seeing what the AI recognized and fixing it (Marko, everyone).
- Not feeling judged (Elena).
- Large text and plain language (Goran).

**Goals**
- Awareness of roughly how much and how balanced they eat (Ana, Elena, Lea).
- Reaching a calorie or protein target (Marko).
- Deciding before eating (Ivan).
- Following general health advice (Goran).
- Looking back and noticing patterns (desk research).
- All without tracking becoming a burden or stress.

**Behavior**
- Most people don't track, or estimate "in their head" (Ivan, Lea, Goran).
- App users search a food database item by item and enter grams; packaged foods are easiest.
- Most people who try an app stop within days.
- Many log later and forget details; some skip meals they can't describe or don't want to admit.

**Problems**
- Slow item-by-item entry.
- Forgetting to log.
- Uncertainty about ingredients.
- Local and home-cooked dishes missing from databases.
- Awkwardness of photographing food in public.
- Guilt and pressure from numbers and limits.
- Wrong AI estimates and capture mistakes.
- Interruptions; meals arriving in parts.

**Context**
- Home, canteen, restaurants, on the move, at the desk.
- Alone, with family, with friends; shared dishes are common.
- Before eating under time pressure, or later when relaxed.
- Phone for capture, laptop for looking back.
- Bad restaurant lighting, noise, one hand busy, weak mobile data.

## 4. Insights

- **I1 Effort decides whether people keep tracking.** Every extra step loses users.
- **I2 Demanding precision makes people log less.** A range for a logged meal beats an exact number for a meal that was skipped.
- **I3 Photos are the easiest input, but not always socially possible.** Every photo flow needs a quiet alternative.
- **I4 Judgment changes behavior.** A calm, non-judgmental interface is a requirement, not decoration.
- **I5 Real meals are home-cooked, local and shared.**
- **I6 Users must see and fix what the AI understood.** Trust comes from visible reasoning and easy correction.
- **I7 AI capture fails in predictable ways.** Bad photos must be detected and the user guided.
- **I8 The first experience decides whether people stay.**
- **I9 Some users think in numbers, others in words.**

## 5. Requirements

Each requirement has an ID, a priority, and the insight (I) or design implication (D) it comes from.
**Must:** the core loop needs it. **Should:** important, planned. **Could:** if time allows.

### 5.1 Functional requirements

**Account and profile**
- **FR1** (Must) The user can register and log in with an e-mail and password.
- **FR2** (Must) The user can switch between Standard and Numbers-light display in profile settings; Standard is the default. *(I9, D14)*
- **FR3** (Should) The user can delete their account and all their data.
- **FR4** (Could) The user can set optional goals (daily calories or protein).

**Meal capture**
- **FR5** (Must) The user can take a meal photo with the camera or upload an image. *(I3)*
- **FR6** (Must) The user can describe a meal in free text. *(I3)*
- **FR7** (Must) The user can dictate a meal by voice and edit the recognized text before sending. *(D1)*
- **FR8** (Must) The system suggests the meal slot (breakfast, lunch, dinner, snack) from the time of day; the user can change it. *(I1)*
- **FR9** (Should) The user can save a meal as a draft and complete it later. *(I1, D2)*
- **FR10** (Should) The user can log a recent or favorite meal again in one tap. *(I1, D8)*
- **FR11** (Should) The user can log only their share of a shared dish (½, ⅓, ¼). *(I5)*

**Estimate**
- **FR12** (Must) The system returns a list of recognized foods, each with a portion, a calorie range and macronutrients (protein, carbohydrates, fat). *(D4)*
- **FR13** (Must) The meal total is shown as a range, e.g. 550–700 kcal. *(I2)*
- **FR14** (Must) Uncertain items are marked with a short reason, e.g. "cooking oil not visible". *(I6)*
- **FR15** (Must) In Numbers-light mode, the meal is shown as a short description and macro proportions; exact values appear on tap. *(I9)*
- **FR16** (Should) When very unsure, the system asks one simple question (e.g. "fried or grilled?") instead of guessing. *(I2, I6)*
- **FR17** (Should) The system can suggest one optional healthier alternative, which the user can dismiss. *(D7)*

**Correction**
- **FR18** (Must) The user can rename or replace a recognized item. *(I6)*
- **FR19** (Must) The user can change a portion with a stepper or preset sizes (small, medium, large), or in grams. *(I6)*
- **FR20** (Must) The user can add a missing item by typing it. *(I6)*
- **FR21** (Must) The user can remove an item. *(I6)*
- **FR22** (Must) Totals update immediately after every change. *(D5)*

**Journal and history**
- **FR23** (Must) Nothing is saved until the user confirms the reviewed meal. *(D3)*
- **FR24** (Must) The user sees today's meals and totals on one screen.
- **FR25** (Must) The user can edit or delete a saved meal; deletion can be undone. *(D3)*
- **FR26** (Should) The user can browse past days in a calendar with photo thumbnails. *(D8)*
- **FR27** (Should) The user can mark a meal as a favorite. *(D8)*
- **FR28** (Could) The user can see a simple weekly overview.

**Guidance and errors**
- **FR29** (Must) If the analysis fails, the input is kept, the problem is explained, and the user can retry or type the meal instead. *(D13)*
- **FR30** (Must) If a photo can't be analyzed, the system says why and offers to retake it or describe the meal. *(I7)*
- **FR31** (Should) Before the first photo, the system shows two or three short tips for a good food photo. *(I7, I8)*
- **FR32** (Should) After the first few meals, a one-time hint mentions Numbers-light mode. *(D14)*
- **FR33** (Must) The estimate screen and sign-up state that values are estimates, not medical advice. *(D11)*

### 5.2 Non-functional requirements

**Performance**
- **NFR1** (Must) Actions that don't use the AI respond within 1 second.
- **NFR2** (Must) After a meal is submitted, an "analyzing" state appears within 1 second. *(D6)*
- **NFR3** (Should) 9 out of 10 analyses return within 10 s for text and 15 s for photos on a normal connection.
- **NFR4** (Must) Totals update within 100 ms after a portion change, without reloading the page.

**Usability** (checked in usability testing)
- **NFR5** (Must) A new user logs a first meal within 2 minutes of registering, without help, in 4 of 5 tests. *(I8)*
- **NFR6** (Must) If the AI is right, saving a meal takes at most 3 interactions after capture. *(I1)*
- **NFR7** (Must) Changing a portion takes at most 2 taps. *(I6)*
- **NFR8** (Should) Re-logging a favorite takes at most 2 taps from the home screen. *(I1)*
- **NFR9** (Should) 4 of 5 test users correctly explain that the value is an estimate. *(I2)*
- **NFR10** (Should) The SUS score in the final evaluation is at least 75 (the average is about 68).

**Accessibility**
- **NFR11** (Must) Main screens meet WCAG 2.1 AA: contrast of at least 4.5:1, text resizable to 200%, labeled controls, text alternatives for images. *(D9)*
- **NFR12** (Must) Color is never the only way information is shown. *(D9)*
- **NFR13** (Must) Touch targets are at least 44 × 44 px. *(D9)*
- **NFR14** (Should) Everything works with a keyboard on desktop, and WAVE reports no errors on the main screens. *(D9)*

**Compatibility**
- **NFR15** (Must) The app works on current Chrome, Safari (iPhone), Edge and Firefox, at widths from 360 to 1440 px.
- **NFR16** (Must) Where voice recognition isn't supported, the microphone button explains why and text input stays available. *(D13)*

**Security and privacy**
- **NFR17** (Must) Personal data and photos are visible only to their owner.
- **NFR18** (Must) Passwords are hashed (Django authentication) and forms are protected against CSRF.
- **NFR19** (Must) The AI API key stays on the server (`.env`) and is never committed to Git.
- **NFR20** (Should) The user is told that meals are sent to an AI service for analysis. *(I6)*

**Reliability**
- **NFR21** (Must) The input is saved before it is sent for analysis, so nothing is lost if the analysis fails. *(D2)*
- **NFR22** (Must) The AI response is checked against a fixed structure; an invalid response is treated as a failed analysis. *(D13)*

**Content and tone**
- **NFR23** (Must) No screen labels food as good, bad, cheat or over the limit, and food is never color-coded red/green. *(I4, D7)*
- **NFR24** (Should) Terms like kcal and macros are explained in plain language the first time they appear. *(D12)*

Scalability is not a goal: this is a course prototype used by a small number of test users.

### 5.3 Traceability to the assignment
- **Input** → FR5–FR11, NFR6, NFR15–NFR16
- **Uncertainty** → FR12–FR16, NFR9
- **Correction** → FR18–FR22, NFR4, NFR7
- **Wellbeing and simplicity** → FR2, FR15, FR17, FR32–FR33, NFR23–NFR24

## Sources

- Cordeiro, F., Bales, E., Cherry, E., Fogarty, J. (2015). Rethinking the Mobile Food Journal: Exploring Opportunities for Lightweight Photo-Based Capture. CHI 2015. https://homes.cs.washington.edu/~jfogarty/publications/chi2015-decaf.pdf
- Cordeiro, F., Epstein, D., Thomaz, E., et al. (2015). Barriers and Negative Nudges: Exploring Challenges in Food Journaling. CHI 2015. Summary: https://news.cs.washington.edu/2015/04/16/barriers-and-negative-nudges-uw-cse-research-team-led-by-james-fogarty-co-authors-new-study-of-mobile-food-journaling/
- Helander, E., Kaipainen, K., Korhonen, I., Wansink, B. (2014). Factors Related to Sustained Use of a Free Mobile App for Dietary Self-Monitoring With Photography and Peer Feedback. JMIR 16(4):e109. https://jmir.org/2014/4/e109
- Levinson, C. A., Fewell, L., Brosof, L. C. (2017). My Fitness Pal calorie tracker usage in the eating disorders. Eating Behaviors. https://pmc.ncbi.nlm.nih.gov/articles/PMC5700836/
- Vasiloglou, M. F., et al. (2021). The Human Factor in Automated Image-Based Nutrition Apps: Analysis of Common Mistakes Using the goFOOD Lite App. JMIR mHealth and uHealth 9(1):e24467. https://mhealth.jmir.org/2021/1/e24467
- FCSE HCI lectures 002 (PACT) and 003 (Understanding users), 2025/26.
