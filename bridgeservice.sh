#!/system/bin/sh
# bridgeservice.sh - manage bridgeservice.py in Termux (support Magisk)

TERMUX_BASE="/data/data/com.termux/files"
PYTHON_BIN="$TERMUX_BASE/usr/bin/python"
BRIDGE_HOME="$TERMUX_BASE/home/bridgeservice"
BRIDGE_PY="$BRIDGE_HOME/bridgeservice.py"
LOG_DIR="$BRIDGE_HOME/logs"
LOG_FILE="$LOG_DIR/service.log"
ALT_LOG="/data/local/tmp/bridge_autostart.log"

export HOME="$TERMUX_BASE/home"
export PATH="$TERMUX_BASE/usr/bin:$TERMUX_BASE/usr/bin/applets:$PATH"
AUTO_UPDATE=0

check_adb_device() {
    echo "[BridgeService] Checking adb devices..."

    ADB_OUT=$(adb devices 2>/dev/null)
    echo "$ADB_OUT"

    DEVICE_COUNT=$(echo "$ADB_OUT" | grep -w "device" | grep -v "List of devices" | wc -l)

    if [ "$DEVICE_COUNT" -eq 0 ]; then
        echo ""
        echo "[BridgeService] ❌ TIDAK ADA DEVICE ADB TERDETEKSI"
        echo ""
        echo "Langkah yang harus dilakukan:"
        echo "STEP 1️⃣  Hubungkan HP ke USB (atau pastikan emulator hidup)"
        echo "STEP 2️⃣  Dari CMD / PC jalankan / Dari AutoCall Enable Network Port:"
        echo "          adb tcpip 5555"
        echo "STEP 3️⃣  Kembali ke Termux, jalankan:"
        echo "          adb connect 127.0.0.1:5555"
        echo "STEP 4️⃣  Jalankan ulang:"
        echo "          bash bridgeservice.sh start"
        echo ""
        return 1
    fi

    echo "[BridgeService] ✅ Device ADB terdeteksi"
    return 0
}
 
update_script() {
    echo "[BridgeService] 🔄 Updating script..."

    cd "$BASE_DIR" || {
        echo "[ERROR] Cannot access $BASE_DIR"
        return 1
    }  

    echo "[2/4] Install required packages..."
    pkg install -y curl git nano || {
        echo "[BridgeService] ❌ package install failed"
        return 1
    }

    echo "[3/4] Remove old bridgeservice directory..."
    rm -rf ~/bridgeservice || {
        echo "[BridgeService] ❌ failed to remove old directory"
        return 1
    }

    echo "[4/4] Clone latest bridgeservice..."
    git clone http://github.com/mrjay59/bridgeservice.git || {
        echo "[BridgeService] ❌ git clone failed"
        return 1
    }

    echo ""
    echo "[BridgeService] ✅ Update selesai"
    echo "Langkah selanjutnya:"
    echo "cd ~/bridgeservice"
    echo "bash bridgeservice.sh start"
    echo ""
}



install() {
    echo "[BridgeService] Installing dependencies..."
    if [ ! -x "$TERMUX_BASE/usr/bin/pkg" ]; then
        echo "[!] Termux environment not detected. Run this from Termux."
        return 1
    fi

    # Jalankan setup terpisah
    local setup_script="$BRIDGE_HOME/setup_bridgeservice.sh"
    if [ -f "$setup_script" ]; then
        bash "$setup_script"
    else
        echo "[BridgeService] setup_bridgeservice.sh not found in $BRIDGE_HOME"
        echo "Please copy it there before running install."
    fi
    register
}
  
