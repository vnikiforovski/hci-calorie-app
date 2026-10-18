# Zalak: Visual Design and Prototype

How Zalak looks (lecture 007, visual interface design) and how the design is prototyped (lecture 008, prototyping). The visual identity below is **v1**: the working direction, tested on real screens before it is final. The link to the final Figma prototype design is: https://www.figma.com/design/TAkknAZ98WZRCS6eSG2ULW/Zalak-Prototype?node-id=0-1&t=yoflVEZF4LBLSHyD-1

## 1. Visual identity v1: Sage & caramel

**Feel:** simple, clear, fresh, playful. Light mode by default; dark mode is an optional preference in Profile.

Chosen after comparing ten directions on the same Home and Result screens. It keeps the freshness of a green base and adds a warm caramel accent that matches the cookie logo, so app and logo read as one brand.

### Colors (60-30-10)

- **60% background:** `#F6F8F2` (sage white)
- **30% surfaces:** card `#FFFFFF`, tint `#E2ECDC` (soft sage), lines `#DCE5D5`
- **10% accent:** caramel `#F0A93B`, **only for actions**: the "+" button, Log, the selected step in sign-up
- **Text:** ink `#1E3A30` (deep green), muted `#56685E`
- **Water:** `#6FB0DA`, its own blue so it never competes with the accent
- **Logo:** cookie `#E9B66A`, chips `#5A3A24`
- **Dark mode:** background `#121A16`, card `#1B2620`, ink `#EAF1EA`, muted `#A9BAAE`, tint `#24332B`, accent `#F2B544`

**Color layer v1.1 (added in Figma after the first feedback, then toned down)**
- **Macro colors** (data only, never actions): protein `#E07B54`, carbs `#E5B84B`, fat `#8E7FD1`. Used in the macro split bar, the macro chips and the small accent bar on each macro card.
- **Pastel tints** for backgrounds behind data: peach `#FCE6D9`, butter `#FBF0CF`, lilac `#ECE8FA`, sky `#E1EFF8`. App chrome (icon tiles, option tiles) stays soft sage, so the screen does not get busy.
- **Diary paper:** page `#FFFCF4`, rules `#EDE6D3`, page edges `#E8DFC8`.
- **Pressed states:** caramel `#D9902A`, ink `#2E5446`. Every button has a pressed variant.
- **Destructive actions only:** deep red label `#B0452E` on rose `#F9E3EA` (Sign out, Delete meal, Delete item, Remove from favorites).
- All of these have dark-mode values in the Figma variables.

**Contrast (WCAG AA, checked):** ink on background 11.5:1, muted text on cards 5.9:1, muted on tint 4.9:1, ink on the caramel button 6.1:1. All above 4.5:1.

**Color rules**
- The accent always means "you can act here", never anything else (consistency, lecture 006).
- No red or green for food, totals or days. Food is never "good" or "bad" (D7).
- Errors use ink text, a warning icon and a soft caramel tint, not alarm red. Red is kept for actions that delete or sign out, so it always means "this removes something".
- Never color alone: confidence, selected day and errors always have an icon or word too.

### Typography

Two fonts, as the lecture allows:
- **Fraunces** (soft serif) for headings, dates and the big numbers. It gives the diary-book feel and a calm, trustworthy look.
- **Figtree** (sans-serif) for everything else: labels, buttons, item lists, forms.

**Scale (mobile):**
- total range: 32 px
- screen titles: 24 px
- sections: 18 px
- body: 16 px (also stops phones zooming into form fields)
- small text: 14 px
- captions: 12 px

**Rules:**
- left-aligned text
- no long centered text
- capitals only for tiny labels
- numbers use tabular figures so they line up

### Numbers

- Ranges with an en dash and the unit once: **650–850 kcal**.
- Calories rounded to 10, grams to 5. Totals can't look more precise than the estimate.
- In lists, numbers are right-aligned so they're easy to compare (lecture 007, sorting numbers).
- Always "eaten", never "left" or "remaining" unless the user switched targets on.

### Shape, spacing, icons

- **Spacing:** a 4 px base (4, 8, 12, 16, 24, 32).
- **Corners:** 12 px for chips and inputs, 18 px for cards, pill buttons, 24 px for the top of bottom sheets.
- **Shadows** only on things that float: the "+" button and bottom sheets.
- **Touch targets:** at least 44 × 44 px.
- **Icons:** Bootstrap Icons (outline), always with a label in navigation.
  - by convention: camera, microphone, pencil = edit, trash = delete
  - by metaphor: a book = Diary, a cookie with a bite = Zalak

### Logo

