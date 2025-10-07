#!/data/data/com.termux/files/usr/bin/bash
# =====================================================
# BRIDGE SERVICE AUTO-SETUP SCRIPT - TERMUX FIXED V2
# Safe mode: skips all packages that cannot compile on Termux
# =====================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_termux() {
    if [ ! -d "/data/data/com.termux/files/usr" ]; then
        log_error "This script must be run inside Termux!"
        exit 1
    fi
    if ! command -v pkg >/dev/null 2>&1; then
        log_warning "'pkg' not found, using apt fallback"
        alias pkg='apt'
    fi
    log_success "Environment: Termux detected"
}

update_system() {
    log_info "Updating system packages..."
    pkg update -y && pkg upgrade -y
    log_success "System updated successfully"
}

install_system_deps() {
    log_info "Installing required Termux packages..."
    pkg install -y python clang make cmake libjpeg-turbo libpng freetype harfbuzz android-tools termux-api procps git
    log_success "System dependencies installed"
}

install_python_safe() {
    log_info "Installing Python environment (safe mode)..."
    python -m ensurepip --upgrade || true
    hash -r

    # Prevent pip from trying to compile anything
    export PIP_NO_BUILD_ISOLATION=true
    export PIP_ONLY_BINARY=:all:
    export PIP_DISABLE_PIP_VERSION_CHECK=1

    log_info "Installing essential Python packages (binary only)..."
    pip install --prefer-binary websocket-client adbutils requests psutil humanize || true

    log_info "Skipping heavy packages (unsupported in Termux): numpy, pillow, uiautomator2"
    log_warning "If you need them, use prebuilt wheels manually later."

    log_success "Python minimal environment ready"
}

setup_project_structure() {
    PROJECT_DIR="$HOME/bridgeservice"
    log_info "Setting up project at $PROJECT_DIR"
    mkdir -p "$PROJECT_DIR"/{logs,backups,config,scripts,tmp}
    cd "$PROJECT_DIR"

    if [ ! -f "bridgeservice.py" ]; then
        echo '#!/usr/bin/env python3' > bridgeservice.py
        echo 'print("Bridge Service Ready")' >> bridgeservice.py
    fi

    cat > config/env.conf <<'EOF'
WS_SERVER="wss://yourserver.example/ws"
USE_ROOT_AUDIO="false"
SILENT_MODE="true"
EOF

    log_success "Project folder created successfully"
}

verify_environment() {
    log_info "Verifying installation..."
    python -c "import websocket,adbutils,requests,psutil,humanize;print('✓ Python core modules OK')" ||         log_warning "Some Python modules might be missing"
    if command -v adb >/dev/null 2>&1; then
        log_success "ADB found: $(adb version | head -1)"
    else
        log_warning "ADB not installed correctly"
    fi
}

finish_message() {
    echo -e "\n${GREEN}✅ Bridge Service setup completed successfully (Safe Mode)${NC}"
    echo "Location: ~/bridgeservice"
    echo "Start service: cd ~/bridgeservice && python bridgeservice.py"
}

main() {
    check_termux
    update_system
    install_system_deps
    install_python_safe
    setup_project_structure
    verify_environment
    finish_message
}

main "$@"
