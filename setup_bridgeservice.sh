#!/data/data/com.termux/files/usr/bin/bash
# setup_bridgeservice.sh - setup environment for BridgeService in Termux

echo "[BridgeSetup] Starting setup process..."

TERMUX_BASE="/data/data/com.termux/files"
BRIDGE_HOME="$TERMUX_BASE/home/bridgeservice"
LOG_DIR="$BRIDGE_HOME/logs"
REQ_FILE="$BRIDGE_HOME/requirements.txt"

# Buat folder logs
mkdir -p "$LOG_DIR"

echo "[BridgeSetup] Updating package list..."
pkg update -y

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
  android-tools

echo "[BridgeSetup] Upgrading pip toolchain..."
python -m pip install --upgrade pip setuptools wheel

echo "[BridgeSetup] Installing required Python libraries..."
python -m pip install --upgrade \
  requests \
  websocket-client \
  pillow \
  psutil \
  aiohttp \
  websockets \
  uiautomator2 \
  adbutils \
  certifi

# Install dari requirements.txt jika ada
if [ -f "$REQ_FILE" ]; then
  echo "[BridgeSetup] Installing additional requirements from $REQ_FILE..."
  python -m pip install -r "$REQ_FILE"
else
  echo "[BridgeSetup] No requirements.txt found, skipping..."
fi

echo "[BridgeSetup] Verifying installation..."
python --version
pip --version

echo "[BridgeSetup] Checking modules..."
python - << 'EOF'
import requests
import websocket
from PIL import Image
print("✔ requests OK")
print("✔ websocket-client OK")
print("✔ pillow (PIL) OK")
EOF

echo "[BridgeSetup] Setup completed successfully!"
echo "[BridgeSetup] Bridge home: $BRIDGE_HOME"
echo "[BridgeSetup] Logs directory: $LOG_DIR"
