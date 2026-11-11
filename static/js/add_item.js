// Result: "Add something Zalak missed". Add stays off while the field is empty (like Analyze),
// and while Zalak answers (1-2 s) the button shows a spinner and the field can't change.
// Wrapped in its own function so its names stay private (see analyzing.js).
(function () {
    var addForm = document.getElementById('add-item');

    if (addForm) {
        var addField = addForm.querySelector('input[name="name"]');
        var addButton = addForm.querySelector('button[type="submit"]');

        function updateAdd() {
            addButton.disabled = addField.value.trim() === '';
        }

        addField.addEventListener('input', updateAdd);
        updateAdd();

        addForm.addEventListener('submit', function (event) {
            if (addField.value.trim() === '') {
                event.preventDefault();
                return;
            }
            addField.readOnly = true;
            addButton.disabled = true;
            addButton.classList.add('is-busy');
            addButton.innerHTML = '<span class="z-spinner" aria-hidden="true"></span><span class="visually-hidden">Adding…</span>';
        });
    }
})();
