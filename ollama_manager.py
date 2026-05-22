"""Start Ollama on demand before summarize/quiz calls."""

from __future__ import annotations

import subprocess
import time

import requests

import config


def ensure_ollama_running() -> None:
    """If Ollama is not responding, start it and wait until ready. Raises RuntimeError on timeout."""
    try:
        requests.get(config.OLLAMA_BASE_URL, timeout=2)
        return
    except Exception:
        pass

    print("Ollama is not running. Starting...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Ollama is not installed. Download it from https://ollama.com and run 'ollama pull llama3'."
        )

    for _ in range(30):
        time.sleep(1)
        try:
            requests.get(config.OLLAMA_BASE_URL, timeout=2)
            print("Ollama ready.")
            return
        except Exception:
            pass

    raise RuntimeError(
        "Ollama did not start within 30 seconds. Try running 'ollama serve' manually."
    )
