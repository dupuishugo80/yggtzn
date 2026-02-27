#!/bin/bash
set -e

# Clean up stale files from previous runs
rm -f /tmp/.X99-lock /tmp/.X99-unix/X99
pkill -f "Xvfb" 2>/dev/null || true
pkill -f "chrome" 2>/dev/null || true
sleep 1

# Persistent cookies via volume
mkdir -p /app/data
if [ ! -f /app/data/cookies.json ]; then
    echo "[]" > /app/data/cookies.json
fi
ln -sf /app/data/cookies.json /app/cookies.json

# Start Xvfb virtual display
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac &
XVFB_PID=$!
export DISPLAY=:99

sleep 2

# Cleanup on exit
cleanup() {
    kill $XVFB_PID 2>/dev/null || true
    pkill -f "chrome" 2>/dev/null || true
    rm -f /tmp/.X99-lock
}
trap cleanup EXIT SIGTERM SIGINT

exec python main.py
