"""Whisper transcription of an audio file."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import config


def transcribe_realtime(capture: object, stop_event: threading.Event) -> str:
    """
    Transcribe audio in 10-second chunks while recording is still active.
    Uses the 'tiny' Whisper model with context injection: each chunk receives
    the preceding transcript as initial_prompt, preserving accuracy across
    chunk boundaries without needing larger windows.
    stop_event should be set when recording has ended; the function processes
    any remaining audio then returns the full accumulated transcript.
    """
    from faster_whisper import WhisperModel

    print("Loading Whisper 'tiny' model (real-time)...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    print("Real-time transcription active. Partial text appears below:\n")

    CHUNK_SECONDS = 10
    # How many characters of prior transcript to feed as context.
    # ~200 chars ≈ Whisper's prompt token budget without waste.
    CONTEXT_CHARS = 200

    parts: list[str] = []
    frame_index = 0

    while True:
        triggered = stop_event.wait(timeout=CHUNK_SECONDS)

        frames, frame_index = capture.frames_since(frame_index)  # type: ignore[attr-defined]

        if frames and capture.sample_rate > 0:  # type: ignore[attr-defined]
            sr: int = capture.sample_rate  # type: ignore[attr-defined]
            ch: int = capture.channels  # type: ignore[attr-defined]

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                with wave.open(tmp_path, "wb") as wf:
                    wf.setnchannels(ch)
                    wf.setsampwidth(2)
                    wf.setframerate(sr)
                    wf.writeframes(b"".join(frames))

                # Pass the tail of the accumulated transcript as context so
                # Whisper can resolve words that span chunk boundaries.
                context = " ".join(parts)
                prompt  = context[-CONTEXT_CHARS:] if len(context) > CONTEXT_CHARS else context

                segments, _ = model.transcribe(
                    tmp_path,
                    beam_size=5,
                    initial_prompt=prompt or None,
                )
                chunk_text = " ".join(seg.text for seg in segments).strip()

                if chunk_text:
                    parts.append(chunk_text)
                    print(f"[Live] {chunk_text}")
            except Exception as exc:
                print(f"WARNING: Real-time chunk failed: {exc}")
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        if triggered:
            break

    return " ".join(parts)


def transcribe(audio_path: str) -> str:
    """Transcribe audio_path and save a .txt alongside it. Returns transcript text."""
    from faster_whisper import WhisperModel  # deferred import: heavy load

    print(f"Loading Whisper model '{config.WHISPER_MODEL}'...")
    model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")

    print(f"Transcribing: {audio_path}")
    segments, _ = model.transcribe(audio_path, beam_size=5)
    text: str = " ".join(seg.text for seg in segments).strip()

    txt_path = Path(audio_path).with_suffix(".txt")
    txt_path.write_text(text, encoding="utf-8")
    print(f"Transcript saved: {txt_path}")
    return text


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py -3.11 transcribe.py <audio_file>")
        sys.exit(1)

    from pathlib import Path
    from save_notes import save_note

    transcript = transcribe(sys.argv[1])

    print("How should this be saved?")
    print("  lecture  - organised under a subject folder (e.g. Lecture Notes/CS3001/2026-05-15.md)")
    print("  other    - saved as a single file           (e.g. Lecture Notes/2026-05-15 - My Recording.md)")
    while True:
        mode = input("Type 'lecture' or 'other': ").strip().lower()
        if mode in ("lecture", "other"):
            break
        print("Please type lecture or other.")

    subject = None
    flat_name = None
    if mode == "lecture":
        while True:
            subject = input("Subject name: ").strip()
            if subject:
                break
            print("Subject name cannot be empty.")
    else:
        while True:
            flat_name = input("Enter file name: ").strip()
            if flat_name:
                break
            print("File name cannot be empty.")

    save_note(
        subject=subject,
        flat_name=flat_name,
        summary_markdown="",
        transcript=transcript,
        duration_seconds=0,
    )
    print("Done.")
