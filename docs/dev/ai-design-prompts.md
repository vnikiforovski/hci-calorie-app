# Zalak: prompts for the AI design tools

Used in the AI exploration step of the prototype (docs/06, section 3). Kept here as a record; the app does not use it.

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
