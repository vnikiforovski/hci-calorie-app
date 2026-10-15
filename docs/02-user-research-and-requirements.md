# Zalak: User Research and Requirements

User research is a systematic process of collecting and analyzing data about users in order to understand them (lecture 003): their **needs**, **goals**, **behavior**, **problems** and **context**.

**Method:** desk research (five published studies) plus six personas built from it and the PACT analysis. The personas and requirements will be checked in usability testing.

## 1. Desk research

- **Effort and uncertainty make people stop.** In a survey of 257 food journalers, 54% forgot to log, 40% skipped foods that were hard to enter, and 65% skipped meals when unsure of the ingredients. 13% avoided logging unhealthy meals (Cordeiro et al., 2015).
- **Photos lower the effort,** cutting skipped entries from 60% to 22%, and they work as memory cues. But 52% felt awkward photographing food in public (Cordeiro et al., 2015).
- **Most people quit early.** Only 2.58% of 189,770 users of a free photo food app kept using it for a week. Those who added text to their first photos were far more likely to stay (Helander et al., 2014).
- **Number-focused tracking can harm.** Among people treated for eating disorders, 73% of MyFitnessPal users felt it contributed to their disorder (Levinson et al., 2017).
- **AI photo capture fails predictably.** 52% of users made at least one capture mistake (Vasiloglou et al., 2021).
- Different goals need different journal designs, not one that captures everything (Cordeiro et al., 2015).

## 2. Personas

- **Ana, 22, curious student (primary).** Wants a rough idea of whether she eats balanced. Quit MyFitnessPal because home-cooked dishes took too long to find. Often eats with friends.
- **Elena, 30, former tracker (primary).** Stopped tracking because exact numbers made her feel guilty. Wants awareness without numbers ruling her day. → calm tone, no judgment, targets off by default.
- **Ivan, 19, first-year student (primary).** Wants to check a meal *before* ordering. Won't type ingredients; often in a queue with one hand free. → speed, "just checking".
- **Marko, 26, gym regular (secondary).** Tracks protein and calories, but guessing every ingredient takes minutes. → grams, fast correction, favorites.
- **Lea, 38, parent who cooks (secondary).** Cooks traditional dishes from a shared pot; constantly interrupted. → local dishes, "my share", drafts.
- **Goran, 55, cautious newcomer (secondary).** Following his doctor's advice; struggles with small text and jargon. → accessibility, plain language, "estimate, not medical advice".

## 3. The five research questions

- **Needs:** logging in seconds; logging even when unsure of the ingredients; local and shared dishes; a discreet option; a result understood at a glance (numbers or words); seeing and fixing what the AI understood; not feeling judged; large text and plain language.
- **Goals:** rough awareness of how much and how balanced they eat; reaching a target (Marko); deciding before eating (Ivan); following health advice (Goran); noticing patterns. All without stress.
- **Behavior:** most people don't track, or estimate in their head. App users search a database item by item; packaged food is easiest. Most quit within days. Many log later and forget.
- **Problems:** slow entry; forgetting; uncertain ingredients; local dishes missing; awkwardness in public; guilt from numbers; wrong AI estimates; interruptions.
- **Context:** home, canteen, restaurants, on the move; alone or with others; before eating in a hurry or later when relaxed; phone for capture, laptop for looking back; bad light, noise, one hand busy.

## 4. Insights

- **I1** Effort decides whether people keep tracking.
- **I2** Demanding precision makes people log less, so show ranges.
- **I3** Photos are easiest, but every photo flow needs a quiet alternative.
- **I4** Judgment changes behavior, so a calm interface is a requirement.
- **I5** Real meals are home-cooked, local and shared.
- **I6** Users must see and fix what the AI understood.
- **I7** AI capture fails predictably, so users need guidance.
- **I8** The first experience decides whether people stay.
- **I9** Numbers motivate some users and stress others, so numbers must come without judgment.

## 5. Requirements

**Must:** the core loop needs it. **Should:** planned. **Could:** if time allows.

### Functional requirements

**Account and profile**
- **FR1** (Must) Register and log in with e-mail and password.
- **FR2** (Must) Use the checker without an account. Logging requires an account: a guest who taps Log is asked to sign up, and the meal is then logged.
- **FR3** (Should) Delete the account and all data.
- **FR4** (Could) Optional goals and targets: BMI, recommended daily calories and macros, macro targets. Off by default, never shown as red or "over".
- **FR36** (Should) Short step-by-step sign-up (4–5 steps): e-mail and password, name, height, weight, activity level, uncertainty preference, AI preferences. Everything except e-mail and password can be skipped.
- **FR37** (Should) Uncertainty preference, "Ask me when unsure" or "Make your best guess", set at sign-up and changeable in the profile; it controls FR16.
- **FR38** (Should) Optional food preferences (e.g. diet, usual cuisine) included in every AI request. No health data.

**Capture**
- **FR5** (Must) Take a meal photo or upload an image.
- **FR6** (Must) Describe a meal in free text.
- **FR7** (Must) Dictate a meal by voice and edit the transcript before sending.
- **FR8** (Must) The meal slot (breakfast, lunch, dinner, snack) is suggested from the time of day and can be changed. Meal slots can be renamed, added or removed (Should).
- **FR9** (Should) Save a meal as a draft and finish it later.
- **FR10** (Should) Re-log a recent, favorite or custom meal ("Your meals") in one tap.
- **FR39** (Should) Create custom meals: "Save as my meal" from any analyzed meal, or build one in a form.
- **FR11** (Should) Log only your share of a shared dish (½, ⅓, ¼).
- **FR35** (Should) Add an optional note to a photo; both are analyzed together.

