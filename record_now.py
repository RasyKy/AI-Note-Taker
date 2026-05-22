"""Immediately start recording loopback audio -- no Zoom detection needed."""

from __future__ import annotations

import argparse
import threading
import time
from datetime import datetime
from pathlib import Path

import config


def _stdin_stop_listener(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            line = input()
            if line.strip().lower() == "stop":
                stop_event.set()
        except (EOFError, OSError):
            break


def prompt_save_mode() -> tuple[str | None, str | None]:
    """Ask the user to name this ad-hoc recording."""
    while True:
        name = input("Enter a name for this recording: ").strip()
        if name:
            return None, name
        print("Name cannot be empty.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcribe", action="store_true", help="Auto-transcribe after recording")
    parser.add_argument("--realtime", action="store_true", help="Transcribe in real-time during recording (lower accuracy)")
    parser.add_argument("--summarize", action="store_true", help="Auto-summarize after transcription")
    parser.add_argument("--quiz", action="store_true", help="Auto-generate quiz after transcription")
    args = parser.parse_args()

    print("Live audio capture started.")
    print("Play your video/audio now.")
    print("Type 'stop' + Enter when done.\n")

    subject, flat_name = prompt_save_mode()

    from audio_capture import AudioCapture
    capture = AudioCapture()
    if not capture.start():
        print("Could not start audio capture. Exiting.")
        return

    session_start = datetime.now()
    print(f"\nRecording started at {session_start.strftime('%H:%M:%S')}...")
    print("Type 'stop' + Enter when done.\n")

    stop_event = threading.Event()
    listener = threading.Thread(target=_stdin_stop_listener, args=(stop_event,), daemon=True)
    listener.start()

    realtime_stop = threading.Event()
    realtime_transcript_holder: list[str] = []

    if args.realtime:
        from transcribe import transcribe_realtime
        def _rt_worker() -> None:
            realtime_transcript_holder.append(transcribe_realtime(capture, realtime_stop))
        rt_thread = threading.Thread(target=_rt_worker, daemon=True)
        rt_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    print("Stopping recording...")
    session_end = datetime.now()
    duration = int((session_end - session_start).total_seconds())

    label = subject or flat_name
    timestamp = session_start.strftime("%Y%m%d_%H%M%S")
    Path(config.TEMP_AUDIO_DIR).mkdir(parents=True, exist_ok=True)
    audio_path = str(Path(config.TEMP_AUDIO_DIR) / f"{timestamp}_{label}.wav")

    wav_path = capture.stop(audio_path)
    if wav_path is None:
        print("No audio captured.")
        return

    print(f"Duration: {duration}s")
    print(f"Audio saved: {wav_path}")

    if args.realtime:
        print("Waiting for real-time transcription to finish final chunk...")
        realtime_stop.set()
        rt_thread.join(timeout=120)
        transcript = realtime_transcript_holder[0] if realtime_transcript_holder else ""
        if not transcript:
            print("WARNING: Real-time transcription produced no text. Falling back to post-processing...")
            print("Transcribing...")
            from transcribe import transcribe
            transcript = transcribe(wav_path)
    elif args.transcribe:
        print("\nTranscribing...")
        from transcribe import transcribe
        transcript = transcribe(wav_path)
    else:
        while True:
            choice = input("\nTranscribe now or save for later? (now/later): ").strip().lower()
            if choice in ("now", "later"):
                break
            print("Please type now or later.")
        if choice == "later":
            print("Run 'Transcribe.bat' on the audio file above when ready.")
            return
        print("\nTranscribing...")
        from transcribe import transcribe
        transcript = transcribe(wav_path)

    summary = ""
    if args.summarize:
        print("Summarizing...")
        from summarize import summarize
        try:
            summary = summarize(transcript, label=label)
        except RuntimeError as exc:
            print(f"WARNING: {exc}")
            summary = "## Summary\n(Summarization unavailable -- Ollama not running)\n"

    from save_notes import save_note
    note_path = save_note(
        subject=subject,
        flat_name=flat_name,
        summary_markdown=summary,
        transcript=transcript,
        duration_seconds=duration,
        date=session_start,
    )

    if args.quiz:
        print("Generating quiz...")
        from generate_quiz import generate_quiz, append_quiz_to_note, extract_transcript_from_note
        from pathlib import Path as _Path
        try:
            quiz = generate_quiz(transcript)
            append_quiz_to_note(_Path(note_path), quiz)
        except RuntimeError as exc:
            print(f"WARNING: Quiz generation failed: {exc}")

    print("Done.")


if __name__ == "__main__":
    main()