- **The bitten cookie:** golden, with cocoa chips and a scalloped bite, next to the lowercase wordmark **zalak** in Fraunces.
- **At small sizes** (browser tab, 24 px and below), the chips are dropped and the cookie becomes one simple shape, so it stays legible (icon legibility, lecture 007).
- **App icon:** the cookie on a deep green tile.
- **The final logo** is drawn in Figma. The bitten-"k" wordmark stays as an alternative.

## 2. Lecture 007 applied to the screens

**Choosing controls:**
- **Buttons:** caramel pill = main action, outlined pill = secondary.
- **Stepper** for portions, **chips** for units and quick answers, **toggles** for preferences.
- **Bottom sheets** for Add meal and Edit item.
- A **progress bar** for sign-up.

**Gestalt:**
- **Proximity:** each food item's name, portion, calories and confidence sit together in one card, with space between items.
- **Similarity:** all meal slots look the same, and all confidence badges share one shape. Different things look different: actions are caramel, information is not.
- **Continuity:** the week strip and the diary pages read as one continuous line of days.
- **Closure:** the week strip and the photo tips are cut off at the edge, which shows there is more to swipe.
- **Common fate:** a diary page turns as one piece, and a bottom sheet slides up together with its content.

**Visual hierarchy** (what is seen first, second, third):
- **Result:** total range → short description → macros → items → actions.
- **Home:** today's calories → macros and water → meal slots.

Hierarchy is set by size (Fraunces numbers), position (top), contrast (ink on white) and space.

**Readability:** users scan rather than read (lecture 007: only 20–28% of a page is read), so screens lead with headings and numbers. Text is at most two short lines, and labels use plain words: "Log to lunch", not "Submit".

**Direct manipulation:** portions are changed on the item itself, and the total updates at once (continuous representation, fast reversible actions).

## 3. Prototyping (lecture 008)

### Representations

The lecture recommends a different form for each purpose:
- **Sketches** on paper: fast layout ideas.
- **Storyboard:** six frames of Ana checking her canteen lunch, from opening "+" to "Logged to lunch".
- **Navigation map:** the sitemap in `05`.
- **Wireframes** in grayscale, then **high-fidelity screens** and the **clickable prototype** in Figma.

### RAST (Rosson and Carroll)

- **Recipients:** the course team and the usability-test participants.
- **Aspects:** the checker flow (input → result → correct → log) and the navigation.
- **Situation:** early design, so low fidelity first, then high fidelity.
- **Technology:** Figma for the prototype; AI tools only for ideas.

### Prototype type

- **Horizontal:** every main screen, clickable but shallow.
- **Vertical:** the checker in depth: all three inputs, analyzing, a clarifying question, editing items, errors, and guest sign-up on Log.

The Figma colors and fonts become CSS variables that override Bootstrap's defaults. The design system then carries straight into the Django app, which makes the prototype partly evolutionary.

### Step 1: Low fidelity

Grayscale Figma wireframes of eight screens: Home, Add meal, Text and voice, Photo, Analyzing, Result, Edit item, Diary page.

Test them with 2–3 people using the test tasks in `03`, before any color. As the lecture warns, people trust polished designs too early, so problems are cheaper to find now.

### Step 2: AI exploration

**Same prompt, same five screens, every tool:**
- Google Stitch
- v0
- Uizard
- Figma AI (Make)
- Claude Design
- Visily, if time allows

A fair comparison needs identical input.

**Criteria for comparing the results:**
- **Hierarchy:** is the total range seen first?
- **Affordances:** do items look editable, and is the "+" obvious?
- **Tone:** no guilt framing, colors used correctly.
- **Accessibility:** contrast, touch sizes, icons with labels.
- **Ideas:** something worth keeping.

We keep layouts and ideas, not a tool's style. The lecture warns that AI produces average UI with no brand identity, so the identity always comes from section 1.

### AI exploration results

All five tools got the same style block and screen prompts. Screenshots are in `competitor screenshots`.

- **v0:** the strongest overall. **Kept:**
  - the diary page as a 2×2 photo grid with binding dots and "Page 13 of 31"
  - the calendar pop-up with dots on logged days
  - the inline question on an unsure item ("How much do you think? A little / About that / A lot")
  - "Add something Zalak missed"
  - the meal-slot dropdown
  - the desktop two-page diary with a side summary

  **Dropped:** the floating pill navigation, because it covers content.
- **Figma AI (Make):** very close to our direction. **Kept:**
  - the "AI estimate" tag on the photo
  - confidence badges with an item count
  - the warm book cover
  - range labels on statistics bars

  **Fixed:** future days drawn as eaten in statistics, and a legend that didn't line up with the meal bar.
