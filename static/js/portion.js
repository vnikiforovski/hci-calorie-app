// Edit item: the amount stepper, the Unit sheet, Reset and the live kcal / macro preview.
// The numbers come from the view (portionData, json_script). Grams follow the same rule as
// units.grams_for in Python, so the preview matches what Save changes stores.
// Wrapped in its own function so its names stay private (see analyzing.js).
(function () {
    var data = JSON.parse(document.getElementById('portionData').textContent);

    var amountInput = document.getElementById('id_amount');
    var unitInput = document.getElementById('id_unit');
    var nameInput = document.getElementById('id_name');

    var state = {
        amount: parseFloat(amountInput.value) || data.saved.amount,
        unit: unitInput.value || data.saved.unit
    };

    var FRACTIONS = {25: '¼', 50: '½', 75: '¾'};

    // ---------- Maths (mirrors meals/units.py) ----------

    function roundTo(value, step) {
        return Math.round(value / step) * step;
    }

    function isMeasured(unit) {
        return unit in data.steps;
    }

    function gramsFor(amount, unit) {
        // The first known portion in the same unit gives the item's own grams per unit (AI first).
        // Weight units are exact, so they always use the table.
        for (var i = 0; i < data.known.length; i++) {
            var known = data.known[i];   // [amount, unit, grams]
            if (known[1] === unit && known[0] && data.weightUnits.indexOf(unit) === -1) {
                return Math.max(roundTo(amount * known[2] / known[0], 5), data.minGrams);
            }
        }
        return Math.max(roundTo(amount * data.gramsPerUnit[unit], 5), data.minGrams);
    }

    function scaled(name, grams, step) {
        return roundTo(data.per100[name] * grams / 100, step);
    }

    function clean(number) {
        return Math.round(number * 100) / 100;   // 0.30000000000000004 -> 0.3
    }

    // ---------- Words ----------

    function formatAmount(amount) {
        amount = clean(amount);
        var whole = Math.floor(amount);
        var hundredths = Math.round((amount - whole) * 100);
        if (FRACTIONS[hundredths]) {
            return (whole || '') + FRACTIONS[hundredths];
        }
        return String(amount);
    }

    function unitLabel(unit, amount) {
        var label = data.labels[unit];
        if (amount > 1 && data.noPlural.indexOf(unit) === -1) {
            label += /ch$/.test(label) ? 'es' : 's';
        }
        return label;
    }

    // ---------- Stepper ----------

    function nextAmount(direction) {
        var amount = state.amount;
        if (isMeasured(state.unit)) {
            var step = data.steps[state.unit];
            var next = clean(amount + direction * step);
            return next >= step ? next : null;
        }
        // Counted units walk the ladder: ¼ ½ ¾ 1 1½ 2 2½ 3 4 5 ... 20
        var ladder = data.ladder;
        if (direction > 0) {
            for (var i = 0; i < ladder.length; i++) {
                if (ladder[i] > amount + 0.001) return ladder[i];
            }
        } else {
            for (var j = ladder.length - 1; j >= 0; j--) {
                if (ladder[j] < amount - 0.001) return ladder[j];
            }
        }
        return null;
    }

    function canStep(direction) {
        var next = nextAmount(direction);
        if (next === null) return false;
        return direction < 0 || gramsFor(next, state.unit) <= data.maxGrams;
    }

    function step(direction) {
        if (!canStep(direction)) return;
        state.amount = nextAmount(direction);
        render();
    }

    document.getElementById('stepDown').addEventListener('click', function () { step(-1); });
    document.getElementById('stepUp').addEventListener('click', function () { step(1); });

    // ---------- Drawing ----------

    function render() {
        var grams = gramsFor(state.amount, state.unit);
        var label = unitLabel(state.unit, state.amount);

        amountInput.value = clean(state.amount);
        unitInput.value = state.unit;

        document.getElementById('amountText').textContent = formatAmount(state.amount);
        document.getElementById('unitText').textContent = label;
        document.querySelector('.z-unit-chip').setAttribute('aria-label', 'Unit: ' + label + '. Change the unit');

        document.getElementById('gramsLine').hidden = state.unit === 'g';
        document.getElementById('gramsText').textContent = grams;

        var kcalMin = scaled('kcal_min', grams, 10);
        var kcalMax = scaled('kcal_max', grams, 10);
        document.getElementById('kcalText').textContent = kcalMin + '–' + kcalMax;

        ['protein', 'carbs', 'fat'].forEach(function (macro) {
            var text = scaled(macro + '_min', grams, 1) + '–' + scaled(macro + '_max', grams, 1);
            document.querySelectorAll('[data-macro="' + macro + '"]').forEach(function (span) {
                span.textContent = text;
            });
        });

        // "was 380–460 kcal" once the portion differs from what is saved
        var changed = kcalMin !== data.saved.kcalMin || kcalMax !== data.saved.kcalMax;
        document.getElementById('wasNote').hidden = !changed;
        document.getElementById('estimateNote').hidden = changed;

        document.getElementById('stepDown').disabled = !canStep(-1);
        document.getElementById('stepUp').disabled = !canStep(1);
    }

    // ---------- Unit sheet ----------

    var sheet = document.getElementById('unitSheet');
    var bowlSizes = document.getElementById('bowlSizes');

    function isBowl(unit) {
        return unit.indexOf('bowl_') === 0;
    }

    function pickedUnit() {
        var choice = sheet.querySelector('input[name="unitChoice"]:checked');
        if (!choice) return state.unit;
        if (choice.value !== 'bowl') return choice.value;
        var size = sheet.querySelector('input[name="bowlSize"]:checked');
        return size ? size.value : 'bowl_m';
    }

    function showBowlSizes() {
        var choice = sheet.querySelector('input[name="unitChoice"]:checked');
        bowlSizes.hidden = !(choice && choice.value === 'bowl');
    }

    function markBowlSize() {
        sheet.querySelectorAll('input[name="bowlSize"]').forEach(function (input) {
            input.parentElement.classList.toggle('active', input.checked);
        });
    }

    // Opening the sheet shows the current unit, on its tab
    sheet.addEventListener('show.bs.offcanvas', function () {
        var value = isBowl(state.unit) ? 'bowl' : state.unit;
        var radio = sheet.querySelector('input[name="unitChoice"][value="' + value + '"]');
        radio.checked = true;
        var size = sheet.querySelector('input[name="bowlSize"][value="' + (isBowl(state.unit) ? state.unit : 'bowl_m') + '"]');
        size.checked = true;
        markBowlSize();
        showBowlSizes();

        var pane = radio.closest('.tab-pane');
        bootstrap.Tab.getOrCreateInstance(document.getElementById('unitTab-' + pane.dataset.tab)).show();
    });

    sheet.addEventListener('change', function (event) {
        if (event.target.name === 'unitChoice') showBowlSizes();
        if (event.target.name === 'bowlSize') markBowlSize();
    });

    function applyUnit(unit) {
        if (unit === state.unit) return;
        var grams = gramsFor(state.amount, state.unit);
        if (isMeasured(unit)) {
            // Measured: keep the same food weight, in the new unit ("2 slices · 60 g" -> 60 g)
            var stepSize = data.steps[unit];
            state.amount = Math.max(stepSize, clean(roundTo(grams / data.gramsPerUnit[unit], stepSize)));
        } else if (isMeasured(state.unit)) {
            state.amount = 1;   // from grams to a counted unit: start at one
        }
        // Between counted units the amount stays, so a bigger bowl stays "1 bowl"
        state.unit = unit;
        render();
    }

    document.getElementById('unitDone').addEventListener('click', function () {
        applyUnit(pickedUnit());
        bootstrap.Offcanvas.getOrCreateInstance(sheet).hide();
    });

    // ---------- Reset: Zalak's estimate again (saved only with Save changes) ----------

    var resetButton = document.getElementById('resetButton');
    if (resetButton) {
        resetButton.addEventListener('click', function () {
            nameInput.value = data.ai.name;
            state.amount = data.ai.amount;
            state.unit = data.ai.unit;
            render();
        });
    }

    // ---------- Re-estimate: show that Zalak is working (one AI call, 1-2 s) ----------

    var reEstimateButton = document.getElementById('reEstimateButton');
    document.getElementById('itemForm').addEventListener('submit', function (event) {
        if (event.submitter !== reEstimateButton) return;
        // Disabled just after the submit has started, so the button's formaction still applies
        setTimeout(function () {
            document.querySelectorAll('#itemForm [type="submit"]').forEach(function (button) {
                button.disabled = true;
            });
            reEstimateButton.innerHTML = '<span class="z-spinner" aria-hidden="true"></span> <span>Asking Zalak…</span>';
        }, 0);
    });

    render();
})();
