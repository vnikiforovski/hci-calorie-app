// Photo + note (docs/05, Figma "Photo · Camera" and "Photo · Add a note"). One hidden file input
// holds the photo, whatever way it arrives; the form sends it with the note. Three modes:
//   live    phones with camera access (https or localhost): a live viewfinder; the shutter copies the
//           frame into the file input (canvas → File → DataTransfer). The stream stops after the
//           capture, when the tab is hidden and when the page is left.
//   native  phones without it, or when the camera is refused: the note step opens at once and
//           "Take a photo" opens the phone's own camera (capture="environment").
//   desktop 992 px and wider: drag a photo onto the page, choose a file or paste one (Ctrl+V);
//           then the photo and the note sit in two columns.
// Wrapped in its own function so its names stay private: the pages load several plain scripts,
// and two global functions with the same name (showStep) once silently replaced each other.
(function () {
    var photoPage = document.getElementById('photoPage');
    var photoForm = document.getElementById('photoMealForm');
    var photoInput = photoForm.querySelector('input[name="photo"]');
    var cameraState = document.getElementById('cameraState');
    var dropState = document.getElementById('dropState');
    var noteState = document.getElementById('noteState');
    var cameraVideo = document.getElementById('cameraVideo');
    var photoPreview = document.getElementById('photoPreview');
    var takePhotoButton = document.getElementById('takePhotoButton');
    var galleryButton = document.getElementById('galleryButton');
    var retakeButton = document.getElementById('retakeButton');
    var noteTipsButton = document.getElementById('noteTipsButton');
    var photoAnalyzeButton = document.getElementById('analyzeButton');
    var noteTitle = document.getElementById('noteTitle');
    var photoMessages = document.querySelectorAll('[data-photo-message]');

    var PHOTO_MESSAGES = {
        notPhoto: "That isn't a photo. Try a JPG or PNG.",
        noCamera: "Zalak can't use the camera here. Use your phone's camera instead.",
    };

    var cameraStream = null;
    var previewUrl = null;
    var photoMode = pickMode();

    function pickMode() {
        if (window.matchMedia('(min-width: 992px)').matches) {
            return 'desktop';
        }
        var canUseCamera = window.isSecureContext && navigator.mediaDevices &&
            typeof navigator.mediaDevices.getUserMedia === 'function' && typeof DataTransfer === 'function';
        return canUseCamera ? 'live' : 'native';
    }

    function showMessage(text) {
        photoMessages.forEach(function (message) { message.textContent = text; });
    }

    // One step at a time: the camera, the desktop drop zone or the note
    function showPhotoStep(step) {
        cameraState.hidden = step !== 'camera';
        dropState.hidden = step !== 'drop';
        noteState.hidden = step !== 'note';
    }

    // The note step with or without a photo: "Take a photo" in the empty ring, Retake once there is one
    function updateNote() {
        var hasPhoto = photoInput.files.length > 0;
        photoPreview.hidden = !hasPhoto;
        takePhotoButton.hidden = hasPhoto;
        galleryButton.hidden = hasPhoto;
        retakeButton.hidden = !hasPhoto;
        noteTipsButton.hidden = hasPhoto;
        photoAnalyzeButton.disabled = !hasPhoto;
    }

    function openPicker(useCamera) {
        if (useCamera) {
            photoInput.setAttribute('capture', 'environment');
        } else {
            photoInput.removeAttribute('capture');
        }
        photoInput.click();
    }

    // A dropped, pasted or captured file goes into the form's file input
    function setFile(file) {
        var transfer = new DataTransfer();
        transfer.items.add(file);
        photoInput.files = transfer.files;
    }

    function showPhoto() {
        var file = photoInput.files[0];
        if (!file) {
            return;   // the picker was closed without a photo: stay where we are
        }
        if (file.type && file.type.indexOf('image/') !== 0) {
            photoInput.value = '';
            showMessage(PHOTO_MESSAGES.notPhoto);
            return;
        }
        stopCamera();
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);   // a retake frees the old preview
        }
        previewUrl = URL.createObjectURL(file);
        photoPreview.src = previewUrl;
        showMessage('');
        showPhotoStep('note');
        updateNote();
        window.scrollTo(0, 0);
        noteTitle.focus();   // screen readers land on the question
    }

    // ---------- Live camera ----------

    function startCamera() {
        if (cameraStream) {
            return;
        }
        navigator.mediaDevices.getUserMedia({
            video: {facingMode: {ideal: 'environment'}, width: {ideal: 1920}},
            audio: false,
        }).then(function (stream) {
            if (cameraState.hidden) {
                stream.getTracks().forEach(function (track) { track.stop(); });   // left the camera meanwhile
                return;
            }
            cameraStream = stream;
            cameraVideo.srcObject = stream;
            cameraVideo.play().catch(function () {});
        }).catch(function (error) {
            // NotAllowedError (refused), NotFoundError (no camera), NotReadableError (busy)...
            console.warn('[camera]', error.name, error.message);
            useNativeCamera(PHOTO_MESSAGES.noCamera);
        });
    }

    function stopCamera() {
        if (cameraStream) {
            cameraStream.getTracks().forEach(function (track) { track.stop(); });
            cameraStream = null;
        }
        cameraVideo.srcObject = null;
    }

    function useNativeCamera(message) {
        stopCamera();
        photoMode = 'native';
        photoPage.dataset.mode = 'native';
        showPhotoStep('note');
        updateNote();
        showMessage(message || '');
    }

    // The shutter: copy what the viewfinder shows (object-fit: cover) into a JPEG file
    function capture() {
        if (!cameraStream || cameraVideo.readyState < 2) {
            return;   // the picture isn't there yet
        }
        var videoWidth = cameraVideo.videoWidth;
        var videoHeight = cameraVideo.videoHeight;
        var box = cameraVideo.getBoundingClientRect();
        var scale = Math.max(box.width / videoWidth, box.height / videoHeight);
        var cropWidth = box.width / scale;
        var cropHeight = box.height / scale;

        var canvas = document.createElement('canvas');
        canvas.width = Math.round(cropWidth);
        canvas.height = Math.round(cropHeight);
        canvas.getContext('2d').drawImage(
            cameraVideo,
            (videoWidth - cropWidth) / 2, (videoHeight - cropHeight) / 2, cropWidth, cropHeight,
            0, 0, canvas.width, canvas.height
        );
        canvas.toBlob(function (blob) {
            try {
                setFile(new File([blob], 'camera.jpg', {type: 'image/jpeg'}));
            } catch (error) {
                console.warn('[camera] could not hand the photo to the form:', error.name);
                useNativeCamera(PHOTO_MESSAGES.noCamera);
                return;
            }
            showPhoto();
        }, 'image/jpeg', 0.9);
    }

    // ---------- Buttons ----------

    document.getElementById('shutterButton').addEventListener('click', capture);
    document.getElementById('uploadButton').addEventListener('click', function () { openPicker(false); });
    document.getElementById('chooseFileButton').addEventListener('click', function () { openPicker(false); });
    takePhotoButton.addEventListener('click', function () { openPicker(true); });
    galleryButton.addEventListener('click', function () { openPicker(false); });
    photoInput.addEventListener('change', showPhoto);

    retakeButton.addEventListener('click', function () {
        if (photoMode === 'live') {
            photoInput.value = '';
            showPhotoStep('camera');
            startCamera();
        } else {
            openPicker(photoMode === 'native');   // desktop: "Choose another"
        }
    });

    // ---------- Desktop: drag and drop, paste ----------

    function hasFiles(event) {
        return event.dataTransfer && Array.prototype.indexOf.call(event.dataTransfer.types, 'Files') !== -1;
    }

    // A photo can be dropped anywhere on the page; a missed drop never opens the file in the tab
    document.addEventListener('dragover', function (event) {
        if (photoMode === 'desktop' && hasFiles(event)) {
            event.preventDefault();
            photoPage.classList.add('is-dragging');
        }
    });
    document.addEventListener('dragleave', function (event) {
        if (!event.relatedTarget) {
            photoPage.classList.remove('is-dragging');   // left the window
        }
    });
    document.addEventListener('drop', function (event) {
        if (photoMode !== 'desktop' || !hasFiles(event)) {
            return;
        }
        event.preventDefault();
        photoPage.classList.remove('is-dragging');
        if (event.dataTransfer.files.length) {
            setFile(event.dataTransfer.files[0]);
            showPhoto();
        }
    });

    // Ctrl+V with an image on the clipboard; pasting text into the note still works as usual
    document.addEventListener('paste', function (event) {
        var files = event.clipboardData && event.clipboardData.files;
        var file = files && files[0];
        if (!file || file.type.indexOf('image/') !== 0) {
            return;
        }
        event.preventDefault();
        setFile(file);
        showPhoto();
    });

    // ---------- The camera only runs while it is seen ----------

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            stopCamera();
        } else if (photoMode === 'live' && !cameraState.hidden) {
            startCamera();
        }
    });
    window.addEventListener('pagehide', stopCamera);
    photoForm.addEventListener('submit', stopCamera);

    // ---------- Start ----------

    function startPhotoPage() {
        photoPage.dataset.mode = photoMode;
        if (photoMode === 'desktop') {
            document.getElementById('retakeLabel').textContent = 'Choose another';
        }
        if (photoInput.files.length) {
            showPhoto();   // back from Result with the photo still chosen
        } else if (photoMode === 'live') {
            showPhotoStep('camera');
            startCamera();
        } else if (photoMode === 'desktop') {
            showPhotoStep('drop');
        } else {
            showPhotoStep('note');
            updateNote();
        }
    }

    startPhotoPage();
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            startPhotoPage();
        }
    });
})();
