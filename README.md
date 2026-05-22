# AI Note Taker

Automatically records, transcribes, and summarises Zoom and Google Meet sessions into structured Markdown notes.

**Windows 11 only.**

---

## Features

- Detects active Zoom or Google Meet calls and starts recording automatically
- Transcribes audio using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (local, CPU-optimised)
- Summarises transcripts via **DeepSeek API** (fast, cloud) or **Ollama + Llama 3** (fully local fallback)
- Checks Google Calendar to name notes automatically
- Saves structured Markdown notes to any folder you choose
- Generates multiple-choice quizzes from notes
- Real-time transcription mode (results appear live during recording)
- Desktop GUI with drag-and-drop for processing existing files

---

## Installation

### 1. Prerequisites

Install these before running the installer:

- **Python 3.11** — [python.org/downloads](https://www.python.org/downloads/)
  During install, check **"Add Python to PATH"**
- **Git** (to clone the repo) — [git-scm.com](https://git-scm.com)

### 2. Clone and install

```
git clone <repo-url>
cd ai-note-taker
```

Then double-click **`Install.bat`**.

The installer will:
- Create a Python virtual environment
- Install all dependencies
- Ask where you want notes saved
- Download and install [Ollama](https://ollama.com) and the Llama 3 model (~4.7 GB, one-time)
- Create a desktop shortcut

### 3. Launch

Double-click **`AI Note Taker`** on your Desktop, or run **`Launch App.bat`** from the project folder.

---

## Summarisation: DeepSeek API vs Ollama

By default the app uses **Ollama (Llama 3)** running locally — no internet required, but slow on CPU (several minutes per session).

For much faster summarisation, set up the **DeepSeek API**:

1. Create an account at [platform.deepseek.com](https://platform.deepseek.com) and generate an API key (free credits included)
2. Set it as a Windows environment variable — run this once in PowerShell:
   ```powershell
   [System.Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "sk-your-key-here", "User")
   ```
3. Restart the app — summarisation now uses DeepSeek automatically

If `DEEPSEEK_API_KEY` is not set, the app falls back to Ollama with no other changes needed.

---

## Google Calendar (optional)

If set up, the app automatically names sessions from your calendar.

1. Go to [Google Cloud Console](https://console.cloud.google.com) and create a new project
2. Enable the **Google Calendar API** (APIs & Services → Enable APIs → search "Google Calendar API")
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
4. Application type: **Desktop app** → click Create → download the JSON file
5. Rename the downloaded file to `credentials.json` and place it in the project folder (same folder as `app.py`)
6. On first use, a browser window opens — sign in to Google and grant calendar read access
7. A `token.json` is saved automatically for future runs

Without this file, the app still works — it just asks you to type a name when a meeting starts.

---

## Usage

### Monitor mode (recommended)
Click **Start Monitor** in the GUI. The app runs silently in the background and automatically:
1. Detects when you join a Zoom or Google Meet call
2. Opens a CMD window and asks you to confirm the session name
3. Records audio for the duration of the call
4. Transcribes → Summarises → Saves note when the call ends

### Record Now
Click **Record Now** to start recording immediately without meeting detection. Useful for in-person lectures or any audio you want to capture.

### Processing existing files
Use the **TOOLS** section in the GUI to drag and drop:
- A `.md` or `.txt` file onto **Generate Quiz** — appends 10 multiple-choice questions to the note
- An audio file onto **Transcribe Audio** — transcribes and saves a note

### Pipeline options

| Checkbox | Effect |
|---|---|
| Transcribe | Transcribe audio after recording |
| Summarize | Generate AI summary after transcription |
| Generate Quiz | Generate 10 MCQs after transcription |
| Real-time transcription | Transcribe in 10-second chunks while recording — results appear live, slightly lower accuracy |

---

## Configuration

`config.py` is the single source of truth for all settings. The GUI writes folder paths back to this file automatically.

| Setting | Description | Default |
|---|---|---|
| `NOTES_ROOT_PATH` | Where Markdown notes are saved | set during install |
| `TEMP_AUDIO_DIR` | Where raw audio recordings are stored | `"./temp_audio"` |
| `WHISPER_MODEL` | Transcription model (`tiny`/`base`/`small`) | `"base"` |
| `OLLAMA_MODEL` | Ollama model name (local fallback) | `"llama3"` |
| `DEEPSEEK_MODEL` | DeepSeek model name | `"deepseek-chat"` |
| `DISCONNECT_TOLERANCE_SECONDS` | Seconds meeting must be gone before session ends | `30` |

Notes are saved as:
- **Calendar session** → `{NOTES_ROOT_PATH}/{subject}/{date}.md`
- **Manual session** → `{NOTES_ROOT_PATH}/{date} - {name}.md`

---

## Known Limitations

**Audio capture:**
- WASAPI loopback captures **all system audio** — if YouTube or Spotify is playing during a meeting, both streams are recorded and mixed into the transcript. Use the Windows Volume Mixer to mute other apps during recording.
- Setting Windows volume to 0 will silence the loopback capture. Use your **headphone's physical mute button** instead.

**Meeting detection:**
- Zoom is detected via window title ("Zoom Meeting") and the `CptHost.exe` process. If Zoom changes its window title in a future update, detection may break.
- Google Meet is detected via browser window title — only works when the Meet tab is the active/foreground tab.

**Transcription:**
- `base` model takes roughly 1 minute of processing per 4 minutes of audio on CPU.
- Real-time mode uses the `tiny` model — faster but less accurate, especially for technical vocabulary.
- No GPU acceleration on Windows with AMD graphics (ROCm is Linux-only).

**General:**
- Windows 11 only. Not portable to macOS or Linux.
- Ollama and Llama 3 require ~4–6 GB of RAM when active.

---

## Troubleshooting

**No audio captured:**
Check that your output device supports WASAPI loopback. Bluetooth headphones generally work. If nothing is captured, try switching to a different output device in Windows sound settings.

**Ollama fails to start:**
Run `ollama serve` in a terminal to see error output. Make sure Ollama is installed with `ollama --version`.

**Summarisation not working:**
If using DeepSeek, verify the key is set: open a new PowerShell window and run `$env:DEEPSEEK_API_KEY` — it should show your key. If empty, re-run the `SetEnvironmentVariable` command and restart the app.

**Google Calendar not detecting events:**
Make sure `credentials.json` is in the project root folder. Delete `token.json` and restart to redo the OAuth flow if authentication stops working.

**CMD window closes immediately:**
An error occurred during the session. Run the relevant `.bat` file (e.g. `Start Monitor.bat`) directly to see the full error output.
