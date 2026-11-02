// Analyzing overlay (docs/05): shown the moment an analysis form is sent, so the wait never
// looks frozen (NFR2: under 1 s). The AI call is one request, so the steps move on timers;
// the bar stops at 90 % and the next page replaces this one when the answer arrives.
// The answer is never held back: if it comes before the last bite, Result simply shows sooner.
// Wrapped in its own function so its names stay private: the pages load several plain scripts,
// and two global functions with the same name (showStep) once silently replaced each other.
(function () {
    var overlay = document.getElementById('analyzing');
    var cancelButton = document.getElementById('analyzingCancel');
    var steps = overlay.querySelectorAll('.z-step');
    var bar = document.getElementById('analyzingBar');
    var nowText = document.getElementById('analyzingNow');
    var STEP_TIMES = [0, 600, 1200];    // ms after sending, one per step: Haiku answers in ~1-2 s
    var BAR_WIDTHS = [28, 60, 90];      // % per step, as in the Figma frames "Analyzing 1-3 of 3"
    var timers = [];
    var sentButton = null;

    function showStep(index) {
        steps.forEach(function (step, i) {
            step.classList.toggle('is-done', i < index);
            step.classList.toggle('is-now', i === index);
        });
        nowText.textContent = steps[index].textContent.trim() + '…';   // read out by screen readers
        bar.style.width = BAR_WIDTHS[index] + '%';
        overlay.dataset.stage = index + 1;   // the CSS takes one more bite out of the cookie
    }

    function startAnalyzing(form) {
        overlay.hidden = false;
        document.body.classList.add('z-no-scroll');
        sentButton = form.querySelector('[type="submit"]');
        if (sentButton) {
            sentButton.disabled = true;   // no double analysis
        }
        bar.style.width = '0%';
        steps.forEach(function (step, i) {
            timers.push(setTimeout(function () { showStep(i); }, STEP_TIMES[i] || 0));
        });
        cancelButton.focus();
    }

    function stopAnalyzing() {
        timers.forEach(clearTimeout);
        timers = [];
        overlay.hidden = true;
        document.body.classList.remove('z-no-scroll');
        steps.forEach(function (step) { step.classList.remove('is-done', 'is-now'); });
        delete overlay.dataset.stage;   // the next analysis starts with a whole cookie
        nowText.textContent = '';
        if (sentButton) {
            sentButton.disabled = false;
            sentButton.focus();
        }
    }

    document.querySelectorAll('form[data-analyzing]').forEach(function (form) {
        form.addEventListener('submit', function () {
            startAnalyzing(form);
        });
    });

    // Cancel stops waiting for the answer; the input is still in the form (docs/05)
    cancelButton.addEventListener('click', function () {
        window.stop();
        stopAnalyzing();
    });

    // While the overlay is open: Escape cancels, and Tab stays on Cancel (the only button)
    document.addEventListener('keydown', function (event) {
        if (overlay.hidden || overlay.classList.contains('is-intro')) {
            return;
        }
        if (event.key === 'Escape') {
            cancelButton.click();
        } else if (event.key === 'Tab') {
            event.preventDefault();
            cancelButton.focus();
        }
    });

    // Figma "Analyzing · Connection lost / No food" (chunk 19): straight after a failed analysis the
    // page opens with the overlay showing the failed step (_analyzing.html shows it before the first
    // paint). After a moment it fades to the page; a tap or a key skips the wait. It is aria-hidden and
    // inert meanwhile: the page's h1 says the same. Afterwards the overlay is the normal one again,
    // ready for Try again.
    var INTRO_MS = 1200;
    var introTimer = null;

    // Back to a clean overlay: dialog semantics, a whole cookie, every step waiting
    function resetOverlay() {
        overlay.hidden = true;
        overlay.classList.remove('is-intro', 'is-leaving');
        document.body.classList.remove('z-no-scroll');
        overlay.removeAttribute('data-failed');
        overlay.removeAttribute('aria-hidden');
        overlay.removeAttribute('inert');
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-labelledby', 'analyzingTitle');
        delete overlay.dataset.stage;
        steps.forEach(function (step) {
            step.classList.remove('is-done', 'is-now', 'is-failed');
            step.querySelector('.z-step-icon i').className = 'bi bi-check-lg';
            step.lastChild.textContent = ' ' + step.dataset.word + ' ';   // the failed step had other words
        });
        bar.style.width = '0%';
    }

    function endIntro() {
        if (!overlay.classList.contains('is-intro') || overlay.classList.contains('is-leaving')) {
            return;
        }
        clearTimeout(introTimer);
        overlay.classList.add('is-leaving');   // fades out (zalak.css)
        setTimeout(resetOverlay, 300);
    }

    if (overlay.hasAttribute('data-failed')) {
        // Drop ?fresh=1, so a reload shows the page straight away
        var url = new URL(window.location.href);
        url.searchParams.delete('fresh');
        window.history.replaceState(null, '', url.pathname + url.search + url.hash);
        if (overlay.hidden) {
            resetOverlay();   // reduced motion: the intro was never shown
        } else {
            introTimer = setTimeout(endIntro, INTRO_MS);
            overlay.addEventListener('click', endIntro);
            document.addEventListener('keydown', endIntro, {once: true});
        }
    }

    // Back from Result can restore this page from the browser cache: don't leave the overlay open
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            stopAnalyzing();
        }
    });
})();
