// Toast (templates/meals/_toast.html): closes by itself, 5 s when it offers Undo
// (docs/05: time to reach Undo) and 2.5 s otherwise (docs/06).
// While the pointer or keyboard focus is on it, it waits, so Undo can't vanish under a finger.
// Wrapped in its own function so its names stay private (see analyzing.js).
(function () {
    var toast = document.getElementById('toast');

    if (toast) {
        var delay = toast.hasAttribute('data-undo') ? 5000 : 2500;
        var timer = null;

        function hide() {
            toast.classList.add('is-hiding');
            // Removed after the fade (or at once when reduced motion turns the fade off)
            setTimeout(function () { toast.hidden = true; }, 300);
        }

        function start() {
            clearTimeout(timer);
            timer = setTimeout(hide, delay);
        }

        function pause() {
            clearTimeout(timer);
        }

        toast.addEventListener('mouseenter', pause);
        toast.addEventListener('mouseleave', start);
        toast.addEventListener('focusin', pause);
        toast.addEventListener('focusout', start);
        start();
    }
})();
