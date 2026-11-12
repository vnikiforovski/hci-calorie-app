// Profile · Preferences: a tap on Ask me / Best guess, or on the "Show lighter ideas" switch,
// saves straight away, as in Figma (no Save button). fetch sends the whole form; the page
// stays, so the keyboard focus stays on the choice. Without JavaScript the <noscript> Save button posts it.
document.querySelectorAll('[data-preferences]').forEach(function (form) {
    var status = form.querySelector('[data-status]');
    var saved = form.querySelector('input[type="radio"]:checked');

    function showLine(value) {
        form.querySelectorAll('[data-when]').forEach(function (line) {
            line.hidden = line.getAttribute('data-when') !== value;
        });
    }

    form.addEventListener('change', function (event) {
        var input = event.target;
        if (input.type === 'radio') {
            showLine(input.value);
        }
        status.textContent = 'Saving…';
        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {'X-Requested-With': 'fetch'},
            credentials: 'same-origin',
        }).then(function (response) {
            if (!response.ok) {
                throw new Error('status ' + response.status);
            }
            if (input.type === 'radio') {
                saved = input;
            }
            status.textContent = 'Saved';
        }).catch(function () {
            // Put the old choice back, so the screen shows what is really saved
            if (input.type === 'checkbox') {
                input.checked = !input.checked;
            } else if (saved) {
                saved.checked = true;
                showLine(saved.value);
            }
            status.textContent = "Couldn't save. Check your connection and try again.";
        });
    });
});