start() {
    mkdir -p "$LOG_DIR"

    
    if [ "$AUTO_UPDATE" = "1" ]; then
        update_script || return 1
    fi

    # 🔥 CEK ADB DEVICE DULU
    if ! check_adb_device; then
        echo "[BridgeService] Service TIDAK dijalankan."
        return 1
    fi

    if pgrep -f "python .*bridgeservice.py" >/dev/null 2>&1; then
        echo "[BridgeService] Already running (pid: $(pgrep -f 'python .*bridgeservice.py' | head -n1))"
        return 0
    fi

    echo "[BridgeService] Starting..."
    nohup "$PYTHON_BIN" -u "$BRIDGE_PY" >> "$LOG_FILE" 2>&1 &
    sleep 2

    if pgrep -f "python .*bridgeservice.py" >/dev/null 2>&1; then
        echo "[BridgeService] Started (pid: $(pgrep -f 'python .*bridgeservice.py' | head -n1))"
        echo "Log file: $LOG_FILE"
    else
        echo "[BridgeService] Failed to start. Check log manually."
    fi
}


stop() {
    pkill -f "python .*bridgeservice.py" 2>/dev/null || true
    sleep 1
    if pgrep -f "python .*bridgeservice.py" >/dev/null 2>&1; then
        echo "[BridgeService] Failed to stop"
    else
        echo "[BridgeService] Stopped"
    fi
}

restart() {
    stop
    sleep 1
    start
}

status() {
    if pgrep -f "python .*bridgeservice.py" >/dev/null 2>&1; then
        echo "[BridgeService] Status: RUNNING (pid: $(pgrep -f 'python .*bridgeservice.py' | head -n1))"
    else
        echo "[BridgeService] Status: STOPPED"
    fi
}

getinfo() {
    echo "[BridgeService] Device Info:"

    # Cek adb
    if command -v adb >/dev/null 2>&1 && adb get-state 1>/dev/null 2>&1; then
        brand=$(adb shell getprop ro.product.brand | tr -d '\r')
        model=$(adb shell getprop ro.product.model | tr -d '\r')
        android=$(adb shell getprop ro.build.version.release | tr -d '\r')
        serial=$(adb shell getprop ro.serialno | tr -d '\r')
    else
        # Fallback tanpa adb (langsung di Termux)
        brand=$(getprop ro.product.brand)
        model=$(getprop ro.product.model)
        android=$(getprop ro.build.version.release)
        serial=$(getprop ro.serialno)
    fi

    # Validasi hasil
    [ -z "$brand" ] && brand="unknown"
    [ -z "$model" ] && model="unknown"
    [ -z "$android" ] && android="unknown"
    [ -z "$serial" ] && serial="unknown"

    echo "brand   : $brand"
    echo "model   : $model"
    echo "android : $android"
    echo "serial  : $serial"
}

getToken() {
    local log=""
    if [ -f "$LOG_FILE" ]; then log="$LOG_FILE"
    elif [ -f "$ALT_LOG" ]; then log="$ALT_LOG"
    fi

    if [ -z "$log" ]; then
        echo "[BridgeService] No log file found."
        return
    fi

    echo "[BridgeService] Extracting token..."
    local token=$(grep -a '"token":"' "$log" | tail -n 1 | grep -oE '"token":"[^"]+' | cut -d'"' -f4)
    if [ -n "$token" ]; then
        echo "Token: $token"
    else
        echo "No token found in logs."
    fi
}

register() {
    echo "[BridgeService] Running registration..."
    "$PYTHON_BIN" register.py
}

logs() {
    local log=""
    if [ -f "$LOG_FILE" ]; then log="$LOG_FILE"
    elif [ -f "$ALT_LOG" ]; then log="$ALT_LOG"
    fi

    if [ -z "$log" ]; then
        echo "[BridgeService] No log file found."
        return
    fi

    local n=${1:-20}
    echo "[BridgeService] Showing last $n lines of log ($log):"
    tail -n "$n" "$log"
}

case "$1" in
    install) install ;;
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    status) status ;;
    getinfo) getinfo ;;
    getToken) getToken ;;
    logs) logs "$2" ;;
    register) register ;;        # ← DITAMBAHKAN DI SINI
    update) update_script ;; 
    *)
        echo "Usage: $0 {install|start|stop|restart|status|getinfo|getToken|logs [lines]}"
        exit 1
        ;;
esac
