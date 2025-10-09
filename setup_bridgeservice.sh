#!/data/data/com.termux/files/usr/bin/bash
# setup_bridgeservice.sh - setup environment for BridgeService in Termux

echo "[BridgeSetup] Starting setup process..."
TERMUX_BASE="/data/data/com.termux/files"
BRIDGE_HOME="$TERMUX_BASE/home/bridgeservice"
LOG_DIR="$BRIDGE_HOME/logs"
REQ_FILE="$BRIDGE_HOME/requirements.txt"

mkdir -p "$LOG_DIR"

echo "[BridgeSetup] Updating package list..."
pkg update -y

echo "[BridgeSetup] Installing required packages..."
pkg install -y python git wget curl nano openssl clang libxml2 libxslt zip unzip

# pastikan pip sudah aktif
echo "[BridgeSetup] Ensuring pip is installed..."
python -m ensurepip --upgrade
pip install --upgrade pip setuptools wheel

echo "[BridgeSetup] Installing Python libraries..."
pip install --upgrade requests psutil uiautomator2 adbutils pillow

# Kalau ada requirements.txt di folder bridgeservice, install juga
if [ -f "$REQ_FILE" ]; then
    echo "[BridgeSetup] Installing additional requirements from $REQ_FILE..."
    pip install -r "$REQ_FILE"
else
    echo "[BridgeSetup] No requirements.txt found, skipping..."
fi

echo "[BridgeSetup] Checking adb installation..."
if ! command -v adb >/dev/null 2>&1; then
    echo "[BridgeSetup] Installing adb..."
    pkg install -y android-tools
fi

echo "[BridgeSetup] Verifying versions..."
python --version
pip --version
adb version | head -n 1

echo "[BridgeSetup] Setup completed successfully!"
echo "[BridgeSetup] Bridge home: $BRIDGE_HOME"
echo "[BridgeSetup] Logs directory: $LOG_DIR"
