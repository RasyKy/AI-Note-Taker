"""Desktop launcher GUI for AI Note Taker."""

from __future__ import annotations

import ctypes
import os
import subprocess
import threading
import winreg
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk
import requests
from tkinterdnd2 import DND_FILES, TkinterDnD

import psutil

import config

PROJECT_DIR = Path(__file__).parent
PYTHON = PROJECT_DIR / "venv" / "Scripts" / "python.exe"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

_TEMP_BAT = PROJECT_DIR / "_launch.bat"

# ── Palette ───────────────────────────────────────────────────────────────────
_BG        = "#eef4f3"
_CARD      = "#ffffff"
_CARD_IN   = "#f2f8f7"
_BORDER    = "#c2d8d6"

_AMBER     = "#0e7c7b"   # primary accent (teal)
_AMBER_H   = "#0a9998"
_AMBER_DIM = "#cde8e7"

_RED       = "#b82c2c"
_RED_H     = "#d03535"
_GREEN     = "#1e5c5b"   # darker teal for Record Now
_GREEN_H   = "#27706f"

_TEXT      = "#0a2624"
_TEXT2     = "#517a78"
_TEXT3     = "#90b5b3"

_OK        = "#0e7c7b"
_ERR       = "#b82c2c"

# ── Fonts ─────────────────────────────────────────────────────────────────────
_F_MONO_SM = ("Consolas", 11)
_F_MONO    = ("Consolas", 13)
_F_BODY    = ("Segoe UI", 14)
_F_BODY_SM = ("Segoe UI", 13)
_F_STATUS  = ("Consolas", 12)
_F_TITLE   = ("Consolas", 13, "bold")


def _short_path(path: str) -> str:
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, len(buf))
    return buf.value or str(path)


def launch_cmd(script: str, *args: str) -> Optional[subprocess.Popen]:
    """Launch script in a new visible CMD window."""
    parts = [f'"{PYTHON}"', f'"{PROJECT_DIR / script}"'] + [f'"{a}"' for a in args]
    _TEMP_BAT.write_text(
        "\r\n".join([
            "@echo off",
            f'cd /d "{PROJECT_DIR}"',
            " ".join(parts),
            "echo.",
            "pause",
        ]),
        encoding="utf-8",
    )
    short_bat = _short_path(str(_TEMP_BAT))
    return subprocess.Popen(
        ["cmd", "/c", short_bat],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def launch_bg(script: str, *args: str) -> Optional[subprocess.Popen]:
    """Launch script as a silent background process with no console window."""
    return subprocess.Popen(
        [str(PYTHON), str(PROJECT_DIR / script)] + list(args),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def check_ollama() -> bool:
    try:
        requests.get(config.OLLAMA_BASE_URL, timeout=2)
        return True
    except Exception:
        return False


def open_vault() -> None:
    folder = Path(config.NOTES_ROOT_PATH)
    if folder.exists():
        os.startfile(str(folder))
    else:
        os.startfile(str(PROJECT_DIR))


_REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_VAL_NAME = "AINoteTaker"


def _startup_command() -> str:
    pythonw = PROJECT_DIR / "venv" / "Scripts" / "pythonw.exe"
    return f'"{pythonw}" "{PROJECT_DIR / "main.py"}"'


def get_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_RUN_KEY) as key:
            val, _ = winreg.QueryValueEx(key, _REG_VAL_NAME)
            return val == _startup_command()
    except OSError:
        return False


def set_startup_enabled(enabled: bool) -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _REG_RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        if enabled:
            winreg.SetValueEx(key, _REG_VAL_NAME, 0, winreg.REG_SZ, _startup_command())
        else:
            try:
                winreg.DeleteValue(key, _REG_VAL_NAME)
            except OSError:
                pass


def find_monitor_pid() -> Optional[int]:
    main_py = str(PROJECT_DIR / "main.py")
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info["cmdline"] or []
            if proc.info["name"] in ("python.exe", "pythonw.exe") and any(
                main_py in arg for arg in cmdline
            ):
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def update_config_value(key: str, new_value) -> None:
    if isinstance(new_value, str):
        new_value = new_value.replace("\\", "/")
        serialized = f'"{new_value}"'
    else:
        serialized = str(new_value)  # True / False
    config_path = PROJECT_DIR / "config.py"
    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith(f"{key} ") or line.startswith(f"{key}="):
            lines[i] = f"{key} = {serialized}\n"
            break
    config_path.write_text("".join(lines), encoding="utf-8")


def _card(parent: ctk.CTkBaseClass, **kw) -> ctk.CTkFrame:
    """Reusable card frame with consistent styling."""
    return ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=6, **kw)


