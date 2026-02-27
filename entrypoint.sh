#!/bin/bash
set -e

# Persistent cookies via volume symlink
mkdir -p /app/data
if [ ! -f /app/data/cookies.json ]; then
    echo "[]" > /app/data/cookies.json
fi
ln -sf /app/data/cookies.json /app/cookies.json

# Start Xvfb virtual display for headful Chrome
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac &
export DISPLAY=:99

sleep 1

exec python main.py
