import subprocess
import threading
import base64
import json
import time

class CallAudioForwarder:
    def __init__(self, adb, ws_client, rate=16000, channels=1, use_root=False):
        self.adb = adb
        self.ws = ws_client
        self.rate = rate
        self.channels = channels
        self.use_root = use_root
        self.proc = None
        self.thread = None
        self.running = False
        self._stop_event = threading.Event()

    def start(self):
        if self.running:
            return
        try:
            if self.use_root:
                cmd = [
                    "adb","shell","su","-c",
                    f"tinycap /dev/stdout -r {self.rate} -b 16 -c {self.channels}"
                ]
            else:
                # Use media record (may only work on newer Android)
                cmd = ["adb","shell","cmd","media","record","--audio-source=VOICE_CALL","--output-format=amr_nb","--output","/dev/stdout"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.running = True
            self._stop_event.clear()
            self.thread = threading.Thread(target=self._reader, daemon=True)
            self.thread.start()
        except Exception as e:
            print("CallAudioForwarder start error:", e)
            self.running = False

    def _reader(self):
        try:
            while self.running and self.proc and self.proc.stdout and not self._stop_event.is_set():
                chunk = self.proc.stdout.read(4096)
                if not chunk:
                    break
                payload = {
                    "type": "audio_chunk",
                    "format": "pcm16" if self.use_root else "amr_nb",
                    "rate": self.rate,
                    "channels": self.channels,
                    "data": base64.b64encode(chunk).decode('ascii')
                }
                try:
                    if self.ws and hasattr(self.ws, "send"):
                        try:
                            self.ws.send(json.dumps(payload))
                        except Exception:
                            # fallback: try sending dict (WS client wrapper may handle it)
                            try:
                                self.ws.send(payload)
                            except Exception:
                                pass
                except Exception as e:
                    print("Audio send error:", e)
                    break
        except Exception as e:
            print("Audio reader error:", e)
        finally:
            self.running = False

    def stop(self):
        if not self.running:
            return
        self.running = False
        self._stop_event.set()
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            finally:
                self.proc = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)

    def start_via_app(self, package_name="com.example.audiorecorder"):
        try:
            self.adb.shell(f"am start -n {package_name}/.AudioRecordService")
            time.sleep(1)
            cmd = ["adb","shell",f"cat /sdcard/{package_name}/audio_output.raw"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.running = True
            self._stop_event.clear()
            self.thread = threading.Thread(target=self._reader, daemon=True)
            self.thread.start()
            return True
        except Exception as e:
            print("start_via_app error:", e)
            return False
