// The slot dropdown on Result and Meal detail (templates/meals/_slot_dropdown.html). Picking a slot
// updates the hidden input (sent by Log on Result, by Save changes on Meal detail), the pill and,
// on Result, the "Log to ..." button. Bootstrap opens and closes the menu.
var slotOptions = document.querySelectorAll('.z-slot-option');
var logSlotLabel = document.getElementById('logSlotLabel');   // only on Result

slotOptions.forEach(function (option) {
    option.addEventListener('click', function () {
        document.getElementById('slotInput').value = option.dataset.value;
        document.getElementById('slotIcon').className = 'bi ' + option.dataset.icon;
        document.getElementById('slotLabel').textContent = option.dataset.label;
        if (logSlotLabel) logSlotLabel.textContent = option.dataset.value;

        slotOptions.forEach(function (other) {
            other.classList.toggle('active', other === option);
            other.removeAttribute('aria-current');
        });
        option.setAttribute('aria-current', 'true');
    });
});
