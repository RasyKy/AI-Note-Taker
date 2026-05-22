"""Manually generate quiz questions from an existing transcript or note."""

from __future__ import annotations

import sys
from pathlib import Path

import requests
import config

QUIZ_PROMPT = """\
You are an academic tutor. Based on the following lecture transcript, generate a quiz to test understanding of the material.

Produce exactly 10 multiple-choice questions. Format each question like this:

**Q1. [Question text]**
A) [Option]
B) [Option]
C) [Option]
D) [Option]
**Answer: [A/B/C/D]**

Only include questions about content clearly covered in the transcript. Do not invent facts.

---

TRANSCRIPT:
{transcript}
"""


def generate_quiz(transcript: str) -> str:
    from ollama_manager import ensure_ollama_running
    ensure_ollama_running()

    prompt = QUIZ_PROMPT.format(transcript=transcript)
    try:
        response = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=300,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to Ollama. Start it with: ollama serve")
    return response.json()["response"].strip()


def append_quiz_to_note(note_path: Path, quiz: str) -> None:
    existing = note_path.read_text(encoding="utf-8")
    updated = existing + f"\n\n## Quiz\n\n{quiz}\n"
    note_path.write_text(updated, encoding="utf-8")
    print(f"Quiz appended to: {note_path}")


def extract_transcript_from_note(note_path: Path) -> str:
    """Pull the transcript out of the <details> block in an existing note."""
    content = note_path.read_text(encoding="utf-8")
    start = content.find("<details>")
    end = content.find("</details>")
    if start == -1 or end == -1:
        return content  # No details block -- use full content as fallback
    block = content[start:end]
    # Strip the <details> and <summary> tags to get just the transcript text
    lines = block.splitlines()
    transcript_lines = [
        line for line in lines
        if not line.strip().startswith("<") and line.strip()
    ]
    return "\n".join(transcript_lines).strip()


def pick_file(prompt_text: str, extensions: set[str]) -> Path:
    while True:
        try:
            raw = input(prompt_text).strip().strip('"')
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            sys.exit(0)
        path = Path(raw)
        if not path.exists():
            print(f"File not found: {path}")
            continue
        if path.suffix.lower() not in extensions:
            print(f"Unsupported file type '{path.suffix}'. Expected: {', '.join(sorted(extensions))}")
            continue
        return path


def main() -> None:
    print("=== Quiz Generator ===")
    print()
    print("Source options:")
    print("  1. An existing Obsidian note (.md) -- extracts transcript from the note")
    print("  2. A plain transcript file (.txt)  -- from a previous transcription")
    print()

    while True:
        choice = input("Choose source (1 or 2): ").strip()
        if choice in ("1", "2"):
            break
        print("Please enter 1 or 2.")

    if choice == "1":
        source_path = pick_file("Path to .md note file: ", {".md"})
        transcript = extract_transcript_from_note(source_path)
        output_path = source_path  # Quiz gets appended to the same note
    else:
        source_path = pick_file("Path to .txt transcript file: ", {".txt"})
        transcript = source_path.read_text(encoding="utf-8").strip()
        # Save quiz alongside the transcript as a separate .md file
        output_path = source_path.with_suffix(".quiz.md")

    if not transcript:
        print("ERROR: No transcript content found.")
        sys.exit(1)

    print(f"\nGenerating quiz from: {source_path.name}")
    print("This may take a minute...")

    try:
        quiz = generate_quiz(transcript)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    if choice == "1":
        append_quiz_to_note(output_path, quiz)
    else:
        output_path.write_text(f"## Quiz\n\n{quiz}\n", encoding="utf-8")
        print(f"Quiz saved to: {output_path}")

    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        source_path = Path(sys.argv[1])
        if not source_path.exists():
            print(f"File not found: {source_path}")
            sys.exit(1)
        if source_path.suffix.lower() == ".md":
            transcript = extract_transcript_from_note(source_path)
            output_path = source_path
        elif source_path.suffix.lower() == ".txt":
            transcript = source_path.read_text(encoding="utf-8").strip()
            output_path = source_path.with_suffix(".quiz.md")
        else:
            print(f"Unsupported file type '{source_path.suffix}'. Expected .md or .txt")
            sys.exit(1)

        if not transcript:
            print("ERROR: No transcript content found.")
            sys.exit(1)

        print(f"Generating quiz from: {source_path.name}")
        print("This may take a minute...")
        try:
            quiz = generate_quiz(transcript)
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)

        if source_path.suffix.lower() == ".md":
            append_quiz_to_note(output_path, quiz)
        else:
            output_path.write_text(f"## Quiz\n\n{quiz}\n", encoding="utf-8")
            print(f"Quiz saved to: {output_path}")
        print("Done.")
    else:
        main()
