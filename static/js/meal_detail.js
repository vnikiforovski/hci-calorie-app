// Meal detail (chunk 15, templates/meals/meal_detail.html). HCI idea 2: every change saves the moment
// it is made, so nothing waits for a button and nothing is lost by leaving the page.
// 1. The slot (slot_select.js fills the hidden input), the time and the name are small forms sent with
//    fetch; a line under the pills says "Saving…", "Saved" or what went wrong. Without JavaScript they
//    post the normal way and the page comes back with a toast.
// 2. The time sheet: an hour : minute wheel (Figma "Overlay · Time", as in phone clock apps). Done saves
//    the time on the meal's own day; a time that hasn't come yet is refused here and on the server.
// 3. The photo: choosing a file sends it at once; Remove asks first (it can't be undone).
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

    // ---------- Saving one change (HCI idea 2) ----------
    const status = document.getElementById('saveStatus');

    // Sends one of the small forms. onDone gets the server's text (the name as saved);
    // onFail gets the calm message. A failed fetch (offline) says so and changes nothing.
    function saveField(form, onDone, onFail) {
        status.textContent = 'Saving…';
        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'fetch' },
            credentials: 'same-origin',
        }).then(function (response) {
            return response.text().then(function (text) {
                if (!response.ok) throw new Error(text || "Couldn't save that. Try again.");
                status.textContent = 'Saved';
                if (onDone) onDone(text);
            });
        }).catch(function (error) {
            const message = error instanceof TypeError ? "Couldn't save. Check your connection and try again." : error.message;
            status.textContent = '';
            if (onFail) onFail(message); else status.textContent = message;
        });
    }

    // The slot: slot_select.js has already written the hidden input when this runs
    const slotForm = document.getElementById('slotForm');
    document.querySelectorAll('.z-slot-option').forEach(function (option) {
        option.addEventListener('click', function () { saveField(slotForm); });
    });

    // ---------- Time ----------
    const sheet = document.getElementById('timeSheet');
    const error = document.getElementById('timeError');
    const reset = document.getElementById('timeReset');   // missing when the logged day isn't offered
    const timeForm = document.getElementById('timeForm');
    const eatenTime = document.getElementById('eatenTime');
    function hideError() { error.hidden = true; }
    const hour = Wheel(document.getElementById('timeHour'), hideError);
    const minute = Wheel(document.getElementById('timeMinute'), hideError);

    function pick(hh, mm) {
        hour.set(hh);
        minute.set(mm);
        hideError();
    }

    // Each time it opens, the sheet starts from the saved time. "show" comes before the slide-in,
    // so the wheels are already in place when the sheet appears.
    sheet.addEventListener('show.bs.offcanvas', function () {
        const parts = eatenTime.value.split(':');
        pick(parts[0], parts[1]);
    });

    if (reset) {
        reset.addEventListener('click', function () {
            pick(reset.dataset.hour, reset.dataset.minute);
        });
    }

    function showTimeError(message) {
        error.textContent = message;
        error.hidden = false;
    }

    document.getElementById('timeDone').addEventListener('click', function () {
        // The day stays the meal's own; only the time changes
        const time = hour.value() + ':' + minute.value();
        // Both are "YYYY-MM-DDTHH:MM" in Zalak's time zone, so text order is time order
        if (sheet.dataset.day + 'T' + time > sheet.dataset.now) {
            showTimeError("That time hasn't come yet. Pick an earlier one.");
            return;
        }
        const before = eatenTime.value;
        eatenTime.value = time;
        saveField(timeForm, function () {
            document.getElementById('timeLabel').textContent = sheet.dataset.dayLabel + ', ' + time;
            bootstrap.Offcanvas.getOrCreateInstance(sheet).hide();
        }, function (message) {
            eatenTime.value = before;
            showTimeError(message);
        });
    });

    // ---------- Name ----------
    const renameForm = document.getElementById('renameForm');
    renameForm.addEventListener('submit', function (event) {
        event.preventDefault();
        saveField(renameForm, function (title) {
            document.getElementById('mealTitle').textContent = title;
            renameForm.querySelector('input[name="title"]').value = title;
            bootstrap.Collapse.getOrCreateInstance(document.getElementById('renameField')).hide();
        });
    });

    // ---------- Photo ----------
    const photoForm = document.getElementById('photoForm');
    const input = document.getElementById('id_photo');
    const note = document.getElementById('photoNote');

    document.querySelectorAll('[data-photo-pick]').forEach(function (button) {
        button.addEventListener('click', function () { input.click(); });
    });

    input.addEventListener('change', function () {
        if (!input.files.length) return;
        note.textContent = 'Saving the photo…';
        photoForm.submit();   // the page comes back with the new photo and a toast
    });

    const removeForm = document.getElementById('photoRemoveForm');
    if (removeForm) {
        removeForm.addEventListener('submit', function (event) {
            if (!window.confirm(removeForm.dataset.confirm)) event.preventDefault();
        });
    }
})();
