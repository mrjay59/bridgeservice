#!/bin/bash
# install_requirements.sh - Installer untuk Bridge Service

echo "🔧 Memulai instalasi package yang diperlukan..."

# Update package list
echo "📦 Update package list..."
pkg update -y

# Install Python dan tools dasar
echo "🐍 Install Python dan tools..."
pkg install -y python python-pip

# Install package Python utama
echo "📚 Install package Python utama..."
pip install websocket-client uiautomator2 adbutils requests Pillow

# Install tools ADB dan Android
echo "📱 Install ADB dan tools Android..."
pkg install -y android-tools termux-api

# Install package tambahan untuk image processing
echo "🖼️ Install package untuk image processing..."
pkg install -y libjpeg-turbo

# Install package system tambahan
echo "⚙️ Install package system tambahan..."
pkg install -y root-repo
pkg install -y termux-exec

# Cek instalasi
echo "✅ Verifikasi instalasi..."
python3 -c "
try:
    import websocket
    import uiautomator2
    import adbutils
    import requests
    from PIL import Image
    print('✅ Semua package Python terinstall dengan baik')
except ImportError as e:
    print(f'❌ Package missing: {e}')
"

echo "🎉 Instalasi selesai!"
echo "📋 Untuk menjalankan service: python3 bridgeservice.py"