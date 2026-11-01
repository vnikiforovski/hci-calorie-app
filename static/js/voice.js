// Voice input (FR7, docs/05): the microphone fills the same text field, so voice and text share
// one pipeline (docs/01). States: idle ("Tap to speak"), listening (pulsing, words appear live,
// "Tap to stop") and done (the text stays and can be edited). The browser's own speech recognition
// is used; where it is missing (Firefox) or blocked (http on the LAN), the mic stays hidden (NFR16).
var SpeechRecognitionApi = window.SpeechRecognition || window.webkitSpeechRecognition;
var voiceBox = document.getElementById('voice');

// Calm messages, shown under the mic; typing always still works
var VOICE_MESSAGES = {
    'not-allowed': "Zalak can't use the microphone. Allow it in the browser, or type instead.",
    'service-not-allowed': "Zalak can't use the microphone. Allow it in the browser, or type instead.",
    'audio-capture': 'No microphone found. You can type instead.',
    'no-speech': "Didn't catch that. Tap to try again, or type it.",
    'network': 'Voice needs an internet connection. You can type instead.',
    'other': 'Voice stopped. Tap to try again, or type it.',
};

if (SpeechRecognitionApi && window.isSecureContext && voiceBox) {
    setUpVoice();
}

function setUpVoice() {
    var form = document.getElementById('textMealForm');
    var field = form.querySelector('textarea[name="text"]');
    var methodInput = form.querySelector('input[name="input_method"]');
    var fieldBox = document.getElementById('voiceField');
    var liveLine = document.getElementById('voiceLive');
    var micButton = document.getElementById('micButton');
    var micLabel = document.getElementById('micLabel');
    var status = document.getElementById('voiceStatus');

    var recognition = null;
    var base = '';          // the text the dictated words are added after
    var firstResult = 0;    // results before this one are already part of base
    var shownUpTo = 0;      // how many results the field shows right now
    var lastWritten = '';   // what this script last put in the field, to notice the user's edits
    var heardWords = false;
    var hadError = false;
    var submitting = false;

    voiceBox.hidden = false;

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

    function setListening(on) {
        micButton.setAttribute('aria-pressed', on ? 'true' : 'false');
        micLabel.textContent = on ? 'Tap to stop' : 'Tap to speak';
        voiceBox.classList.toggle('is-listening', on);
        fieldBox.classList.toggle('is-listening', on);
        liveLine.hidden = !on;
    }

    function showStatus(message, onlyForScreenReaders) {
        status.textContent = message;
        status.classList.toggle('visually-hidden', Boolean(onlyForScreenReaders));
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
            words += event.results[i][0].transcript;   // final words, then the live (interim) ones
        }
        shownUpTo = event.results.length;
        words = words.trim();
        if (words === '') {
            return;
        }
        heardWords = true;
        methodInput.value = 'voice';   // stays voice even if the words are edited afterwards
        write(base + words);
    }

    function onError(event) {
        if (event.error === 'aborted') {
            return;   // we stopped it ourselves (Analyze)
        }
        hadError = true;
        showStatus(VOICE_MESSAGES[event.error] || VOICE_MESSAGES.other);
    }

    // Tap to stop, the browser's own stop after a silence, an error or Analyze all end here
    function onEnd() {
        recognition = null;
        setListening(false);
        if (submitting || hadError) {
            return;
        }
        if (heardWords) {
            // Done: the text is ready to check and fix (a misheard "tavče gravče", docs/01)
            showStatus('Done. You can edit the text.', true);
            field.focus();
            field.setSelectionRange(field.value.length, field.value.length);
        }
    }

    function start() {
        recognition = new SpeechRecognitionApi();
        recognition.lang = 'en-US';
        recognition.continuous = true;        // keep listening through short pauses
        recognition.interimResults = true;    // words appear while speaking
        recognition.onresult = onResult;
        recognition.onerror = onError;
        recognition.onend = onEnd;

        base = withSeparator(field.value);
        lastWritten = field.value;
        firstResult = 0;
        shownUpTo = 0;
        heardWords = false;
        hadError = false;
        showStatus('');

        try {
            recognition.start();
        } catch (error) {
            recognition = null;
            showStatus(VOICE_MESSAGES.other);
            return;
        }
        setListening(true);   // at once, before the permission prompt: every tap answers within 1 s
    }

    micButton.addEventListener('click', function () {
        if (recognition) {
            recognition.stop();   // onEnd shows the done state
        } else {
            start();
        }
    });

    // Analyze while listening: stop first, the words so far are already in the field
    form.addEventListener('submit', function () {
        if (recognition) {
            submitting = true;
            recognition.abort();
        }
    });

    // Back from Result can restore this page from the browser cache: start again from idle
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            if (recognition) {
                recognition.abort();
            }
            recognition = null;
            submitting = false;
            setListening(false);
            showStatus('');
        }
    });
}
