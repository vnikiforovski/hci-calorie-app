// Meal detail (chunk 15, templates/meals/meal_detail.html).
// 1. The time sheet: an hour : minute wheel (Figma "Overlay · Time", as in phone clock apps).
//    Done copies the day and time into the meal form's hidden fields and the pill. Opening the
//    sheet again starts from those fields, so closing it another way changes nothing.
//    The server checks the time again on Save.
// 2. The photo: Add / Replace open the hidden file input and show the chosen photo at once;
//    Remove hides it. Nothing is saved until Save changes.
(function () {
    const smooth = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';

    // One wheel column. The list has two empty rows of padding above and below, so row n sits in
    // the middle band when the column is scrolled to n row-heights. Scroll snapping does the rest.
    function Wheel(element, onChange) {
        const items = Array.from(element.querySelectorAll('.z-wheel-item'));
        let index = Math.max(0, items.findIndex(function (item) { return item.classList.contains('is-selected'); }));
        let wheelDelta = 0;
        let target = null;      // while we scroll the column ourselves, its scroll events are ignored
        let targetTimer = null;

        function rowHeight() { return items[0].offsetHeight; }

        function mark(i) {
            index = Math.min(Math.max(i, 0), items.length - 1);
            items.forEach(function (item, n) { item.classList.toggle('is-selected', n === index); });
            element.setAttribute('aria-valuenow', Number(items[index].dataset.value));
            element.setAttribute('aria-valuetext', items[index].dataset.value);
            onChange();
        }

        function go(i, behavior) {
            mark(i);
            target = index * rowHeight();
            clearTimeout(targetTimer);
            targetTimer = setTimeout(function () { target = null; }, 500);   // in case it never arrives
            element.scrollTo({ top: target, behavior: behavior || smooth });
        }

        // Swipe or drag: the row in the band is the choice
        element.addEventListener('scroll', function () {
            if (target !== null) {
                if (Math.abs(element.scrollTop - target) < 2) target = null;   // arrived
                return;
            }
            const i = Math.round(element.scrollTop / rowHeight());
            if (i !== index) mark(i);
        });

        // A mouse wheel moves one row per notch (a trackpad needs a bit more travel)
        element.addEventListener('wheel', function (event) {
            event.preventDefault();
            wheelDelta += event.deltaY;
            if (Math.abs(wheelDelta) >= 40) {
                go(index + Math.sign(wheelDelta));
                wheelDelta = 0;
            }
        }, { passive: false });

        items.forEach(function (item, n) {
            item.addEventListener('click', function () { go(n); element.focus(); });
        });

        // The spinbutton keys
        element.addEventListener('keydown', function (event) {
            const moves = { ArrowUp: -1, ArrowDown: 1, PageUp: -3, PageDown: 3 };
            if (event.key in moves) go(index + moves[event.key]);
            else if (event.key === 'Home') go(0);
            else if (event.key === 'End') go(items.length - 1);
            else return;
            event.preventDefault();
        });

        return {
            value: function () { return items[index].dataset.value; },
            set: function (value) {
                const i = items.findIndex(function (item) { return item.dataset.value === value; });
                if (i >= 0) go(i, 'auto');
            },
        };
    }

    // ---------- Time ----------
    const sheet = document.getElementById('timeSheet');
    const error = document.getElementById('timeError');
    const reset = document.getElementById('timeReset');   // missing when the logged day isn't offered
    const eatenTime = document.getElementById('eatenTime');
    function hideError() { error.hidden = true; }
    const hour = Wheel(document.getElementById('timeHour'), hideError);
    const minute = Wheel(document.getElementById('timeMinute'), hideError);

    function pick(hh, mm) {
        hour.set(hh);
        minute.set(mm);
        hideError();
    }

    // Each time it opens, the sheet starts from what the form will send. "show" comes before the
    // slide-in, so the wheels are already in place when the sheet appears.
    sheet.addEventListener('show.bs.offcanvas', function () {
        const parts = eatenTime.value.split(':');
        pick(parts[0], parts[1]);
    });

    if (reset) {
        reset.addEventListener('click', function () {
            pick(reset.dataset.hour, reset.dataset.minute);
        });
    }

    document.getElementById('timeDone').addEventListener('click', function () {
        // The day stays the meal's own; only the time changes
        const time = hour.value() + ':' + minute.value();
        // Both are "YYYY-MM-DDTHH:MM" in Zalak's time zone, so text order is time order
        if (sheet.dataset.day + 'T' + time > sheet.dataset.now) {
            error.hidden = false;
            return;
        }
        eatenTime.value = time;
        document.getElementById('timeLabel').textContent = sheet.dataset.dayLabel + ', ' + time;
        bootstrap.Offcanvas.getOrCreateInstance(sheet).hide();
    });

    // ---------- Photo ----------
    const hero = document.getElementById('mealHero');
    const input = document.getElementById('id_photo');
    const photo = document.getElementById('mealPhoto');
    const removeFlag = document.getElementById('removePhoto');
    const note = document.getElementById('photoNote');

    document.querySelectorAll('[data-photo-pick]').forEach(function (button) {
        button.addEventListener('click', function () { input.click(); });
    });

    input.addEventListener('change', function () {
        const file = input.files[0];
        if (!file) return;
        photo.src = URL.createObjectURL(file);
        removeFlag.value = '';
        hero.dataset.state = 'photo';
        note.textContent = 'New photo. Save changes to keep it.';
    });

    document.getElementById('photoRemove').addEventListener('click', function () {
        input.value = '';
        removeFlag.value = '1';
        hero.dataset.state = 'none';
        note.textContent = 'Photo removed. Save changes to keep it this way.';
    });
})();
