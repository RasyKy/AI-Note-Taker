"""Format and save notes as Markdown."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import config


def save_note(
    summary_markdown: str,
    transcript: str,
    duration_seconds: int,
    subject: Optional[str] = None,
    flat_name: Optional[str] = None,
    date: datetime | None = None,
) -> str:
    """
    Write the note file and return its path.

    If subject is given: {NOTES_ROOT_PATH}/{subject}/{date}.md
    If flat_name is given: {NOTES_ROOT_PATH}/{date} - {flat_name}.md
    """
    if date is None:
        date = datetime.now()

    date_str = date.strftime("%Y-%m-%d")
    duration_str = _format_duration(duration_seconds)
    title = subject or flat_name or "Note"

    content = f"""# {title} - {date_str}

**Date:** {date_str}
**Subject:** {title}
**Duration:** {duration_str}

{summary_markdown}

---

<details>
<summary>Full Transcript</summary>

{transcript}

</details>
"""

    root = Path(config.NOTES_ROOT_PATH)

    if subject:
        note_dir = root / subject
        note_dir.mkdir(parents=True, exist_ok=True)
        note_path = note_dir / f"{date_str}.md"
    else:
        root.mkdir(parents=True, exist_ok=True)
        note_path = root / f"{date_str} - {flat_name}.md"

    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
        content = existing + "\n\n---\n\n" + content

    note_path.write_text(content, encoding="utf-8")
    print(f"Note saved: {note_path}")
    return str(note_path)


_SUMMARY_PLACEHOLDER = "## Summary\n(Summarizing...)\n"


def update_summary(note_path: str, summary_markdown: str) -> None:
    """Replace the placeholder summary written by save_note() with the real one."""
    path = Path(note_path)
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    if _SUMMARY_PLACEHOLDER in content:
        content = content.replace(_SUMMARY_PLACEHOLDER, summary_markdown, 1)
        path.write_text(content, encoding="utf-8")
        print(f"Note updated with summary: {path}")


def _format_duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"
