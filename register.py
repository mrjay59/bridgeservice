#!/usr/bin/env python3
import json
import requests
import subprocess
import socket
import sys
import os

# ===============================================
# Import fungsi dari bridgeservice.py
# ===============================================
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT)

try:
    from bridgeservice import (
        get_device_info,
        get_sim_info,
        get_serial,
        get_local_ip,
        AdbWrapper
    )
except Exception as e:
    print("❌ Tidak dapat memuat fungsi dari bridgeservice.py:", e)
    sys.exit(1)


# ===============================================
# Kirim data registrasi
# ===============================================
def register_device():
    adb = AdbWrapper()

    # Ambil serial
    serial = get_serial(adb)
    if not serial:
        print("❌ Serial perangkat tidak ditemukan")
        return

    # Ambil info device
    device_info = get_device_info(adb)

    # Ambil info SIM
    sim1 = get_sim_info(adb, 0)
    sim2 = get_sim_info(adb, 1)

    # Ambil IP lokal
    ip_local = get_local_ip(adb)

    profile = {
        "platform": "termux",
        "device": device_info,
        "serial": serial,
        "ip_local": ip_local,
        "sims": [sim1, sim2]
    }

    #print("📡 Mengirim data registrasi ke server...")
    #print(json.dumps(profile, indent=2, ensure_ascii=False))
  
    # GANTI URL JIKA PERLU
    url = "https://mrjay59.com/api/cpost/device/register"

    try:
        r = requests.post(url, json=profile, timeout=10)
        if r.status_code == 200:
          # print("✅ Registrasi berhasil!")
            print("Server response:", r.text)
        else:
            print("❌ Registrasi gagal:", r.status_code, r.text)
    except Exception as e:
        print("❌ Error kirim data:", e)


if __name__ == "__main__":
    register_device()
