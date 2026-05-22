@echo off
title AI Note Taker - Generate Quiz
cd /d "%~dp0"
echo === Quiz Generator ===
echo.
echo You can provide a note or transcript in two ways:
echo   1. Drag and drop a .md note or .txt transcript onto this .bat file
echo   2. Run it directly and type the file path when prompted
echo.

if "%~1"=="" (
    venv\Scripts\python.exe generate_quiz.py
) else (
    echo File: %~1
    echo.
    venv\Scripts\python.exe -c "
import sys
from pathlib import Path
from generate_quiz import generate_quiz, append_quiz_to_note, extract_transcript_from_note

path = Path(sys.argv[1])
if path.suffix.lower() == '.md':
    transcript = extract_transcript_from_note(path)
    print(f'Generating quiz from note: {path.name}')
    print('This may take a minute...')
    quiz = generate_quiz(transcript)
    append_quiz_to_note(path, quiz)
elif path.suffix.lower() == '.txt':
    transcript = path.read_text(encoding='utf-8').strip()
    out = path.with_suffix('.quiz.md')
    print(f'Generating quiz from transcript: {path.name}')
    print('This may take a minute...')
    quiz = generate_quiz(transcript)
    out.write_text(f'## Quiz\n\n{quiz}\n', encoding='utf-8')
    print(f'Quiz saved to: {out}')
else:
    print(f'ERROR: Unsupported file type: {path.suffix}')
    print('Drop a .md note or .txt transcript file.')
" "%~1"
)

echo.
pause
