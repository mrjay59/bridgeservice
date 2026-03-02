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
import requests
import urllib.parse  # Pindah import ke atas
from datetime import datetime, timezone


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
            msg = data.get("msg")
            return data.get("active")
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

def send_ussd_and_read(adb: AdbWrapper, code: str, sim: int = 0, wait_response_sec: int = 6):
    """
    Dial USSD code and attempt to force-select SIM (sim=0 SIM1, sim=1 SIM2).
    Returns dict with keys: ok, error, raw_ui, ussd_text
    """
    result = {"ok": False, "error": None, "raw_ui": None, "ussd_text": None}
    try:
        if not code:
            result['error'] = "empty code"
            return result
        enc = _encode_ussd(code)  # *999%23
        sim_index = int(sim) if sim is not None else 0

        # try dialing with several intent variants
        intents = [
            f"am start -a android.intent.action.CALL -d tel:{enc}",
            f"am start -a android.intent.action.CALL -d tel:{enc} --ei android.telecom.extra.SIM_SLOT_INDEX {sim_index}",
            f"am start -a android.intent.action.CALL -d tel:{enc} --ei simSlot {sim_index} --ei subscription {sim_index} --ei com.android.phone.extra.slot {sim_index}",
        ]
        dialed = False
        for it in intents:
            try:
                adb.shell(it)
                dialed = True
                time.sleep(0.3)
            except Exception:
                pass
        if not dialed:
            result['error'] = "failed to send dial intent"
            return result

        # Wait shortly for chooser/ussd popup
        time.sleep(0.8)

        # If uiautomator2 available, try to click SIM choice then capture hierarchy
        if UIAUTOMATOR2_AVAILABLE:
            try:
                d = u2.connect()  # may throw if cannot connect
                # try to click via common labels
                sim_labels = ["SIM 1","SIM 2","SIM1","SIM2","Use SIM 1","Use SIM 2","Pilih SIM","Pilih kartu","Kartu 1","Kartu 2","Call with SIM 1","Call with SIM 2","Panggil dengan SIM 1","Panggil dengan SIM 2"]
                chosen = False
                for lbl in sim_labels:
                    try:
                        e = d(text=lbl)
                        if e.exists:
                            e.click()
                            chosen = True
                            break
                    except Exception:
                        pass
                # try to click first/second button if still not chosen
                if not chosen:
                    try:
                        buttons = d(className="android.widget.Button")
                        if buttons.exists:
                            idx = 0 if sim_index==0 else (1 if buttons.count>1 else 0)
                            buttons[idx].click()
                            chosen = True
                    except Exception:
                        pass
                # wait for USSD response to appear
                time.sleep(wait_response_sec)
                ui_dump = d.dump_hierarchy()
                result['raw_ui'] = ui_dump
                # parse XML and extract large text blocks
                try:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(ui_dump)
                    texts = []
                    for node in root.iter('node'):
                        txt = node.attrib.get('text') or node.attrib.get('content-desc') or ''
                        if txt and len(txt.strip())>3:
                            texts.append(txt.strip())
                    if texts:
                        result['ussd_text'] = max(texts, key=lambda s: len(s))
                except Exception:
                    pass
                result['ok'] = True
                return result
            except Exception as e:
                # u2 connect/click failed -> fallback to dump method
                #print("u2 error:", e)
                pass

        # Fallback: uiautomator dump + parse + click coordinates if chooser present
        chosen = False
        for attempt in range(4):
            try:
                adb.shell('uiautomator dump /sdcard/ussd_dump.xml')
                local_tmp = '/data/data/com.termux/files/home/bridgeservice/ussd_dump.xml'
                # pull or read
                try:
                    adb.pull('/sdcard/ussd_dump.xml', local_tmp)
                    xml_text = open(local_tmp, 'r', encoding='utf-8', errors='ignore').read()
                except Exception:
                    xml_text = adb.shell('cat /sdcard/ussd_dump.xml') or ""
                result['raw_ui'] = xml_text
                # parse xml for candidate buttons / text nodes
                try:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(xml_text)
                    candidates = []
                    for node in root.iter('node'):
                        cls = node.attrib.get('class','')
                        text = (node.attrib.get('text') or node.attrib.get('content-desc') or "").strip()
                        bounds = node.attrib.get('bounds','')
                        if bounds and ( 'Button' in cls or 'TextView' in cls or text):
                            candidates.append((text, bounds))
                    # find SIM-labeled node
                    target_bounds = None
                    sim_targets = ['SIM 1','SIM 2','SIM1','SIM2','SIM 1','SIM 2','Pilih SIM','Pilih kartu','kartu SIM 1','kartu SIM 2','Kartu 1','Kartu 2']
                    for text,bounds in candidates:
                        if not text:
                            continue
                        tlow = text.lower()
                        for st in sim_targets:
                            if st.lower() in tlow:
                                # choose matching sim index if present
                                if str(sim+1) in tlow or ('sim 1' in st.lower() and sim==0) or ('sim 2' in st.lower() and sim==1):
                                    target_bounds = bounds
                                    break
                                else:
                                    target_bounds = bounds
                                    break
                        if target_bounds:
                            break
                    # fallback pick by order
                    if not target_bounds and candidates:
                        nonempty = [c for c in candidates if c[0]]
                        if nonempty:
                            idx = sim if sim < len(nonempty) else 0
                            target_bounds = nonempty[idx][1]
                    if target_bounds:
                        m = re.findall(r'\[(-?\d+),(-?\d+)\]', target_bounds)
                        if len(m)>=2:
                            l,t = map(int, m[0]); r,b = map(int, m[1])
                            cx = (l+r)//2; cy = (t+b)//2
                            adb.shell(f"input tap {cx} {cy}")
                            chosen = True
                            time.sleep(1.2)
                            break
                except Exception:
                    pass
            except Exception:
                pass
            time.sleep(0.8)

        # After selecting (or if chooser didn't appear), wait for USSD response and dump xml
        time.sleep(wait_response_sec)
        try:
            adb.shell('uiautomator dump /sdcard/ussd_dump.xml')
            local_tmp = '/data/data/com.termux/files/home/bridgeservice/ussd_dump.xml'
            try:
                adb.pull('/sdcard/ussd_dump.xml', local_tmp)
                xml_text = open(local_tmp, 'r', encoding='utf-8', errors='ignore').read()
            except Exception:
                xml_text = adb.shell('cat /sdcard/ussd_dump.xml') or ""
            result['raw_ui'] = xml_text
            # parse text blocks
            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(xml_text)
                texts = []
                for node in root.iter('node'):
                    txt = node.attrib.get('text') or node.attrib.get('content-desc') or ''
                    if txt and len(txt.strip())>3:
                        texts.append(txt.strip())
                if texts:
                    result['ussd_text'] = max(texts, key=lambda s: len(s))
            except Exception:
                pass
        except Exception:
            pass

        result['ok'] = True
        return result

    except Exception as e:
        result['error'] = str(e)
        return result

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
            # baris SIM adalah LinearLayout langsung di ListView
            if node.attrib.get("class") == "android.widget.LinearLayout":
                bounds = node.attrib.get("bounds")
                if not bounds:
                    continue

                # Filter hanya row dalam area ListView
                # (menghindari container lain)
                parent = node.attrib.get("package") == "com.android.dialer"
                if parent:
                    sim_rows.append(bounds)

        if len(sim_rows) < sim_index + 1:
            return False

        # ==========================
        # 3️⃣ Tap berdasarkan index
        # ==========================
        bounds = sim_rows[sim_index]
        nums = list(map(int, re.findall(r"\d+", bounds)))

        if len(nums) != 4:
            return False

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
        self.send({"type":"bridge_hello", "message":"device online update data","id":str(uuid.uuid4()),"info":profile,"serial":serial})

    def _on_message(self, ws, message):
        try:
           
            payload = json.loads(message)
            
            fitur = payload.get("fitur")
            data_list = payload.get("data", [])

            if fitur != "locAndro":
                self._send_ws_error("unknown_fitur", fitur)
                return

            if not isinstance(data_list, list):
                self._send_ws_error("invalid_payload", "Format payload salah")
                return

            for item in data_list:
                try:
                    self._handle_locandro_item(ws, item)
                    self._send_ws_ack("done", item)
                except Exception as e:
                    self._send_ws_error("process_failed", str(e), item)  

        except json.JSONDecodeError as e:
            print("❌ JSON error:", e)
            self._send_ws_error("json_error", str(e))              

        except Exception as e:
            self._send_ws_error("internal_error", str(e))

    def _handle_locandro_item(self, ws, item: dict):
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
                    self.process_whatsapp(item)               

                elif platform == "TLC":
                    self.process_telepon_selular(item)

                elif platform == "SMS":
                    self.process_sms(item)

                elif platform == "ADB":
                    self.process_adbshell(item)

                elif platform == "CMD":
                    self.process_cmd(item)

                elif platform == "SS":
                    self.process_ssb(item)

                elif platform == "USSD":
                    code = item.get("text"); sim = item.get("sim", 0)
                    try:
                        res = send_ussd_and_read(self.adb, code, sim)
                    except Exception as e:
                        res = {"ok": False, "error": str(e)}
                    self.send({"type": "send_ussd_result", "result": res, "serial": serial})


                item["status"] = "success"
                self._send_ack(ws, item, True)

            except Exception as e:
                item["status"] = "failed"
                item["retry"] = item.get("retry", 0) + 1
                item["lastError"] = str(e)

                self._send_ack(ws, item, False)

    def _send_ws_ack(self, status, payload):
        with self._connection_lock:
            if not self.ws_connected:
                return
        msg = {
            "type": "ack",
            "message": "reply ack to client ",
            "status": status,
            "payload": payload
        }
        try:
            self.ws.send(json.dumps(msg))
        except Exception:
            pass

    def _send_ws_error(self, code, message, payload=None):
        with self._connection_lock:
            if not self.ws_connected:
                return
        msg = {
            "type": "error",
            "code": code,
            "message": message,
            "payload": payload
        }
        try:
            self.ws.send(json.dumps(msg))
        except Exception:
            pass

    def durasi_to_seconds(d):
        if not d:
            return 0
        parts = list(map(int, d.split(":")))
        if len(parts) == 2:
            return parts[0]*60 + parts[1]
        if len(parts) == 3:
            return parts[0]*3600 + parts[1]*60 + parts[2]
        return 0

    def process_whatsapp(self, item):
        # WAO
        number = item.get("to")
        permission = item.get("permission")
        app = item.get("platform", "WAB")
        delay = item.get("delay")

        if permission == "call":            
            call_type = item.get("type","voice")
                   
            if self.wa:
                self.wa.app = app
                self.wa.package = "com.whatsapp.w4b" if app=="WAB" else "com.whatsapp"
                self.wa.open_whatsapp_chat(number)                
                time.sleep(2)

                # 🔥 CEK NOMOR TIDAK TERDAFTAR
                if self.wa.handle_not_registered_popup():
                    print(f"Nomor {number} tidak terdaftar, skip")
                    return  # ⬅️ LANJUT ITEM BERIKUTNYA
                
                 # 3️⃣ Tap tombol end call
                self.wa._tap_button(
                    "e2ee_description_close_button",
                    desc_keywords=["tutup", "end", "panggilan"]
                )
                         
                self.wa.click_call(call_type)
                time.sleep(2) 
                # 2️⃣ Handle popup jika muncul
                self.wa.handle_call_popup()
                time.sleep(delay)     
                self.wa._tap_button("end_call_button")                
                durasi = self.wa.get_durasi()
                if self.durasi_to_seconds(durasi) >= 10:                   
                    self.wa._tap_button("end_call_button")

        elif permission == "message":    
            text = item.get("text")          
            if self.wa:
                self.wa.app = app
                self.wa.package = "com.whatsapp.w4b" if app=="WAB" else "com.whatsapp"
                self.wa.open_whatsapp_chat(number)
                time.sleep(3)

                if self.wa.handle_not_registered_popup():
                    print(f"Nomor {number} tidak terdaftar, skip")
                    return  # ⬅️ LANJUT ITEM BERIKUTNYA
                                
                self.wa.toggle_entry()
                 # 3️⃣ Tap tombol end call
                self.wa._tap_button(
                    "e2ee_description_close_button",
                    desc_keywords=["tutup", "end", "panggilan"]
                )                            
                self.wa.type_text_like_human(text)
                time.sleep(delay)  
                self.wa.send_message()      

    def process_telepon_selular(self, item):
        # TLC
        number = item.get("to")
        permission = item.get("permission")       
        delay = item.get("delay")

        if permission == "call":  
            duration = self.ui_call.get_duration()
            sim = item.get("sim", 0)  # 0 untuk SIM 1, 1 untuk SIM 2
            make_cellular_call(self.adb, number, sim)
            time.sleep(delay)
            self.ui_call.end_call()
            if duration >= "00:10":
                print("⛔ Ending call...")
                self.ui_call.end_call()

    def process_sms(self, item):           
        permission = item.get("permission")       
        delay = item.get("delay")

        if permission == "message":  
            n = item.get("to"); t = item.get("text"); s = item.get("sim", 0)
            self.sms.send_sms(n, t, s)
            time.sleep(delay)

    def process_adbshell(self, item):
        serial = get_serial(self.adb)
        cmd = item.get("text", "")
        out = ""
        try:
          out = self.adb.shell(cmd)
        except Exception as e:
          out = str(e)
          self.send({"type": "adb_shell_result", "out": out, "serial": serial})

    def process_cmd(self, item):
        serial = get_serial(self.adb)
        cmd = item.get("text", "")
        out = ""
        try:
          out = run_local(cmd)
        except Exception as e:
          out = str(e)
          self.send({"type": "adb_shell_result", "out": out, "serial": serial})

    def process_ssb(self, item):
        serial = get_serial(self.adb)
        cmd = item.get("text", "")
        out = ""
        try:
          out = capture_screenshot_base64(self.adb)
        except Exception as e:
          out = str(e)
          self.send({"type": "adb_shell_result", "out": out, "serial": serial})
   
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
        log_print(f"WS run error: {e}", "ERROR")
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

                self.ws.run_forever(ping_interval=30, ping_timeout=10)

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
    is_active = check_device_status(serial)
    
    if not is_active:
        print("⛔ Perangkat belum aktif atau belum terdaftar di server.")
        return
    else:
        print("✅ Perangkat terdaftar & aktif di server. Melanjutkan...")

    # Jalankan WS
    #  client
    ws_url = f"wss://ws.autocall.my.id/ws?username={serial}"
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