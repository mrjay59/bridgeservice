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
except Exception as e:
    print('Warning: local modules import issue:', e)

WS_SERVER = os.environ.get("BRIDGE_WS", "wss://s14223.blr1.piesocket.com/v3/1?api_key=WVXN94EfJrQO7fSpSwwKJZgxbavdLdKLZBPLLlQR&notify_self=1")
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", 1800))  # 30 minutes default
POLL_SMS_INTERVAL = 3

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

def get_device_info(adb: AdbWrapper):
    try:
        brand = adb.shell("getprop ro.product.manufacturer").strip()
        model = adb.shell("getprop ro.product.model").strip()
        android = adb.shell("getprop ro.build.version.release").strip()
        return {"brand": brand, "model": model, "android": android}
    except Exception:
        return {}

def get_serial(adb: AdbWrapper):
    try:
        s = adb.shell("getprop ro.serialno").strip()
        if not s:
            s = adb.shell("getprop ro.boot.serialno").strip()
        return s or None
    except Exception:
        return None

# Minimal SIM/IMEI helpers (keeps previous logic brief)
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
import urllib.parse
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
    
def make_cellular_call(self, number, sim=0):
    """
    Melakukan panggilan selular biasa dengan pemilihan SIM
    """
    try:
        number = self._clean_phone_number(number)
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
                result = self.adb.shell(intent)
                time.sleep(2)  # Tunggu intent diproses
                
                # Cek apakah muncul popup pemilihan SIM
                if self.handle_sim_chooser(sim_index):
                    time.sleep(1)
                
                return True
            except Exception:
                continue
        
        # Method 2: Fallback ke intent biasa
        try:
            self.adb.shell(f'am start -a android.intent.action.CALL -d tel:{number}')
            time.sleep(2)
            # Coba handle SIM chooser jika muncul
            self.handle_sim_chooser(sim_index)
            return True
        except Exception:
            pass
        
        return False
        
    except Exception as e:
        print(f"Cellular call error: {e}")
        return False

def make_cellular_call_via_ussd(self, number, sim=0):
    """
    Melakukan panggilan menggunakan USSD code (alternatif method)
    """
    try:
        number = self.clean_phone_number(number)
        sim_index = int(sim)
        
        # Encode number untuk USSD
        encoded_number = urllib.parse.quote(number, safe='')
        
        intents = [
            f'am start -a android.intent.action.CALL -d tel:{encoded_number} --ei android.telecom.extra.SIM_SLOT_INDEX {sim_index}',
            f'am start -a android.intent.action.CALL -d tel:{encoded_number} --ei subscription {sim_index}'
        ]
        
        for intent in intents:
            try:
                self.adb.shell(intent)
                time.sleep(3)
                
                # Handle SIM chooser
                if self.handle_sim_chooser(sim_index):
                    time.sleep(2)
                
                return True
            except Exception:
                continue
        
        return False
        
    except Exception as e:
        print(f"USSD call error: {e}")
        return False

def handle_sim_chooser(self, sim_index):
    """
    Menangani popup pemilihan SIM jika muncul
    Returns: True jika berhasil memilih SIM, False jika tidak
    """
    try:
        # Tunggu sebentar untuk popup muncul
        time.sleep(1.5)
        
        # Method 1: Menggunakan uiautomator2 jika available
        if UIAUTOMATOR2_AVAILABLE:
            try:
                d = u2.connect()
                
                # Daftar teks yang mungkin untuk tombol SIM
                sim_texts = [
                    f"SIM {sim_index + 1}",
                    f"SIM{sim_index + 1}",
                    f"Kartu {sim_index + 1}",
                    f"Kartu SIM {sim_index + 1}",
                    f"Use SIM {sim_index + 1}",
                    f"Pilih SIM {sim_index + 1}",
                    f"Call with SIM {sim_index + 1}",
                    f"Panggil dengan SIM {sim_index + 1}"
                ]
                
                # Coba klik berdasarkan teks
                for text in sim_texts:
                    if d(text=text).exists:
                        d(text=text).click()
                        return True
                
                # Coba klik berdasarkan index jika ada multiple buttons
                buttons = d(className="android.widget.Button")
                if buttons.exists and buttons.count > sim_index:
                    buttons[sim_index].click()
                    return True
                    
            except Exception:
                pass
        
        # Method 2: Menggunakan coordinate tapping berdasarkan hierarchy dump
        xml_dump = self.adb.shell('uiautomator dump /sdcard/window_dump.xml && cat /sdcard/window_dump.xml')
        if not xml_dump:
            return False
            
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_dump)
            
            sim_elements = []
            for node in root.iter('node'):
                text = node.attrib.get('text', '') + ' ' + node.attrib.get('content-desc', '')
                bounds = node.attrib.get('bounds', '')
                
                # Cari elemen yang terkait SIM
                sim_keywords = ['sim', 'kartu', 'call with', 'panggil dengan']
                if any(keyword in text.lower() for keyword in sim_keywords) and bounds:
                    sim_elements.append((text, bounds))
            
            # Jika ditemukan elemen SIM, pilih berdasarkan index
            if len(sim_elements) > sim_index:
                bounds = sim_elements[sim_index][1]
                coords = re.findall(r'\d+', bounds)
                if len(coords) >= 4:
                    x1, y1, x2, y2 = map(int, coords[:4])
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    self.adb.shell(f'input tap {cx} {cy}')
                    return True
                    
        except Exception:
            pass
            
        return False
        
    except Exception as e:
        print(f"SIM chooser handler error: {e}")
        return False

