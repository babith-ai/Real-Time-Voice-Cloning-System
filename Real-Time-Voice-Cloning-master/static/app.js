/**
 * Voice Cloning Studio - Frontend JavaScript
 * Handles recording, synthesis, and playback
 */

let mediaRecorder;
let audioChunks = [];
let recordingStartTime;
let timerInterval;
let currentEmbedding = null;
let synthesizedAudioBlob = null;
let audioContext;
let mediaStream;

// DOM Elements
const recordBtn = document.getElementById('recordBtn');
const stopBtn = document.getElementById('stopBtn');
const clearBtn = document.getElementById('clearBtn');
const status = document.getElementById('status');
const timer = document.getElementById('timer');
const timerDisplay = document.getElementById('time');
const waveformContainer = document.getElementById('waveform-container');
const playbackSection = document.getElementById('playback-section');
const recordedAudio = document.getElementById('recordedAudio');
const useBtn = document.getElementById('useBtn');
const textInput = document.getElementById('textInput');
const charCount = document.getElementById('charCount');
const synthesizeBtn = document.getElementById('synthesizeBtn');
const synthesisStatus = document.getElementById('synthesis-status');
const synthesisSection = document.getElementById('synthesis-section');
const outputSection = document.getElementById('output-section');
const outputAudioContainer = document.getElementById('output-audio-container');
const outputAudio = document.getElementById('outputAudio');
const downloadBtn = document.getElementById('downloadBtn');
const playBtn = document.getElementById('playBtn');
const loading = document.getElementById('loading');
const loadingText = document.getElementById('loadingText');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkMicrophonePermission();
});

function setupEventListeners() {
    recordBtn.addEventListener('click', startRecording);
    stopBtn.addEventListener('click', stopRecording);
    clearBtn.addEventListener('click', clearRecording);
    useBtn.addEventListener('click', useRecording);
    textInput.addEventListener('input', updateCharCount);
    synthesizeBtn.addEventListener('click', synthesizeText);
    downloadBtn.addEventListener('click', downloadAudio);
    playBtn.addEventListener('click', playAudio);
}

async function checkMicrophonePermission() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(track => track.stop());
        showStatus('Microphone access granted', 'success');
    } catch (err) {
        showStatus('⚠ Microphone permission denied. Please enable it in browser settings.', 'error');
        recordBtn.disabled = true;
    }
}

async function startRecording() {
    try {
        audioChunks = [];
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaStream = stream;
        
        // Create AudioContext and ScriptProcessorNode for better audio capture
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

        mediaRecorder.ondataavailable = (e) => {
            audioChunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
            handleRecordingComplete(stream);
        };

        mediaRecorder.start();
        recordingStartTime = Date.now();
        recordBtn.disabled = true;
        stopBtn.disabled = false;
        clearBtn.disabled = true;
        timer.classList.remove('hidden');
        startTimer();
        showStatus('🔴 Recording... speak now', 'info');
    } catch (err) {
        showStatus('Error accessing microphone: ' + err.message, 'error');
    }
}

function stopRecording() {
    if (mediaRecorder) {
        mediaRecorder.stop();
        stopBtn.disabled = true;
        clearTimer();
        timer.classList.add('hidden');
        showStatus('⏸ Recording stopped, processing...', 'info');
    }
}

function startTimer() {
    let seconds = 0;
    timerInterval = setInterval(() => {
        seconds++;
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        timerDisplay.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }, 1000);
}

function clearTimer() {
    if (timerInterval) clearInterval(timerInterval);
}

function clearRecording() {
    audioChunks = [];
    recordedAudio.src = '';
    playbackSection.classList.add('hidden');
    waveformContainer.classList.add('hidden');
    recordBtn.disabled = false;
    clearBtn.disabled = true;
    useBtn.disabled = true;
    currentEmbedding = null;
    showStatus('Recording cleared', 'info');
}

