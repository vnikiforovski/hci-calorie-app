// "Jump to a date" on Home and in the Diary (chunks 14, 16). Its ‹ › reload the page with ?month=…, which closes the sheet;
// the template marks it data-open-on-load then, and this opens it again where the user was.
(function () {
    const sheet = document.querySelector('#dateSheet[data-open-on-load]');
    if (sheet) bootstrap.Offcanvas.getOrCreateInstance(sheet).show();
})();
