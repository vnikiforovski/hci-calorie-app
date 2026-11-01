// Detail chips under a text field ("portion: " on Text and voice, "cooked in oil" under a photo):
// a chip adds its words to the field of its own form for the user to finish.
// On a form marked data-require-text (Text and voice), Analyze stays disabled while the field
// is empty (docs/05, Constraints); under a photo the note is optional, so Analyze is always on.
document.querySelectorAll('.z-chip[data-insert]').forEach(function (chip) {
    var field = chip.form.querySelector('textarea');
    chip.addEventListener('click', function () {
        var text = field.value.trimEnd();
        if (text !== '' && !text.endsWith(',')) {
            text += ',';
        }
        field.value = (text === '' ? '' : text + ' ') + chip.dataset.insert;
        field.focus();
        field.setSelectionRange(field.value.length, field.value.length);
        field.dispatchEvent(new Event('input'));   // the Analyze rule below (and voice.js) notice it
    });
});

document.querySelectorAll('form[data-require-text]').forEach(function (form) {
    var field = form.querySelector('textarea');
    var analyzeButton = form.querySelector('[type="submit"]');

    function updateAnalyze() {
        analyzeButton.disabled = field.value.trim() === '';
    }

    field.addEventListener('input', updateAnalyze);
    updateAnalyze();
});
