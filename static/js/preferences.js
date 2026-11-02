// Profile · Preferences (chunk 18): a tap on Ask me / Best guess saves straight away, as in Figma
// (no Save button). fetch sends the form; the page stays, so the keyboard focus stays on the choice.
// Without JavaScript the <noscript> Save button posts the form the normal way.
document.querySelectorAll('[data-preferences]').forEach(function (form) {
    var status = form.querySelector('[data-status]');
    var saved = form.querySelector('input[type="radio"]:checked');

    function showLine(value) {
        form.querySelectorAll('[data-when]').forEach(function (line) {
            line.hidden = line.getAttribute('data-when') !== value;
        });
    }

    form.addEventListener('change', function (event) {
        var radio = event.target;
        showLine(radio.value);
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
            saved = radio;
            status.textContent = 'Saved';
        }).catch(function () {
            // Put the old choice back, so the screen shows what is really saved
            if (saved) {
                saved.checked = true;
                showLine(saved.value);
            }
            status.textContent = "Couldn't save. Check your connection and try again.";
        });
    });
});
