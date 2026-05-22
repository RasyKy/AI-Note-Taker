"""Background meeting monitor -- runs silently, spawns a session CMD window when a meeting is detected."""

from __future__ import annotations

import ctypes
import subprocess
import time
from pathlib import Path

import config
from meeting_detect import is_in_meeting

PROJECT_DIR  = Path(__file__).parent
PYTHON       = PROJECT_DIR / "venv" / "Scripts" / "python.exe"
_SESSION_BAT = PROJECT_DIR / "_session.bat"


def _short_path(path: str) -> str:
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, len(buf))
    return buf.value or str(path)


def _launch_session(
    subject: str | None,
    alt_subject: str | None,
    reconnect: bool,
    run_quiz: bool,
    realtime: bool,
) -> subprocess.Popen:
    """Spawn session.py in a new CMD window for one recording session."""
    parts = [f'"{PYTHON}"', f'"{PROJECT_DIR / "session.py"}"']
    if subject:
        parts += ['"--subject"', f'"{subject}"']
    if alt_subject:
        parts += ['"--alt-subject"', f'"{alt_subject}"']
    if reconnect:
        parts.append('"--reconnect"')
    if run_quiz:
        parts.append('"--quiz"')
    if realtime:
        parts.append('"--realtime"')

    _SESSION_BAT.write_text(
        "\r\n".join([
            "@echo off",
            f'cd /d "{PROJECT_DIR}"',
            " ".join(parts),
            "echo.",
            "pause",
        ]),
        encoding="utf-8",
    )
    short_bat = _short_path(str(_SESSION_BAT))
    return subprocess.Popen(
        ["cmd", "/c", short_bat],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def monitor_loop(run_quiz: bool = False, realtime: bool = False) -> None:
    """Poll for meetings silently. When detected, open a CMD window for the session."""
    RECONNECT_WINDOW_SECONDS = 5 * 60
    last_calendar_subject: str | None = None
    last_session_end:      float | None = None

    while True:
        try:
            if is_in_meeting():
                from calendar_check import get_candidate_events
                candidates = get_candidate_events()

                reconnect    = False
                alt_subject  = None

                if candidates:
                    subject     = candidates[0]
                    alt_subject = candidates[1] if len(candidates) > 1 else None
                elif (
                    last_calendar_subject is not None
                    and last_session_end is not None
                    and (time.time() - last_session_end) < RECONNECT_WINDOW_SECONDS
                ):
                    subject   = last_calendar_subject
                    reconnect = True
                else:
                    subject = None  # session.py will prompt the user

                proc = _launch_session(subject, alt_subject, reconnect, run_quiz, realtime)
                proc.wait()

                last_calendar_subject = candidates[0] if candidates else (subject if reconnect else None)
                last_session_end      = time.time()

                while is_in_meeting():
                    time.sleep(config.POLL_INTERVAL_SECONDS)

            time.sleep(config.POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiz",     action="store_true")
    parser.add_argument("--realtime", action="store_true")
    args = parser.parse_args()
    # Fall back to saved config values when started without explicit flags
    # (e.g. via Monitor on boot registry entry).
    run_quiz  = args.quiz     or config.PIPELINE_QUIZ
    realtime  = args.realtime or config.PIPELINE_REALTIME
    monitor_loop(run_quiz=run_quiz, realtime=realtime)
