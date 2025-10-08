#!/data/data/com.termux/files/usr/bin/bash
# bridgeservice.sh - manage bridgeservice.py in Termux
BRIDGE_HOME="$HOME/bridgeservice"
BRIDGE_PY="$BRIDGE_HOME/bridgeservice.py"
LOG_FILE="$BRIDGE_HOME/logs/service.log"

start() {
    mkdir -p "$BRIDGE_HOME/logs"
    if pgrep -f "python .*bridgeservice.py" >/dev/null 2>&1; then
        echo "[BridgeService] Already running (pid: $(pgrep -f 'python .*bridgeservice.py' | head -n1))"
        return 0
    fi
    nohup python "$BRIDGE_PY" > "$LOG_FILE" 2>&1 &
    sleep 2
    if pgrep -f "python .*bridgeservice.py" >/dev/null 2>&1; then
        echo "[BridgeService] Started (pid: $(pgrep -f 'python .*bridgeservice.py' | head -n1))"
    else
        echo "[BridgeService] Failed to start. Check $LOG_FILE"
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
        local info=$(grep -a '"type":"bridge_hello"' "$LOG_FILE" | tail -n 1)
        if [ -n "$info" ]; then
            echo "$info" | grep -oE '"(serial|android_id|device_model)"[^,}]*'
        else
            echo "  No bridge_hello data found in logs."
        fi
    else
        echo "[BridgeService] Log file not found: $LOG_FILE"
    fi
}

getToken() {
    if [ -f "$LOG_FILE" ]; then
        echo "[BridgeService] Extracting token from log..."
        local token=$(grep -a '"token":"' "$LOG_FILE" | tail -n 1 | grep -oE '"token":"[^"]+' | cut -d'"' -f4)
        if [ -n "$token" ]; then
            echo "Token: $token"
        else
            echo "No token found in logs."
        fi
    else
        echo "[BridgeService] Log file not found: $LOG_FILE"
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "[BridgeService] Showing last 20 lines of log:"
        tail -n 20 "$LOG_FILE"
    else
        echo "[BridgeService] Log file not found: $LOG_FILE"
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    status) status ;;
    getinfo) getinfo ;;
    getToken) getToken ;;
    logs) logs ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|getinfo|getToken|logs}"
        exit 1
        ;;
esac
