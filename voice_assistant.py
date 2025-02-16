from flask import Flask, request, Response, stream_with_context
import re, requests, io, wave, base64, json, time
import numpy as np
from TTS.api import TTS

app = Flask(__name__)

# -------------------------------
# Global Conversation History
# -------------------------------
conversation_history = []

# -------------------------------
# API Configuration
# -------------------------------
API_CONFIG = {
    'host': 'localhost',
    'port': 1234,
    'base_url': '/v1/chat/completions'
}

def get_api_url():
    return f"http://{API_CONFIG['host']}:{API_CONFIG['port']}{API_CONFIG['base_url']}"

# -------------------------------
# Utility Functions
# -------------------------------
def clean_response(text):
    """Clean and normalize text."""
    text = text.lower()
    question_starters = [
        "what is", "what are", "how to", "how do", "why is", "why are",
        "when is", "when are", "where is", "where are", "who is", "who are",
        "can you", "could you", "would you", "tell me"
    ]
    last_question_pos = -1
    for starter in question_starters:
        pos = text.rfind(starter)
        if pos > last_question_pos:
            last_question_pos = pos
    if last_question_pos != -1:
        text = text[last_question_pos:]
        sentences = re.split('[.!?]', text)
        for i, sentence in enumerate(sentences):
            if not any(starter in sentence.lower() for starter in question_starters):
                text = '. '.join(sentences[i:])
                break
    text = re.sub(r'\s+', ' ', text).strip()
    if text:
        text = text[0].upper() + text[1:]
    text = re.sub(r'^[?]\s*', '', text)
    return text

def query_local_api(prompt):
    """
    Uses your real API endpoint to get a conversation response.
    Conversation history is maintained.
    """
    global conversation_history
    try:
        messages = []
        if not conversation_history or conversation_history[0].get("role") != "system":
            system_message = {
                "role": "system",
                "content": ("You are a helpful assistant. Provide direct answers without "
                            "repeating the question. Keep responses clear and concise.")
            }
            messages.append(system_message)
            conversation_history.insert(0, system_message)
        messages.extend(conversation_history[-5:])
        user_message = {"role": "user", "content": prompt}
        messages.append(user_message)
        conversation_history.append(user_message)
        payload = {"messages": messages, "temperature": 0.7, "max_tokens": 2000}
        response = requests.post(get_api_url(), json=payload, headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            response_data = response.json()
            assistant_message = response_data['choices'][0]['message']['content']
            cleaned = clean_response(assistant_message)
            conversation_history.append({"role": "assistant", "content": cleaned})
            return cleaned
        else:
            print(f"API Error: Status code {response.status_code}")
            return "I'm sorry, I encountered an API error."
    except Exception as e:
        print(f"Error in API query: {e}")
        return "I'm sorry, there was an error processing your request."

# -------------------------------
# Initialize Jenny TTS Model
# -------------------------------
tts_model = TTS(model_name="tts_models/en/jenny/jenny", progress_bar=False, gpu=False)

# -------------------------------
# SSE Streaming Endpoint
# -------------------------------
@app.route('/converse_stream')
def converse_stream():
    query = request.args.get("q", "").strip()
    if not query:
        return Response("Empty query", status=400)

    response_text = query_local_api(query)
    # Split response into sentences using punctuation as delimiter.
    sentences = re.split(r'(?<=[.!?])\s+', response_text)

    def generate():
        for sentence in sentences:
            if sentence:
                try:
                    # Synthesize the sentence using Jenny TTS.
                    audio_samples = tts_model.tts(sentence)
                    audio_np = np.array(audio_samples)
                    # Convert float samples (assumed in [-1,1]) to 16-bit PCM.
                    audio_int16 = (audio_np * 32767).astype(np.int16)
                    
                    # Write to a WAV file in memory.
                    wav_io = io.BytesIO()
                    with wave.open(wav_io, 'wb') as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(48000)
                        wav_file.writeframes(audio_int16.tobytes())
                    wav_data = wav_io.getvalue()
                    audio_base64 = base64.b64encode(wav_data).decode('utf-8')
                except Exception as e:
                    print("TTS generation error for sentence:", sentence, e)
                    audio_base64 = ""
                
                payload = json.dumps({"sentence": sentence, "audio": audio_base64})
                yield f"data: {payload}\n\n"
                time.sleep(0.1)
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

# -------------------------------
# HTML Page with Recording & Streaming
# -------------------------------
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
      <title>Web Voice Assistant (Streaming with Recording)</title>
      <style>
        #transcript { margin-top: 1em; }
      </style>
    </head>
    <body>
      <h1>Voice Assistant Conversation</h1>
      <p>
        <button id="startButton">Start Recording</button>
        <button id="stopButton" disabled>Stop Recording</button>
      </p>
      <p>
        <input type="text" id="query" placeholder="Your query will appear here" size="50"/>
        <button id="sendButton">Send</button>
      </p>
      <!-- Transcript now appears below the text box -->
      <div id="transcript"></div>
      <audio id="assistantAudio"></audio>
      <script>
        // Initialize Speech Recognition (Chrome-only)
        var recognition;
        if (!('webkitSpeechRecognition' in window)) {
          alert("Your browser does not support speech recognition. Please use Chrome.");
        } else {
          recognition = new webkitSpeechRecognition();
          recognition.continuous = false;
          recognition.interimResults = false;
          recognition.lang = 'en-US';
          recognition.onresult = function(event) {
            var transcript = event.results[0][0].transcript;
            document.getElementById('query').value = transcript;
          };
          recognition.onerror = function(event) {
            console.error(event);
          };
        }
        
        // Start/Stop recording buttons.
        document.getElementById('startButton').addEventListener('click', function() {
          recognition.start();
          document.getElementById('startButton').disabled = true;
          document.getElementById('stopButton').disabled = false;
        });
        document.getElementById('stopButton').addEventListener('click', function() {
          recognition.stop();
          document.getElementById('startButton').disabled = false;
          document.getElementById('stopButton').disabled = true;
        });
        
        // Audio playback queue.
        const audioQueue = [];
        let isPlaying = false;
        const audioElement = document.getElementById('assistantAudio');
        const transcriptEl = document.getElementById('transcript');

        function playNext() {
          if (audioQueue.length > 0) {
            isPlaying = true;
            const segment = audioQueue.shift();
            audioElement.src = "data:audio/wav;base64," + segment;
            audioElement.play();
          } else {
            isPlaying = false;
          }
        }
        audioElement.onended = playNext;
        
        // When the user clicks Send, start streaming the response.
        document.getElementById('sendButton').addEventListener('click', function() {
          const query = document.getElementById('query').value;
          if (!query) return;
          // Clear any previous transcript and queued audio.
          transcriptEl.innerHTML = "";
          audioQueue.length = 0;
          isPlaying = false;
          
          const eventSource = new EventSource('/converse_stream?q=' + encodeURIComponent(query));
          eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            // Append the sentence text to the transcript (now below the text box).
            transcriptEl.innerHTML += data.sentence + " ";
            if (data.audio) {
              audioQueue.push(data.audio);
              if (!isPlaying) {
                playNext();
              }
            }
          };
          eventSource.onerror = function(event) {
            console.error("EventSource error:", event);
            eventSource.close();
          };
        });
      </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