- **Claude Design:** the reference build of all five screens. Kept the bar with the "+" in the corner, the "Tell Zalak" correction field, and the Profile structure.
- **Stitch:** rejected. Wordy, off-tone copy ("nourishment", "mindful note"), busy layout.
- **Uizard:** rejected. Generic layout with no clear hierarchy.

This confirms the lecture's point that AI gives a fast average draft. Every kept idea was re-drawn in our own design system.

**Low-fidelity step:** skipped on purpose. The five AI tools already gave many layout options for the main screens, and these were compared against fixed criteria, which is the job wireframes would have done. Screens without an AI draft (sign-up, Analyzing, errors, settings pages) are designed directly from the components.

### Step 3: High fidelity in Figma

**File pages:**
- Cover
- Foundations: color and type variables, light and dark
- Components
- Wireframes
- Mobile screens (390 × 844)
- Desktop screens (1440)
- Prototype

**Components with variants**, all built with auto-layout:
- button: primary / secondary / disabled
- food item: sure / likely / unsure
- meal slot: empty / filled / to finish
- day pill: default / selected / today
- bottom sheet
- bottom bar
- input field with microphone

**Prototype flows:**
1. Check and log a meal (photo + note).
2. Correct a portion and replace an item.
3. Guest check → Log → sign-up → logged.
4. Turn diary pages and jump with the calendar.
5. Re-log a favorite from Your meals.

**What is built and wired (October 2026).** No wireframes: we went straight from the AI exploration to high fidelity.
- **Screens:** Home, Home · Logged (with toast), Add meal sheet, Photo · Camera, photo tips 1–3, Add a note, Text and voice (empty and listening), Analyzing 1–3, Result, Edit item, Diary · Today, Diary · Yesterday, Diary · Your meals, Meal detail, Saved meal, Statistics, Customize, Profile, Preferences.
- **Edit item:** food name with suggestions, amount stepper with quick fractions (¼ to 3), units grouped as Weight (g, kg, oz, lb), Volume (ml, l, cup, fl oz), Kitchen (tsp, tbsp, handful, pinch) and Portion (piece, slice, bowl, plate, serving), bowl size, how it was cooked, the gram equivalent and a live kcal and macro preview.
- **Diary as a book:** the order is … yesterday ← today → Your meals (the back of the book). Every new day becomes a page between today and Your meals. Pages turn with the page arrows (push animation); the ribbon always opens Your meals.
- **Meal detail:** opened from a diary entry or a Home slot. The time can be changed and defaults to the time the meal was logged. Actions: Save changes, Log again, Delete meal, and a heart to save it.
- **Interactivity:**
  - Buttons and toggles change state when pressed.
  - The loading screens advance on their own: 1.2 s, 1.2 s, then 1 s to Result.
  - Toasts confirm actions and close after 2.5 s.
  - Bottom bars and action bars stay fixed while scrolling.
- **Flow starting points in Figma:** 1 Main app, 2 First launch and sign-up, 3 Log a meal, 4 Diary, 5 Profile.

**Round 3 changes (after the second feedback)**
- **Edit item uses progressive disclosure** (the same lesson as the first Profile page): only the food, the amount stepper and two rows are shown. Units open in a sheet with four tabs (Portion, Weight, Volume, Kitchen), cooking opens in its own sheet, and nutrition is a collapsed card that expands.
- **More than one meal per slot:** slots are categories, not single meals. Home adds them up ("Snack · 2 meals · 200–270") and tapping the slot opens a sheet with each meal. The Diary lists every meal separately by its time, so the page just gets longer.
- **Diary notebook:** white pages with sage rules, Figtree for times and notes (no more italic serif), polaroid photos kept. Your meals is an index tab on the edge of the book, visible on every page, because it belongs to the divider at the back. The ribbon only marks today.
- **Profile everywhere:** Diary and Statistics headers have the profile button, like Home.
- **Add meal:** colored option cards (peach, sky, lilac), meal slot chips with icons, and recent meals as photo cards with "Log again" instead of plus buttons.
- **New screens:** Welcome, Sign in, Create account (2 steps), Personal details, Goals and targets, Account and privacy, the My meals tab, Statistics for last week, and the Mon 12 and Tue 13 diary pages. New sheets: meal slot, meal time, jump to a date, unit, how it was cooked, and the snack slot.
- **Final round:** error and empty states (no food found in the photo, offline with the meal saved for later, Home on the first day), the guest flow (check a meal without an account → "Keep this meal?" → sign-up), dark mode (Home and Diary), and desktop at 1440 (Home in two columns, Diary as an open two-page spread). Sign-up now ends on the first-day Home.
- **Usability test (lecture 009):** friends tried the prototype. They liked the app and found it intuitive, so no changes were needed before building.
- **Interactive components:** meal slot picker, choice chips, favorite heart, water glasses (tap to add a glass), checkbox, amount stepper with live kcal, nutrition card, unit tabs, cooking options, and toggles.

