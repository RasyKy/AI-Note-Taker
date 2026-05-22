"""Summarization via DeepSeek API (cloud) or Ollama/Llama 3 (local fallback)."""

from __future__ import annotations

import sys

import config

PROMPT_TEMPLATE = """\
You are a note-taking assistant. Summarize the following transcript from a recorded session{label_clause}.

Respond ONLY in Markdown with these exact sections:
## Summary
(2-3 paragraph concise summary)

## Key Topics
(bulleted list of main topics covered)

## Definitions
(terms introduced with brief explanations, or "None" if no new terms)

## Tasks / Action Items
(any tasks, assignments, or follow-ups mentioned, or "None")

---

TRANSCRIPT:
{transcript}
"""


def _build_prompt(transcript: str, label: str) -> str:
    label_clause = f" titled '{label}'" if label else ""
    return (
        PROMPT_TEMPLATE
        .replace("{label_clause}", label_clause)
        .replace("{transcript}", transcript)
    )


def _summarize_deepseek(transcript: str, label: str) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

    stream = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": _build_prompt(transcript, label)}],
        stream=True,
    )

    parts: list[str] = []
    print()
    for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        if token:
            parts.append(token)
            print(token, end="", flush=True)
    print("\n")
    return "".join(parts).strip()


def _summarize_ollama(transcript: str, label: str) -> str:
    import json as _json
    import requests

    from ollama_manager import ensure_ollama_running
    ensure_ollama_running()

    try:
        response = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json={"model": config.OLLAMA_MODEL, "prompt": _build_prompt(transcript, label), "stream": True},
            stream=True,
            timeout=300,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to Ollama. Start it with: ollama serve")
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama request timed out after 5 minutes.")
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Ollama request failed: {exc}")

    parts: list[str] = []
    print()
    for line in response.iter_lines():
        if not line:
            continue
        chunk = _json.loads(line)
        token = chunk.get("response", "")
        if token:
            parts.append(token)
            print(token, end="", flush=True)
        if chunk.get("done"):
            break
    print("\n")
    return "".join(parts).strip()


def summarize(transcript: str, label: str = "") -> str:
    """Summarize a transcript. Uses DeepSeek API if configured, otherwise Ollama."""
    if config.DEEPSEEK_API_KEY:
        print("Using DeepSeek API...")
        return _summarize_deepseek(transcript, label)
    print("Using Ollama (set DEEPSEEK_API_KEY in config.py to use DeepSeek)...")
    return _summarize_ollama(transcript, label)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py -3.11 summarize.py <transcript_file>")
        sys.exit(1)

    from pathlib import Path
    from save_notes import save_note

    transcript_path = Path(sys.argv[1])
    text = transcript_path.read_text(encoding="utf-8")

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

    print("Summarizing...")
    summary = summarize(text)

    save_note(
        subject=subject,
        flat_name=flat_name,
        summary_markdown=summary,
        transcript=text,
        duration_seconds=0,
    )
    print("Done.")
