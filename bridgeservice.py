#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bridgeservice.py - Revised by assistant
Features added:
- Heartbeat every 30 minutes to WS with serial & timestamp
- Result messages include device serial
- Explicit update_scripts action only (no implicit auto-update)
- Uses os.getcwd() for local paths, safer adb wrappers, and guarded WS sends
"""
import os
import re
import json
import time
import uuid
import base64
import threading
import subprocess
import sys
from PIL.DdsImagePlugin import item
import requests
import urllib.parse  # Pindah import ke atas
from datetime import datetime, timezone
from queue import Queue


try:
    import websocket
except Exception as e:
    print('websocket-client required:', e)
    sys.exit(1)

# Optional libs
UIAUTOMATOR2_AVAILABLE = False
try:
    import uiautomator2 as u2
    UIAUTOMATOR2_AVAILABLE = True
except Exception:
    UIAUTOMATOR2_AVAILABLE = False

ADBUTILS_AVAILABLE = False
try:
    import adbutils
    ADBUTILS_AVAILABLE = True
except Exception:
    ADBUTILS_AVAILABLE = False
 
# Local modules
try:
    from WhatsAppAutomation import WhatsAppAutomation
    from CallAudioForwarder import CallAudioForwarder
    from UICallController import UICallController
except Exception as e:
    print('Warning: local modules import issue:', e)

WS_SERVER = os.environ.get("BRIDGE_WS", "wss://ws.autocall.my.id/ws")
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", 1200))  # 20 minutes default
POLL_SMS_INTERVAL = 3

def check_device_status(serial):
    url = "https://mrjay59.com/api/cpost/device/state" 
    payload = {"serial": serial,"tipe": "cekstate"}

    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code == 200:
            print("Server response:", r.text)
            data = r.json()        
            return data
        else:
            print("❌ Server error:", r.status_code)
            return False
    except Exception as e:
        print("❌ Connection error:", e)
        return False

def run_local(cmd, capture=True):
    try:
        if isinstance(cmd, (list, tuple)):
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE if capture else None,
                                    stderr=subprocess.PIPE if capture else None)
        else:
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE if capture else None,
                                    stderr=subprocess.PIPE if capture else None)
        out, err = proc.communicate(timeout=60)
        if capture and out is not None:
            return out.decode('utf-8', errors='ignore')
        return None
    except Exception as e:
        # timeout or other
        return None

class AdbWrapper:
    def __init__(self):
        self.adb_client = None
        if ADBUTILS_AVAILABLE:
            try:
                self.adb_client = adbutils.adb.device()
            except Exception:
                self.adb_client = None

    def shell(self, cmd):
        try:
            if self.adb_client:
                return self.adb_client.shell(cmd) or ""
            else:
                out = run_local(f"adb shell {cmd}")
                return out or ""
        except Exception as e:
            return ""

    def pull(self, remote, local):
        try:
            if self.adb_client:
                return self.adb_client.pull(remote, local)
            else:
                run_local(f"adb pull {remote} {local}")
        except Exception:
            pass

    def push(self, local, remote):
        try:
            if self.adb_client:
                return self.adb_client.push(local, remote)
            else:
                run_local(f"adb push {local} {remote}")
        except Exception:
            pass

def get_local_ip(adb: AdbWrapper):
    try:
        out = adb.shell("ip route") or adb.shell("ip route get 8.8.8.8")
        for line in (out or "").splitlines():
            if "wlan0" in line and "src" in line:
                parts = line.split()
                if "src" in parts:
                    idx = parts.index("src")
                    if idx + 1 < len(parts):
                        return parts[idx+1]
            m = re.search(r"src\s+(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "0.0.0.0"

def get_root_info():
    try:
        euid = os.geteuid()
        if euid == 0:
            try:
                user = subprocess.check_output(["whoami"]).decode().strip()
            except:
                user = "root"
            return {
                "status": True,
                "user": user
            }
        else:
            return {
                "status": False,
                "user": None
            }
    except:
        return {
            "status": False,
            "user": None
        }
    
def get_device_info(adb: AdbWrapper):
    try:
        def safe(cmd):
            try:
                return adb.shell(cmd).strip()
            except:
                return ""

        iplocal = get_local_ip(adb)

        brand = safe("getprop ro.product.manufacturer")
        model = safe("getprop ro.product.model")
        android = safe("getprop ro.build.version.release")
        sdk = safe("getprop ro.build.version.sdk")

        # Device name (About phone)
        device_name = safe("settings get global device_name")
        if not device_name or device_name == "null":
            device_name = safe("settings get secure device_name")
        if not device_name or device_name == "null":
            device_name = safe("getprop ro.product.device")

        # Identitas unik
        serial = safe("getprop ro.serialno")
        if not serial or serial == "unknown":
            serial = safe("settings get secure android_id")

        # Hardware info
        abi = safe("getprop ro.product.cpu.abi")
        hardware = safe("getprop ro.hardware")
        fingerprint = safe("getprop ro.build.fingerprint")

        # Root check
        root_status = get_root_info()

        # Network
        network = safe("getprop gsm.network.type")

        # SIM / Card Info
        imei_list = get_all_imei(adb)
        number_list = get_all_numbers(adb)
        operator_list = get_operator(adb)
        signal_list = get_signal_strength(adb)
        iccid_list = get_all_iccid(adb)
        sim_state_list = get_sim_state(adb)

        cardinfo = {
            "network_type": network,
            "operator": operator_list,
            "signal_dbm": signal_list,
            "iccid": iccid_list,
            "imei": imei_list,
            "number": number_list,
            "sim_state": sim_state_list,
            "dual_sim": len(sim_state_list) > 1
        }

        return {
            "brand": brand,
            "model": model,
            "android": android,
            "sdk": sdk,
            "device_name": device_name,
            "serial": serial,
            "abi": abi,
            "hardware": hardware,
            "fingerprint": fingerprint,
            "root": root_status,
            "iplocal": iplocal,
            "cardinfo": cardinfo
        }

    except Exception as e:
        print("get_device_info error:", e)
        return {}
    
def get_sim_state(adb):
    try:
        out = adb.shell("getprop gsm.sim.state").strip()
        return [x.strip() for x in out.split(',') if x]
    except:
        return []
        
def get_iccid(adb, slot=0):
    try:
        out = adb.shell(f"service call iphonesubinfo {11+slot}") or ""
        matches = re.findall(r"'(.*?)'", out)
        iccid = ''.join(matches).replace('.', '').strip()
        if iccid and len(iccid) > 10:
            return iccid
    except:
        pass
    return None

def get_all_iccid(adb):
    iccids = []
    for slot in range(2):
        val = get_iccid(adb, slot)
        if val and val not in iccids:
            iccids.append(val)
    return iccids
    
def get_signal_strength(adb):
    try:
        out = adb.shell("dumpsys telephony.registry | grep -i 'mSignalStrength'") or ""
        match = re.search(r"dbm=(-?\d+)", out)
        if match:
            return [int(match.group(1))]
    except:
        pass
    return []
    
def get_operator(adb):
    try:
        out = adb.shell("getprop gsm.operator.alpha").strip()
        if not out:
            out = adb.shell("getprop gsm.sim.operator.alpha").strip()
        return [x for x in out.split(',') if x]
    except:
        return []
    
def get_all_imei(adb):
    imeis = []
    for slot in range(2):  # support dual sim
        imei = get_imei(adb, slot)
        if imei and imei not in imeis:
            imeis.append(imei)
    return imeis

def get_all_numbers(adb):
    numbers = []
    for slot in range(2):
        sim = get_sim_info(adb, slot)
        num = sim.get("number")
        if num and num not in numbers:
            numbers.append(num)
    return numbers

def get_serial(adb: AdbWrapper):    
    try:
        s = adb.shell("getprop ro.serialno").strip()
        if not s:
            s = adb.shell("getprop ro.boot.serialno").strip()
        return s or None
    except Exception:
        return None

def get_imei(adb: AdbWrapper, slot=0):
    try:
        out = adb.shell(f"service call iphonesubinfo {1+slot}") or ""
        matches = re.findall(r"\'(.*?)\'", out)
        imei = ''.join(matches).replace('.', '').replace(' ', '') if matches else None
        return imei or None
    except Exception:
        return None
  
def get_sim_info(adb: 'AdbWrapper', slot=0):
    """
    Mengambil informasi nomor SIM dari device via ADB.
    Menggunakan metode adb.shell() dari class AdbWrapper.
    """
    info = {}
    cmds = [
        f"service call iphonesubinfo {slot + 7}",
        "dumpsys telephony.registry | grep -m 1 'mLine1Number'",
        "dumpsys subscription | grep -m 1 'number'"
    ]

    # Jalankan semua perintah secara berurutan
    for cmd in cmds:
        try:
            result = adb.shell(cmd).strip()
            if not result:
                # coba pakai su -c jika root diaktifkan
                result = adb.shell(f"su -c \"{cmd}\"").strip()
        except Exception:
            result = ""

        if not result:
            continue

        # Parsing berbagai kemungkinan format output
        if "mLine1Number" in result:
            match = re.search(r"mLine1Number\s*=\s*(\+?\d+)", result)
            if match:
                info["number"] = match.group(1)
                break

        elif "number=" in result:
            match = re.search(r"number\s*=\s*(\+?\d+)", result)
            if match:
                info["number"] = match.group(1)
                break

        elif "Result:" in result or "Parcel" in result:
            # service call iphonesubinfo biasanya return hex → decode
            chars = re.findall(r"'(.*?)'", result)
            if chars:
                msisdn = ''.join(chars).replace('.', '').strip()
                if msisdn and any(ch.isdigit() for ch in msisdn):
                    info["number"] = msisdn
                    break

    # Jika tetap tidak ditemukan
    if "number" not in info:
        info["number"] = None

    return info

def capture_screenshot_base64(adb: AdbWrapper):
    remote = "/sdcard/bridgeservice_screenshot.png"
    local = os.path.join(os.getcwd(), "bridgeservice_screenshot.png")
    try:
        adb.shell(f"screencap -p {remote}")
        adb.pull(remote, local)
        if os.path.exists(local):
            with open(local, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
        out = adb.shell(f"cat {remote}") or ""
        if out:
            b = out.encode('latin1') if isinstance(out, str) else out
            return base64.b64encode(b).decode("ascii")
    except Exception:
        pass
    return None

# ----------------- USSD helper -----------------
def _encode_ussd(code: str) -> str:
    # encode '#' etc
    return urllib.parse.quote(code, safe='')

def send_ussd_auto(adb, code, sim=0, keywords=None, timeout=15):
    """
    USSD auto navigation by keyword
    """
    result = {
        "ok": False,
        "history": [],
        "error": None
    }

    try:
        keywords = keywords or []

        enc = _encode_ussd(code)
        adb.shell(f'am start -a android.intent.action.CALL -d tel:{enc}')
        time.sleep(1)

        handle_sim_chooser(adb, sim)

        step_index = 0

        for i in range(10):
            # ================= WAIT UI =================
            start = time.time()
            xml = ""

            while time.time() - start < timeout:
                adb.shell("uiautomator dump /sdcard/ussd.xml")
                xml = adb.shell("cat /sdcard/ussd.xml")

                if "android:id/message" in xml:
                    break

                time.sleep(1)

            if not xml:
                return {**result, "error": "no response"}

            # ================= PARSE =================
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml[xml.index("<?xml"):])

            message = None
            for node in root.iter("node"):
                if node.attrib.get("resource-id") == "android:id/message":
                    message = node.attrib.get("text", "").strip()
                    break

            if not message:
                continue

            result["history"].append(message)

            # ================= ERROR =================
            if "mmi" in message.lower() or "connection problem" in message.lower():
                adb.shell("input keyevent 4")
                return {**result, "ok": False, "error": message}

            # ================= CHECK INPUT =================
            if "input_field" not in xml:
                adb.shell("input keyevent 4")
                return {**result, "ok": True, "final": message}

            # ================= AUTO PICK =================
            choice = None

            if step_index < len(keywords):
                kw = keywords[step_index]
                choice = pick_menu_by_keyword(message, kw)
                step_index += 1

            # fallback
            if not choice:
                choice = "1"

            print(f"[USSD AUTO] pilih: {choice}")

            # ================= SEND =================
            adb.shell(f'input text "{choice}"')
            time.sleep(0.5)

            click_by_resource_id(adb, "android:id/button1")

            time.sleep(2)

        return {**result, "error": "max step reached"}

    except Exception as e:
        return {**result, "error": str(e)}
    
def pick_menu_by_keyword(message, keyword):
    """
    Ambil nomor menu berdasarkan keyword
    """
    lines = message.splitlines()

    for line in lines:
        # contoh: "2.Spesial Buat U"
        m = re.match(r"^\s*(\d+)[\.\)]\s*(.+)", line)
        if not m:
            continue

        number = m.group(1)
        text = m.group(2).lower()

        if keyword.lower() in text:
            return number

    return None

def click_by_resource_id(adb, rid):
    adb.shell("uiautomator dump /sdcard/tmp.xml")
    xml = adb.shell("cat /sdcard/tmp.xml")

    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml[xml.index("<?xml"):])

    for node in root.iter("node"):
        if node.attrib.get("resource-id") == rid:
            bounds = node.attrib.get("bounds")
            nums = list(map(int, re.findall(r"\d+", bounds)))
            x1,y1,x2,y2 = nums
            cx,cy = (x1+x2)//2,(y1+y2)//2
            adb.shell(f"input tap {cx} {cy}")
            return True
    return False

# --- Fungsi helper untuk cellular call (standalone) ---
def clean_phone_number(number):
    """
    Membersihkan format nomor telepon
    """
    cleaned = re.sub(r'[^\d+]', '', str(number))
    
    # Format Indonesia: ubah 0xxx menjadi +62xxx
    if cleaned.startswith('0') and not cleaned.startswith('+'):
        cleaned = '+62' + cleaned[1:]
    elif not cleaned.startswith('+'):
        cleaned = '+62' + cleaned
        
    return cleaned

def make_cellular_call(adb: AdbWrapper, number, sim=0):
    """
    Melakukan panggilan selular biasa dengan pemilihan SIM
    """
    try:
        number = clean_phone_number(number)
        sim_index = int(sim)
        
        # Method 1: Menggunakan intent dengan extra SIM slot
        intents = [
            f'am start -a android.intent.action.CALL -d tel:{number} --ei android.telecom.extra.SIM_SLOT_INDEX {sim_index}',
            f'am start -a android.intent.action.CALL -d tel:{number} --ei subscription {sim_index}',
            f'am start -a android.intent.action.CALL -d tel:{number} --ei com.android.phone.extra.slot {sim_index}',
            f'am start -a android.intent.action.CALL -d tel:{number} --ei slot {sim_index}'
        ]
        
        for intent in intents:
            try:
                result = adb.shell(intent)
                time.sleep(2)  # Tunggu intent diproses
                
                # Cek apakah muncul popup pemilihan SIM
                if handle_sim_chooser(adb, sim_index):
                    time.sleep(1)
                
                return True
            except Exception:
                continue
        
        # Method 2: Fallback ke intent biasa
        try:
            adb.shell(f'am start -a android.intent.action.CALL -d tel:{number}')
            time.sleep(2)
            # Coba handle SIM chooser jika muncul
            handle_sim_chooser(adb, sim_index)
            return True
        except Exception:
            pass
        
        return False
        
    except Exception as e:
        print(f"Cellular call error: {e}")
        return False

def make_cellular_call_via_ussd(adb: AdbWrapper, number, sim=0):
    """
    Melakukan panggilan menggunakan USSD code (alternatif method)
    """
    try:
        number = clean_phone_number(number)
        sim_index = int(sim)
        
        # Encode number untuk USSD
        encoded_number = urllib.parse.quote(number, safe='')
        
        intents = [
            f'am start -a android.intent.action.CALL -d tel:{encoded_number} --ei android.telecom.extra.SIM_SLOT_INDEX {sim_index}',
            f'am start -a android.intent.action.CALL -d tel:{encoded_number} --ei subscription {sim_index}'
        ]
        
        for intent in intents:
            try:
                adb.shell(intent)
                time.sleep(3)
                
                # Handle SIM chooser
                if handle_sim_chooser(adb, sim_index):
                    time.sleep(2)
                
                return True
            except Exception:
                continue
        
        return False
        
    except Exception as e:
        print(f"USSD call error: {e}")
        return False

def handle_sim_chooser(adb, sim_index: int):
    """
    Menangani popup pemilihan SIM (Dialer)
    sim_index: 0 = SIM 1, 1 = SIM 2
    """
    try:
        time.sleep(1.2)  # tunggu popup muncul

        # Dump UI
        adb.shell("uiautomator dump /sdcard/window_dump.xml")
        time.sleep(0.3)
        xml = adb.shell("cat /sdcard/window_dump.xml")

        if "<?xml" not in xml:
            return False

        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml[xml.index("<?xml"):])

        # ===============================
        # 1️⃣ Pastikan ini popup pilih SIM
        # ===============================
        is_sim_dialog = False
        for node in root.iter("node"):
            if node.attrib.get("resource-id") == "com.android.dialer:id/alertTitle":
                title = node.attrib.get("text", "").lower()
                if "sim" in title:
                    is_sim_dialog = True
                    break

        if not is_sim_dialog:
            return False

        # ==================================
        # 2️⃣ Ambil semua row SIM (ListView)
        # ==================================
        sim_rows = []

        for node in root.iter("node"):
            if node.attrib.get("resource-id") == "com.android.dialer:id/select_dialog_listview":

                # ambil children langsung (SIM list)
                for child in node:
                    bounds = child.attrib.get("bounds")
                    if bounds:
                        sim_rows.append(bounds)

                break

        # ==========================
        # 3️⃣ Tap berdasarkan index
        # ==========================
        if len(sim_rows) <= sim_index:
            return False

        bounds = sim_rows[sim_index]

        nums = list(map(int, re.findall(r"\d+", bounds)))
        x1, y1, x2, y2 = nums
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        adb.shell(f"input tap {cx} {cy}")
        return True

    except Exception as e:
        print("handle_sim_chooser error:", e)
        return False

def log_print(msg, level="INFO"):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)

# --- SMSHandler simplified ---
class SMSHandler:
    def __init__(self, wsclient, adb: AdbWrapper):
        self.ws = wsclient
        self.adb = adb
        self.last_seen_ids = set()

    def list_sms(self):
        try:
            out = run_local("termux-sms-list")
            return json.loads(out) if out else []
        except Exception:
            return []

    def send_sms(self, number, text, sim=0):
        sim_idx = int(sim) if sim is not None else 0
        number = self._clean_phone_number(number)
        self.ws.send({"type":"sms_debug","message":f"Sending SMS to {number} via SIM {sim_idx+1}"})
        # Try termux-sms-send first (common in Termux)
        try:
            cmd = f'termux-sms-send -n {number} "{text}"'
            run_local(cmd)
            return True
        except Exception:
            pass
        return False

    def _clean_phone_number(self, number):
        cleaned = re.sub(r'[^\d+]', '', str(number))
        if not cleaned.startswith('+'):
            if cleaned.startswith('0'):
                cleaned = '+62' + cleaned[1:]
            else:
                cleaned = '+62' + cleaned
        return cleaned

    def poll_loop(self):
        while True:
            try:
                msgs = self.list_sms()
                new = []

                for m in msgs:
                    mid = m.get('_id') or m.get('id') or m.get('date')
                    if mid not in self.last_seen_ids:
                        new.append(m)
                        self.last_seen_ids.add(mid)

                for m in reversed(new):
                    try:
                        sms_payload = dict(m)
                        sms_payload["read"] = True
                        sms_payload["forwarded"] = True

                        self.ws.send({
                            "type": "sms_received",
                            "data": sms_payload,
                            "serial": get_serial(self.adb)
                        })

                    except Exception as e:
                        log_print(f"SMS send error: {e}", "ERROR")

                if len(self.last_seen_ids) > 2000:
                    self.last_seen_ids = set(list(self.last_seen_ids)[-1000:])

            except Exception as e:
                log_print(f"SMSHandler poll error: {e}", "ERROR")

            time.sleep(POLL_SMS_INTERVAL)


class WSClient:
    def __init__(self, url):
        self.url = url
        self.ws = None
        self.adb = AdbWrapper()
        self.sms = SMSHandler(self, self.adb)
     
        self.ui_call = None
        self._stop = threading.Event()
        self.wa = None
        self.reconnect_attempt = 0

        self.command_queue = Queue()

        # worker thread
        self.worker_thread = threading.Thread(
            target=self._command_worker,
            daemon=True
        )
        self.worker_thread.start()
        
        try:
            self.wa = WhatsAppAutomation(self.adb, app="business")
            self.ui_call = UICallController(self.adb)
        except Exception:
            self.wa = None
            self.ui_call = None

        use_root_audio = os.environ.get("USE_ROOT_AUDIO", "false").lower() == "true"
        try:
            self.audio_forwarder = CallAudioForwarder(self.adb, self, use_root=use_root_audio)
            if self.wa:
                self.wa.audio_forwarder = self.audio_forwarder
        except Exception:
            self.audio_forwarder = None
        
        # Variabel untuk melacak status koneksi
        self.ws_connected = False
        self._connection_lock = threading.Lock()
        
        # start heartbeat thread (tapi tunggu koneksi dulu)
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()

    def log(self, message, level="INFO"):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] [{level}] {message}")

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        t2 = threading.Thread(target=self.sms.poll_loop, daemon=True)
        t2.start()

    def stop(self):
        self._stop.set()
        with self._connection_lock:
            self.ws_connected = False
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass

    def send(self, data):
        try:
            # Selalu sertakan serial jika belum ada
            try:
                serial = get_serial(self.adb)
                if isinstance(data, dict) and 'serial' not in data:
                    data = {**data, "serial": serial}
            except Exception:
                pass

            payload = json.dumps(data)
            

            # Cek apakah WebSocket sudah terhubung
            with self._connection_lock:
                if not self.ws_connected:
                    print(f"⏳ WebSocket not connected, skipping send for: {data.get('type', 'unknown')}")
                    return

            # Pastikan koneksi WebSocket sudah siap
            if (
                self.ws 
                and hasattr(self.ws, "sock") 
                and self.ws.sock 
                and getattr(self.ws.sock, "connected", False)
            ):
                try:
                    self.ws.send(payload)
                    print(f"✅ WS sent: {data.get('type', 'unknown')}")  # log lebih ringkas
                except Exception as e:
                    print(f"⚠️ WS send failed for {data.get('type', 'unknown')}: {e}")
                    # Coba update status koneksi
                    with self._connection_lock:
                        self.ws_connected = False
            else:
                print(f"⏳ WebSocket socket not ready, skipping: {data.get('type', 'unknown')}")
                with self._connection_lock:
                    self.ws_connected = False

        except Exception as e:
            print(f"❌ WS send exception for {data.get('type', 'unknown')}: {e}")

    def _on_open(self, ws):
        log_print("WebSocket connected")
        self.reconnect_attempt = 0
        with self._connection_lock:
            self.ws_connected = True
        
        device_info = get_device_info(self.adb)
        ip_local = get_local_ip(self.adb)
        serial = get_serial(self.adb)
        sim1 = {"imei": get_imei(self.adb, 0), **get_sim_info(self.adb, 0)}
        sim2 = {"imei": get_imei(self.adb, 1), **get_sim_info(self.adb, 1)}
        profile = {"platform":"termux","device":device_info,"serial":serial,"ip_local":ip_local}
        self.send({"type":"heartbeat", "message":"device online update data","id":str(uuid.uuid4()),"info":profile,"serial":serial})

    def _on_message(self, ws, message):

        try:

            payload = json.loads(message)

            msg_type = payload.get("type")
            sender = payload.get("from")      # siapa yang kirim
            target = payload.get("to")        # username tujuan
            request_id = payload.get("request_id")

            print("FROM:", sender)
            print("REQUEST_ID:", request_id)

            # hanya proses command
            if msg_type != "command":
                return

            fitur = payload.get("fitur")
            data_list = payload.get("data", [])

            if fitur != "locAndro":
                self._send_ws_error("unknown_fitur", fitur, sender, request_id)
                return

            if not isinstance(data_list, list):
                self._send_ws_error("invalid_payload", "data harus array", sender, request_id)
                return

            for item in data_list:

                job = {
                    "item": item,
                    "sender": sender,
                    "request_id": request_id
                }

                self.command_queue.put(job)

                print("📥 QUEUE COMMAND:", item.get("platform"))

        except json.JSONDecodeError as e:

            print("❌ JSON error:", e)

            self._send_ws_error(
                "json_error",
                str(e),
                None,
                None
            )

        except Exception as e:

            self._send_ws_error(
                "internal_error",
                str(e),
                None,
                None
            )

    def _handle_locandro_item(self, ws, item: dict, to_user, request_id):
        device = item.get("device")
        connection = item.get("connection", "").upper()
        platform = item.get("platform", "").upper()
        serial = get_serial(self.adb)

        # 🔒 FILTER CONNECTION
        if connection != "TERMUX":
            self.log(f"⏭ skip device {device} (connection={connection})")
            return      

        if(serial == device):
            try:
                self.log(f"📞 [{device}] {platform} → {item.get('to')}")

                item["status"] = "processing"

                # ROUTING PLATFORM
                if platform == "WAO" or platform == "WAB":
                    res = self.process_whatsapp(item)

                elif platform == "TLC":
                    res = self.process_telepon_selular(item)

                elif platform == "SMS":
                    res = self.process_sms(item)

                elif platform == "ADB":
                    res = self.process_adbshell(item)

                elif platform == "CMD":
                    res = self.process_cmd(item)

                elif platform == "SS":
                    res = self.process_ssb(item)

                elif platform == "USSD":
                    code = item.get("text")
                    sim = item.get("sim", 0)
                    keywords = item.get("auto", [])

                    try:
                        res = send_ussd_auto(self.adb, code, sim, keywords)

                        self.ws.send(json.dumps({
                            "event": "ussd_result",
                            "data": res
                        }))

                    except Exception as e:
                        res = {"ok": False, "msg": str(e)}

                else:
                    res = {"ok": False, "msg": "unknown platform"}


                status = "success" if res.get("ok", True) else "failed"

                self._send_ws_ack(
                    status,
                    {
                        "device": device,
                        "platform": platform,
                        "result": res
                    },
                    to_user,
                    request_id
                )        

            except Exception as e:
                 self._send_ws_ack(
                    "failed",
                    {"error": str(e)},
                    to_user,
                    request_id
                )
    
    def _command_worker(self):

        print("🧵 Worker started")

        while True:

            try:

                job = self.command_queue.get()

                print("⚙️ Worker processing job")

                item = job["item"]
                sender = job["sender"]
                request_id = job["request_id"]

                self._handle_locandro_item(
                    self.ws,
                    item,
                    sender,
                    request_id
                )

            except Exception as e:

                print("❌ Worker error:", e)

            finally:

                self.command_queue.task_done()
                        
    def _send_ws_ack(self, status, payload, to_user, request_id):

        msg = {
            "type": "ack",
            "to": to_user,
            "status": status,
            "request_id": request_id,
            "payload": payload
        }

        try:

            with self._connection_lock:

                if not self.ws_connected:
                    print("⚠️ ACK skipped (WS disconnected)")
                    return

            self.ws.send(json.dumps(msg))

            print("📤 ACK SENT:", status)

        except Exception as e:

            print("❌ ACK send error:", e)

    def _send_ws_error(self, error, message, to_user=None, request_id=None):

        msg = {
            "type": "ack",
            "status": "error",
            "error": error,
            "message": message,
            "request_id": request_id
        }

        if to_user:
            msg["to"] = to_user

        try:
            self.ws.send(json.dumps(msg))
        except:
            pass

    def durasi_to_seconds(self, d):

        if not d:
            return 0

        d = d.replace(".", ":")

        parts = [int(x) for x in d.split(":") if x.isdigit()]

        if len(parts) == 1:
            return parts[0]

        if len(parts) == 2:
            return parts[0]*60 + parts[1]

        if len(parts) == 3:
            return parts[0]*3600 + parts[1]*60 + parts[2]

        return 0

    def process_whatsapp(self, item):

        number = item.get("to")
        permission = item.get("permission")
        app = item.get("platform", "WAB")
        delay = item.get("delay", 25)

        if not self.wa:
            return {"ok": False, "msg": "WhatsAppAutomation not ready"}

        try:

            self.wa.app = app
            self.wa.package = "com.whatsapp.w4b" if app=="WAB" else "com.whatsapp"

            if permission == "call":

                call_type = item.get("type","voice")

                self.wa.open_whatsapp_chat(number)
                time.sleep(0.5)

                # VALIDASI LOGIN
                if not self.wa.ensure_logged_in():
                    return {"ok": False, "msg": "WhatsApp belum login"}

                if self.wa.handle_not_registered_popup():
                    return {"ok": False, "msg": f"Nomor {number} tidak terdaftar"}

                self.wa.handle_privacy_popup()

                self.wa.click_call(call_type)
                time.sleep(1)

                self.wa.handle_call_popup()
                # tunggu screen call muncul
                if not self.wa.wait_voip_screen():
                    self.wa.click_call(call_type)
                    # return {"ok": False, "msg": "VOIP screen tidak muncul"}

                get_call_status = self.wa.get_call_status()   

                # start timer
                call_start = time.time()

                time.sleep(delay)

                call_seconds = int(time.time() - call_start)

                durasi = f"{call_seconds//60:02d}:{call_seconds%60:02d}"

                self.wa.wake_any_call_screen()                
                self.wa._tap_button("end_call_button")

                seconds = self.durasi_to_seconds(durasi)

                if seconds >= 10:
                    return {
                        "ok": True,
                        "msg": "Panggilan WhatsApp berhasil",
                        "duration": durasi,
                        "call_status": get_call_status,
                        "number": number
                    }
                else:
                    return {
                        "ok": True,
                        "msg": "Durasi panggilan terlalu singkat",
                        "duration": durasi,
                        "call_status": get_call_status,
                        "number": number
                    }
                
            elif permission == "message":

                text = item.get("text")

                self.wa.open_whatsapp_chat(number)
                time.sleep(1)

                if self.wa.handle_not_registered_popup():
                    return {"ok": False, "msg": f"Nomor {number} tidak terdaftar"}

                self.wa.toggle_entry()

                self.wa._tap_button(
                    "e2ee_description_close_button",
                    desc_keywords=["tutup", "end", "panggilan"]
                )

                self.wa.type_text_like_human(text)

                time.sleep(delay)

                self.wa.send_message()

                return {"ok": True, "msg": "Pesan WhatsApp berhasil", "number": number}

            else:
                return {"ok": False, "msg": "permission tidak dikenal", "number": number}

        except Exception as e:

            return {"ok": False, "msg": str(e)}   

    def process_telepon_selular(self, item):
        number = item.get("to")
        permission = item.get("permission")       
        delay = item.get("delay", 15)

        if permission == "call":
            sim = item.get("sim", 0)

            make_cellular_call(self.adb, number, sim)

            # ⏳ tunggu sampai connected
            if not self.ui_call.wait_until_connected(timeout=20):
                return {"ok": False, "msg": "Call tidak connect"}

            # ⏱ mulai ambil durasi real
            call_start = time.time()
            duration = "00:00"

            while time.time() - call_start < delay:
                duration = self.ui_call.get_duration()
                time.sleep(1)

            print("⛔ Ending call...")
            self.ui_call.end_call()

            seconds = self.durasi_to_seconds(duration)

            return {
                "ok": True,
                "msg": "Telepon selular selesai",
                "duration": duration,
                "seconds": seconds,
                "number": number
            }
    
    def process_sms(self, item):           
        permission = item.get("permission")       
        delay = item.get("delay")         

        if permission == "message":  
            n = item.get("to"); t = item.get("text"); s = item.get("sim", 0)
            self.sms.send_sms(n, t, s)
            time.sleep(delay)
            return {"ok": True, "msg": "SMS berhasil", "number": n}

    def process_adbshell(self, item):
        serial = get_serial(self.adb)
        cmd = item.get("text", "")
        out = ""
        try:
          out = self.adb.shell(cmd)
          return {"ok": True, "msg": out}
        except Exception as e:
          out = str(e)
          return {"ok": False, "msg": out}
        
    def process_cmd(self, item):
        serial = get_serial(self.adb)
        cmd = item.get("text", "")
        out = ""
        try:
          out = run_local(cmd)
          return {"ok": True, "msg": out}
        except Exception as e:
          out = str(e)
          return {"ok": False, "msg": out}

    def process_ssb(self, item):
        serial = get_serial(self.adb)
        cmd = item.get("text", "")
        out = ""
        try:
          out = capture_screenshot_base64(self.adb)
          return {"ok": True, "msg": out}
        except Exception as e:
          out = str(e)
          return {"ok": False, "msg": out}
   
    def update_python_scripts(self, data):
        try:
            repo_url = data.get("repo_url", "").strip()
            branch = data.get("branch", "main").strip()
            files_to_update = data.get("files", [])
            do_backup = data.get("backup", True)
            do_restart = data.get("restart", False)
            if not repo_url:
                self.send({"type":"py_update_progress","message":"repo_url required"})
                return False
            # Basic download flow (requests may not be installed)
            try:
                import requests
            except Exception:
                self.send({"type":"py_update_progress","message":"requests not available"})
                return False
            base_raw_url = ""
            if "github.com" in repo_url:
                parts = repo_url.rstrip('/').split('/')
                if len(parts)>=5:
                    username=parts[-2]; repo_name=parts[-1]
                    base_raw_url = f"https://raw.githubusercontent.com/{username}/{repo_name}/{branch}"
                else:
                    return False
            else:
                return False
            # download files list or common set
            common_files = files_to_update or ["bridgeservice.py","WhatsAppAutomation.py","CallAudioForwarder.py","requirements.txt","config.json"]
            for fn in common_files:
                url = f"{base_raw_url}/{fn}"
                try:
                    r = requests.get(url, timeout=20)
                    if r.status_code==200:
                        with open(fn, 'w', encoding='utf-8') as f:
                            f.write(r.text)
                        self.send({"type":"py_update_progress","message":f"updated {fn}"})
                except Exception as e:
                    self.send({"type":"py_update_progress","message":f"failed {fn}: {e}"})
            if do_restart:
                self._restart_service()
            return True
        except Exception as e:
            self.send({"type":"py_update_progress","message":f"error: {e}"})
            return False

    def _restart_service(self):
        try:
            self.stop()
            time.sleep(1)
            script_path = os.path.abspath(__file__)
            os.execv(sys.executable, [sys.executable, script_path])
        except Exception as e:
            print("Restart failed:", e)
            sys.exit(1)

    def _on_close(self, ws, code, reason):        
        log_print(f"❌ WS closed: {code} - {reason}", "ERROR")
        with self._connection_lock:
            self.ws_connected = False

    def _on_error(self, ws, err):
        log_print(f"WS run error: {err}", "ERROR")
        with self._connection_lock:
            self.ws_connected = False

    def _run(self):
        while not self._stop.is_set():
            try:
                self.reconnect_attempt += 1
                log_print(f"Connecting to {self.url} (attempt {self.reconnect_attempt})")

                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_message=self._on_message,
                    on_open=self._on_open,
                    on_close=self._on_close,
                    on_error=self._on_error
                )

                self.ws.run_forever(ping_interval=20, ping_timeout=15)

            except Exception as e:
                log_print(f"WS run error: {e}", "ERROR")

            log_print("Reconnecting in 5 seconds...", "WARN")
            time.sleep(5)

    def _heartbeat_loop(self):
        """Loop heartbeat yang hanya mengirim jika WebSocket terhubung"""
        heartbeat_count = 0
        while True:
            try:
                # Tunggu sedikit untuk memastikan koneksi awal
                if heartbeat_count < 3:
                    time.sleep(10)  # Tunggu 10 detik untuk koneksi awal
                else:
                    time.sleep(HEARTBEAT_INTERVAL or 1800)
                
                # Cek apakah WebSocket terhubung
                with self._connection_lock:
                    if not self.ws_connected:
                        print(f"💤 Heartbeat skipped - WebSocket not connected")
                        heartbeat_count += 1
                        continue
                
                serial = get_serial(self.adb)
                device_info = get_device_info(self.adb)
                payload = {
                    "type": "heartbeat",
                    "device_info": device_info,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "count": heartbeat_count
                }
                print(f"❤️ Sending heartbeat #{heartbeat_count}")
                self.send(payload)
                heartbeat_count += 1
                
            except Exception as e:
                print(f"💔 Heartbeat error: {e}")
                time.sleep(60)  # Tunggu lebih singkat jika error

def main():
    print("🚀 Starting Bridge Service...")

        # 🔹 Jalankan register dulu
    from register import register_device
    register_device()

    adb = AdbWrapper()
    # Ambil serial perangkat
    serial = get_serial(adb)
    if not serial:
        print("❌ Tidak dapat membaca serial perangkat ADB!")
        return

    print(f"🔍 Mengecek status perangkat serial: {serial}")

    # Cek ke server apakah serial aktif
    respon = check_device_status(serial)
    
    username = respon.get("username")
    is_active = respon.get("active")

    if not username:
        print("❌ username tidak ditemukan di server")
        return

    if not is_active: 
        print("⛔ Perangkat belum aktif atau belum terdaftar di server.")
        return
    else:
        print("✅ Perangkat terdaftar & aktif di server. Melanjutkan...")

    # Jalankan WS
    #  client
    ws_url = f"wss://ws.autocall.my.id/ws?username={username}"
    client = WSClient(ws_url)
    client.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        client.stop()

if __name__ == "__main__":
    main()