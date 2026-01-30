#!/data/data/com.termux/files/usr/bin/bash
# setup_bridgeservice.sh - FULL setup BridgeService for Termux with logging

set -o pipefail

TERMUX_BASE="/data/data/com.termux/files"
BRIDGE_HOME="$TERMUX_BASE/home/bridgeservice"
LOG_DIR="$BRIDGE_HOME/logs"
SETUP_LOG="$LOG_DIR/setup.log"
REQ_FILE="$BRIDGE_HOME/requirements.txt"

mkdir -p "$LOG_DIR"

exec > >(tee -a "$SETUP_LOG") 2>&1

echo "======================================"
echo "[BridgeSetup] START $(date)"
echo "======================================"

echo "[BridgeSetup] Updating packages..."
pkg update -y || echo "[WARN] pkg update failed"

echo "[BridgeSetup] Installing base packages..."
pkg install -y \
  python \
  python-pip \
  git \
  wget \
  curl \
  nano \
  openssl \
  clang \
  libxml2 \
  libxslt \
  zip \
  unzip \
  busybox \
  procps \
  android-tools \
  termux-api || echo "[ERROR] base package install failed"

echo "[BridgeSetup] Upgrading pip toolchain..."
python -m pip install --upgrade pip setuptools wheel || echo "[ERROR] pip upgrade failed"

echo "[BridgeSetup] Installing Python dependencies..."
python -m pip install --upgrade \
  requests \
  websocket-client \
  pillow \
  psutil \
  adbutils \
  uiautomator2 \
  aiohttp \
  websockets \
  certifi \
  xmltodict || echo "[ERROR] pip module install failed"

if [ -f "$REQ_FILE" ]; then
  echo "[BridgeSetup] Installing from requirements.txt..."
  python -m pip install -r "$REQ_FILE" || echo "[ERROR] requirements.txt install failed"
else
  echo "[BridgeSetup] No requirements.txt found"
fi

echo "[BridgeSetup] Verifying Python modules..."
python - << 'EOF'
mods = [
    ("requests", "requests"),
    ("websocket", "websocket-client"),
    ("PIL", "pillow"),
    ("adbutils", "adbutils"),
    ("uiautomator2", "uiautomator2"),
]
for m, pkg in mods:
    try:
        __import__(m)
        print(f"✔ {pkg} OK")
    except Exception as e:
        print(f"❌ {pkg} FAILED:", e)
EOF

echo "[BridgeSetup] Verifying system tools..."
command -v adb && adb version | head -n 1 || echo "❌ adb not found"
command -v termux-sms-list || echo "⚠️ termux-api not available"

echo "======================================"
echo "[BridgeSetup] DONE $(date)"
echo "[BridgeSetup] Log file: $SETUP_LOG"
echo "======================================"
