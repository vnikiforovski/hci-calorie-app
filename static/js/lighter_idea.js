// The × on Result's lighter idea: hide it with fetch, so the page and the scroll stay.
// The server answers 204; the card goes and the focus moves to the meal's name, so it isn't lost.
// If fetch fails, the form posts the normal way (the server hides it and shows Result again).
document.querySelectorAll('[data-lighter-hide]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
        event.preventDefault();
        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {'X-Requested-With': 'fetch'},
            credentials: 'same-origin',
        }).then(function (response) {
            if (response.status !== 204) {
                throw new Error('status ' + response.status);
            }
            var card = form.closest('[data-lighter-idea]');
            var heading = document.querySelector('.z-summary h1');
            card.remove();
            if (heading) {
                heading.setAttribute('tabindex', '-1');
                heading.focus();
            }
        }).catch(function () {
            form.submit();
        });
    });
});
