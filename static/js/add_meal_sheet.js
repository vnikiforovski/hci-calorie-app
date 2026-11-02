// Add meal sheet (chunk 14, templates/meals/_add_meal_sheet.html).
// A slot's "+" (data-slot="dinner") opens the sheet with that slot chosen; the corner "+" opens it
// with the slot from the time and the "picked from the time" hint. Choosing a chip updates
// "Add to …". The slot itself travels in the form (a radio), so this file only keeps the words in step.
(function () {
    const sheet = document.getElementById('addMealSheet');
    if (!sheet) return;

    const label = sheet.querySelector('[data-add-slot-label]');
    const hint = document.getElementById('addSlotHint');   // missing on a past day
    const radios = sheet.querySelectorAll('input[name="slot"]');

    function choose(slot, fromTime) {
        radios.forEach(function (radio) { radio.checked = radio.value === slot; });
        label.textContent = slot;
        if (hint) hint.hidden = !fromTime;
    }

    // Bootstrap passes the button that opened the sheet as relatedTarget
    sheet.addEventListener('show.bs.offcanvas', function (event) {
        const slot = event.relatedTarget && event.relatedTarget.dataset.slot;
        choose(slot || sheet.dataset.defaultSlot, !slot);
    });

    radios.forEach(function (radio) {
        radio.addEventListener('change', function () { choose(radio.value, false); });
    });
})();
