// Every POST form is sent once: a double tap on Log, Just checking, Delete or Undo must not send the
// action twice (the second answer used to be an error page). The server also copes with a second
// request; this keeps it from being sent at all.
// Left alone: the account forms (auth.js does the same and changes the button's words) and the forms
// with the Analyzing overlay (analyzing.js disables their button, and Cancel must allow another try).
// The listener is on the document, so it runs after a form's own listeners: a send that another
// script stopped (an empty Add item field, the lighter idea's fetch) doesn't count.
(function () {
    var ONCE = 'form[method="post"]:not([data-auth-form]):not([data-analyzing])';

    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (event.defaultPrevented || !form.matches(ONCE)) {
            return;
        }
        if (form.hasAttribute('data-sent')) {
            event.preventDefault();
            return;
        }
        form.setAttribute('data-sent', '');
    });

    // Back from the next page (the browser may restore this page as it was): ready to send again
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            document.querySelectorAll('form[data-sent]').forEach(function (form) {
                form.removeAttribute('data-sent');
            });
        }
    });
})();
