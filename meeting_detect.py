"""Detect whether the user is currently in an active Zoom or Google Meet call."""

from __future__ import annotations

import ctypes
import ctypes.wintypes

import psutil


def _all_window_titles() -> list[str]:
    """Return the titles of all visible windows on the system."""
    titles: list[str] = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def _cb(hwnd: int, _: int) -> bool:
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                titles.append(buf.value)
        return True

    cb = WNDENUMPROC(_cb)
    ctypes.windll.user32.EnumWindows(cb, 0)
    return titles


def is_in_zoom_meeting() -> bool:
    """
    True when the user is inside an active Zoom meeting (not just the home screen).
    Uses two independent signals:
      1. A window titled "Zoom Meeting" exists (primary).
      2. CptHost.exe is running -- Zoom spawns this during meetings (secondary).
    Either signal alone is treated as in-meeting.
    """
    titles = _all_window_titles()
    if any("Zoom Meeting" in t for t in titles):
        return True
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] == "CptHost.exe":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def is_in_google_meet() -> bool:
    """
    True when any browser window has an active Google Meet tab in focus.
    Detects Chrome, Edge, Firefox, and any other browser via window title scan.
    """
    return any("Google Meet" in t for t in _all_window_titles())


def is_in_meeting() -> bool:
    """True if the user is in a Zoom meeting or a Google Meet call."""
    return is_in_zoom_meeting() or is_in_google_meet()
