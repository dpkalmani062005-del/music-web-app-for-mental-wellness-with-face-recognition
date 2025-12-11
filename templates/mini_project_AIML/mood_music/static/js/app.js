/*
  Frontend logic for AI Mood Detection Music Player
  - Initializes camera stream
  - Loads face-api.js models from /static/models
  - Runs face expression detection and updates a Chart.js bar chart
  - Every 5 seconds, selects the dominant mood and requests a song from backend
  - Avoids reloading the same song path repeatedly when mood doesn't change
*/

const videoEl = document.getElementById('video');
const audioEl = document.getElementById('audio');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusEl = document.getElementById('status');
const overlayMsgEl = document.getElementById('overlayMsg');
const moodEl = document.getElementById('mood');

// Chart.js setup
let chart;
const chartCtx = document.getElementById('moodChart').getContext('2d');

// Config
const MODEL_URL = '/static/models';
const DETECT_INTERVAL_MS = 1000; // run expression detection every 1s
const MOOD_UPDATE_MS = 5000; // update song every 5s

// State
let streamStarted = false;
let detectionTimer = null;
let moodUpdateTimer = null;
let lastDetections = null; // last detection result
let lastPlayedPath = null; // avoid reloading same src
let lastDominantMood = null;
let currentStream = null; // track the media stream

// Expressions in face-api.js: neutral, happy, sad, angry, fearful, disgusted, surprised
const orderedEmotions = ['neutral', 'happy', 'sad', 'angry', 'fearful', 'disgusted', 'surprised'];

function initChart() {
  chart = new Chart(chartCtx, {
    type: 'bar',
    data: {
      labels: orderedEmotions,
      datasets: [
        {
          label: 'Emotion Confidence',
          data: new Array(orderedEmotions.length).fill(0),
          backgroundColor: orderedEmotions.map((e) => (e === 'happy' ? 'rgba(255, 206, 86, 0.6)' : 'rgba(255,255,255,0.3)')),
          borderColor: 'rgba(255, 206, 86, 1)',
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
          max: 1,
          ticks: {
            color: '#ddd',
          },
          grid: { color: 'rgba(255,255,255,0.1)' },
        },
        x: {
          ticks: { color: '#ccc' },
          grid: { color: 'rgba(255,255,255,0.05)' },
        },
      },
      plugins: {
        legend: { labels: { color: '#eee' } },
      },
    },
  });
}

function updateChart(expressions) {
  if (!chart) return;
  const values = orderedEmotions.map((k) => expressions[k] || 0);
  chart.data.datasets[0].data = values;
  chart.update();
}

function clearChart() {
  if (!chart) return;
  chart.data.datasets[0].data = new Array(orderedEmotions.length).fill(0);
  chart.update();
}

function setStatus(msg) {
  statusEl.textContent = msg;
}

function showNoFaceOverlay(show) {
  overlayMsgEl.classList.toggle('hidden', !show);
}

async function loadModels() {
  await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
  await faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL);
}

function getUserMediaCompat(constraints) {
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    return navigator.mediaDevices.getUserMedia(constraints);
  }
  const getUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia;
  if (!getUserMedia) {
    return Promise.reject(new Error('getUserMedia not available'));
  }
  return new Promise((resolve, reject) => {
    try {
      getUserMedia.call(navigator, constraints, resolve, reject);
    } catch (e) {
      reject(e);
    }
  });
}

async function startCamera() {
  try {
    // If modern API is missing, we will try legacy prefixes below

    // Check camera permission state if supported
    try {
      if (navigator.permissions && navigator.permissions.query) {
        const p = await navigator.permissions.query({ name: 'camera' });
        if (p.state === 'denied') {
          setStatus('Camera permission is blocked. Allow it in browser site settings and retry.');
          return;
        }
      }
    } catch (_) { /* ignore */ }

    const primary = { video: { facingMode: 'user' }, audio: false };
    let stream;
    try {
      stream = await getUserMediaCompat(primary);
    } catch (e1) {
      console.warn('Primary constraint failed, trying fallback {video:true}', e1);
      const fallback = { video: true, audio: false };
      stream = await getUserMediaCompat(fallback);
    }

    videoEl.srcObject = stream;
    // Ensure video starts; some browsers need explicit play on user gesture
    try { await videoEl.play(); } catch (e) { console.warn('video.play() failed (will display once stream has data):', e); }
    streamStarted = true;
    currentStream = stream;
    setStatus('Camera is on. Models loading...');
  } catch (err) {
    console.error(err);
    const hint = 'Check Windows privacy (Settings > Privacy & security > Camera), ensure browser has access, close other apps using camera, and allow camera in site settings.';
    setStatus(`Error: Unable to access camera. (${err?.name || 'Unknown'}) ${hint}`);
  }
}

