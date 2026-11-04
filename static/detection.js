document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('camera-video');
    const overlay = document.getElementById('camera-overlay');
    const captureCanvas = document.getElementById('capture-canvas');
    const startButton = document.getElementById('start-camera');
    const stopButton = document.getElementById('stop-camera');
    const captureButton = document.getElementById('capture-frame');
    const status = document.getElementById('camera-status');
    const message = document.getElementById('camera-message');
    const resultEmpty = document.getElementById('result-empty');
    const resultContent = document.getElementById('result-content');
    const recent = document.getElementById('recent-predictions');
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    let mediaStream = null;
    let sessionId = null;
    let timerId = null;
    let sending = false;
    let predictions = [];

    async function postJson(url, payload = {}) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            const error = new Error(data.error || 'Request failed.');
            error.status = response.status;
            throw error;
        }
        return data;
    }

    function clearOverlay() {
        const context = overlay.getContext('2d');
        context.clearRect(0, 0, overlay.width, overlay.height);
    }

    async function sendFrame() {
        if (!sessionId || !video.videoWidth || sending) return;
        sending = true;
        captureCanvas.width = video.videoWidth;
        captureCanvas.height = video.videoHeight;
        captureCanvas.getContext('2d').drawImage(video, 0, 0);
        try {
            const result = await postJson('/api/detection', {
                session_id: sessionId,
                image: captureCanvas.toDataURL('image/jpeg', 0.72)
            });
            clearOverlay();
            if (!result.face_detected) {
                message.textContent = 'No face detected. Move into the frame and adjust the lighting.';
                return;
            }
            message.textContent = 'Prediction saved to your detection history.';
            document.getElementById('result-emotion').textContent = result.emotion[0].toUpperCase() + result.emotion.slice(1);
            document.getElementById('result-confidence').textContent = `${result.confidence.toFixed(1)}%`;
            document.getElementById('confidence-bar').style.width = `${Math.max(0, Math.min(100, result.confidence))}%`;
            document.getElementById('result-time').textContent = new Date(result.timestamp).toLocaleTimeString();
            resultEmpty.hidden = true;
            resultContent.hidden = false;
            const [x, y, width, height] = result.bbox;
            const context = overlay.getContext('2d');
            context.strokeStyle = '#9b8cff';
            context.lineWidth = Math.max(2, video.videoWidth / 300);
            context.strokeRect(x, y, width, height);
            predictions.unshift({ emotion: result.emotion, confidence: result.confidence });
            predictions = predictions.slice(0, 5);
            recent.innerHTML = predictions.map(item =>
                `<div class="recent-prediction"><span>${item.emotion[0].toUpperCase() + item.emotion.slice(1)}</span><strong>${item.confidence.toFixed(1)}%</strong></div>`
            ).join('');
        } catch (error) {
            message.textContent = error.message;
            if (error.status === 401) window.location.href = '/login';
        } finally {
            sending = false;
        }
    }

    async function stopCamera() {
        if (timerId) window.clearInterval(timerId);
        timerId = null;
        if (mediaStream) mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
        video.srcObject = null;
        clearOverlay();
        startButton.disabled = false;
        stopButton.disabled = true;
        captureButton.disabled = true;
        status.textContent = 'Camera stopped';
        status.classList.remove('status-active');
        document.getElementById('camera-placeholder').hidden = false;
        if (sessionId) {
            const currentSession = sessionId;
            sessionId = null;
            try { await postJson(`/api/detection/sessions/${currentSession}/stop`); }
            catch (error) { message.textContent = error.message; }
        }
    }

    startButton.addEventListener('click', async () => {
        startButton.disabled = true;
        message.textContent = 'Requesting camera permission…';
        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
            video.srcObject = mediaStream;
            await video.play();
            overlay.width = video.videoWidth;
            overlay.height = video.videoHeight;
            document.getElementById('camera-placeholder').hidden = true;
            const created = await postJson('/api/detection/sessions');
            sessionId = created.session_id;
            stopButton.disabled = false;
            captureButton.disabled = false;
            status.textContent = 'Detection active';
            status.classList.add('status-active');
            message.textContent = 'Detection is running. Predictions are recorded to your account.';
            timerId = window.setInterval(sendFrame, 1600);
            await sendFrame();
        } catch (error) {
            if (mediaStream) mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
            video.srcObject = null;
            document.getElementById('camera-placeholder').hidden = false;
            clearOverlay();
            startButton.disabled = false;
            message.textContent = error.name === 'NotAllowedError'
                ? 'Camera permission was denied. Allow camera access and try again.'
                : error.message;
        }
    });

    stopButton.addEventListener('click', stopCamera);
    captureButton.addEventListener('click', sendFrame);
    window.addEventListener('pagehide', () => {
        if (mediaStream) mediaStream.getTracks().forEach(track => track.stop());
        if (sessionId && navigator.sendBeacon) {
            const token = new URLSearchParams({ csrf_token: csrfToken });
            navigator.sendBeacon(`/api/detection/sessions/${sessionId}/stop`, token);
        }
    });
});