def clean_phone_number(self, number):
    """
    Membersihkan format nomor telepon
    """
    import re
    cleaned = re.sub(r'[^\d+]', '', str(number))
    
    # Format Indonesia: ubah 0xxx menjadi +62xxx
    if cleaned.startswith('0') and not cleaned.startswith('+'):
        cleaned = '+62' + cleaned[1:]
    elif not cleaned.startswith('+'):
        cleaned = '+62' + cleaned
        
    return cleaned

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
        import re
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
                    mid = m.get('id') or m.get('date') or json.dumps(m)
                    if mid not in self.last_seen_ids:
                        new.append(m); self.last_seen_ids.add(mid)
                for m in reversed(new):
                    try:
                        self.ws.send({"type":"sms_received","data":m,"serial":get_serial(self.adb)})
                    except Exception:
                        pass
                if len(self.last_seen_ids) > 2000:
                    self.last_seen_ids = set(list(self.last_seen_ids)[-1000:])
            except Exception as e:
                print("SMSHandler poll error:", e)
            time.sleep(POLL_SMS_INTERVAL)

class WSClient:
    def __init__(self, url):
        self.url = url
        self.ws = None
        self.adb = AdbWrapper()
        self.sms = SMSHandler(self, self.adb)
        self._stop = threading.Event()
        self.wa = None
        try:
            self.wa = WhatsAppAutomation(self.adb, app="business")
        except Exception:
            self.wa = None

        use_root_audio = os.environ.get("USE_ROOT_AUDIO", "false").lower() == "true"
        try:
            self.audio_forwarder = CallAudioForwarder(self.adb, self, use_root=use_root_audio)
            if self.wa:
                self.wa.audio_forwarder = self.audio_forwarder
        except Exception:
            self.audio_forwarder = None

        # start heartbeat thread
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        t2 = threading.Thread(target=self.sms.poll_loop, daemon=True)
        t2.start()

    def stop(self):
        self._stop.set()
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

            # Pastikan koneksi WebSocket sudah siap
            if (
                self.ws 
                and hasattr(self.ws, "sock") 
                and self.ws.sock 
                and getattr(self.ws.sock, "connected", False)
            ):
                try:
                    self.ws.send(payload)
                    print(f"WS sent: {payload[:100]}...")  # log sebagian isi
                except Exception as e:
                    print(f"⚠️ WS send failed: {e}")
            else:
                print("⏳ WebSocket not ready, skipping send for:", data.get("type", "unknown"))

        except Exception as e:
            print(f"❌ WS send exception: {e}")

    def _on_open(self, ws):
        device_info = get_device_info(self.adb)
        ip_local = get_local_ip(self.adb)
        serial = get_serial(self.adb)
        sim1 = {"imei": get_imei(self.adb, 0), **get_sim_info(self.adb, 0)}
        sim2 = {"imei": get_imei(self.adb, 1), **get_sim_info(self.adb, 1)}
        profile = {"platform":"termux","device":device_info,"serial":serial,"ip_local":ip_local,"sims":[sim1,sim2]}
        self.send({"type":"bridge_hello","id":str(uuid.uuid4()),"info":profile,"serial":serial})

    def _on_message(self, ws, message):
        try:
            msg = json.loads(message)
        except Exception:
            return
        action = msg.get("action")
        data = msg.get("data", {})
        req_id = msg.get("id")
        serialnum = msg.get("serialnum")
        serial = get_serial(self.adb)

        # If message targets this device by serial (or no serial provided), process actions
        if serialnum and serialnum != serial:
            # not for this device -- ignore
            return

        if not action:
            print("Received message without action:", msg)
            return

        # Core actions
        if action == "send_sms":
            n = data.get("number"); t = data.get("text"); s = data.get("sim", 0)
            ok = self.sms.send_sms(n, t, s)
            self.send({"type": "send_sms_result", "ok": ok, "id": req_id, "serial": serial})

        elif action == "open_app":
            pkg = data.get("package"); ok = False
            if pkg:
                try:
                    self.adb.shell(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
                    ok = True
                except Exception as e:
                    self.send({"type": "error", "msg": str(e), "id": req_id, "serial": serial})
            self.send({"type": "open_app_result", "ok": ok, "id": req_id, "serial": serial})

        elif action == "adb_shell":
            cmd = data.get("cmd", "")
            out = ""
            try:
                out = self.adb.shell(cmd)
            except Exception as e:
                out = str(e)
            self.send({"type": "adb_shell_result", "out": out, "id": req_id, "serial": serial})

        elif action == "send_ussd":
            code = data.get("code"); sim = data.get("sim", 0)
            from bridgeservice import send_ussd_and_read as ussd  # local import to reuse function if present
            try:
                res = ussd(self.adb, code, sim)
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            self.send({"type": "send_ussd_result", "result": res, "id": req_id, "serial": serial})

        elif action == "wa_open_chat":
            number = data.get("number")
            app = data.get("app", "business")
            if self.wa:
                self.wa.app = app
                self.wa.package = "com.whatsapp.w4b" if app=="business" else "com.whatsapp"
                ok = self.wa.open_whatsapp_chat(number)
            else:
                ok = False
            self.send({"type":"wa_open_chat_result","ok":ok,"id":req_id,"serial":serial})

        elif action == "wa_call":
            number = data.get("number")
            app = data.get("app", "business")
            call_type = data.get("type","voice")
            ok = False
            if self.wa:
                self.wa.app = app
                self.wa.package = "com.whatsapp.w4b" if app=="business" else "com.whatsapp"
                self.wa.open_whatsapp_chat(number)
                time.sleep(5)
                ok = self.wa.click_call(call_type)
            self.send({"type":"wa_call_result","ok":ok,"id":req_id,"serial":serial})

        elif action == "audio_start":
            use_root = data.get("use_root", False)
            if self.audio_forwarder:
                self.audio_forwarder.use_root = use_root
                self.audio_forwarder.start()
                ok = True
            else:
                ok = False
            self.send({"type": "audio_start_result", "ok": ok, "id": req_id, "serial": serial})

        elif action == "audio_stop":
            if self.audio_forwarder:
                self.audio_forwarder.stop()
            self.send({"type": "audio_stop_result", "ok": True, "id": req_id, "serial": serial})

        elif action == "cellular_call":
            number = data.get("number")
            sim = data.get("sim", 0)  # 0 untuk SIM 1, 1 untuk SIM 2
            ok = self.make_cellular_call(number, sim)
            self.send({"type":"cellular_call_result","ok":ok,"id":req_id,"serial":serial})

        elif action == "cellular_call_ussd":
            number = data.get("number")
            sim = data.get("sim", 0)
            ok = self.make_cellular_call_via_ussd(number, sim)
            self.send({"type":"cellular_call_result","ok":ok,"id":req_id,"serial":serial})

        elif action == "update_scripts":
            success = self.update_python_scripts(data)
            self.send({"type": "py_update_result", "ok": success, "id": req_id, "serial": serial})

        else:
            self.send({"type": "unknown_action", "action": action, "id": req_id, "serial": serial})

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
        print("WS closed", code, reason)

    def _on_error(self, ws, err):
        print("WS error:", err)

    def _run(self):
        while not self._stop.is_set():
            try:
                print("Connecting to", self.url)
                self.ws = websocket.WebSocketApp(self.url,
                                                 on_message=self._on_message,
                                                 on_open=self._on_open,
                                                 on_close=self._on_close,
                                                 on_error=self._on_error)
                self.ws.run_forever()
            except Exception as e:
                print("WS run error:", e)
            time.sleep(5)

    def _heartbeat_loop(self):
        while True:
            try:
                serial = get_serial(self.adb)
                payload = {"type":"heartbeat","serial":serial,"timestamp":datetime.now(timezone.utc).isoformat()}
                self.send(payload)
            except Exception as e:
                print("heartbeat error:", e)
            time.sleep(HEARTBEAT_INTERVAL or 1800)

def main():
    client = WSClient(WS_SERVER)
    client.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.stop()

if __name__ == "__main__":
    main()
