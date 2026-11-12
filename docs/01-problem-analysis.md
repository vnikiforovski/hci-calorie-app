# Zalak: Problem Analysis

Zalak (залак, Macedonian for "a bite") estimates the calories and macronutrients of a meal from a photo, a text description or a voice note, and lets the user correct the estimate before logging it. The focus is interaction design, not nutritional accuracy.

**The four problems from the assignment**, which every decision is checked against:
1. **Input:** the easiest way to enter a meal
2. **Uncertainty:** communicating that an estimate may be wrong
3. **Correction:** fixing misidentified food or wrong portions
4. **Wellbeing:** no guilt or obsessive counting; useful, simple, unobtrusive

**Design goals**
- **Fast:** logging must feel quicker than not logging.
- **Honest:** the AI proposes, the user decides; estimates are ranges.
- **Forgiving:** everything can be edited or undone.
- **Calm:** awareness without guilt; food is never "good" or "bad".
- **Inclusive:** accessible, for beginners and experienced users.
- **Focused:** every feature serves the core loop *capture → review → correct → save*.

## 1. PACT analysis (lecture 002)

### People
A heterogeneous group: people losing or maintaining weight, fitness users, casual users, older users, people with health conditions.
- **Primary target:** young adults and students who want awareness without obsession. Fitness users are secondary. Clinical use (insulin dosing, allergies) is not targeted, but the app must stay safe for those users.
- **Physical:** low vision and color blindness (~8% of men), so color is never the only cue. Users often have one hand busy while eating.
- **Psychological:** people forget what they ate and recognize more easily than they recall. Some think in numbers, others in words. Numbers motivate some and cause guilt in others. Trust in AI varies.
- **Social:** different experience with technology and nutrition. Local home-cooked dishes (tavče gravče, burek, sarma) are harder for AI. Different diets and fasting periods.

