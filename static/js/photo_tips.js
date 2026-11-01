// Photo tips (docs/05 "the first time, swipeable tips cards ... Don't show again"; Figma Tips 1-3).
// The cards swipe by themselves (CSS scroll snap); this script follows the scroll to light the dots
// and swap Skip / Next for the checkbox and Got it on the last card. On phones the sheet opens by
// itself until "Don't show these tips again", which is kept in the Profile (or the session for a guest).
// Wrapped in its own function so its names stay private: the pages load several plain scripts,
// and two global functions with the same name (showStep) once silently replaced each other.
(function () {
    var tipsSheet = document.getElementById('photoTips');
    var tipsTrack = document.getElementById('tipsTrack');
    var tipSlides = tipsTrack.querySelectorAll('.z-tip');
    var tipDots = tipsSheet.querySelectorAll('.z-tip-dots span');
    var tipsMore = document.getElementById('tipsMore');
    var tipsLast = document.getElementById('tipsLast');
    var tipsDontShow = document.getElementById('tipsDontShow');
    var tipsReduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var currentTip = 0;
    var tipsSaved = false;

    function updateTips() {
        var index = Math.round(tipsTrack.scrollLeft / tipsTrack.clientWidth);
        currentTip = Math.max(0, Math.min(tipSlides.length - 1, index));
        tipDots.forEach(function (dot, i) { dot.classList.toggle('active', i === currentTip); });
        var isLast = currentTip === tipSlides.length - 1;
        tipsMore.hidden = isLast;
        tipsLast.hidden = !isLast;
    }

    tipsTrack.addEventListener('scroll', updateTips);

    document.getElementById('tipsNext').addEventListener('click', function () {
        tipsTrack.scrollTo({
            left: (currentTip + 1) * tipsTrack.clientWidth,
            behavior: tipsReduceMotion ? 'auto' : 'smooth',
        });
    });

    // Every opening starts at the first tip
    tipsSheet.addEventListener('show.bs.offcanvas', function () {
        tipsTrack.scrollLeft = 0;
        updateTips();
    });

    // Closed with the box ticked: remember it on the server, so the tips stop opening by themselves
    tipsSheet.addEventListener('hidden.bs.offcanvas', function () {
        if (!tipsDontShow.checked || tipsSaved) {
            return;
        }
        tipsSaved = true;
        fetch(tipsSheet.dataset.seenUrl, {
            method: 'POST',
            headers: {'X-CSRFToken': document.querySelector('input[name="csrfmiddlewaretoken"]').value},
            credentials: 'same-origin',
        }).catch(function () {
            tipsSaved = false;   // offline: try again the next time the sheet closes
        });
    });

    // First visits on a phone: open the tips over the camera (the desktop has a Tips link instead)
    if (tipsSheet.hasAttribute('data-auto-open') && !window.matchMedia('(min-width: 992px)').matches) {
        bootstrap.Offcanvas.getOrCreateInstance(tipsSheet).show();
    }
})();
