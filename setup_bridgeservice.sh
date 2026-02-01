#!/data/data/com.termux/files/usr/bin/bash
# setup_bridgeservice.sh - STABLE FINAL for Termux

set -e
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
pkg update -y

echo "[BridgeSetup] Installing base system packages..."
pkg install -y \
  python \
  git \
  wget \
  curl \
  nano \
  openssl \
  clang \
  libxml2 \
  libxslt \
  busybox \
  procps \
  android-tools \
  termux-api \
  python-pillow \
  python-psutil

echo "[BridgeSetup] Python version:"
python --version
pip --version

echo "[BridgeSetup] Installing Python modules (pip-safe only)..."
pip install --no-cache-dir \
  requests \
  websocket-client \
  adbutils \
  uiautomator2 \
  aiohttp \
  websockets \
  certifi \
  xmltodict

if [ -f "$REQ_FILE" ]; then
  echo "[BridgeSetup] Installing from requirements.txt..."
  pip install --no-cache-dir -r "$REQ_FILE"
fi

echo "[BridgeSetup] Verifying Python modules..."
python << 'EOF'
mods = [
    "requests",
    "websocket",
    "PIL",
    "adbutils",
    "uiautomator2",
]
failed = False
for m in mods:
    try:
        __import__(m)
        print(f"✔ {m} OK")
    except Exception as e:
        failed = True
        print(f"❌ {m} FAILED:", e)

if failed:
    raise SystemExit("❌ Python dependency verification failed")
EOF

echo "[BridgeSetup] Verifying system tools..."
command -v adb && adb version | head -n 1
command -v termux-sms-list

echo "======================================"
echo "[BridgeSetup] DONE $(date)"
echo "[BridgeSetup] Log file: $SETUP_LOG"
echo "======================================"
