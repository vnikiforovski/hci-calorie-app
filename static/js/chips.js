// Text and voice: Analyze stays disabled while the field is empty (docs/05, Constraints),
// and the detail chips add a short prompt such as "portion: " for the user to finish.
var mealText = document.querySelector('#textMealForm textarea[name="text"]');
var analyzeButton = document.getElementById('analyzeButton');

function updateAnalyze() {
    analyzeButton.disabled = mealText.value.trim() === '';
}

document.querySelectorAll('.z-chip[data-insert]').forEach(function (chip) {
    chip.addEventListener('click', function () {
        var text = mealText.value.trimEnd();
        if (text !== '' && !text.endsWith(',')) {
            text += ',';
        }
        mealText.value = (text === '' ? '' : text + ' ') + chip.dataset.insert;
        mealText.focus();
        mealText.setSelectionRange(mealText.value.length, mealText.value.length);
        updateAnalyze();
    });
});

mealText.addEventListener('input', updateAnalyze);
updateAnalyze();