def _card_header(card: ctk.CTkFrame, label: str) -> ctk.CTkFrame:
    """Top row inside a card: section label on left, returns the row frame."""
    row = ctk.CTkFrame(card, fg_color="transparent")
    row.pack(fill="x", padx=14, pady=(10, 6))
    ctk.CTkLabel(
        row,
        text=label,
        font=ctk.CTkFont(*_F_MONO_SM),
        text_color=_TEXT2,
    ).pack(side="left")
    return row


class DropZone(ctk.CTkFrame):
    """A frame that accepts drag-and-drop file drops and click-to-browse."""

    def __init__(
        self,
        parent,
        title: str,
        subtitle: str,
        filetypes: list[tuple[str, str]],
        callback,
        **kw,
    ) -> None:
        super().__init__(
            parent,
            fg_color=_CARD_IN,
            border_color=_BORDER,
            border_width=1,
            corner_radius=4,
            **kw,
        )
        self._callback = callback
        self._filetypes = filetypes

        self._lbl_title = ctk.CTkLabel(
            self, text=title, font=ctk.CTkFont(*_F_BODY_SM), text_color=_TEXT
        )
        self._lbl_title.pack(pady=(14, 2))

        self._lbl_sub = ctk.CTkLabel(
            self, text=subtitle, font=ctk.CTkFont(*_F_MONO_SM), text_color=_TEXT3
        )
        self._lbl_sub.pack(pady=(0, 14))

        # Register drop target on frame and both labels so nothing intercepts
        for widget in (self, self._lbl_title, self._lbl_sub):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)
            widget.dnd_bind("<<DragEnter>>", self._on_enter)
            widget.dnd_bind("<<DragLeave>>", self._on_leave)
            widget.bind("<Button-1>", self._on_click)

    def _on_drop(self, event) -> None:
        path = event.data.strip()
        if path.startswith("{") and path.endswith("}"):
            path = path[1:-1]
        self._on_leave(None)
        self._callback(path)

    def _on_enter(self, event) -> None:
        self.configure(fg_color=_AMBER_DIM, border_color=_AMBER)

    def _on_leave(self, event) -> None:
        self.configure(fg_color=_CARD_IN, border_color=_BORDER)

    def _on_click(self, event) -> None:
        path = filedialog.askopenfilename(filetypes=self._filetypes)
        if path:
            self._callback(path)


