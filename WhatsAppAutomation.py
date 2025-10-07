import xml.etree.ElementTree as ET
import time, re, subprocess
import base64
from PIL import Image
import io
import threading

class WhatsAppAutomation:
    def __init__(self, adb, app="business"):
        self.adb = adb
        self.app = app
        self.package = "com.whatsapp.w4b" if app == "business" else "com.whatsapp"
        self.ws = None
        self.audio_forwarder = None
        self._monitor_running = False
        self._call_monitor_thread = None

    def login_whatsappbybarcode(self):
        try:
            if not self._click_agree_continue():
                return False
            time.sleep(1)
            if not self._open_linked_devices_menu():
                return False
            time.sleep(1)
            qr = self._get_qr_code()
            return qr
        except Exception as e:
            print("login_whatsappbybarcode error:", e)
            return False

    def login_whatsappbynumber(self, phone_number):
        try:
            if not self._click_agree_continue():
                return False
            time.sleep(1)
            if not phone_number:
                print("phone_number required for number login")
                return False
            if not self._input_phone_number(phone_number):
                return False
            time.sleep(1)
            if not self._confirm_phone_number():
                return False
            return True
        except Exception as e:
            print("login_whatsappbynumber error:", e)
            return False

    def login_whatsapp_business(self):
        try:
            if not self._click_agree_continue_business():
                return False
            time.sleep(1)
            return self.login_whatsappbybarcode()
        except Exception as e:
            print("login_whatsapp_business error:", e)
            return False

    def _click_agree_continue(self):
        xml = self.dump_ui()
        try:
            root = ET.fromstring(xml)
        except Exception:
            return False
        for node in root.iter('node'):
            if node.attrib.get('resource-id') == 'com.whatsapp:id/eula_accept' and node.attrib.get('text') == 'AGREE AND CONTINUE':
                bounds = node.attrib.get('bounds')
                if bounds:
                    x1,y1,x2,y2 = map(int, re.findall(r'\d+', bounds))
                    cx,cy = (x1+x2)//2, (y1+y2)//2
                    self.adb.shell(f"input tap {cx} {cy}")
                    time.sleep(1)
                    return True
        return False

    def _click_agree_continue_business(self):
        xml = self.dump_ui()
        try:
            root = ET.fromstring(xml)
        except Exception:
            return False
        for node in root.iter('node'):
            if node.attrib.get('resource-id') == 'com.whatsapp.w4b:id/eula_accept' and node.attrib.get('text') == 'AGREE AND CONTINUE':
                bounds = node.attrib.get('bounds')
                if bounds:
                    x1,y1,x2,y2 = map(int, re.findall(r'\d+', bounds))
                    cx,cy = (x1+x2)//2, (y1+y2)//2
                    self.adb.shell(f"input tap {cx} {cy}")
                    time.sleep(1)
                    return True
        return False

    def _input_phone_number(self, phone_number):
        xml = self.dump_ui()
        try:
            root = ET.fromstring(xml)
        except Exception:
            return False
        phone_field = None
        for node in root.iter('node'):
            if node.attrib.get('class') == 'android.widget.EditText' and 'registration_phone' in (node.attrib.get('resource-id') or ''):
                phone_field = node; break
        if not phone_field:
            return False
        bounds = phone_field.attrib.get('bounds')
        if bounds:
            x1,y1,x2,y2 = map(int, re.findall(r'\d+', bounds))
            cx,cy = (x1+x2)//2, (y1+y2)//2
            self.adb.shell(f"input tap {cx} {cy}")
            time.sleep(0.5)
            self.adb.shell(f"input text {phone_number}")
            time.sleep(0.5)
            # try click next
            xml2 = self.dump_ui()
            try:
                root2 = ET.fromstring(xml2)
                for node in root2.iter('node'):
                    if node.attrib.get('resource-id') and 'registration_submit' in node.attrib.get('resource-id') and (node.attrib.get('text') or '').upper()=='NEXT':
                        b = node.attrib.get('bounds')
                        if b:
                            x1,y1,x2,y2 = map(int, re.findall(r'\d+', b))
                            cx,cy = (x1+x2)//2,(y1+y2)//2
                            self.adb.shell(f"input tap {cx} {cy}")
                            time.sleep(1)
                            return True
            except Exception:
                pass
        return False

    def _confirm_phone_number(self):
        xml = self.dump_ui()
        try:
            root = ET.fromstring(xml)
        except Exception:
            return False
        for node in root.iter('node'):
            if node.attrib.get('resource-id') == 'android:id/button1' and (node.attrib.get('text') or '').lower() in ('yes','telepon','ok'):
                bounds = node.attrib.get('bounds')
                if bounds:
                    x1,y1,x2,y2 = map(int, re.findall(r'\d+', bounds))
                    cx,cy = (x1+x2)//2,(y1+y2)//2
                    self.adb.shell(f"input tap {cx} {cy}")
                    time.sleep(1)
                    return True
        return False

    def _open_linked_devices_menu(self):
        xml = self.dump_ui()
        try:
            root = ET.fromstring(xml)
        except Exception:
            return False
        for node in root.iter('node'):
            if (node.attrib.get('content-desc')=='More options' or node.attrib.get('resource-id')=='com.whatsapp:id/menuitem_overflow'):
                b = node.attrib.get('bounds')
                if b:
                    x1,y1,x2,y2 = map(int, re.findall(r'\d+', b))
                    cx,cy = (x1+x2)//2,(y1+y2)//2
                    self.adb.shell(f"input tap {cx} {cy}")
                    time.sleep(1)
                    xml2 = self.dump_ui()
                    try:
                        root2 = ET.fromstring(xml2)
                        for n2 in root2.iter('node'):
                            if (n2.attrib.get('text') or '').lower().find('link')!=-1:
                                b2 = n2.attrib.get('bounds')
                                if b2:
                                    x1,y1,x2,y2 = map(int, re.findall(r'\d+', b2))
                                    cx,cy = (x1+x2)//2,(y1+y2)//2
                                    self.adb.shell(f"input tap {cx} {cy}")
                                    time.sleep(1)
                                    return True
                    except Exception:
                        pass
        return False

    def _get_qr_code(self):
        xml = self.dump_ui()
        try:
            root = ET.fromstring(xml)
        except Exception:
            return None
        for node in root.iter('node'):
            if (node.attrib.get('content-desc')=='QR code' or 'registration_qr' in (node.attrib.get('resource-id') or '')):
                bounds = node.attrib.get('bounds')
                if bounds:
                    coords = list(map(int, re.findall(r'\d+', bounds)))
                    if len(coords)>=4:
                        x1,y1,x2,y2 = coords[:4]
                        screenshot_path = "/sdcard/qr_code.png"
                        self.adb.shell(f"screencap -p {screenshot_path}")
                        subprocess.run(["adb","pull",screenshot_path,"."])
                        try:
                            img = Image.open("qr_code.png")
                            qr_img = img.crop((x1,y1,x2,y2))
                            buffered = io.BytesIO()
                            qr_img.save(buffered, format="PNG")
                            return base64.b64encode(buffered.getvalue()).decode()
                        except Exception as e:
                            print("qr process error:", e)
                            return None
        return None

    def get_call_status(self):
        try:
            out = self.adb.shell("dumpsys activity top") or ""
            if "VoipActivityV3" not in out and "voip" not in out.lower():
                return "idle"
            # try find subtitle text longer than 2 chars
            m = re.search(r'text=\"([^\"]{2,50})\"', out)
            if m:
                return m.group(1)
            return "in_call"
        except Exception:
            return "unknown"

    def _tap_button(self, button_id):
        try:
            out = self.adb.shell("dumpsys activity top") or ""
            m = re.search(rf'{button_id}.*?(\d+),(\d+)-(\d+),(\d+)', out)
            if m:
                x1,y1,x2,y2 = map(int, m.groups())
                cx,cy = (x1+x2)//2,(y1+y2)//2
                self.adb.shell(f"input tap {cx} {cy}")
                time.sleep(1)
                return True
        except Exception as e:
            print("_tap_button error:", e)
        return False

    def end_call(self):
        return self._tap_button("end_call_button")

    def toggle_mute(self):
        return self._tap_button("mute_button")

    def toggle_speaker(self):
        return self._tap_button("audio_route_button")

    def toggle_camera(self):
        return self._tap_button("camera_button")

    def open_whatsapp_chat(self, number):
        try:
            self.adb.shell(f"am start -a android.intent.action.VIEW -d 'https://wa.me/{number}' {self.package}")
            time.sleep(2)
            xml = self.dump_ui()
            try:
                root = ET.fromstring(xml)
            except Exception:
                return True
            for node in root.iter('node'):
                desc = node.attrib.get('content-desc') or ''
                txt = node.attrib.get('text') or ''
                if desc == 'Tutup' or txt.upper() in ('OKE','OK'):
                    b = node.attrib.get('bounds')
                    if b:
                        x1,y1,x2,y2 = map(int, re.findall(r'\d+', b))
                        cx,cy = (x1+x2)//2,(y1+y2)//2
                        self.adb.shell(f"input tap {cx} {cy}")
                        time.sleep(1)
                        break
            return True
        except Exception as e:
            print("open_whatsapp_chat error:", e)
            return False

    def dump_ui(self, path="/sdcard/wa_dump.xml"):
        try:
            self.adb.shell(f"uiautomator dump {path}")
            out, _ = subprocess.Popen(["adb","shell",f"cat {path}"], stdout=subprocess.PIPE).communicate()
            return out.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def click_call(self, call_type="voice"):
        xml = self.dump_ui()
        try:
            root = ET.fromstring(xml)
        except Exception:
            return False
        target_desc = "Telepon suara" if call_type=="voice" else "Telepon video"
        for node in root.iter('node'):
            desc = node.attrib.get('content-desc') or ''
            if target_desc in desc:
                b = node.attrib.get('bounds')
                if b:
                    x1,y1,x2,y2 = map(int, re.findall(r'\d+', b))
                    cx,cy = (x1+x2)//2,(y1+y2)//2
                    self.adb.shell(f"input tap {cx} {cy}")
                    time.sleep(1)
                    return True
        return False

    def start_call_monitor(self):
        if self._call_monitor_thread and self._call_monitor_thread.is_alive():
            return
        self._monitor_running = True
        self._call_monitor_thread = threading.Thread(target=self._call_monitor_loop, daemon=True)
        self._call_monitor_thread.start()

    def stop_call_monitor(self):
        self._monitor_running = False
        if self._call_monitor_thread:
            self._call_monitor_thread.join(timeout=2)
            self._call_monitor_thread = None

    def _call_monitor_loop(self):
        while self._monitor_running:
            try:
                status = self.get_call_status()
                if status in ("Berdering","in_call"):
                    if self.audio_forwarder and not getattr(self.audio_forwarder, "running", False):
                        self.audio_forwarder.start()
                else:
                    if self.audio_forwarder and getattr(self.audio_forwarder, "running", False):
                        self.audio_forwarder.stop()
                time.sleep(2)
            except Exception as e:
                print("call monitor error:", e)
                time.sleep(2)