async function handleRecordingComplete(stream) {
    stream.getTracks().forEach(track => track.stop());

    const recordedBlob = new Blob(audioChunks, { type: 'audio/webm' });
    
    // Decode the webm blob to PCM, then convert to WAV
    showLoading(true, 'Processing audio...');
    
    try {
        const arrayBuffer = await recordedBlob.arrayBuffer();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        
        // Convert AudioBuffer to WAV Blob
        const wavBlob = await audioBufferToWav(audioBuffer);
        recordedAudio.src = URL.createObjectURL(wavBlob);

        // Display waveform
        drawWaveformFromAudioBuffer(audioBuffer);
        waveformContainer.classList.remove('hidden');
        playbackSection.classList.remove('hidden');
        clearBtn.disabled = false;
        useBtn.disabled = false;

        // Process recording (send WAV to backend)
        showLoading(true, 'Processing your voice...');
        const formData = new FormData();
        formData.append('audio', wavBlob, 'recording.wav');

        const response = await fetch('/api/record', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        console.log('Recording response:', response.status, result);

        if (response.ok) {
            currentEmbedding = result.embedding;
            showStatus('✓ Voice recorded successfully! Click "Use This Recording" to continue.', 'success');
        } else {
            showStatus('Error: ' + result.error, 'error');
            useBtn.disabled = true;
        }
    } catch (err) {
        console.error('Error processing recording:', err);
        showStatus('Error processing recording: ' + err.message, 'error');
        useBtn.disabled = true;
    } finally {
        showLoading(false);
    }
}

// Convert AudioBuffer to WAV Blob
async function audioBufferToWav(audioBuffer) {
    const numberOfChannels = audioBuffer.numberOfChannels;
    const sampleRate = audioBuffer.sampleRate;
    const format = 1; // PCM
    const bitDepth = 16;
    
    // Get channel data
    const channels = [];
    for (let i = 0; i < numberOfChannels; i++) {
        channels.push(audioBuffer.getChannelData(i));
    }
    
    // Calculate correct buffer size
    const numSamples = audioBuffer.length;
    const dataSize = numSamples * numberOfChannels * (bitDepth / 8);
    const bufferSize = 44 + dataSize; // 44 byte header + PCM data
    
    const arrayBuffer = new ArrayBuffer(bufferSize);
    const view = new DataView(arrayBuffer);
    
    // Helper to write strings
    const writeString = (view, offset, string) => {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    };
    
    // Write WAV header
    writeString(view, 0, 'RIFF');
    view.setUint32(4, bufferSize - 8, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true); // fmt chunk size
    view.setUint16(20, format, true); // format code (PCM)
    view.setUint16(22, numberOfChannels, true); // channels
    view.setUint32(24, sampleRate, true); // sample rate
    view.setUint32(28, sampleRate * numberOfChannels * bitDepth / 8, true); // byte rate
    view.setUint16(32, numberOfChannels * bitDepth / 8, true); // block align
    view.setUint16(34, bitDepth, true); // bits per sample
    writeString(view, 36, 'data');
    view.setUint32(40, dataSize, true); // data size
    
    // Write PCM data
    let index = 44;
    for (let i = 0; i < numSamples; i++) {
        for (let channel = 0; channel < numberOfChannels; channel++) {
            let sample = channels[channel][i];
            // Clamp and convert to 16-bit PCM
            sample = Math.max(-1, Math.min(1, sample));
            sample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
            view.setInt16(index, sample, true);
            index += 2;
        }
    }
    
    return new Blob([arrayBuffer], { type: 'audio/wav' });
}

// Draw waveform from AudioBuffer (faster than decoding again)
function drawWaveformFromAudioBuffer(audioBuffer) {
    const canvas = document.getElementById('waveform');
    const ctx = canvas.getContext('2d');
    
    const width = canvas.width;
    const height = canvas.height;
    const data = audioBuffer.getChannelData(0);
    const step = Math.ceil(data.length / width);
    const amp = height / 2;
    
    ctx.fillStyle = '#f8f9fa';
    ctx.fillRect(0, 0, width, height);
    
    ctx.strokeStyle = '#667eea';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, amp);
    
    for (let i = 0; i < width; i++) {
        let min = 1.0;
        let max = -1.0;
        for (let j = 0; j < step; j++) {
            const datum = data[i * step + j];
            if (datum < min) min = datum;
            if (datum > max) max = datum;
        }
        ctx.lineTo(i, amp - max * amp);
        ctx.lineTo(i, amp - min * amp);
    }
    
    ctx.lineTo(width, amp);
    ctx.stroke();
}


function useRecording() {
    if (currentEmbedding) {
        showStatus('✓ Recording selected. Now write text to synthesize!', 'success');
        // Enable synthesis section
        synthesisSection.classList.add('active');
        textInput.disabled = false;
        synthesizeBtn.disabled = false;
        outputSection.classList.add('active');
    } else {
        showStatus('Error: No embedding available. Try recording again.', 'error');
    }
}

function updateCharCount() {
    charCount.textContent = textInput.value.length;
    if (textInput.value.length > 500) {
        textInput.value = textInput.value.substring(0, 500);
        charCount.textContent = '500';
    }
}

async function synthesizeText() {
    const text = textInput.value.trim();

    if (!text) {
        showStatus('Please enter text to synthesize', 'error');
        return;
    }

    if (!currentEmbedding) {
        showStatus('Please record a voice sample first', 'error');
        return;
    }

    showLoading(true, 'Synthesizing speech... (this may take a minute)');
    synthesisStatus.textContent = '';

    try {
        const payload = {
            text: text,
            embedding: currentEmbedding
        };

        const response = await fetch('/api/synthesize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            synthesizedAudioBlob = await response.blob();
            outputAudio.src = URL.createObjectURL(synthesizedAudioBlob);
            outputAudioContainer.classList.remove('hidden');
            outputSection.classList.add('active');
            showStatus('✓ Speech synthesized successfully!', 'success');
            showLoading(false);
        } else {
            const error = await response.json();
            showStatus('Error: ' + (error.error || 'Synthesis failed'), 'error');
            showLoading(false);
        }
    } catch (err) {
        showStatus('Error during synthesis: ' + err.message, 'error');
        showLoading(false);
    }
}

function downloadAudio() {
    if (synthesizedAudioBlob) {
        const url = URL.createObjectURL(synthesizedAudioBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `voice_cloning_${Date.now()}.wav`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showStatus('✓ Audio downloaded!', 'success');
    }
}

function playAudio() {
    if (outputAudio.src) {
        if (outputAudio.paused) {
            outputAudio.play();
            playBtn.textContent = '⏸ Pause';
        } else {
            outputAudio.pause();
            playBtn.textContent = '▶ Play';
        }
    }
}

function showStatus(message, type = 'info') {
    status.textContent = message;
    status.className = `status-message show ${type}`;
    setTimeout(() => {
        status.classList.remove('show');
    }, 5000);
}

function showLoading(show, text = 'Processing...') {
    if (show) {
        loading.classList.remove('hidden');
        loadingText.textContent = text;
    } else {
        loading.classList.add('hidden');
    }
}