function dominantMoodFromExpressions(expressions) {
  let bestKey = null;
  let bestVal = -1;
  for (const key of orderedEmotions) {
    const v = expressions[key] ?? 0;
    if (v > bestVal) {
      bestVal = v;
      bestKey = key;
    }
  }
  return bestKey || 'neutral';
}

async function detectLoop() {
  if (!streamStarted) return;
  try {
    const detections = await faceapi
      .detectSingleFace(
        videoEl,
        new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 })
      )
      .withFaceExpressions();

    if (!detections) {
      lastDetections = null;
      showNoFaceOverlay(true);
      moodEl.textContent = '-';
      clearChart();
      setStatus('No face detected.');
    } else {
      lastDetections = detections;
      showNoFaceOverlay(false);
      const expressions = detections.expressions || {};
      updateChart(expressions);
      const mood = dominantMoodFromExpressions(expressions);
      moodEl.textContent = mood;
      setStatus('Detecting emotions...');
    }
  } catch (e) {
    console.error(e);
  }
}

async function updateSongForMood() {
  if (!lastDetections) return; // do nothing if no face
  const mood = dominantMoodFromExpressions(lastDetections.expressions || {});
  if (!mood) return;

  // Avoid refetch if mood unchanged and audio is already playing same src
  if (mood === lastDominantMood && audioEl.currentSrc && !audioEl.paused) {
    return;
  }

  try {
    const resp = await fetch(`/api/song/${mood}`);
    const data = await resp.json();
    if (!data.ok) {
      setStatus(data.message || 'No songs available.');
      return;
    }
    const nextPath = data.path; // e.g., /static/static_music/happy1.mp3
    if (nextPath && nextPath !== lastPlayedPath) {
      audioEl.src = nextPath;
      await audioEl.play().catch(() => {/* autoplay may fail; user can press play */});
      lastPlayedPath = nextPath;
      lastDominantMood = mood;
      setStatus(`Playing: ${data.file} for mood ${data.mood}`);
    }
  } catch (e) {
    console.error(e);
  }
}

function stopDetection() {
  if (detectionTimer) {
    clearInterval(detectionTimer);
    detectionTimer = null;
  }
  if (moodUpdateTimer) {
    clearInterval(moodUpdateTimer);
    moodUpdateTimer = null;
  }
}

function stopCamera() {
  if (currentStream) {
    currentStream.getTracks().forEach(track => track.stop());
    currentStream = null;
  }
  videoEl.srcObject = null;
  streamStarted = false;
  lastDetections = null;
  clearChart();
  showNoFaceOverlay(false);
  moodEl.textContent = '-';
}

async function onStart() {
  startBtn.disabled = true;
  stopBtn.disabled = false;
  setStatus('Starting...');
  await startCamera();
  if (!streamStarted) { 
    startBtn.disabled = false; 
    stopBtn.disabled = true;
    return; 
  }
  try {
    await loadModels();
    setStatus('Models loaded. Detecting...');
  } catch (e) {
    console.error(e);
    setStatus('Error loading models. Place files in /static/models');
    startBtn.disabled = false;
    stopBtn.disabled = true;
    return;
  }

  initChart();
  detectionTimer = setInterval(detectLoop, DETECT_INTERVAL_MS);
  moodUpdateTimer = setInterval(updateSongForMood, MOOD_UPDATE_MS);
}

function onStop() {
  stopDetection();
  stopCamera();
  startBtn.disabled = false;
  stopBtn.disabled = true;
  setStatus('Stopped. Camera off. Song locked.');
}

startBtn.addEventListener('click', onStart);
stopBtn.addEventListener('click', onStop);


