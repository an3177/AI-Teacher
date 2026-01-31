// AI Interview Teacher - Voice Chat JavaScript

const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const chatContainer = document.getElementById("chatContainer");
const statusDiv = document.getElementById("status");
const typingIndicator = document.getElementById("typingIndicator");

let ws;
let mediaRecorder;
let audioContext;
let audioQueue = [];
let isPlaying = false;
let recordedChunks = [];
let isListening = false;

function updateStatus(message, type = 'info') {
  statusDiv.textContent = message;
  statusDiv.className = `status ${type}`;
  console.log(`[${type.toUpperCase()}] ${message}`);
}

function addMessage(text, isUser = true) {
  const messageDiv = document.createElement('div');
  if (isUser) {
    messageDiv.className = "message user";
  } else {
    messageDiv.className = "message ai";
  }

  messageDiv.innerHTML = `
    <div class="message-content">${text}</div>
  `;

  chatContainer.appendChild(messageDiv);
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function showTyping(show) {
  if (show) {
    typingIndicator.className = 'typing-indicator active';
  } else {
    typingIndicator.className = 'typing-indicator';
  }
  if (show) {
    chatContainer.appendChild(typingIndicator);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }
}

async function playAudioChunk(arrayBuffer) {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    console.log('Audio context initialized');
  }
  
  if (audioContext.state === 'suspended') {
    await audioContext.resume();
  }
  
  try {
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer.slice(0));
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContext.destination);
    
    return new Promise((resolve) => {
      source.onended = resolve;
      source.start();
    });
  } catch (error) {
    console.error("Error playing audio:", error);
  }
}

async function processAudioQueue() {
  if (isPlaying || audioQueue.length === 0) return;
  
  isPlaying = true;
  updateStatus("AI is speaking...", "success");
  
  while (audioQueue.length > 0) {
    const chunk = audioQueue.shift();
    try {
      await playAudioChunk(chunk);
    } catch (error) {
      console.error('Error processing audio chunk:', error);
    }
  }
  
  isPlaying = false;
  updateStatus("Ready to practice", "info");
}

let silenceTimeout;
let inactivityTimeout;
let countdownInterval;
let consecutiveSilenceFrames = 0;
const SILENCE_DURATION = 2000; 
const INACTIVITY_DURATION = 60000; 
const SILENCE_THRESHOLD = 150;
const FRAMES_FOR_SILENCE = 15;

function startCountdown(seconds) {
  clearInterval(countdownInterval);
  let remaining = seconds;
  updateStatus(`AI is thinking... (${remaining}s)`, "processing");
  
  countdownInterval = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
      clearInterval(countdownInterval);
      updateStatus("AI is responding...", "processing");
    } else {
      updateStatus(`AI is thinking... (${remaining}s)`, "processing");
    }
  }, 1000);
}

function startContinuousListening() {
  try {
    clearInterval(countdownInterval);
    startBtn.disabled = true;
    stopBtn.disabled = false;
    recordedChunks = [];
    isListening = true;
    updateStatus("Connecting...", "info");

    // Connect WebSocket
    ws = new WebSocket("ws://localhost:8000/voice_chat");
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      updateStatus("Listening continuously...", "recording");
      startRecording();
    };

    ws.onmessage = async (event) => {
      // Handle JSON messages (transcripts)
      if (typeof event.data === 'string') {
        const data = JSON.parse(event.data);
        
        if (data.type === 'user_transcript') {
          addMessage(data.text, true);
          showTyping(true);
          startCountdown(5); // Estimate 5 seconds for AI to think
        } else if (data.type === 'ai_transcript') {
          clearInterval(countdownInterval);
          showTyping(false);
          addMessage(data.text, false);
          
          // Only resume listening if still in listening mode
          if (isListening && ws && ws.readyState === WebSocket.OPEN) {
            updateStatus("Listening...", "recording");
            startRecording();
          }
        }
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      updateStatus("Connection error", "error");
    };

    ws.onclose = () => {
      isListening = false;
      startBtn.disabled = false;
      stopBtn.disabled = true;
      updateStatus("Stopped listening", "info");
    };

  } catch (error) {
    console.error("Error:", error);
    updateStatus("Error: " + error.message, "error");
    isListening = false;
    startBtn.disabled = false;
    stopBtn.disabled = true;
  }
}

