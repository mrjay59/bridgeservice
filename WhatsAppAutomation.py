import xml.etree.ElementTree as ET
import time, re, subprocess
import base64
from PIL import Image
import io
import threading
import time
import random

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
            # Dump UI
            self.adb.shell("uiautomator dump /sdcard/window_dump.xml")
            time.sleep(0.3)

            xml = self.adb.shell("cat /sdcard/window_dump.xml")
            if "<?xml" not in xml:
                return "idle"

            root = ET.fromstring(xml[xml.index("<?xml"):])

            # 1️⃣ Pastikan benar-benar di UI call WhatsApp
            in_call_ui = False
            for node in root.iter("node"):
                res_id = node.attrib.get("resource-id", "")
                if res_id.endswith(":id/call_screen_root"):
                    in_call_ui = True
                    break

            if not in_call_ui:
                return "idle"

            # 2️⃣ Ambil status dari subtitle (PALING AKURAT)
            for node in root.iter("node"):
                res_id = node.attrib.get("resource-id", "")
                if res_id.endswith(":id/subtitle"):
                    txt = node.attrib.get("text", "").strip()
                    if txt:
                        return txt.lower()  # contoh: memanggil, berdering, terhubung

            # 3️⃣ Fallback: cari kata kunci status
            fallback_keywords = [
                "memanggil", "berdering", "sedang",
                "calling", "ringing", "connected"
            ]

            for node in root.iter("node"):
                txt = node.attrib.get("text", "").lower()
                if any(k in txt for k in fallback_keywords):
                    return txt

            # 4️⃣ Default
            return "in_call"

        except Exception as e:
            print("get_call_status error:", e)
            return "unknown"

    def _wake_call_ui(self):
        self.adb.shell("input keyevent 24")  # VOLUME_UP
        time.sleep(0.2)

    def _tap_button(self, button_id: str, desc_keywords=None):
        try:
            # 🔥 WAJIB: bangunkan UI call (tap area kosong)
            #self.adb.shell("input tap 360 720")  # tengah layar (720x1440)
            #time.sleep(0.6)

            # Dump UI setelah UI muncul
            self.adb.shell("uiautomator dump /sdcard/window_dump.xml")
            time.sleep(0.4)

            xml = self.adb.shell("cat /sdcard/window_dump.xml")
            if "<?xml" not in xml:
                print("UI dump invalid")
                return False

            root = ET.fromstring(xml[xml.index("<?xml"):])

            for node in root.iter("node"):
                res_id = node.attrib.get("resource-id", "")
                desc = node.attrib.get("content-desc", "").lower()
                clickable = node.attrib.get("clickable") == "true"
                enabled = node.attrib.get("enabled") == "true"

                match = False

                if button_id and button_id in res_id:
                    match = True

                if desc_keywords and any(k.lower() in desc for k in desc_keywords):
                    match = True

                if not match or not enabled:
                    continue

                bounds = node.attrib.get("bounds")
                if not bounds:
                    continue

                nums = re.findall(r"\d+", bounds)
                if len(nums) != 4:
                    continue

                x1, y1, x2, y2 = map(int, nums)
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                print(f"Tap {res_id or desc} at {cx},{cy}")
                self.adb.shell(f"input tap {cx} {cy}")
                time.sleep(0.7)
                return True

            print("Button not found:", button_id)
            return False

        except Exception as e:
            print("_tap_button error:", e)
            return False

    def end_call(self) -> bool:
        try:
            status = (self.get_call_status() or "").lower()
            print("Call status:", status)

            valid_states = [
                "calling", "ringing", "connected", "in_call",
                "berdering", "memanggil", "sedang", "tidak dijawab"
            ]

            if not any(s in status for s in valid_states):
                print("Not in call UI")
                return False

            tapped = self._tap_button(
                "end_call_button",
                desc_keywords=["keluar", "panggilan", "end"]
            )

            if not tapped:
                print("Failed tap end call")
                return False

            time.sleep(1.2)
            new_status = (self.get_call_status() or "").lower()

            print("New status:", new_status)
            return new_status in ["idle", "ended", ""]

        except Exception as e:
            print("end_call error:", e)
            return False

    def toggle_mute(self):
        return self._tap_button("mute_button")

    def toggle_speaker(self):
        return self._tap_button("audio_route_button")

    def toggle_camera(self):
        return self._tap_button("camera_button")
    
    def toggle_entry(self):
        return self._tap_button("entry")

    def send_message(self) -> bool:
        return self.tap_image_button_by_label("kirim")

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
        
    def handle_not_registered_popup(self) -> bool:
        """
        Deteksi popup nomor tidak terdaftar
        Return True jika popup muncul & ditutup
        """
        try:
            # Dump UI
            self.adb.shell("uiautomator dump /sdcard/window_dump.xml")
            time.sleep(0.4)

            xml = self.adb.shell("cat /sdcard/window_dump.xml")
            if "<?xml" not in xml:
                return False

            root = ET.fromstring(xml[xml.index("<?xml"):])

            keywords = [
                "tidak terdaftar",
                "tidak menggunakan whatsapp",
                "isn't on whatsapp",
                "not on whatsapp"
            ]

            popup_found = False

            for node in root.iter("node"):
                text = (node.attrib.get("text") or "").lower()
                desc = (node.attrib.get("content-desc") or "").lower()

                if any(k in text or k in desc for k in keywords):
                    popup_found = True
                    break

            if not popup_found:
                return False

            # Klik tombol OK / Tutup
            for node in root.iter("node"):
                res_id = node.attrib.get("resource-id", "")
                text = (node.attrib.get("text") or "").lower()
                clickable = node.attrib.get("clickable") == "true"

                if not clickable:
                    continue

                if (
                    res_id == "android:id/button2"
                    or text in ["ok", "tutup", "close", "batal"]
                ):
                    bounds = node.attrib.get("bounds")
                    if bounds:
                        x1, y1, x2, y2 = map(int, re.findall(r"\d+", bounds))
                        cx, cy = (x1 + x2)//2, (y1 + y2)//2
                        self.adb.shell(f"input tap {cx} {cy}")
                        time.sleep(0.5)
                        print("Popup noreg ditutup")
                        return True

            return True

        except Exception as e:
            print("handle_not_registered_popup error:", e)
            return False
       
    def _klik_touch(self, key, pkg):
        
        # cari tombol berdasarkan resource-id yang mengandung key
        xml = self.dump_ui()
        try:
            root = ET.fromstring(xml[xml.index("<?xml"):])
            for node in root.iter("node"):
                rid = node.attrib.get("resource-id") or ""
                if key in rid:
                    bounds = node.attrib.get("bounds")
                    if bounds:
                        x1,y1,x2,y2 = map(int, re.findall(r"\d+", bounds))
                        cx,cy = (x1+x2)//2, (y1+y2)//2
                        self.adb.shell(f"input tap {cx} {cy}")
                        return True
        except:
            pass
        return False
    
    def get_durasi(self) -> str:
        """
        Ambil durasi call WhatsApp dari subtitle
        Return: "00:12", "01:05", "" jika belum connected
        """
        try:
            # UI refresh via dump (BUKAN tap)
            self.adb.shell("uiautomator dump /sdcard/window_dump.xml")
            time.sleep(0.3)

            xml = self.adb.shell("cat /sdcard/window_dump.xml")
            if "<?xml" not in xml:
                return ""

            root = ET.fromstring(xml[xml.index("<?xml"):])

            # 1️⃣ Pastikan benar di UI call
            in_call_ui = False
            for node in root.iter("node"):
                if node.attrib.get("resource-id", "").endswith(":id/call_screen_root"):
                    in_call_ui = True
                    break

            if not in_call_ui:
                return ""

            # Regex durasi
            time_patterns = [
                re.compile(r"^\d{1,2}:\d{2}$"),
                re.compile(r"^\d{1,2}:\d{2}:\d{2}$")
            ]

            # 2️⃣ Ambil subtitle (status / durasi)
            for node in root.iter("node"):
                if node.attrib.get("resource-id", "").endswith(":id/subtitle"):
                    txt = node.attrib.get("text", "").strip()
                    if any(p.match(txt) for p in time_patterns):
                        return txt
                    else:
                        # subtitle ada tapi belum durasi (Memanggil, Berdering, dll)
                        return ""

            # 3️⃣ Fallback (jarang dipakai)
            for node in root.iter("node"):
                txt = node.attrib.get("text", "").strip()
                if any(p.match(txt) for p in time_patterns):
                    return txt

            return ""

        except Exception as e:
            print("get_durasi error:", e)
            return ""

    def type_text_like_human(self, txtpes: str):
        try:
            time.sleep(0.8)  # delay awal sebelum mengetik

            for ch in txtpes:
                if ch == " ":
                    # spasi
                    self.adb.shell("input keyevent 62")  # KEYCODE_SPACE

                elif ch in ("\n", "\r"):
                    # enter / newline
                    self.adb.shell("input keyevent 66")  # KEYCODE_ENTER

                else:
                    # character biasa
                    key = self._escape_adb_text(ch)
                    self.adb.shell(f"input text {key}")

                # delay seperti manusia: 80–160ms
                time.sleep(self._random_delay(0.08, 0.16))

        except Exception as e:
            print("type_text_like_human error:", e)

    def _escape_adb_text(self, ch: str) -> str:
        # sama seperti VB → handle karakter spesial agar aman di shell
        if ch == "'":
            return "\\'"
        elif ch in "&|><();!#$`\\\"":
            return "\\" + ch
        else:
            return ch

    def _random_delay(self, min_s: float, max_s: float) -> float:
        return random.uniform(min_s, max_s)

    def dump_ui(self, path="/sdcard/wa_dump.xml"):
        try:
            self.adb.shell(f"uiautomator dump {path}")
            out, _ = subprocess.Popen(["adb","shell",f"cat {path}"], stdout=subprocess.PIPE).communicate()
            return out.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def tap_image_button_by_label(self, target_label: str) -> bool:
        """
        Tap ImageButton berdasarkan label (content-desc / resource-id / text)
        Contoh label: 'Kirim', 'Send', 'End', 'Mute'
        """
        try:
            # 1️⃣ Dump UI hierarchy
            self.adb.shell("uiautomator dump /sdcard/window_dump.xml")
            time.sleep(0.4)

            xml = self.adb.shell("cat /sdcard/window_dump.xml")
            if "<?xml" not in xml:
                return False

            root = ET.fromstring(xml[xml.index("<?xml"):])

            normalized_target = target_label.strip().lower()

            # 2️⃣ Loop semua node ImageButton
            for node in root.iter("node"):
                cls = node.attrib.get("class", "")
                if cls.lower() != "android.widget.imagebutton":
                    continue

                desc = (node.attrib.get("content-desc") or "").strip().lower()
                res_id = (node.attrib.get("resource-id") or "").strip().lower()
                txt = (node.attrib.get("text") or "").strip().lower()

                # 3️⃣ Matching seperti VB.NET
                match = (
                    (desc and normalized_target in desc) or
                    (res_id and normalized_target in res_id) or
                    (txt and normalized_target in txt)
                )

                if not match:
                    continue

                bounds = node.attrib.get("bounds")
                if not bounds:
                    continue

                nums = re.findall(r"\d+", bounds)
                if len(nums) != 4:
                    continue

                x1, y1, x2, y2 = map(int, nums)
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                # 4️⃣ Tap tombol
                self.adb.shell(f"input tap {cx} {cy}")
                time.sleep(0.5)
                return True

        except Exception as e:
            print("tap_image_button_by_label error:", e)

        return False
    
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

    def handle_call_popup(self, timeout=3.0) -> bool:
        """
        Handle popup konfirmasi 'Telepon' setelah klik voice call
        Return True jika popup diklik, False jika tidak muncul
        """
        end_time = time.time() + timeout

        while time.time() < end_time:
            try:
                self.adb.shell("uiautomator dump /sdcard/window_dump.xml")
                time.sleep(0.3)

                xml = self.adb.shell("cat /sdcard/window_dump.xml")
                if "<?xml" not in xml:
                    continue

                root = ET.fromstring(xml[xml.index("<?xml"):])

                for node in root.iter("node"):
                    text = node.attrib.get("text", "").strip().lower()
                    res_id = node.attrib.get("resource-id", "")
                    clickable = node.attrib.get("clickable") == "true"
                    enabled = node.attrib.get("enabled") == "true"

                    # Match tombol Telepon
                    if (
                        clickable and enabled and
                        (
                            res_id == "android:id/button1" or
                            text == "Telepon"
                        )
                    ):
                        bounds = node.attrib.get("bounds")
                        if not bounds:
                            continue

                        nums = re.findall(r"\d+", bounds)
                        if len(nums) == 4:
                            x1, y1, x2, y2 = map(int, nums)
                            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                            print("Popup Telepon detected → tap")
                            self.adb.shell(f"input tap {cx} {cy}")
                            time.sleep(0.5)
                            return True

            except Exception as e:
                print("handle_call_popup error:", e)

            time.sleep(0.3)

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
