// Toast (templates/meals/_toast.html). HCI idea 4, "an Undo that waits":
// - With Undo it stays until the × (or Escape) closes it, or the next page replaces it. A timer that
//   takes Undo away while someone is still reading or tabbing to it is not fair (WCAG 2.2.1).
// - Without Undo it only confirms ("Changes saved"), so it closes by itself after 2.5 s (docs/06),
//   and waits while the pointer or the keyboard focus is on it.
// Wrapped in its own function so its names stay private (see analyzing.js).
(function () {
    var toast = document.getElementById('toast');
    if (!toast) return;

    var hasUndo = toast.hasAttribute('data-undo');
    var timer = null;

    function hide() {
        clearTimeout(timer);
        toast.classList.add('is-hiding');
        // Removed after the fade (or at once when reduced motion turns the fade off)
        setTimeout(function () { toast.hidden = true; }, 300);
    }

    function start() {
        if (hasUndo) return;
        clearTimeout(timer);
        timer = setTimeout(hide, 2500);
    }

    toast.querySelector('[data-toast-close]').addEventListener('click', hide);
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && !toast.hidden && !document.querySelector('.offcanvas.show')) hide();
    });
    toast.addEventListener('mouseenter', function () { clearTimeout(timer); });
    toast.addEventListener('mouseleave', start);
    toast.addEventListener('focusin', function () { clearTimeout(timer); });
    toast.addEventListener('focusout', start);
    start();
})();
