#!/data/data/com.termux/files/usr/bin/bash
# bridgeservice.sh - manage bridgeservice.py in Termux
BRIDGE_HOME="/data/data/com.termux/files/home/bridgeservice"
BRIDGE_PY="$BRIDGE_HOME/bridgeservice.py"
LOG_DIR="$BRIDGE_HOME/logs"
LOG_FILE="$LOG_DIR/service.log"
ALT_LOG="/data/local/tmp/bridge_autostart.log"

start() {
    mkdir -p "$LOG_DIR"
    if pgrep -f "python .*bridgeservice.py" >/dev/null 2>&1; then
        echo "[BridgeService] Already running (pid: $(pgrep -f 'python .*bridgeservice.py' | head -n1))"
        return 0
    fi
    echo "[BridgeService] Starting..."
    nohup python -u "$BRIDGE_PY" >> "$LOG_FILE" 2>&1 &
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
    if [ -f "$LOG_FILE" ]; then
        echo "[BridgeService] Device Info:"
        # Cari baris terakhir yang mengandung bridge_hello
        local info=$(grep -a "'type': 'bridge_hello'" "$LOG_FILE" | tail -n 1)
        if [ -n "$info" ]; then
            # Bersihkan prefix log
            info=$(echo "$info" | sed "s/.*Received message without action: //")
            # Ubah kutip tunggal ke ganda supaya bisa diproses grep
            info=$(echo "$info" | sed "s/'/\"/g")
            # Tampilkan beberapa field penting
            echo "$info" | grep -oE '"(brand|model|android|serial|ip_local)"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/"//g' | sed 's/: /= /'
        else
            echo "  No bridge_hello data found in logs."
        fi
    else
        echo "[BridgeService] Log file not found: $LOG_FILE"
    fi
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
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    status) status ;;
    getinfo) getinfo ;;
    getToken) getToken ;;
    logs) logs "$2" ;;   # contoh: ./bridgeservice.sh logs 50
    *)
        echo "Usage: $0 {start|stop|restart|status|getinfo|getToken|logs [lines]}"
        exit 1
        ;;
esac