async function startRecording() {
  try {
    recordedChunks = [];
    
    // Capture microphone
    const stream = await navigator.mediaDevices.getUserMedia({ 
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      } 
    });

    const mimeType = 'audio/webm;codecs=opus';
    mediaRecorder = new MediaRecorder(stream, { 
      mimeType,
      audioBitsPerSecond: 128000
    });

    // Analyze audio in real-time for silence detection
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    source.connect(analyser);

    let isSpeaking = false;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    const checkSilence = () => {
      analyser.getByteFrequencyData(dataArray);
      
      // More robust silence detection using frequency analysis
      const lowFreq = dataArray.slice(0, dataArray.length / 3).reduce((a, b) => a + b) / (dataArray.length / 3);
      const midFreq = dataArray.slice(dataArray.length / 3, 2 * dataArray.length / 3).reduce((a, b) => a + b) / (dataArray.length / 3);
      const voiceEnergy = Math.max(lowFreq, midFreq); // Voice typically in low-mid frequencies
      
      if (voiceEnergy < SILENCE_THRESHOLD) {
        // Potential silence
        consecutiveSilenceFrames++;
        if (consecutiveSilenceFrames >= FRAMES_FOR_SILENCE && isSpeaking) {
          isSpeaking = false;
          console.log(`Consistent silence detected (${consecutiveSilenceFrames} frames), waiting ${SILENCE_DURATION}ms before stopping...`);
          // Set timeout to stop recording if silence continues
          clearTimeout(silenceTimeout);
          silenceTimeout = setTimeout(() => {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
              console.log('Stopping recording after silence period');
              mediaRecorder.stop();
            }
          }, SILENCE_DURATION);
        }
      } else {
        // Sound detected
        consecutiveSilenceFrames = 0; // Reset silence counter
        if (!isSpeaking) {
          isSpeaking = true;
          clearTimeout(silenceTimeout);
          updateStatus("🎤 Recording...", "recording");
        }
      }
      
      requestAnimationFrame(checkSilence);
    };

    checkSilence();

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        recordedChunks.push(e.data);
      }
    };

    mediaRecorder.onstop = async () => {
      clearTimeout(silenceTimeout);
      clearTimeout(inactivityTimeout);
      clearInterval(countdownInterval);
      
      // Stop audio stream tracks
      stream.getTracks().forEach(track => track.stop());
      
      if (recordedChunks.length > 0 && ws && ws.readyState === WebSocket.OPEN && isListening) {
        updateStatus("Sending audio...", "info");
        const audioBlob = new Blob(recordedChunks, { type: mimeType });
        console.log(`Sending ${audioBlob.size} bytes of audio`);
        ws.send(audioBlob);
        recordedChunks = [];
      }
    };

    mediaRecorder.start();

  } catch (error) {
    console.error("Error starting recording:", error);
    updateStatus("Error: " + error.message, "error");
  }
}

startBtn.onclick = startContinuousListening;

stopBtn.onclick = () => {
  clearTimeout(silenceTimeout);
  clearTimeout(inactivityTimeout);
  clearInterval(countdownInterval);
  
  isListening = false;
  updateStatus("Stopped", "info");
  startBtn.disabled = false;
  stopBtn.disabled = true;

  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(track => track.stop());
  }
  if (ws) ws.close();
  
  audioQueue = [];
  isPlaying = false;
  recordedChunks = [];
  showTyping(false);
};

// Load selected background on page load
window.addEventListener('DOMContentLoaded', () => {
  const selectedBackground = localStorage.getItem('selectedBackground');
  if (selectedBackground) {
    document.body.className = selectedBackground + '-background';
  }
});
