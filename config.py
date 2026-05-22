import os

# Where notes are saved.
# Calendar sessions go to: {NOTES_ROOT_PATH}/{subject}/{date}.md
# Manual sessions go to:   {NOTES_ROOT_PATH}/{date} - {name}.md
NOTES_ROOT_PATH = "C:/Personal/Notes/AI Notes"

# Where raw audio recordings are stored temporarily.
TEMP_AUDIO_DIR = "./temp_audio"

# Whisper
WHISPER_MODEL = "base"

# Ollama (used as fallback if DeepSeek API key is not set)
OLLAMA_MODEL = "llama3"
OLLAMA_BASE_URL = "http://localhost:11434"

# DeepSeek API (cloud summarization -- faster than local Ollama)
# Set DEEPSEEK_API_KEY as a Windows user environment variable (never put the key in this file).
# Get a key at https://platform.deepseek.com
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"

# Meeting detection
ZOOM_PROCESS_NAME = "Zoom.exe"
POLL_INTERVAL_SECONDS = 5

# How long the meeting must be gone before the session ends.
# Example: 30 = end after 30 seconds, 300 = tolerate up to 5 minutes of disconnection.
DISCONNECT_TOLERANCE_SECONDS = 30

# Pipeline settings -- saved by the GUI, used by monitor on boot.
PIPELINE_TRANSCRIBE = False
PIPELINE_SUMMARIZE = True
PIPELINE_QUIZ = False
PIPELINE_REALTIME = True






