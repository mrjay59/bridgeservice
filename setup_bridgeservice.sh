#!/data/data/com.termux/files/usr/bin/bash
# setup_bridgeservice.sh - STABLE FINAL (Termux SAFE)

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
pkg update -y || true

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
  python-pillow || {
    echo "❌ Base package install failed"
    exit 1
}

echo "[BridgeSetup] Python info:"
python --version
pip --version

echo "[BridgeSetup] Installing Python modules via pip..."
pip install --no-cache-dir \
  requests \
  websocket-client \
  psutil \
  adbutils \
  uiautomator2 \
  aiohttp \
  websockets \
  certifi \
  xmltodict || {
    echo "❌ pip install failed"
    exit 1
}

if [ -f "$REQ_FILE" ]; then
  echo "[BridgeSetup] Installing from requirements.txt..."
  pip install --no-cache-dir -r "$REQ_FILE" || {
    echo "❌ requirements.txt install failed"
    exit 1
  }
fi

echo "[BridgeSetup] Verifying Python modules..."
python << 'EOF'
modules = {
    "requests": "requests",
    "websocket": "websocket-client",
    "PIL": "pillow",
    "psutil": "psutil",
    "adbutils": "adbutils",
    "uiautomator2": "uiautomator2"
}

failed = False
for mod, name in modules.items():
    try:
        __import__(mod)
        print(f"✔ {name} OK")
    except Exception as e:
        failed = True
        print(f"❌ {name} FAILED:", e)

if failed:
    raise SystemExit("❌ Dependency verification failed")
EOF

echo "[BridgeSetup] Verifying system tools..."
command -v adb && adb version | head -n 1 || exit 1
command -v termux-sms-list || echo "⚠️ termux-api not available"

echo "======================================"
echo "[BridgeSetup] DONE $(date)"
echo "[BridgeSetup] Log file: $SETUP_LOG"
echo "======================================"
