// Voice input (FR7, docs/05): the microphone fills the same text field, so voice and text share
// one pipeline (docs/01). States: idle ("Tap to speak"), listening (pulsing, words appear live,
// "Tap to stop") and done (the text stays and can be edited). The browser's own speech recognition
// is used; where it is missing (Firefox) or blocked (http on the LAN), the mic stays hidden (NFR16).
//
// Chunk 8b: a small state machine (idle → starting → listening → stopping → idle), because Chrome
// on Android sometimes never sends onend or onerror. Two timers make sure the button always comes
// back: one for a start that never begins, one for a stop that never ends. Every event is logged
// as "[voice] …" (see it on a phone through chrome://inspect → Remote devices).
//
// Chunk 24: any form with data-voice gets its own mic, so Tell Zalak can be dictated too. The parts
// are found by data attribute inside that form:
//   data-voice-field   the text field the words go into          (needed)
//   data-voice-box     shown once the browser can listen         (needed)
//   data-voice-mic     the button                                (needed)
//   data-voice-status  the calm message line                     (needed)
//   data-voice-label   "Tap to speak" / "Tap to stop"            (optional)
//   data-voice-fieldbox, data-voice-live, data-voice-wave       (optional: the big page's looks)
//   data-voice-method  the hidden input_method, set to "voice"   (optional)
// Wrapped in a function so its names stay private (see analyzing.js).
(function () {
var SpeechRecognitionApi = window.SpeechRecognition || window.webkitSpeechRecognition;

// Android Chrome: continuous mode ends silently or repeats results, so there one phrase per tap
var VOICE_IS_ANDROID = /Android/i.test(navigator.userAgent);
var VOICE_START_TIMEOUT = 4000;   // ms to wait for onstart
var VOICE_STOP_TIMEOUT = 1500;    // ms to wait for onend after stop()

// Calm messages, shown under the mic; typing always still works
var VOICE_MESSAGES = {
    'not-allowed': "Zalak can't use the microphone. Allow it in the browser, or type instead.",
    'service-not-allowed': "Zalak can't use the microphone. Allow it in the browser, or type instead.",
    'audio-capture': 'No microphone found. Type it instead.',
    'network': 'Voice needs an internet connection. Type it instead.',
    'default': "Couldn't hear you. Type it instead.",
};

if (SpeechRecognitionApi && window.isSecureContext) {
    document.querySelectorAll('form[data-voice]').forEach(setUpVoice);
}

function setUpVoice(form) {
    var field = form.querySelector('[data-voice-field]');
    var voiceBox = form.querySelector('[data-voice-box]');
    var micButton = form.querySelector('[data-voice-mic]');
    var status = form.querySelector('[data-voice-status]');
    if (!field || !voiceBox || !micButton || !status) {
        return;
    }
    var methodInput = form.querySelector('[data-voice-method]');
    var fieldBox = form.querySelector('[data-voice-fieldbox]');
    var liveLine = form.querySelector('[data-voice-live]');
    var micLabel = form.querySelector('[data-voice-label]');
    var wave = form.querySelector('[data-voice-wave]');

    var recognition = null;   // the one live SpeechRecognition, or null
    var state = 'idle';       // idle | starting | listening | stopping
    var startTimer = null;
    var stopTimer = null;
    var pulseTimer = null;

    var base = '';          // the text the dictated words are added after
    var firstResult = 0;    // results before this one are already part of base
    var shownUpTo = 0;      // how many results the field shows right now
    var lastWritten = '';   // what this script last put in the field, to notice the user's edits
    var heardWords = false;
    var hadError = false;
    var submitting = false;

    voiceBox.hidden = false;

    function log() {
        console.debug.apply(console, ['[voice]'].concat(Array.prototype.slice.call(arguments)));
    }

    // "two eggs" + dictation → "two eggs, toast…", like the detail chips (chips.js)
    function withSeparator(text) {
        if (text.trim() === '') {
            return '';
        }
        if (/\s$/.test(text)) {
            return text;            // e.g. after the chip "portion: "
        }
        return /[,.;:]$/.test(text) ? text + ' ' : text + ', ';
    }

    function write(text) {
        field.value = text;
        lastWritten = text;
        field.scrollTop = field.scrollHeight;
        field.dispatchEvent(new Event('input'));   // chips.js turns Analyze on
    }

    function setButton(listening) {
        micButton.setAttribute('aria-pressed', listening ? 'true' : 'false');
        micButton.classList.toggle('is-listening', listening);
        if (micLabel) micLabel.textContent = listening ? 'Tap to stop' : 'Tap to speak';
        voiceBox.classList.toggle('is-listening', listening);
        if (fieldBox) fieldBox.classList.toggle('is-listening', listening);
        if (liveLine) liveLine.hidden = !listening;
    }

    function showStatus(message, onlyForScreenReaders) {
        status.textContent = message;
        status.classList.toggle('visually-hidden', Boolean(onlyForScreenReaders));
    }

    function settleWaves() {
        clearTimeout(pulseTimer);
        voiceBox.classList.remove('is-speaking');
        if (wave) wave.classList.remove('is-pulse');
    }

    function pulseWaves() {
        if (!wave) return;
        wave.classList.add('is-pulse');
        clearTimeout(pulseTimer);
        pulseTimer = setTimeout(function () { wave.classList.remove('is-pulse'); }, 150);
    }

    // Back to idle, whatever happened. Safe to call more than once.
    function finish(message) {
        clearTimeout(startTimer);
        clearTimeout(stopTimer);
        if (recognition) {
            detach(recognition);   // late events from this instance are ignored from now on
        }
        recognition = null;
        state = 'idle';
        setButton(false);
        settleWaves();

        if (message) {
            showStatus(message);
        } else if (heardWords && !submitting && !hadError) {
            // Done: the text is ready to check and fix (a misheard "tavče gravče", docs/01)
            showStatus('Done. You can edit the text.', true);
            field.focus();
            field.setSelectionRange(field.value.length, field.value.length);
        }
    }

    function detach(rec) {
        rec.onstart = rec.onaudiostart = rec.onspeechstart = rec.onspeechend = null;
        rec.onresult = rec.onnomatch = rec.onerror = rec.onend = null;
    }

    // Stop listening right now: drop the handlers first, then abort (its events are not wanted)
    function abortNow(message) {
        var rec = recognition;
        finish(message);
        if (rec) {
            try {
                rec.abort();
            } catch (error) {
                log('abort() threw', error.name);
            }
        }
    }

    function fail(code, detail) {
        hadError = true;
        console.warn('[voice]', code, detail || '');
        abortNow(VOICE_MESSAGES[code] || VOICE_MESSAGES['default']);
    }

    function onResult(event) {
        if (field.value !== lastWritten) {
            // The user typed or tapped a chip while listening ("you can edit the text anytime"):
            // their text is the new start, and the words already shown are not added again
            base = withSeparator(field.value);
            firstResult = shownUpTo;
        }
        var words = '';
        for (var i = firstResult; i < event.results.length; i++) {
            var part = event.results[i][0].transcript.trim();   // finals, then the live (interim) one
            if (part === '') {
                continue;
            }
            if (words !== '' && part.toLowerCase().indexOf(words.toLowerCase()) === 0) {
                words = part;   // Android repeats the earlier words in the next result: keep it once
            } else {
                words = words === '' ? part : words + ' ' + part;
            }
        }
        shownUpTo = event.results.length;
        if (words === '') {
            return;
        }
        heardWords = true;
        if (methodInput) methodInput.value = 'voice';   // stays voice even if the words are edited afterwards
        write(base + words);
        pulseWaves();
    }

    function start() {
        var rec = new SpeechRecognitionApi();
        rec.lang = 'en-US';
        rec.continuous = !VOICE_IS_ANDROID;   // desktop: keep listening through short pauses
        rec.interimResults = true;            // words appear while speaking
        rec.maxAlternatives = 1;

        // Each handler first checks that rec is still the live instance
        rec.onstart = function () {
            if (rec !== recognition) { return; }
            log('onstart');
            clearTimeout(startTimer);
            state = 'listening';
        };
        rec.onaudiostart = function () {
            if (rec !== recognition) { return; }
            log('onaudiostart');
        };
        rec.onspeechstart = function () {
            if (rec !== recognition) { return; }
            log('onspeechstart');
            voiceBox.classList.add('is-speaking');
        };
        rec.onspeechend = function () {
            if (rec !== recognition) { return; }
            log('onspeechend');
            settleWaves();
            if (VOICE_IS_ANDROID) {
                stop();   // one phrase per tap: end right after the user stops talking
            }
        };
        rec.onresult = function (event) {
            if (rec !== recognition) { return; }
            onResult(event);
        };
        rec.onnomatch = function () {
            if (rec !== recognition) { return; }
            fail('no-match');
        };
        rec.onerror = function (event) {
            if (rec !== recognition) { return; }
            if (event.error === 'aborted') {
                log('onerror aborted');
                return;   // onend follows
            }
            fail(event.error, event.message);
        };
        rec.onend = function () {
            if (rec !== recognition) { return; }
            log('onend');
            finish();
        };

        recognition = rec;
        state = 'starting';
        base = withSeparator(field.value);
        lastWritten = field.value;
        firstResult = 0;
        shownUpTo = 0;
        heardWords = false;
        hadError = false;
        showStatus('');
        setButton(true);   // at once, so every tap answers within 1 s; a second tap always stops

        startTimer = setTimeout(function () {
            if (rec === recognition && state === 'starting') {
                fail('start-timeout');   // Chrome never confirmed: no mic, or the speech service is busy
            }
        }, VOICE_START_TIMEOUT);

        try {
            rec.start();
            log('start()', 'continuous=' + rec.continuous);
        } catch (error) {
            fail('start-failed', error.name);   // e.g. InvalidStateError: an old instance still runs
        }
    }

    function stop() {
        if (!recognition || state === 'stopping') {
            return;
        }
        var rec = recognition;
        state = 'stopping';
        clearTimeout(startTimer);
        log('stop()');
        try {
            rec.stop();
        } catch (error) {
            log('stop() threw', error.name);
        }
        // Android may never send onend after stop(): don't wait for it forever
        stopTimer = setTimeout(function () {
            if (rec === recognition) {
                log('no onend after stop(), aborting');
                abortNow();
            }
        }, VOICE_STOP_TIMEOUT);
    }

    micButton.addEventListener('click', function () {
        if (state === 'idle') {
            start();
        } else if (state === 'stopping') {
            abortNow();   // a second tap while stopping: stop at once
        } else {
            stop();
        }
    });

    // Analyze while listening: stop first, the words so far are already in the field
    form.addEventListener('submit', function () {
        if (recognition) {
            submitting = true;
            abortNow();
        }
    });

    // Back from Result can restore this page from the browser cache: start again from idle
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            submitting = false;
            abortNow();
            showStatus('');
        }
    });
}
})();
