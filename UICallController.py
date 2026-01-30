import time
import re
import xml.etree.ElementTree as ET
  

class UICallController:
    def __init__(self, adb):
        self.adb = adb
        self.dump_path = "/sdcard/uicall.xml"
  
    # ==================================================
    # INTERNAL HELPERS
    # ==================================================
    def _dump_ui(self):
        self.adb.shell(f"uiautomator dump {self.dump_path}")
        time.sleep(0.25)
        xml = self.adb.shell(f"cat {self.dump_path}")
        if "<?xml" not in xml:
            return ""
        return xml[xml.index("<?xml"):]

    def _tap_bounds(self, bounds):
        nums = list(map(int, re.findall(r"\d+", bounds)))
        if len(nums) != 4:
            return False
        x1, y1, x2, y2 = nums
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        self.adb.shell(f"input tap {cx} {cy}")
        return True

    def _find_node(self, *, res_id=None, text=None, class_name=None):
        xml = self._dump_ui()
        if not xml:
            return None

        root = ET.fromstring(xml)

        for node in root.iter("node"):
            if res_id and node.attrib.get("resource-id") != res_id:
                continue
            if text and node.attrib.get("text", "").lower() != text.lower():
                continue
            if class_name and node.attrib.get("class") != class_name:
                continue
            return node

        return None

    # ==================================================
    # PUBLIC API
    # ==================================================

    # 1️⃣ END CALL
    def end_call(self) -> bool:
        """
        End call (primary + fallback uiautomator)
        """
        if self.end_call_uiautomator():
            return True
        return False
    
    def end_call_uiautomator(self) -> bool:
        """
        End call berbasis uiautomator (robust, multi fallback)
        """
        xml = self._dump_ui()
        if not xml:
            return False

        root = ET.fromstring(xml)

        # 1️⃣ Strategy utama: resource-id resmi dialer
        for node in root.iter("node"):
            if node.attrib.get("resource-id") == "com.android.dialer:id/incall_end_call":
                return self._tap_bounds(node.attrib.get("bounds", ""))

        # 2️⃣ Strategy kedua: content-desc (End / Hang up)
        for node in root.iter("node"):
            desc = node.attrib.get("content-desc", "").lower()
            if any(k in desc for k in ["end", "hang", "tutup", "akhiri"]):
                bounds = node.attrib.get("bounds", "")
                if bounds:
                    return self._tap_bounds(bounds)

        # 3️⃣ Strategy ketiga: ImageButton (biasanya tombol merah)
        for node in root.iter("node"):
            if (
                node.attrib.get("class") == "android.widget.ImageButton"
                and node.attrib.get("clickable") == "true"
            ):
                bounds = node.attrib.get("bounds", "")
                if bounds:
                    return self._tap_bounds(bounds)

        # 4️⃣ Strategy terakhir: clickable node paling bawah layar
        candidates = []
        for node in root.iter("node"):
            if node.attrib.get("clickable") == "true":
                bounds = node.attrib.get("bounds", "")
                nums = re.findall(r"\d+", bounds)
                if len(nums) == 4:
                    x1, y1, x2, y2 = map(int, nums)
                    candidates.append((y2, bounds))

        if candidates:
            # pilih yang paling bawah (y terbesar)
            _, bounds = sorted(candidates, reverse=True)[0]
            return self._tap_bounds(bounds)

        return False


    # 2️⃣ NOMOR / NAMA TUJUAN
    def get_target(self) -> str:
        xml = self._dump_ui()
        if not xml:
            return ""

        root = ET.fromstring(xml)

        # 1️⃣ Resource-id AOSP
        for node in root.iter("node"):
            if node.attrib.get("resource-id") == "com.android.dialer:id/contactgrid_contact_name":
                return node.attrib.get("text", "").strip()

        # 2️⃣ Content-desc mengandung nomor / nama
        for node in root.iter("node"):
            desc = node.attrib.get("content-desc", "")
            if desc and any(c.isdigit() for c in desc):
                return desc.strip()

        # 3️⃣ Text berbentuk nomor telp / nama (heuristic)
        for node in root.iter("node"):
            txt = node.attrib.get("text", "").strip()
            if not txt:
                continue
            if txt.startswith("+") or txt.replace(" ", "").isdigit():
                return txt
            if len(txt) >= 3 and txt.isalpha():
                return txt

        return ""


    # 3️⃣ DURASI CALL
    def get_duration(self) -> str:
        xml = self._dump_ui()
        if not xml:
            return "00:00"

        root = ET.fromstring(xml)

        # 1️⃣ Resource-id AOSP
        for node in root.iter("node"):
            if node.attrib.get("resource-id") == "com.android.dialer:id/contactgrid_bottom_timer":
                txt = node.attrib.get("text", "").strip()
                if txt:
                    return txt

        # 2️⃣ Text format waktu (mm:ss / hh:mm:ss)
        for node in root.iter("node"):
            txt = node.attrib.get("text", "").strip()
            if re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", txt):
                return txt

        # 3️⃣ Content-desc format waktu
        for node in root.iter("node"):
            desc = node.attrib.get("content-desc", "")
            if re.match(r".*\d+:\d+.*", desc):
                return desc.strip()

        return "00:00"


    # 4️⃣ STATUS CALL
    def get_status(self) -> str:
        xml = self._dump_ui()
        if not xml:
            return "unknown"

        root = ET.fromstring(xml)

        STATUS_KEYWORDS = [
            "calling", "dialing", "ringing", "connected",
            "ongoing", "sedang", "berdering", "memanggil",
            "panggilan", "in call"
        ]

        # 1️⃣ Resource-id AOSP
        for node in root.iter("node"):
            if node.attrib.get("resource-id") == "com.android.dialer:id/contactgrid_status_text":
                txt = node.attrib.get("text", "").strip()
                if txt:
                    return txt

        # 2️⃣ Content-desc
        for node in root.iter("node"):
            desc = node.attrib.get("content-desc", "").lower()
            if any(k in desc for k in STATUS_KEYWORDS):
                return desc

        # 3️⃣ Text keyword
        for node in root.iter("node"):
            txt = node.attrib.get("text", "").lower().strip()
            if any(k in txt for k in STATUS_KEYWORDS):
                return txt

        # 4️⃣ Fallback heuristik: jika ada durasi berarti connected
        duration = self.get_duration()
        if duration != "00:00":
            return "connected"

        return "unknown"


    # 5️⃣ TOGGLE MUTE
    def toggle_mute(self) -> bool:
        node = self._find_node(
            text="Mute",
            class_name="android.widget.TextView"
        )
        if node is not None:
            return self._tap_bounds(node.attrib.get("bounds", ""))
        return False

    # ==================================================
    # HIGH LEVEL UTIL
    # ==================================================
    def is_in_call(self) -> bool:
        """
        Deteksi apakah sedang berada di layar panggilan
        """
        return self.get_status() != "unknown"

    def wait_until_connected(self, timeout=20) -> bool:
        """
        Tunggu sampai call benar-benar connected
        """
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status().lower()
            if any(k in status for k in ["connected", "sedang", "ongoing"]):
                return True
            time.sleep(1)
        return False
