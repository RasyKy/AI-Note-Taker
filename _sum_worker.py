"""Isolated summarization worker -- called by session.py via subprocess."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: _sum_worker.py <transcript_file> <note_path> [label]")
        sys.exit(1)

    transcript_file = Path(sys.argv[1])
    note_path       = sys.argv[2]
    label           = sys.argv[3] if len(sys.argv) > 3 else ""

    try:
        transcript = transcript_file.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: Could not read transcript file {transcript_file}: {exc}")
        sys.exit(1)

    try:
        from summarize import summarize
        from save_notes import update_summary
    except Exception as exc:
        print(f"ERROR: Import failed: {exc}")
        traceback.print_exc()
        sys.exit(1)

    try:
        summary = summarize(transcript, label=label)
        update_summary(note_path, summary)
        print("Summary saved.")
        sys.exit(0)
    except Exception as exc:
        print(f"WARNING: Summarization failed: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
