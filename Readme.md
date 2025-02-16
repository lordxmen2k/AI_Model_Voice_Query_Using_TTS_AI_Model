# Voice Assistant with Streaming TTS

This project is a Flask-based voice assistant that leverages Text-to-Speech (TTS) capabilities to generate audio responses based on user queries. The assistant processes user input, sends it to a local API for conversational responses, cleans and processes the text, and then streams synthesized audio back to the client via Server-Sent Events (SSE).

## Features

- **Speech Recognition:**  
  Uses the Chrome-specific `webkitSpeechRecognition` API to capture user queries.
  
- **Text Query Processing:**  
  Sends queries to a local API endpoint to retrieve conversational responses. Conversation history is maintained for context.

- **Text-to-Speech (TTS):**  
  Utilizes the `TTS` library to synthesize voice responses using the "Jenny" model.

- **Streaming Audio:**  
  Streams audio responses to the client as Base64-encoded WAV files via an SSE endpoint.

- **Web Interface:**  
  A simple HTML interface allows users to record their voice, view the transcribed query, and listen to the assistant's audio response.

## Endpoints

- **`/converse_stream`:**  
  Streams TTS audio and text responses for a given query.  
  **Usage:**  
  Access via browser with query parameter, e.g., `http://<host>:5000/converse_stream?q=Your%20question`.

- **`/`:**  
  Serves the HTML page that provides the user interface for recording and playing the voice assistant responses.

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/voice-assistant.git
   cd voice-assistant
