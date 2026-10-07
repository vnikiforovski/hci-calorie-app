# Problem Analysis

## 0. Brainstorming (from the intro lecture)

- We want the app to be interactive
- We want the app to be fast
- We want the app to be usable and look good
- We want the design to be user-centered, the user is the most important. We have to think about the primary and secondary (indirect) users.
- We have to think about the individual differences between the users (cognitive, age, physical, culture)
- We have to also focus on the activities, or what the user wants to do with the app. We have to define the simple tasks, the more complex ones, but also if there are collaborative and time critical activities in the app.
- We have to look at the context, or to think about the environment the app could be used in. That could be the physical context (at restaurants, at home...), time context (day/night, time constraints...), social (alone or in a group), cognitive (the level of attention needed, or stress) and technological context (the device, internet connection).
- We have to understand the difference between the UI and UX and try to make them the best we can.
- We have to define the UI, the input and output. We want the UI to be easy to use.
- We will have to have notifications or visual indications that help users understand what is happening.
- We can maybe make an UX analysis at the end.
- We have to always think if any new feature or the whole app creates value and solves the problem that this app is made to solve.
- We should also have a few alternative design ideas
- We have to think what users want to get done, not what the technology can do.
- We should also think about security and what wrong usage of the app could mean and how to make it not confuse the users.

Where AI can be used: 

- Research and analysis: analyzing and creating user surveys, interviews; generating user scenarios, interviews; 
- Generating ideas and concepts: creating user stories, suggesting functionalities, user journeys
- UI/UX design: proposed interface designs, generating test-scenarios, translations
- Prototyping and development: generating code (HTML, CSS, JS, BootStrap, Django, Python), proposed visual components

## 1. PACT Analysis

### 1.1 People
- **Physical differences:** Accessibility settings, W3C Web Content Accessibility Guidelines (WCAG), Wave for accessibility, vision, haptics, audio output chime or click, place to enable/disable audio, Fitts' Law, different app feeling based on sex on login?, caution about diabetes or other food related complications and sicknesses, like allergies or cultural restrictions maybe like warnings if the input food can have food ingredients that people shouldn't have, or for anorexia or obese people, next the age of the user, bmi, heigh, weight, physical activity, homogeneous or heterogeneous users?, Ergonomics for the UI buttons and stuff, the size of the UI elements, 
- **Psychological differences:** The app should be simple enough so that people could learn it easy and use it for it's main purpose and not use their own memory, so we should keep records of the food recorded or maybe their goals too, and also have encouraging messages and messages that lower their stress and give motivation,
- **Social differences:** We should also take in account the social differences like cultural, but also their familiarity with using apps like this,  place where people can learn more about calories and micronutrients like interesting facts that can be enabled/disabled maybe based on experience level, tutorials for how to use the app? The app will be in English and maybe some more languages if we have time.

I think the users are a heterogeneous group. There could be people wanting to lose weight, people into fitness, casual users, people with health problems, old people, athletes. We want to make the app so that users return to it every day and use it as their journal. There should be numbers, but also descriptions based on the numbers that blunt the effect of just numbers and maybe propose healthier alternatives.

### 1.2 Activities
- **Purpose:** I think the purpose is for users to use it as their journal for their diet. Many people would use it to check the food before they have it or just document what they have had that day. We can also have a part for water intake and liquid calories too.
- **Time aspects** (frequency, time pressure, interruptions, response time): every meal they have, and if there is time pressure like eating at a restaurant or choosing what to order for take away it should be fast and simple and mostly use photos as input, but also they could input the meals at the end of the day when they have more time. I think while documenting the meals users should be able to finish it later and maybe just take a photo or type the meal name fast and take care of the details and confirm the finished input later. It should be as fast as possible having in consideration that this is a student project that won't go in deployment, and we are probably going to use Claude API so that will increase the time. 
- **Cooperation:** I think most users would use it on their own, but maybe also have capabilities for having a personal helper or trainer or doctor that also has access to the account and leaves notes.
- **Complexity** (well-defined or not?): I think that we will probably make a mobile app that will have a photo camera input as the main input and voice input and also a text input like a way to correct any missing ingredients or as input as well for when you want to go in detail with everything and also a desktop app that will be more like a place where you can see the details and input photos as imports. Have like a calendar with every day documented, dashboard, trends and a personalized profile with favorite meals for quick input. Weekly history and goals and streaks. It will be done so that you can differentiate the different inputs easily. And every input will go to a place where you can check everything before submitting. 
- **Safety-critical / errors:** I think the safety isn't that important, but we should think about the impact the result could have on the people and how to blunt it. If users make a mistake they should be able to go back easily. And also have warnings for allergies and other health problems.
- **Nature of content:** I think the input should be camera, photos, voice and text. The data will be saved and also the calories and micronutrients too. 

### 1.3 Context
- **Physical:** Everywhere, at restaurants, at home...?
- **Social:** No social context
- **Organizational:** The app is for the users, so payment or any other monetization ways for us could be advertisements or maybe a small subscription for the app will decide from the competitors analysis.

### 1.4 Technologies
- **Input:** Phone camera, voice, text, computer file for photos, keyboard for text and maybe microphone for voice.
- **Output:** Phone and Computer monitor screens. Maybe a small haptic or chime when an output is done. Maybe some notifications too.
- **Communication:** Said it before. The app should be fast and the user should correct the output if needed.
- **Content:** Saved meals and calories and micronutrient data.

### 1.5 Key design implications
_(filled in after review)_

## Bonus: open questions and notes
- Is the app going to be for mobile, desktop or both? I think both if time allows.
- How will the processing of the calories and micro nutrients be done? Using the Claude API or is there a smarter way?
- I want to implement all the input methods: text, photo and speech. How will they all be done?
- Maybe have a haptic feedback output for something
- Personalized interface
- Suggestions and recommendations in the app from an LLM?
- Human-in-the-loop, Trust calibration and clear AI boundaries
- An LLM can make the PACT analysis and complete this analysis.
- The calories and micronutrients output should be a range.