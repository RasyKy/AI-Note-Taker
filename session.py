"""Single recording session -- spawned by the background monitor when Zoom is detected."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import config
from meeting_detect import is_in_meeting

PROJECT_DIR = Path(__file__).parent
PYTHON      = PROJECT_DIR / "venv" / "Scripts" / "python.exe"


def _stdin_stop_listener(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            line = input()
            if line.strip().lower() == "stop":
                stop_event.set()
        except (EOFError, OSError):
            break



def _check_existing_note(subject: str | None, flat_name: str | None) -> None:
    date_str = datetime.now().strftime("%Y-%m-%d")
    root = Path(config.NOTES_ROOT_PATH)
    if subject:
        note_path = root / subject / f"{date_str}.md"
    else:
        note_path = root / f"{date_str} - {flat_name}.md"
    if note_path.exists():
        print(f"Note already exists for today: {note_path.name}")
        print("This session will be appended to it.\n")


def _resolve_session_identity(
    calendar_subject: str | None,
    alt_subject: str | None,
    reconnect: bool,
) -> tuple[str | None, str | None]:
    """Return (subject, flat_name). Prompts the user if needed."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    root = Path(config.NOTES_ROOT_PATH)

    print("Meeting detected.\n")

    if reconnect and calendar_subject:
        print(f"Reconnecting to session: {calendar_subject}\n")
        return calendar_subject, None

    # Two calendar candidates -- ambiguous which meeting the user is actually in.
    if calendar_subject and alt_subject:
        print("Two calendar events found. Which meeting are you in?\n")
        print(f"  1. {calendar_subject}  (currently scheduled)")
        print(f"  2. {alt_subject}  (starting soon)")
        print()
        while True:
            choice = input("Enter 1 or 2: ").strip()
            if choice == "1":
                return calendar_subject, None
            if choice == "2":
                return alt_subject, None
            print("Please type 1 or 2.")

    if calendar_subject:
        note_path = root / calendar_subject / f"{date_str}.md"
        print(f"Calendar event detected:  {calendar_subject}")
        print(f"Note will be saved to:    {note_path}")
        print()
        rename = input("Press Enter to confirm, or type a different name: ").strip()
        subject = rename if rename else calendar_subject
        return subject, None

    from calendar_check import is_calendar_configured
    if is_calendar_configured():
        print("No calendar event found for this time.")
    else:
        print("Google Calendar not configured (no credentials.json).")
        print("See README for setup instructions.")
    print()
    while True:
        name = input("Enter a name for this recording: ").strip()
        if name:
            return None, name
        print("Name cannot be empty.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject",     default="", help="Primary calendar event name")
    parser.add_argument("--alt-subject", default="", help="Secondary calendar candidate (disambiguation)")
    parser.add_argument("--reconnect",   action="store_true", help="Reconnecting to previous session, skip prompts")
    parser.add_argument("--quiz",        action="store_true")
    parser.add_argument("--realtime",    action="store_true")
    args = parser.parse_args()

    subject, flat_name = _resolve_session_identity(
        args.subject or None,
        getattr(args, "alt_subject", None) or None,
        args.reconnect,
    )
    label = subject or flat_name or "Recording"

    _check_existing_note(subject, flat_name)

    print("Type 'stop' + Enter to end recording early, or leave the meeting.\n")

    from audio_capture import AudioCapture
    capture = AudioCapture()
    if not capture.start():
        print("Could not start audio capture. Aborting.")
        return

    session_start = datetime.now()
    print(f"Started at {session_start.strftime('%H:%M:%S')}.\n")

    stop_event = threading.Event()
    listener   = threading.Thread(target=_stdin_stop_listener, args=(stop_event,), daemon=True)
    listener.start()

    realtime_stop              = threading.Event()
    realtime_transcript_holder: list[str] = []

    if args.realtime:
        from transcribe import transcribe_realtime
        def _rt_worker() -> None:
            realtime_transcript_holder.append(transcribe_realtime(capture, realtime_stop))
        rt_thread = threading.Thread(target=_rt_worker, daemon=True)
        rt_thread.start()

    gone_since: float | None = None

    try:
        while True:
            if stop_event.is_set():
                print("Manual stop requested.")
                break
            time.sleep(config.POLL_INTERVAL_SECONDS)
            if is_in_meeting():
                gone_since = None
            else:
                if gone_since is None:
                    gone_since = time.time()
                    print("Meeting ended. Waiting to confirm...")
                if time.time() - gone_since >= config.DISCONNECT_TOLERANCE_SECONDS:
                    print("Meeting has ended. Ending session.")
                    break
    except KeyboardInterrupt:
        print("\nForce stopped.")

    session_end = datetime.now()
    duration    = int((session_end - session_start).total_seconds())
    mins, secs  = divmod(duration, 60)
    print(f"\nSession ended. Duration: {mins}m {secs}s")
    print("Processing audio -- please wait, do not close this window...\n")

    # Stop realtime thread BEFORE stopping the capture so the thread can
    # finish reading any remaining buffered frames without a race on PyAudio.
    if args.realtime:
        print("Waiting for real-time transcription to finish final chunk...")
        realtime_stop.set()
        rt_thread.join(timeout=120)

    timestamp  = session_start.strftime("%Y%m%d_%H%M%S")
    Path(config.TEMP_AUDIO_DIR).mkdir(parents=True, exist_ok=True)
    audio_path = str(Path(config.TEMP_AUDIO_DIR) / f"{timestamp}_{label}.wav")

    print("Saving audio...")
    wav_path = capture.stop(audio_path)

    # --- Step 1: Transcribe ---
    try:
        if args.realtime:
            transcript = realtime_transcript_holder[0] if realtime_transcript_holder else ""
            if not transcript:
                print("WARNING: Real-time produced no text. Falling back to post-processing...")
                if wav_path:
                    print("Transcribing (this may take a few minutes on CPU)...")
                    from transcribe import transcribe
                    transcript = transcribe(wav_path)
                else:
                    print("No audio captured and no real-time transcript. Nothing to save.")
                    return
        else:
            if wav_path is None:
                print("No audio was captured.")
                return
            print("Transcribing (this may take a few minutes on CPU)...")
            from transcribe import transcribe
            transcript = transcribe(wav_path)
    except Exception as exc:
        print(f"\nERROR during transcription: {exc}")
        if wav_path:
            print(f"Audio preserved at: {wav_path}")
        return

    print("Transcription complete.\n")

    # --- Step 2: Save note immediately with transcript ---
    from save_notes import save_note, _SUMMARY_PLACEHOLDER
    note_path = save_note(
        subject=subject,
        flat_name=flat_name,
        summary_markdown=_SUMMARY_PLACEHOLDER,
        transcript=transcript,
        duration_seconds=duration,
        date=session_start,
    )
    print(f"Transcript saved to: {note_path}\n")

    # --- Step 3: Summarize in isolated subprocess (avoids background thread crashes) ---
    print("Summarizing (this may take several minutes on CPU)...")
    import os
    tmp_transcript = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(transcript)
            tmp_transcript = f.name
        result = subprocess.run(
            [str(PYTHON), "-u", str(PROJECT_DIR / "_sum_worker.py"), tmp_transcript, note_path, label or ""],
            timeout=600,
            cwd=str(PROJECT_DIR),
        )
        if result.returncode != 0:
            print(f"WARNING: Summarization process exited with code {result.returncode}. Note has transcript only.")
    except subprocess.TimeoutExpired:
        print("WARNING: Summarization timed out after 10 minutes. Note has transcript only.")
    except Exception as exc:
        print(f"WARNING: Could not run summarization: {exc}")
    finally:
        if tmp_transcript:
            try:
                os.unlink(tmp_transcript)
            except Exception:
                pass

    # --- Step 4: Quiz (optional) ---
    if args.quiz:
        print("Generating quiz...")
        from generate_quiz import generate_quiz, append_quiz_to_note
        try:
            quiz = generate_quiz(transcript)
            append_quiz_to_note(Path(note_path), quiz)
            print("Quiz appended to note.\n")
        except Exception as exc:
            print(f"WARNING: Quiz generation failed: {exc}\n")


if __name__ == "__main__":
    main()
