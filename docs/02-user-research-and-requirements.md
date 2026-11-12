# Zalak: User Research and Requirements

User research is a systematic process of collecting and analyzing data about users in order to understand them (lecture 003): their **needs**, **goals**, **behavior**, **problems** and **context**.

**Method:** desk research (five published studies) plus six personas built from it and the PACT analysis. The Figma prototype was tried informally by friends (docs/06); no formal usability test was run.

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

**MoSCoW:** **Must** (the core loop needs it), **Should** (planned), **Could** (if time allows). Each requirement ends with what was built: **built**, **changed** (built differently, with how) or **not built**.

### Functional requirements

**Account and profile**
- **FR1** (Must) Register and sign in with e-mail and password. *Built.*
- **FR2** (Must) Use the checker without an account. Logging requires an account: a guest who taps Log is asked to sign up, and the meal is then logged. *Built: "Keep this meal?" → sign up or sign in → logged, with Undo.*
- **FR3** (Should) Delete the account and all data. *Built (asks for the password once).*
- **FR4** (Could) Optional goals and targets: BMI, recommended daily calories and macros. Off by default, never shown as red or "over". *Not built.*
- **FR36** (Should) Short sign-up; everything except e-mail and password can be skipped. *Changed: 2 steps (name, e-mail, password; then height, weight and activity, skippable). The uncertainty preference lives in Profile.*
- **FR37** (Should) Uncertainty preference, "Ask me" or "Best guess"; it controls FR16. *Changed: in Profile → Preferences only, default "Ask me".*
- **FR38** (Should) Optional food preferences included in every AI request. *Not built.*

**Capture**
- **FR5** (Must) Take a meal photo or upload an image. *Built: live camera on phones, the phone's own camera as fallback, drag, choose or paste on a laptop.*
- **FR6** (Must) Describe a meal in free text. *Built, with example and detail chips.*
- **FR7** (Must) Dictate a meal by voice and edit the transcript before sending. *Built (Chrome, Edge, Safari).*
- **FR8** (Must) The meal slot is suggested from the time of day and can be changed. *Built.* Renaming, adding or removing slots (Should): *not built.*
- **FR9** (Should) Save a meal as a draft and finish it later. *Built: every input is a draft first; unfinished ones show on Home as "To finish".*
- **FR10** (Should) Re-log a recent, favorite or own meal ("Your meals") in one tap. *Built: Recent in the Add meal sheet, Log again on Meal detail and Saved meal.*
- **FR39** (Should) Create own meals. *Built: "Create your own meal" on Your meals runs the normal checker and saves to My meals.*
- **FR11** (Should) Log only your share of a shared dish (½, ⅓, ¼). *Changed: a "Shared dish" chip on the photo note, and the amount stepper goes down to ¼.*
- **FR35** (Should) An optional note on a photo; both are analyzed together. *Built.*

**Estimate**
- **FR12** (Must) A list of recognized foods, each with a portion, a calorie range and macros. *Built.*
- **FR13** (Must) The meal total is shown as a range. *Built.*
- **FR14** (Must) Uncertain items are marked with a short reason. *Built.*
- **FR15** (Should) Each result has a short neutral description (e.g. "a filling lunch with good protein"). *Built.*
- **FR16** (Should) When very unsure, the system asks one simple question instead of guessing. *Built: on the unsure item, with A little / About that / A lot.*
- **FR17** (Should) When only checking, a small dismissible card suggests a lighter idea. Only when a clearly lighter option exists; can be turned off; never a pop-up. *Built (Preferences → Show lighter ideas).*

**Correction**
- **FR18** (Must) Rename or replace an item. *Built, plus "Re-estimate" and "Tell Zalak" for the whole meal.*
- **FR19** (Must) Change a portion: stepper, household measures (bowl, slice, piece) or grams. *Built: stepper with fractions, a typed amount, and a unit sheet with four groups.*
- **FR20** (Must) Add a missing item. *Built.*
- **FR21** (Must) Remove an item. *Built, with Undo.*
- **FR22** (Must) Totals update immediately. *Built: live on Edit item; saved changes show at once on Result.*

**Journal**
- **FR23** (Must) Nothing is saved until the user confirms. *Built: a draft never counts anywhere until Log.*
- **FR24** (Must) Home: the week at the top (arrows, a calendar for any date); calories and macros for the chosen day; meal slots with a "+" each. *Built. Water: not built.*
- **FR25** (Must) Edit or delete a saved meal, with undo. *Built: each change on Meal detail saves at once; delete has Undo.*
- **FR26** (Should) A diary of past days with meal photos, a quick calendar, and a bookmark for favorite and own meals. *Built, including the "book" look (two pages on a laptop); pages turn with arrows, not swipes.*
- **FR27** (Should) Mark a meal as a favorite. *Built.*
- **FR28** (Could) A simple weekly overview. *Built: Statistics for a week or a month.*
- **FR40** (Could) Water intake. *Not built.*
- **FR41** (Could) Customizable statistics. *Not built (one default layout).*

**Guidance and errors**
- **FR29** (Must) If the analysis fails, the input is kept, the problem is explained, and the user can retry or type instead. *Built.*
- **FR30** (Must) If a photo can't be analyzed, say why and offer a retake or text. *Built ("No food found" with what Zalak saw).*
- **FR31** (Should) Photo tips as swipeable cards, shown automatically the first time, with "Don't show again"; afterwards a "Tips" button. *Built.*
- **FR32** (Must) Each item shows sure / likely / unsure, with a reason when unsure. *Built: icon, word and a three-dot meter.*
- **FR33** (Must) "Estimate, not medical advice" at sign-up and on Result. *Built (also on Meal detail and in Help).*
- **FR34** (Should) "Just checking": see an estimate and discard it. *Built.*

### Non-functional requirements

- **Performance:** **NFR1** non-AI actions in under 1 s · **NFR2** "analyzing" shown in under 1 s · **NFR3** 9 of 10 analyses within 10 s (text) or 15 s (photo); the AI call stops after 20 s with a calm error · **NFR4** totals update in under 100 ms
- **Usability** (targets for a usability test, not run): **NFR5** first meal within 2 min of registering · **NFR6** saving takes ≤3 interactions after capture when the AI is right · **NFR7** changing a portion takes ≤2 taps · **NFR8** re-logging a favorite takes ≤2 taps · **NFR9** testers understand the value is an estimate · **NFR10** SUS ≥ 75
- **Accessibility:** **NFR11** WCAG 2.1 AA · **NFR12** never color alone · **NFR13** 44 × 44 px targets (exceptions: the phone week strip and the Your meals tab, which meet WCAG 2.2's 24 px) · **NFR14** keyboard use; no automated accessibility errors (checked with axe-core on 32 pages)
- **Compatibility:** **NFR15** major browsers, 360–1440 px · **NFR16** text fallback where voice isn't supported
- **Security:** **NFR17** data visible only to its owner · **NFR18** hashed passwords and CSRF protection · **NFR19** API key only on the server · **NFR20** users are told meals go to an AI service (sign-up and Help)
- **Reliability:** **NFR21** input saved before analysis · **NFR22** AI output validated against a fixed structure and realistic limits
- **Tone:** **NFR23** no "good/bad/cheat/over the limit" for a food or the user, no red/green for food or days. Describing what a meal contains ("good protein and fibre") is allowed. · **NFR24** terms like kcal and macros explained ("How to read this estimate" under every total, and Help)

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
