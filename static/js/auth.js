// Account pages (chunk 12): Sign in, Create account 1 and 2.
// 1. The eye button shows or hides the password.
// 2. The "At least 8 characters" hint gets a tick while typing.
// 3. A field's error message goes away once you change that field.
// 4. A second tap doesn't send the form twice, and the button says what is happening.

// 1. Show / hide password. aria-pressed tells screen readers the state; the label stays "Show password".
document.querySelectorAll('[data-password-toggle]').forEach(function (button) {
    var input = document.getElementById(button.getAttribute('aria-controls'));
    var icon = button.querySelector('i');

    button.addEventListener('click', function () {
        var show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        button.setAttribute('aria-pressed', show ? 'true' : 'false');
        icon.className = show ? 'bi bi-eye-slash' : 'bi bi-eye';
        input.focus();   // keep typing where you were
    });
});

// 2. Live tick on the length hint (the server still checks everything else)
document.querySelectorAll('[data-min-length]').forEach(function (hint) {
    var input = document.getElementById(hint.getAttribute('data-for'));
    var min = parseInt(hint.getAttribute('data-min-length'), 10);
    var icon = hint.querySelector('i');

    function update() {
        var met = input.value.length >= min;
        hint.classList.toggle('is-met', met);
        icon.className = met ? 'bi bi-check-circle-fill' : 'bi bi-circle';
    }

    input.addEventListener('input', update);
    update();
});

// 3. Django marks a field with an error aria-invalid="true" and its message has the id
// "id_<name>_error". Once the field is changed the message is out of date, so it goes;
// the server checks again on submit.
document.querySelectorAll('form[data-auth-form] [aria-invalid="true"]').forEach(function (field) {
    var eventName = (field.type === 'checkbox' || field.type === 'radio') ? 'change' : 'input';
    field.addEventListener(eventName, function () {
        field.form.querySelectorAll('[name="' + field.name + '"]').forEach(function (same) {
            same.removeAttribute('aria-invalid');
        });
        var error = document.getElementById('id_' + field.name + '_error');
        if (error) {
            error.hidden = true;
        }
    }, { once: true });
});

// 4. Send once. The button isn't disabled: a disabled button's name (e.g. "skip") would not be sent.
document.querySelectorAll('form[data-auth-form]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
        if (form.hasAttribute('data-sending')) {
            event.preventDefault();
            return;
        }
        form.setAttribute('data-sending', '');

        var button = event.submitter;
        if (button && button.hasAttribute('data-busy-text')) {
            button.setAttribute('data-idle-text', button.textContent);
            button.textContent = button.getAttribute('data-busy-text');
            button.setAttribute('aria-disabled', 'true');
        }
    });
});

// Back from the next page (the browser may restore this page as it was): ready to send again
window.addEventListener('pageshow', function (event) {
    if (!event.persisted) {
        return;
    }
    document.querySelectorAll('form[data-sending]').forEach(function (form) {
        form.removeAttribute('data-sending');
        form.querySelectorAll('[data-idle-text]').forEach(function (button) {
            button.textContent = button.getAttribute('data-idle-text');
            button.removeAttribute('aria-disabled');
        });
    });
});
