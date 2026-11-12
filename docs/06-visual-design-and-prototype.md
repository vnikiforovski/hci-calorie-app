# Zalak: Visual Design and Prototype

How Zalak looks (lecture 007, visual interface design) and how it was prototyped (lecture 008, prototyping). The Figma prototype: https://www.figma.com/design/TAkknAZ98WZRCS6eSG2ULW/Zalak-Prototype (export: `figma-prototype.pdf`).

## 1. Visual identity: Sage & caramel

**Feel:** simple, clear, fresh, playful. Chosen after comparing ten directions on the same Home and Result screens: a fresh green base with a warm caramel accent that matches the cookie logo, so app and logo read as one brand. In the app the colors and fonts are CSS variables that override Bootstrap's (`static/css/zalak.css`).

### Colors (60-30-10)

- **60% background:** `#F6F8F2` (sage white)
- **30% surfaces:** card `#FFFFFF`, tint `#E2ECDC` (soft sage), lines `#DCE5D5`
- **10% accent:** caramel `#F0A93B`, **only for actions**: the "+" button, Log, Analyze, the main button on every screen
- **Text:** ink `#1E3A30` (deep green), muted `#56685E`
- **Logo:** cookie `#E9B66A`, chips `#5A3A24`
- **Macro colors** (data only, never actions): protein `#E07B54`, carbs `#E5B84B`, fat `#8E7FD1`, always next to the macro's name
- **Pastel tints** behind data: peach `#FCE6D9`, butter `#FBF0CF`, lilac `#ECE8FA`, sky `#E1EFF8` (e.g. a meal without a photo gets its slot's pastel)
- **Pressed states:** caramel `#D9902A`, ink `#2E5446`
- **Destructive actions only:** deep red label `#B0452E` on rose `#F9E3EA` (Sign out, Delete meal, Delete item, Remove from favorites, Delete account)

**Contrast (WCAG AA, checked):** ink on background 11.5:1, muted text on cards 5.9:1, muted on tint 4.9:1, ink on the caramel button 6.1:1; field borders `#7E9486` reach 3:1.

**Color rules**
- The accent always means "you can act here", never anything else (consistency, lecture 006).
- No red or green for food, totals or days. Food is never "good" or "bad" (D7).
- Errors use ink text, an icon and a soft tint, not alarm red. Red is kept for actions that delete or sign out, so it always means "this removes something".
- Never color alone: confidence, the selected day and errors always have an icon or a word too.

### Typography

Two fonts, as the lecture allows, served from the app itself:
- **Fraunces** (soft serif) for headings, dates and big numbers: the diary-book feel and a calm, trustworthy look.
- **Figtree** (sans-serif) for everything else: labels, buttons, item lists, forms.

**Scale (phone):** total range 32 px · screen titles 24–28 px · sections 18 px · body 16 px (also stops phones zooming into fields) · small text 14 px · captions 12 px.

**Rules:** left-aligned text, no long centered text, capitals only for tiny labels, tabular figures so numbers line up.

### Numbers

- Ranges with an en dash and the unit once: **650–850 kcal**.
- Calories rounded to 10, grams to 5. Totals can't look more precise than the estimate.
- In lists, numbers are right-aligned so they're easy to compare (lecture 007).
- Always "eaten", never "left" or "remaining".

### Shape, spacing, icons

- **Spacing:** a 4 px base (4, 8, 12, 16, 24, 32).
- **Corners:** 12 px for chips and inputs, 18 px for cards, pill buttons, 24 px for the top of bottom sheets.
- **Shadows** only on things that float: the "+" button, sheets and toasts.
- **Touch targets:** at least 44 × 44 px.
- **Icons:** Bootstrap Icons (outline), always with a label in navigation; by convention (camera, microphone, pencil = edit, trash = delete) and by metaphor (a book = Diary, a bitten cookie = Zalak).

### Logo

- **The bitten cookie:** golden, with cocoa chips and a scalloped bite, next to the lowercase wordmark **zalak** in Fraunces.
- **At small sizes** (the browser tab) the chips are dropped and the cookie becomes one simple shape, so it stays legible (icon legibility, lecture 007).
- **On the Analyzing screen** the cookie loses one bite per step: the logo doubles as the progress indicator.

## 2. Lecture 007 applied to the screens

**Choosing controls:**
- **Buttons:** caramel pill = main action, outlined pill = secondary, rose = destructive.
- **Stepper** for portions, **chips** for slots, details and quick answers, a **switch** for "Show lighter ideas", a **segmented control** for "Ask me / Best guess", Week / Month and activity level.
- **Bottom sheets** for quick choices: Add meal, unit, time, calendar, the slot's meals, "Keep this meal?".
- A **progress bar** for sign-up and for Analyzing.

**Gestalt:**
- **Proximity:** each food item's name, portion, calories and confidence sit together in one card, with space between items.
- **Similarity:** all meal slots look the same, and all confidence badges share one shape. Different things look different: actions are caramel, information is not.
- **Continuity:** the week strip and the diary pages read as one line of days.
- **Closure:** the next Recent card peeks in at the edge of the Add meal sheet, which shows there is more.
- **Common fate:** a bottom sheet slides up together with its content.

**Visual hierarchy** (what is seen first, second, third):
- **Result:** total range → short description → macros → items → actions.
- **Home:** the day's calories → macros → meal slots.

Hierarchy is set by size (Fraunces numbers), position (top), contrast (ink on white) and space.

**Readability:** users scan rather than read (lecture 007: only 20–28% of a page is read), so screens lead with headings and numbers, text is at most two short lines, and labels use plain words: "Log to lunch", not "Submit".

**Direct manipulation:** the portion stepper changes the kcal and macros on the same screen as you tap (continuous representation, fast reversible actions).

## 3. Prototyping (lecture 008)

### Representations

The lecture recommends a different form for each purpose: **sketches** for fast layout ideas, a **navigation map** (the sitemap in `05`), **high-fidelity screens** and a **clickable prototype** in Figma, and finally the **working app**, which reuses the prototype's colors and fonts directly (an evolutionary prototype).

### RAST (Rosson and Carroll)

- **Recipients:** the course team, friends who tried the prototype.
- **Aspects:** the checker flow (input → result → correct → log) and the navigation.
- **Situation:** early design, then high fidelity.
- **Technology:** Figma for the prototype; AI design tools only for ideas; Django for the app.

### Prototype type

- **Horizontal:** every main screen, clickable but shallow.
- **Vertical:** the checker in depth: all three inputs, Analyzing, the clarifying question, editing items, errors, and the guest sign-up on Log.

### Step 1: AI exploration (instead of low-fidelity wireframes)

Five AI design tools got the same style block and the same five screen prompts (Home, Add meal + Result, Diary, Statistics, Profile; kept in `dev/ai-design-prompts.md`). A fair comparison needs identical input. The results were compared on fixed criteria: **hierarchy** (is the total range seen first?), **affordances** (do items look editable, is the "+" obvious?), **tone** (no guilt framing), **accessibility** (contrast, touch sizes, labels) and **ideas** worth keeping.

- **v0:** the strongest. Kept: the diary page with photos, the calendar with dots on logged days, the inline question on an unsure item (A little / About that / A lot), "Add something Zalak missed", the slot dropdown, the two-page desktop diary. Dropped: a floating pill navigation that covers content.
- **Figma AI (Make):** kept the "AI estimate" tag on the photo and range labels on statistics bars; fixed future days drawn as eaten.
- **Claude Design:** kept the bottom bar with the "+" in the corner, the "Tell Zalak" correction field and the Profile structure.
- **Stitch, Uizard:** rejected (wordy, off-tone copy; no clear hierarchy).

This matches the lecture's warning: AI gives a fast average draft with no identity, so every kept idea was redrawn in Zalak's own design system. Low-fidelity wireframes were skipped on purpose, because the compared AI drafts already did their job.

### Step 2: High fidelity in Figma

- **File pages:** cover, foundations (color and type variables), components, mobile screens (390 × 844), desktop screens (1440), prototype.
- **Components with variants**, built with auto-layout: button, food item (sure / likely / unsure), meal slot (empty / filled / to finish), day pill, bottom sheet, bottom bar, input field with microphone.
- **Rounds of feedback** shaped the final screens: progressive disclosure on Edit item (units in a sheet), several meals per slot, the diary as a notebook with "Your meals" as a tab on its edge, the profile button on every main page, and the error, empty and guest states.
- **Informal test (lecture 009):** friends tried the clickable prototype, found it intuitive and liked it, so no changes were needed before building.

### Step 3: From prototype to app

The app follows the Figma frames. Where it differs, it is on purpose:
- **Added in the app:** "Re-estimate" on Edit item, "Use a photo instead" / "Type it instead" and a guest chooser, the "To finish" rows for drafts, the failed-step moment and "Still working" on the Analyzing screen, a typed amount on Edit item, "How to read this estimate" under every total, the "Where your meals go" card in Help, error pages for missing pages.
- **Changed after the heuristic evaluation** (`dev/audit.md`): Meal detail saves every change at once, so Figma's "Save changes" is gone (one save rule: Nielsen's consistency and error prevention); the Undo toast stays until it is closed (user control, WCAG 2.2.1).
- **Simplified:** Edit item has no "How it was cooked" row and no name suggestions; the amount stepper walks fractions itself (¼ ½ ¾ 1 1½ …) instead of separate chips; the time sheet changes only the time, not the day.
- **Not built from Figma:** water glasses, goals and targets, Customize statistics, dark mode (designed for Home and the Diary), page swipes in the Diary.
- **Accessibility pass:** checked with axe-core on 32 pages at 390 and 1440 px with no violations; targets raised to 44 px, except the phone week strip and the "Your meals" tab, which meet WCAG 2.2's 24 px.