**Estimate**
- **FR12** (Must) A list of recognized foods, each with a portion, a calorie range and macros.
- **FR13** (Must) The meal total is shown as a range.
- **FR14** (Must) Uncertain items are marked with a short reason.
- **FR15** (Should) Each result has a short neutral description next to the numbers (e.g. "a filling lunch with good protein").
- **FR16** (Should) When very unsure, the system asks one simple question instead of guessing.
- **FR17** (Should) When the user is only checking, a small dismissible card suggests a lighter idea, e.g. "A lighter idea: chicken wrap, ~550 kcal". It appears only when a meaningfully lighter alternative exists and can be turned off. Never a pop-up.

**Correction**
- **FR18** (Must) Rename or replace an item.
- **FR19** (Must) Change a portion: stepper, sizes, household measures (bowl, slice, piece) or grams.
- **FR20** (Must) Add a missing item.
- **FR21** (Must) Remove an item.
- **FR22** (Must) Totals update immediately.

**Journal**
- **FR23** (Must) Nothing is saved until the user confirms.
- **FR24** (Must) Home page: the week's days at the top (arrows change the week, a small calendar jumps to any date); calories, macros and water dashboards for the chosen day; meal slots with a "+" each.
- **FR25** (Must) Edit or delete a saved meal, with undo.
- **FR26** (Should) A diary of past days with meal photos, a quick calendar, and a bookmark section for favorite and custom meals. A "book" look with page swipes is Could.
- **FR40** (Could) Water intake: tap-to-fill glasses with an editable daily amount.
- **FR41** (Could) Customizable statistics, with a default that works for everyone.
- **FR27** (Should) Mark a meal as a favorite.
- **FR28** (Could) A simple weekly overview.

**Guidance and errors**
- **FR29** (Must) If the analysis fails, the input is kept, the problem is explained, and the user can retry or type instead.
- **FR30** (Must) If a photo can't be analyzed, say why and offer a retake or text.
- **FR31** (Should) Photo tips as swipeable cards shown automatically the first time, with "Don't show again"; afterwards a "Tips" button next to the camera.
- **FR32** (Must) Each item on the result screen shows the AI's confidence as sure / likely / unsure, with a reason when unsure.
- **FR33** (Must) "Estimate, not medical advice" at sign-up and on the result screen.
- **FR34** (Should) "Just checking": see an estimate and discard it without saving.

### Non-functional requirements

- **Performance:**
  - **NFR1** non-AI actions in under 1 s
  - **NFR2** "analyzing" shown in under 1 s
  - **NFR3** 9 of 10 analyses within 10 s (text) or 15 s (photo)
  - **NFR4** totals update in under 100 ms
- **Usability:**
  - **NFR5** first meal within 2 min of registering, in 4 of 5 tests
  - **NFR6** saving takes ≤3 interactions after capture when the AI is right
  - **NFR7** changing a portion takes ≤2 taps
  - **NFR8** re-logging a favorite takes ≤2 taps
  - **NFR9** 4 of 5 testers understand the value is an estimate
  - **NFR10** SUS ≥ 75
- **Accessibility:**
  - **NFR11** WCAG 2.1 AA
  - **NFR12** never color alone
  - **NFR13** 44 × 44 px targets
  - **NFR14** keyboard use; no WAVE errors
- **Compatibility:**
  - **NFR15** major browsers, 360–1440 px
  - **NFR16** text fallback where voice isn't supported
- **Security:**
  - **NFR17** data visible only to its owner
  - **NFR18** hashed passwords and CSRF protection
  - **NFR19** API key only on the server
  - **NFR20** users are told meals go to an AI service
- **Reliability:**
  - **NFR21** input saved before analysis
  - **NFR22** AI output validated against a fixed structure
- **Tone:**
  - **NFR23** no "good/bad/cheat/over the limit", no red/green food
  - **NFR24** terms like kcal and macros explained on first use

### Traceability to the assignment
- **Input** → FR5–FR11, FR35
- **Uncertainty** → FR12–FR16, FR32, FR34, FR37
- **Correction** → FR18–FR22
- **Wellbeing** → FR4 (off by default), FR15, FR17, FR33, NFR23–NFR24

## Sources

- Cordeiro et al. (2015). Rethinking the Mobile Food Journal. CHI 2015. https://homes.cs.washington.edu/~jfogarty/publications/chi2015-decaf.pdf
- Cordeiro et al. (2015). Barriers and Negative Nudges: Exploring Challenges in Food Journaling. CHI 2015. https://news.cs.washington.edu/2015/04/16/barriers-and-negative-nudges-uw-cse-research-team-led-by-james-fogarty-co-authors-new-study-of-mobile-food-journaling/
- Helander et al. (2014). Factors Related to Sustained Use of a Free Mobile App for Dietary Self-Monitoring. JMIR 16(4):e109. https://jmir.org/2014/4/e109
- Levinson et al. (2017). My Fitness Pal calorie tracker usage in the eating disorders. Eating Behaviors. https://pmc.ncbi.nlm.nih.gov/articles/PMC5700836/
- Vasiloglou et al. (2021). The Human Factor in Automated Image-Based Nutrition Apps. JMIR mHealth and uHealth 9(1):e24467. https://mhealth.jmir.org/2021/1/e24467
