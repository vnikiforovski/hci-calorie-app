// Add meal sheet (chunk 14, templates/meals/_add_meal_sheet.html).
// The button that opens the sheet can choose for it:
//   data-slot="dinner"                      a slot's "+" (Home), "Add another snack", "Tap to add it" (Diary)
//   data-day="2026-11-01" data-day-label="Sun 1"   "Add a meal to this day" (Diary); data-day="" means today
// Without them the sheet uses the page's defaults: the slot from the time and, on a past day of Home or
// the Diary, that day. The "picked from the time" hint shows only when the clock really chose the slot.
// The slot and day travel in the form (a radio and a hidden input); this file keeps the words in step.
// Recent (chunk 22): each card is its own POST form, so the slot and day are copied into its hidden
// inputs too. Without JavaScript they keep the page's defaults.
(function () {
    const sheet = document.getElementById('addMealSheet');
    if (!sheet) return;

    const slotLabel = sheet.querySelector('[data-add-slot-label]');
    const dayLabel = sheet.querySelector('[data-add-day-label]');
    const dayInput = sheet.querySelector('input[name="day"]');
    const hint = document.getElementById('addSlotHint');
    const radios = sheet.querySelectorAll('input[name="slot"]');

    const recentSlots = sheet.querySelectorAll('[data-recent-slot]');
    const recentDays = sheet.querySelectorAll('[data-recent-day]');

    function choose(slot, fromTime) {
        radios.forEach(function (radio) { radio.checked = radio.value === slot; });
        recentSlots.forEach(function (input) { input.value = slot; });
        slotLabel.textContent = slot;
        hint.hidden = !fromTime || dayInput.value !== '';
    }

    function setDay(day, label) {
        dayInput.value = day;
        recentDays.forEach(function (input) { input.value = day; });
        dayLabel.textContent = day ? ' · ' + label : '';
    }

    // Bootstrap passes the button that opened the sheet as relatedTarget
    sheet.addEventListener('show.bs.offcanvas', function (event) {
        const trigger = event.relatedTarget ? event.relatedTarget.dataset : {};
        if ('day' in trigger) setDay(trigger.day, trigger.dayLabel || '');
        else setDay(sheet.dataset.defaultDay, sheet.dataset.defaultDayLabel);
        choose(trigger.slot || sheet.dataset.defaultSlot, !trigger.slot);
    });

    radios.forEach(function (radio) {
        radio.addEventListener('change', function () { choose(radio.value, false); });
    });
})();
