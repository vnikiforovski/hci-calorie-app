# Zalak: Problem Analysis

Zalak (залак, Macedonian for "a bite") estimates the calories and macronutrients of a meal from a photo, a text description or a voice note, and lets the user correct the estimate. The focus is interaction design, not nutritional accuracy.

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
- **Time:** 3–6 times a day, so it must be extremely simple. Often under time pressure and interrupted, so users need to capture now and finish later. AI takes several seconds, longer than the ~1 s users expect, so immediate feedback is needed.
- **Cooperation:** mostly individual; shared dishes need a "my share" option.
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
- **Input:** camera or upload, text, voice (browser speech recognition; editable text; not in Firefox), touch for portions.
- **Output:** visual feedback for every action; sound optional and off by default; vibration only on Android, so only an extra.
- **Communication:** browser → Django → Claude API. The API key stays on the server. Every failure gets a message, a retry and a text fallback.

## 2. Design implications

- **D1** Three input modes, one pipeline and one review screen
- **D2** Quick capture now, finish later (drafts)
- **D3** Nothing is saved without the user's confirmation
- **D4** Uncertainty shown honestly: calorie ranges, marked items, a short reason
- **D5** Correction is a first-class action; totals update instantly
- **D6** Immediate feedback while the AI works
- **D7** Calm presentation: no good/bad food, no red/green, no alarms; healthier swaps only as optional ideas
- **D8** Recognition over recall: recent and favorite meals, photo history
- **D9** Accessible by default: WCAG 2.1 AA, 44 px touch targets, frequent actions within thumb reach
- **D10** Discreet by default: sound off, text always available, no social sharing
- **D11** Safe boundaries: no allergen claims; "estimate, not medical advice"
- **D12** Progressive disclosure: summary first, details on tap
- **D13** Graceful failure: always a fallback, never a dead end
- **D14** Usable immediately: Zalak works as a calorie checker without an account; signing up unlocks logging, the diary and the profile
- **D15** Photo plus an optional note, analyzed together

## 3. Scope

Priorities, in order:
1. **The checker (non-negotiable):** photo/text/voice input; photo note; range estimates with per-item uncertainty; correction and portions; check or log; healthier option; works without an account.
2. **The app around it:** home page with week strip and dashboards; short sign-up; diary with photos; favorites and custom meals; drafts; accessibility; responsive layout.
3. **Last:** water tracking, goals, BMI and recommended calories and macros, the diary "book" style, customizable statistics, Macedonian language.

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
- **Output:** mainly visual (text, numbers, photos, simple charts on the screen). An optional short sound or vibration for confirmation.

**How the modalities are combined.** The value lies in how modalities are combined, not how many there are.
- **Sequential:** speak, then check and edit the transcript; the AI interprets a photo, then the user corrects by touch.
- **Complementary:** photo + note (D15). The photo shows what and how much; the note adds what a photo can't show ("cooked in butter", "I ate half").
- **Redundant:** uncertainty shown with an icon and text, never by color alone.
- **Simultaneous:** not used; it adds complexity without helping the task.
- The three inputs are also **alternatives**: any one can log a meal, so users pick what fits the context.

**Fusion.** Late fusion: the photo and note are sent to the AI together and produce one interpretation, which reduces ambiguity (a white sauce: yogurt or mayonnaise?). Voice becomes text first, so there is one pipeline. Photo and note belong to the same draft until Analyze, so their order doesn't matter (time alignment).

**Challenges.**
- **Ambiguity:** uncertain items, a clarifying question, easy correction.
- **Noise:** photo tips, "can't analyze" messages, editable transcript.
- **Latency:** immediate "analyzing" state.
- **Complexity:** one shared pipeline.
- **Environment and device:** text is always available.

**Speech.** Useful when the hands are busy, but English speech recognition will likely mishear local dish names ("tavče gravče") and Macedonian accents, and speaking aloud in public is awkward. So voice is never the only way, and the transcript is always editable.

**Output.** Visual output is the main channel. Audio is limited to an optional confirmation sound (an earcon), off by default. No speech output.

**Multimodal vs multimedia.** Zalak's inputs are multimodal (interaction); its history of photos, text and numbers is multimedia (presentation).
