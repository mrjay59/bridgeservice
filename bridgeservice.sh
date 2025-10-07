#!/data/data/com.termux/files/usr/bin/bash
# bridgeservice.sh - manage bridgeservice.py in Termux home
BRIDGE_HOME="$HOME/bridgeservice"
BRIDGE_PY="$BRIDGE_HOME/bridgeservice.py"
LOG_FILE="$BRIDGE_HOME/logs/service.log"

start() {
    mkdir -p "$BRIDGE_HOME/logs"
    if pgrep -f "python .*bridgeservice.py" >/dev/null 2>&1; then
        echo "Bridge service already running (pid: $(pgrep -f 'python .*bridgeservice.py' | head -n1))"
        return 0
    fi
    nohup python "$BRIDGE_PY" > "$LOG_FILE" 2>&1 &
    sleep 1
    if pgrep -f "python .*bridgeservice.py" >/dev/null 2>&1; then
        echo "Bridge service started (pid: $(pgrep -f 'python .*bridgeservice.py' | head -n1))"
    else
        echo "Failed to start bridge service. Check $LOG_FILE"
    fi
}

stop() {
    pkill -f "python .*bridgeservice.py" 2>/dev/null || true
    sleep 1
    if pgrep -f "python .*bridgeservice.py" >/dev/null 2>&1; then
        echo "Failed to stop bridge service"
    else
        echo "Bridge service stopped"
    fi
}

restart() {
    stop
    sleep 1
    start
}

getinfo() {
    # Show last bridge_hello message from log or attempt to read via grepping for "bridge_hello"
    if [ -f "$LOG_FILE" ]; then
        grep -a '"type":"bridge_hello"' "$LOG_FILE" | tail -n 1 || echo "No bridge_hello found in logs"
    else
        echo "Log file not found: $LOG_FILE"
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    getinfo) getinfo ;;
    *) echo "Usage: $0 {start|stop|restart|getinfo}" ; exit 1 ;;
esac