## 4. Prompt for the AI design tools

Each tool gets the **style block** plus **one screen prompt** per request (style block + screen 1, then style block + screen 2, and so on). Sign-up, settings subpages and error states are designed directly in Figma, because they reuse the same patterns.

```text
STYLE BLOCK
Design a mobile web app called "Zalak" (Macedonian for "a bite"): an AI meal
calorie checker. The user photographs or describes a meal; the AI estimates
calories and macros as ranges; the user corrects anything wrong and logs it.
Feel: simple, clear, fresh, playful. Light mode. Phone frame 390x844.
Colors: background #F6F8F2 (sage white), cards #FFFFFF, soft tint #E2ECDC,
text #1E3A30 (deep green), secondary text #56685E, accent caramel #F0A93B used
ONLY for primary actions, water #6FB0DA.
Fonts: Fraunces (soft serif) for headings and big numbers, Figtree for all
other text. Rounded cards (18px), pill buttons, bottom sheets, outline icons
with labels, generous white space, no gradients.
Rules: calories are always ranges ("650-850 kcal") and always "eaten", never
"left" or "remaining". No red or green for food, no scores, no streaks.
Logo: a golden cookie with a bite taken out, next to the word "zalak".
Bottom bar: Home, Diary, Statistics, and a raised caramel "+" button in the
bottom-right corner.
```

```text
SCREEN 1: HOME
Top: logo left, round profile icon right. Below: a 7-day week strip
(Mo 12 to Su 18), Thursday 15 selected as a dark pill. A large card "Eaten
today: 1,110-1,390 kcal" with a thin bar split by meal. Three small cards:
Protein 62-74 g, Carbs 150-175 g, Fat 45-55 g. A water row with 8 small
glasses, 5 filled. Then meal slots Breakfast, Lunch, Snack, Dinner: each with
a small food photo, a one-line description, a kcal range and a "+" button.
Dinner is empty: "Nothing yet".
```

```text
SCREEN 2: ADD MEAL AND RESULT
(a) A bottom sheet over Home titled "Add to lunch" with three large options:
"Photo", "Text and voice", "Your meals", and a short "Recent" list below.
(b) The result screen: meal photo at the top; "Lunch"; title "Tavče gravče
with bread and salad"; the total "650-850 kcal" as the largest element; one
neutral line "A filling lunch with good protein and fibre"; macro chips.
Then a list of food items, each with name, portion ("1 bowl · 300 g"),
kcal range, a pencil icon, and a confidence badge with icon and word: Sure,
Likely or Unsure. "Cooking oil" is Unsure with the reason "Oil is hard to see
in a photo". Fixed at the bottom: an outlined "Just checking" button and a
caramel "Log to lunch" button, plus the small text "Estimate, not medical
advice".
```

```text
SCREEN 3: DIARY AS A BOOK
The diary looks like an open notebook: one page per day, swiped like a book.
The page shows the date in Fraunces ("Tuesday, 13 October"), the day's meals
as photo cards with time, name and kcal range, and the day's total at the
bottom. Small arrows to turn pages and a calendar icon to jump to a date.
A "Your meals" tab like a bookmark ribbon on the side of the book.
Also show a desktop version (1440 wide) with two pages side by side.
```

```text
SCREEN 4: STATISTICS
Title "Statistics" with a Week / Month switch (Week selected) and the dates
"12-18 October". A bar chart of calories eaten per day, each bar showing the
estimated range (a solid part and a lighter top part); no target line, no red
or green days. Under it: "On average 1,450-1,700 kcal a day". A card with the
average macro split as one stacked bar (protein, carbs, fat) with grams. A
water card: "On average 6 of 8 glasses". A "Most logged" list with three meals
and how often they were logged. A small "Customize" button at the top right to
turn cards on or off. Calm and neutral: it shows patterns, it never judges.
```

```text
SCREEN 5: PROFILE
Top: round avatar, name "Viktor", e-mail. Grouped list sections with simple
row items and chevrons:
- Personal data: height, weight, activity level
- Preferences: "When Zalak is unsure" with a two-option switch "Ask me" /
  "Best guess"; food preferences as chips (e.g. "Vegetarian", "Macedonian
  cuisine"); toggle "Show lighter ideas"; "Meal slots"; toggle "Dark mode"
- Goals and targets: a toggle "Show daily targets" (off by default) with a
  short note "Optional. Zalak works fine without targets."
- Water: "8 glasses a day"
- Your meals: "12 saved"
- Account: change password, sign out, delete account
Footer note: "Zalak gives estimates, not medical advice."
```
