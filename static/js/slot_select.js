// Result: the slot dropdown. Picking a slot updates the hidden input (submitted by Log in chunk 9),
// the pill and the "Log to ..." button. Bootstrap opens and closes the menu.
var slotOptions = document.querySelectorAll('.z-slot-option');

slotOptions.forEach(function (option) {
    option.addEventListener('click', function () {
        document.getElementById('slotInput').value = option.dataset.value;
        document.getElementById('slotIcon').className = 'bi ' + option.dataset.icon;
        document.getElementById('slotLabel').textContent = option.dataset.label;
        document.getElementById('logSlotLabel').textContent = option.dataset.value;

        slotOptions.forEach(function (other) {
            other.classList.toggle('active', other === option);
            other.removeAttribute('aria-current');
        });
        option.setAttribute('aria-current', 'true');
    });
});
