FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg2 \
    curl \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    xvfb \
    x11-utils \
    x11-xserver-utils \
    dbus-x11 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    libxrender1 \
    libxi6 \
    libxtst6 \
    python3-tk \
    scrot \
    procps \
    xdotool \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub \
       | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pyautogui

# Pre-download UC ChromeDriver during build
RUN python -c "from seleniumbase import SB; SB(uc=True, headless=True).__enter__()" || true

COPY . .
RUN chmod +x entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV DBUS_SESSION_BUS_ADDRESS=/dev/null

EXPOSE 7474

ENTRYPOINT ["./entrypoint.sh"]