### Activities
- **Purpose:** *journal* (after eating) and *check* (before eating, e.g. when ordering). Both follow *capture → estimate → review → save*.
- **Time:** 3–6 times a day, so it must be extremely simple. Often under time pressure and interrupted, so users need to capture now and finish later. AI takes a few seconds, longer than the ~1 s users expect, so immediate feedback is needed.
- **Cooperation:** mostly individual; for shared dishes the user logs their own portion.
- **Complexity:** logging is well-defined (step by step); correcting is not (users must work out what's wrong), so it needs free editing.
- **Safety-critical:** carb estimates used for insulin, false allergen safety, and psychological harm from guilt.
- **Errors:** AI errors (wrong food, portion, hidden oil) and user errors (wrong photo, duplicate, accidental delete) must be fixable in place, with undo.
- **Content:** photo, text or speech in; food items, calorie range and macros out. Personal, sensitive data.

### Context
- **Physical:** home (calm, good light), restaurants (dim light, little time), on the move (one hand, noise). Light and noise affect photo and voice, so every input needs a fallback.
- **Social:** eating is social. Photographing or speaking a meal in front of others is awkward, so the app must be discreet. No expert is present, so the app must explain itself.
- **Organizational:** personal use only.

### Technologies
- **Platform:** one responsive Django + Bootstrap web app, mobile-first: phone for capture, laptop for looking back.
- **Input:** camera or upload (drag and drop or paste on a laptop), text, voice (the browser's speech recognition; editable text; not in Firefox), touch for portions.
- **Output:** visual only. No sound and no vibration (D10).
- **Communication:** browser → Django → Claude API (Claude Haiku 5.5). The API key stays on the server. Every failure gets a message, a retry and a text fallback.

## 2. Design implications

- **D1** Three input modes, one pipeline and one review screen
- **D2** Quick capture now, finish later (drafts)
- **D3** Nothing is saved without the user's confirmation
- **D4** Uncertainty shown honestly: calorie ranges, marked items, a short reason
- **D5** Correction is a first-class action; totals update instantly
- **D6** Immediate feedback while the AI works
- **D7** Calm presentation: no good/bad food, no red/green, no alarms; lighter ideas only as optional suggestions
- **D8** Recognition over recall: recent and favorite meals, photo history
- **D9** Accessible by default: WCAG 2.1 AA, 44 px touch targets, frequent actions within thumb reach
- **D10** Discreet by default: silent, text always available, no social sharing
- **D11** Safe boundaries: no allergen claims; "estimate, not medical advice"
- **D12** Progressive disclosure: summary first, details on tap
- **D13** Graceful failure: always a fallback, never a dead end
- **D14** Usable immediately: Zalak works as a calorie checker without an account; signing up unlocks logging, the diary and the profile
- **D15** Photo plus an optional note, analyzed together

## 3. Scope

**Built** (the core loop and the app around it):
- the checker: photo + note, text and voice, Analyzing, Result with ranges and per-item confidence, correction (edit, add, remove, re-estimate, "Tell Zalak"), Log or Just checking, error states, the guest checker
- a lighter idea when only checking
- accounts with a short sign-up; Home with week strip, dashboards and meal slots; meal detail with edit and delete
- the Diary as a book, Your meals (favorites and own meals), drafts ("To finish"), Statistics for a week or a month
- Profile: personal details, uncertainty preference, lighter ideas on/off, password, delete account, help
- responsive layout (390 px and 1440 px) and an accessibility pass

**Not built** (planned as "last" or "could"; left out to finish the core well): water tracking, goals and targets (BMI, recommended calories, macro targets), "my share" fractions for shared dishes (the user sets the portion instead), food preferences sent to the AI, renaming meal slots, customizable statistics, dark mode, Macedonian language.

**Out of scope:**
- native apps (one web app is enough)
- micronutrients (unreliable from photos)
- allergen warnings (false safety)
- trainer or doctor access (privacy)
- push notifications (nagging)
- streaks (guilt)
- monetization
- a separate numbers-free display mode (Zalak is a calorie checker; guilt is handled by tone instead, D7)

## 4. Multimodal interaction (lecture 010)

**Modality, medium, device.** A message is encoded in a medium, sent through a device and perceived through a modality.
- **Input:** photo (sight, image, camera); text (sight + touch, text, keyboard); voice (speech, sound → text, microphone); corrections (touch, direct manipulation, touchscreen).
- **Output:** visual (text, numbers, photos, simple charts on the screen).

**How the modalities are combined.** The value lies in how modalities are combined, not how many there are.
- **Sequential:** speak, then check and edit the transcript; the AI interprets a photo, then the user corrects by touch, or by saying what was wrong ("Tell Zalak", typed or spoken).
- **Complementary:** photo + note (D15). The photo shows what and how much; the note adds what a photo can't show ("cooked in butter", "I ate half").
- **Redundant:** uncertainty shown with an icon, a word and a three-dot meter, never by color alone.
- **Simultaneous:** not used; it adds complexity without helping the task.
- The three inputs are also **alternatives**: any one can log a meal, and each input page links to the other ("Use a photo instead", "Type it instead"), so users pick what fits the context.

**Fusion.** Late fusion: the photo and note are sent to the AI together and produce one interpretation, which reduces ambiguity (a white sauce: yogurt or mayonnaise?). Voice becomes text first, so there is one pipeline. Photo and note belong to the same draft until Analyze, so their order doesn't matter (time alignment).

**Challenges.**
- **Ambiguity:** uncertain items, a clarifying question, easy correction.
- **Noise:** photo tips, a "No food found" page that says what Zalak saw, an editable transcript.
- **Latency:** an immediate Analyzing screen.
- **Complexity:** one shared pipeline.
- **Environment and device:** text is always available.

**Speech.** Useful when the hands are busy, but English speech recognition mishears local dish names ("tavče gravče") and Macedonian accents, and speaking aloud in public is awkward. So voice is never the only way, and the transcript is always editable.

**Output.** Visual output only. An optional confirmation sound was considered and dropped: it adds little and goes against D10.

**Multimodal vs multimedia.** Zalak's inputs are multimodal (interaction); its history of photos, text and numbers is multimedia (presentation).