class App(TkinterDnD.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI Note Taker")
        self.resizable(False, False)
        self.configure(bg=_BG)

        self._ollama_label: Optional[ctk.CTkLabel] = None
        self._status_label: Optional[ctk.CTkLabel] = None
        self._monitor_btn: Optional[ctk.CTkButton] = None
        self._record_btn: Optional[ctk.CTkButton] = None
        self._checkboxes: list[ctk.CTkCheckBox] = []
        self._monitor_pid: Optional[int] = None
        self._pulse_dot: Optional[ctk.CTkLabel] = None
        self._pulsing = False

        self._build_ui()
        self._schedule_ollama_check()
        self._detect_running_monitor()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_header()
        self._build_capture_card()
        self._build_pipeline_card()
        self._build_tools_card()
        self._build_storage_card()
        # Bottom breathing room
        ctk.CTkFrame(self, fg_color="transparent", height=12).pack()

    def _build_header(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="#d6ecea", corner_radius=0)
        bar.pack(fill="x")

        ctk.CTkLabel(
            bar,
            text="AI  NOTE  TAKER",
            font=ctk.CTkFont(*_F_TITLE),
            text_color=_AMBER,
        ).pack(side="left", padx=18, pady=12)

        self._ollama_label = ctk.CTkLabel(
            bar,
            text="◌  checking",
            font=ctk.CTkFont(*_F_STATUS),
            text_color=_TEXT2,
        )
        self._ollama_label.pack(side="right", padx=18, pady=12)

        # Divider
        ctk.CTkFrame(self, fg_color=_BORDER, height=1, corner_radius=0).pack(fill="x")
        ctk.CTkFrame(self, fg_color="transparent", height=12).pack()

    def _build_capture_card(self) -> None:
        card = _card(self)
        card.pack(fill="x", padx=16, pady=(0, 8))

        hdr = _card_header(card, "CAPTURE")

        # Pulsing dot on the right of the header
        self._pulse_dot = ctk.CTkLabel(
            hdr,
            text="●",
            font=ctk.CTkFont(size=10),
            text_color=_TEXT3,
        )
        self._pulse_dot.pack(side="right")

        # Button row
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 6))
        btn_row.columnconfigure(0, weight=3)
        btn_row.columnconfigure(1, weight=2)

        self._monitor_btn = ctk.CTkButton(
            btn_row,
            text="Start Monitor",
            height=42,
            corner_radius=5,
            font=ctk.CTkFont(*_F_BODY),
            fg_color=_AMBER,
            hover_color=_AMBER_H,
            text_color="#ffffff",
            command=self._start_monitor,
        )
        self._monitor_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self._record_btn = ctk.CTkButton(
            btn_row,
            text="Record Now",
            height=42,
            corner_radius=5,
            font=ctk.CTkFont(*_F_BODY),
            fg_color=_GREEN,
            hover_color=_GREEN_H,
            text_color="#ffffff",
            command=self._record_now,
        )
        self._record_btn.grid(row=0, column=1, sticky="ew")

        # Monitor on boot checkbox
        startup_row = ctk.CTkFrame(card, fg_color="transparent")
        startup_row.pack(fill="x", padx=14, pady=(6, 4))

        self._cb_startup = ctk.BooleanVar(value=get_startup_enabled())
        ctk.CTkCheckBox(
            startup_row,
            text="Monitor on boot",
            variable=self._cb_startup,
            command=self._on_startup_toggle,
            font=ctk.CTkFont(*_F_BODY_SM),
            text_color=_TEXT,
            fg_color=_AMBER,
            hover_color=_AMBER_DIM,
            checkmark_color="#ffffff",
            border_color=_TEXT2,
            corner_radius=3,
        ).pack(side="left")

        ctk.CTkLabel(
            startup_row,
            text="start monitor automatically when Windows starts",
            font=ctk.CTkFont("Consolas", 11),
            text_color=_TEXT3,
        ).pack(side="left", padx=(10, 0))

        # Status line — hidden when empty, shown dynamically
        self._status_label = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(*_F_STATUS),
            text_color=_AMBER,
            anchor="w",
        )

    def _build_pipeline_card(self) -> None:
        card = _card(self)
        card.pack(fill="x", padx=16, pady=(0, 8))

        _card_header(card, "PIPELINE")

        inner = ctk.CTkFrame(card, fg_color=_CARD_IN, corner_radius=4)
        inner.pack(fill="x", padx=14, pady=(0, 10))

        # Primary checkboxes
        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            row1,
            text="after recording",
            font=ctk.CTkFont(*_F_MONO_SM),
            text_color=_TEXT2,
        ).pack(side="left", padx=(0, 14))

        self._cb_transcribe = ctk.BooleanVar(value=config.PIPELINE_TRANSCRIBE)
        self._cb_realtime   = ctk.BooleanVar(value=config.PIPELINE_REALTIME)
        self._cb_summarize  = ctk.BooleanVar(value=config.PIPELINE_SUMMARIZE)
        self._cb_quiz       = ctk.BooleanVar(value=config.PIPELINE_QUIZ)

        cb1 = ctk.CTkCheckBox(
            row1,
            text="Transcribe",
            variable=self._cb_transcribe,
            command=self._on_transcribe_toggle,
            font=ctk.CTkFont(*_F_BODY_SM),
            text_color=_TEXT,
            fg_color=_AMBER,
            hover_color=_AMBER_DIM,
            checkmark_color="#ffffff",
            border_color=_TEXT2,
            corner_radius=3,
        )
        cb1.pack(side="left", padx=(0, 14))

        cb2 = ctk.CTkCheckBox(
            row1,
            text="Summarize",
            variable=self._cb_summarize,
            command=self._on_dependent_toggle,
            font=ctk.CTkFont(*_F_BODY_SM),
            text_color=_TEXT,
            fg_color=_AMBER,
            hover_color=_AMBER_DIM,
            checkmark_color="#ffffff",
            border_color=_TEXT2,
            corner_radius=3,
        )
        cb2.pack(side="left", padx=(0, 14))

        cb3 = ctk.CTkCheckBox(
            row1,
            text="Generate Quiz",
            variable=self._cb_quiz,
            command=self._on_dependent_toggle,
            font=ctk.CTkFont(*_F_BODY_SM),
            text_color=_TEXT,
            fg_color=_AMBER,
            hover_color=_AMBER_DIM,
            checkmark_color="#ffffff",
            border_color=_TEXT2,
            corner_radius=3,
        )
        cb3.pack(side="left")

        # Divider inside inner card
        ctk.CTkFrame(inner, fg_color=_BORDER, height=1, corner_radius=0).pack(
            fill="x", padx=0, pady=(4, 0)
        )

        # Real-time row
        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(6, 10))

        cb4 = ctk.CTkCheckBox(
            row2,
            text="Real-time transcription",
            variable=self._cb_realtime,
            command=self._on_realtime_toggle,
            font=ctk.CTkFont(*_F_BODY_SM),
            text_color=_TEXT2,
            fg_color=_AMBER,
            hover_color=_AMBER_DIM,
            checkmark_color="#ffffff",
            border_color=_TEXT3,
            corner_radius=3,
        )
        cb4.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            row2,
            text="transcribes while recording  /  accuracy may be lower",
            font=ctk.CTkFont("Consolas", 11),
            text_color=_TEXT3,
        ).pack(side="left")

        self._checkboxes = [cb1, cb2, cb3, cb4]

    def _build_tools_card(self) -> None:
        card = _card(self)
        card.pack(fill="x", padx=16, pady=(0, 8))

        _card_header(card, "TOOLS")

        zone_row = ctk.CTkFrame(card, fg_color="transparent")
        zone_row.pack(fill="x", padx=14, pady=(0, 12))
        zone_row.columnconfigure(0, weight=1)
        zone_row.columnconfigure(1, weight=1)

        DropZone(
            zone_row,
            title="Generate Quiz",
            subtitle="drop .md or .txt  /  click to browse",
            filetypes=[("Note / Transcript", "*.md *.txt"), ("All files", "*.*")],
            callback=self._launch_quiz,
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        DropZone(
            zone_row,
            title="Transcribe Audio",
            subtitle="drop audio file  /  click to browse",
            filetypes=[("Audio / Video", "*.wav *.mp3 *.mp4 *.m4a *.ogg *.flac *.webm"), ("All files", "*.*")],
            callback=self._launch_transcribe,
        ).grid(row=0, column=1, sticky="ew")

    def _build_storage_card(self) -> None:
        card = _card(self)
        card.pack(fill="x", padx=16, pady=(0, 8))

        _card_header(card, "STORAGE")

        # Notes folder row
        self._notes_dir_entry = self._folder_row(card, "notes", str(Path(config.NOTES_ROOT_PATH).resolve()), self._pick_notes_dir)

        # Audio folder row
        self._audio_dir_entry = self._folder_row(card, "audio", str(Path(config.TEMP_AUDIO_DIR).resolve()), self._pick_audio_dir)

        # Open vault button
        ctk.CTkButton(
            card,
            text="Open Notes in Explorer",
            height=36,
            corner_radius=4,
            font=ctk.CTkFont(*_F_BODY_SM),
            fg_color=_CARD_IN,
            hover_color=_BORDER,
            text_color=_TEXT2,
            border_color=_BORDER,
            border_width=1,
            command=open_vault,
        ).pack(fill="x", padx=14, pady=(0, 12))

    # ── State management ──────────────────────────────────────────────────────

    def _set_status(self, text: str) -> None:
        if text:
            self._status_label.configure(text=text)
            self._status_label.pack(fill="x", padx=14, pady=(0, 4))
        else:
            self._status_label.pack_forget()

    def _set_active(self, active: bool) -> None:
        state = "normal" if active else "disabled"
        self._monitor_btn.configure(state=state)
        self._record_btn.configure(state=state)
        for cb in self._checkboxes:
            cb.configure(state=state)
        if active:
            self._set_status("")
            self._record_btn.configure(
                text="Record Now", fg_color=_GREEN, hover_color=_GREEN_H, text_color="#ffffff"
            )
            self._monitor_btn.configure(text="Start Monitor")

    def _set_monitor_btn_state(self, monitoring: bool) -> None:
        if monitoring:
            self._monitor_btn.configure(
                text="Stop Monitoring",
                fg_color=_RED,
                hover_color=_RED_H,
                text_color="#ffffff",
            )
            self._set_status("monitoring  /  waiting for zoom")
            self._start_pulse()
        else:
            self._monitor_btn.configure(
                text="Start Monitor",
                fg_color=_AMBER,
                hover_color=_AMBER_H,
                text_color="#000000",
            )
            self._set_status("")
            self._stop_pulse()

    def _start_pulse(self) -> None:
        self._pulsing = True
        self._pulse_tick()

    def _stop_pulse(self) -> None:
        self._pulsing = False
        if self._pulse_dot:
            self._pulse_dot.configure(text_color=_TEXT3)

    def _pulse_tick(self) -> None:
        if not self._pulsing or not self._pulse_dot:
            return
        current = self._pulse_dot.cget("text_color")
        next_color = _AMBER if current == _TEXT3 else _TEXT3
        self._pulse_dot.configure(text_color=next_color)
        self.after(900, self._pulse_tick)

    # ── Process management ────────────────────────────────────────────────────

    def _watch_record(self, proc: subprocess.Popen) -> None:
        proc.wait()
        self.after(0, self._set_active, True)

    def _watch_monitor(self, pid: int) -> None:
        try:
            psutil.Process(pid).wait()
        except psutil.NoSuchProcess:
            pass
        self._monitor_pid = None
        self.after(0, self._set_monitor_btn_state, False)

    def _detect_running_monitor(self) -> None:
        pid = find_monitor_pid()
        if pid:
            self._monitor_pid = pid
            self._set_monitor_btn_state(True)
            threading.Thread(target=self._watch_monitor, args=(pid,), daemon=True).start()

    # ── Checkbox logic ────────────────────────────────────────────────────────

    def _save_pipeline(self) -> None:
        update_config_value("PIPELINE_TRANSCRIBE", self._cb_transcribe.get())
        update_config_value("PIPELINE_SUMMARIZE",  self._cb_summarize.get())
        update_config_value("PIPELINE_QUIZ",       self._cb_quiz.get())
        update_config_value("PIPELINE_REALTIME",   self._cb_realtime.get())

    def _on_transcribe_toggle(self) -> None:
        if self._cb_transcribe.get():
            self._cb_realtime.set(False)
        elif not self._cb_realtime.get():
            self._cb_summarize.set(False)
            self._cb_quiz.set(False)
        self._save_pipeline()

    def _on_realtime_toggle(self) -> None:
        if self._cb_realtime.get():
            self._cb_transcribe.set(False)
        elif not self._cb_transcribe.get():
            self._cb_summarize.set(False)
            self._cb_quiz.set(False)
        self._save_pipeline()

    def _on_dependent_toggle(self) -> None:
        if self._cb_summarize.get() or self._cb_quiz.get():
            if not self._cb_transcribe.get() and not self._cb_realtime.get():
                self._cb_transcribe.set(True)
        self._save_pipeline()

    def _record_now_flags(self) -> list[str]:
        flags = []
        if self._cb_realtime.get():
            flags.append("--realtime")
        elif self._cb_transcribe.get():
            flags.append("--transcribe")
        if self._cb_summarize.get():
            flags.append("--summarize")
        if self._cb_quiz.get():
            flags.append("--quiz")
        return flags

    # ── Button actions ────────────────────────────────────────────────────────

    def _record_now(self) -> None:
        steps = []
        if self._cb_realtime.get():
            steps.append("Transcribe (real-time, lower accuracy)")
        elif self._cb_transcribe.get():
            steps.append("Transcribe")
        if self._cb_summarize.get():
            steps.append("Summarize")
        if self._cb_quiz.get():
            steps.append("Generate Quiz")

        msg = (
            f"After recording, will automatically:\n\n{' → '.join(steps)}\n\nStart recording?"
            if steps else
            "No post-processing selected. Recording only.\n\nStart recording?"
        )
        if not messagebox.askokcancel("Record Now", msg):
            return

        proc = launch_cmd("record_now.py", *self._record_now_flags())
        if proc:
            self._set_active(False)
            self._set_status("recording  /  see cmd window")
            threading.Thread(target=self._watch_record, args=(proc,), daemon=True).start()

    def _start_monitor(self) -> None:
        if self._monitor_pid is not None:
            subprocess.Popen(
                ["taskkill", "/F", "/T", "/PID", str(self._monitor_pid)],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._monitor_pid = None
            self._set_monitor_btn_state(False)
            return

        flags: list[str] = []
        if self._cb_quiz.get():
            flags.append("--quiz")
        if self._cb_realtime.get():
            flags.append("--realtime")
        proc = launch_bg("main.py", *flags)
        if proc:
            self._monitor_pid = proc.pid
            self._set_monitor_btn_state(True)
            threading.Thread(target=self._watch_monitor, args=(proc.pid,), daemon=True).start()

    def _folder_row(self, parent: ctk.CTkFrame, label: str, initial: str, command) -> ctk.CTkEntry:
        """Reusable labeled folder-picker row. Returns the entry widget."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 6))
        ctk.CTkLabel(
            row,
            text=label,
            font=ctk.CTkFont(*_F_MONO_SM),
            text_color=_TEXT2,
            width=38,
            anchor="w",
        ).pack(side="left", padx=(0, 8))
        entry = ctk.CTkEntry(
            row,
            font=ctk.CTkFont("Consolas", 10),
            fg_color=_CARD_IN,
            border_color=_BORDER,
            text_color=_TEXT,
            height=32,
        )
        entry.insert(0, initial)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            row,
            text="...",
            width=36,
            height=32,
            corner_radius=4,
            font=ctk.CTkFont(*_F_BODY_SM),
            fg_color=_CARD_IN,
            hover_color=_BORDER,
            text_color=_TEXT2,
            border_color=_BORDER,
            border_width=1,
            command=command,
        ).pack(side="left")
        return entry

    def _on_startup_toggle(self) -> None:
        set_startup_enabled(self._cb_startup.get())

    def _pick_notes_dir(self) -> None:
        folder = filedialog.askdirectory(title="Select notes save folder")
        if not folder:
            return
        folder = str(Path(folder))
        self._notes_dir_entry.delete(0, "end")
        self._notes_dir_entry.insert(0, folder)
        update_config_value("NOTES_ROOT_PATH", folder)
        config.NOTES_ROOT_PATH = folder

    def _launch_quiz(self, path: str) -> None:
        launch_cmd("generate_quiz.py", path)

    def _launch_transcribe(self, path: str) -> None:
        launch_cmd("transcribe.py", path)

    def _pick_audio_dir(self) -> None:
        folder = filedialog.askdirectory(title="Select audio save folder")
        if not folder:
            return
        folder = str(Path(folder))
        self._audio_dir_entry.delete(0, "end")
        self._audio_dir_entry.insert(0, folder)
        update_config_value("TEMP_AUDIO_DIR", folder)
        config.TEMP_AUDIO_DIR = folder


    # ── Ollama polling ────────────────────────────────────────────────────────

    def _schedule_ollama_check(self) -> None:
        threading.Thread(target=self._do_ollama_check, daemon=True).start()

    def _do_ollama_check(self) -> None:
        online = check_ollama()
        self.after(0, self._update_ollama_label, online)
        self.after(30_000, self._schedule_ollama_check)

    def _update_ollama_label(self, online: bool) -> None:
        if online:
            self._ollama_label.configure(text="●  ollama  on", text_color=_OK)
        else:
            self._ollama_label.configure(text="◌  ollama  auto", text_color=_TEXT2)


if __name__ == "__main__":
    app = App()
    app.mainloop()
