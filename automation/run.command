#!/bin/bash
set -euo pipefail
STUDIO_ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/opt/node@22/bin:/usr/local/opt/node@22/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$STUDIO_ROOT"
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  echo "Katsu Studio needs FFmpeg. Install it with: brew install ffmpeg"
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  if command -v python3.12 >/dev/null; then
    python3.12 -m venv .venv
  else
    echo "Install Python 3.12 first (brew install python@3.12)."
    exit 1
  fi
fi
if ! .venv/bin/python -c 'import katsu, fastapi, openai, PIL, num2words, keyring' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -e ./backend
fi
if [ ! -f frontend/dist/index.html ]; then
  if ! command -v npm >/dev/null; then
    echo "Install Node.js first (brew install node)."
    exit 1
  fi
  (cd frontend && npm ci && npm run build)
fi
if .venv/bin/python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8850/api/health", timeout=1)' >/dev/null 2>&1; then
  open "http://127.0.0.1:8850"
  exit 0
fi
.venv/bin/python -c 'import threading,webbrowser; threading.Timer(2,lambda:webbrowser.open("http://127.0.0.1:8850")).start()' &
echo "Katsu Studio is opening at http://127.0.0.1:8850"
echo "Keep this window open while a video is producing. Press Control+C to stop."
exec .venv/bin/python -m uvicorn katsu.main:create_app --factory --host 127.0.0.1 --port 8850 --no-access-log
