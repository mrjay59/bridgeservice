# BridgeService AI Coding Instructions

## Project Overview
BridgeService is a Termux-based Android automation bridge that:
- Connects Android devices to a WebSocket command server (`wss://ws.autocall.my.id/ws`)
- Executes multi-platform commands: WhatsApp (voice/video calls, messages), cellular calls, SMS, USSD codes, ADB shell, and screenshots
- Manages device inventory (serial, IMEI, SIM info, IP discovery, network status)
- Runs as a persistent daemon with SMS polling and heartbeat mechanisms

## Architecture & Data Flows

### Core Components
1. **BridgeService main** (`bridgeservice.py`): Daemon orchestrator with WebSocket client, device info collector, command router
2. **WhatsAppAutomation** (`WhatsAppAutomation.py`, 1049 lines): UI automation for WhatsApp Web/Business (XML parsing, click detection, call/message workflows)
3. **UICallController** (`UICallController.py`): Native dialer call management via uiautomator XML dumps
4. **CallAudioForwarder** (`CallAudioForwarder.py`): Real-time call audio capture (PCM16 or AMR-NB) streamed base64-encoded over WebSocket
5. **Register** (`register.py`): Device self-registration with server (serial, SIM info, local IP, device profile)

### Command Flow (WebSocket → Execution)
```
WS Message (type: "command", fitur: "locAndro")
  → _on_message() → command_queue.put(job)
  → _command_worker() → _handle_locandro_item()
  → Route by platform (WAO/WAB/TLC/SMS/ADB/CMD/SS/USSD)
  → Process-specific handler (e.g., process_whatsapp, process_telepon_selular)
  → _send_ws_ack() with result + serial
```

### Device Identification
- **Serial**: Primary identifier sent in every WS message; extracted via `getprop ro.serialno` or `getprop ro.boot.serialno`
- **Command filtering**: `_handle_locandro_item()` checks `connection=="TERMUX"` and `serial==device` before executing
- **Dual SIM support**: Indices 0/1 for both IMEI/numbers; methods like `get_imei(adb, slot)` poll iphonesubinfo service

## Critical Patterns

### ADB Command Wrapper
```python
AdbWrapper: Dual-mode execution
  - If adbutils available: use adbutils.adb.device() (faster)
  - Fallback: subprocess.Popen("adb shell ...") (universal compatibility)
```
Always use `adb.shell(cmd)` not raw subprocess for consistency.

### Error Handling Philosophy
- **Graceful degradation**: Missing features (uiautomator2, adbutils) are optional; code continues with fallbacks
- **WS safety**: Check `self.ws_connected` before sending; wrap sends in try/except
- **Timeout patterns**: Use `time.sleep(seconds)` between UI checks; max 10 iterations for USSD menu loops
- **No exceptions crash daemon**: Caught in `_command_worker()`, logged, continue processing

### Threading Model
- **Main**: WSClient._run() (WebSocket listener)
- **SMS poller**: SMSHandler.poll_loop() (3-sec intervals, termux-sms-list)
- **Command worker**: Queue-based (jobs from WS messages)
- **Audio forwarder**: Subprocess reader thread (optional, root-dependent)
- **Heartbeat**: _heartbeat_loop() (1200 sec default, device online update)

### SMS/USSD Patterns
- **SMS forwarding**: Termux termux-sms-list → last_seen_ids (set, max 2000) prevents duplicates
- **USSD flow**: URL-encode code, launch via `am start -a android.intent.action.CALL`, poll uiautomator XML, parse menu by keyword regex, click by bounds
- **Phone number normalization**: Regex strip non-digits, prefix +62 if Indonesia, validate dual SIM slots

## Environment & Setup

### Key Environment Variables
- `BRIDGE_WS`: WebSocket URL (default: `wss://ws.autocall.my.id/ws`)
- `HEARTBEAT_INTERVAL`: Seconds between heartbeats (default: 1200 = 20 min)
- `USE_ROOT_AUDIO`: Enable root-based tinycap audio (default: false)

### Setup Workflow (Termux)
1. Run `bash setup_bridgeservice.sh` → installs python, pip, PIL, android-tools, termux-api
2. `pip install -r requirements.txt` → requests, websocket-client, pillow, aiohttp, websockets, psutil
3. `python register.py` → self-register device with API server
4. `python bridgeservice.py` → start daemon (daemonize via nohup or systemd wrapper if available)

### Debug/Logging
- Print-based logging with timestamps: `log_print(msg, level)` in code
- No external logging framework (keep minimal deps)
- stdout/stderr captured in setup logs (`$BRIDGE_HOME/logs/setup.log`)

## Integration Points & APIs

### External Services
- **Registry API**: `https://mrjay59.com/api/cpost/device/register` (POST device profile)
- **Device state API**: `https://mrjay59.com/api/cpost/device/state` (POST serial + "cekstate")
- **WebSocket server**: Commands + heartbeat/ack messages (custom JSON protocol)

### Device Capabilities Queried
- `getprop ro.product.{manufacturer,model,device}` → brand/model info
- `getprop ro.build.version.{release,sdk}` → Android version/SDK
- `dumpsys telephony.registry | grep mSignalStrength` → signal strength dBm
- `service call iphonesubinfo {1,7,11,13}` → IMEI, number, SIM state, ICCID (slot-aware)
- `ip route get 8.8.8.8 | grep src` → local IP discovery

## Developer Workflows

### Adding a New Command Handler
1. Add case in `_handle_locandro_item()` platform switch (e.g., `platform=="NEWCMD"`)
2. Create `process_newcmd(self, item)` method returning `{"ok": bool, "msg": str, ...}`
3. Ensure method extracts serial via `get_serial(self.adb)` and logs action
4. Return result shape: `{"ok": ..., "msg": ..., "device": ..., "platform": ...}`

### Testing Device Commands
- Use `bridgeservice.py` in foreground (console prints all WS/execution debug)
- Send WebSocket message with correct structure: `{"type":"command", "fitur":"locAndro", "from":"testuser", "data":[...]}`
- Verify serial matches device: `adb shell getprop ro.serialno`
- Check WS ack response for status/payload

### Common Troubleshooting
- **"WebSocket not connected"**: Check internet, verify BRIDGE_WS URL, ensure WS_SERVER is reachable
- **"Call doesn't connect"**: UICallController.wait_until_connected() timeout → device may require screen unlock or settings changes
- **"WhatsApp not logged in"**: ensure_logged_in() checks for specific UI elements; manual login may be required after reinstall
- **Audio not forwarding**: USE_ROOT_AUDIO requires root + tinycap binary; fallback uses media record (Android 10+ unpredictable)

## File Structure Notes
- **Single-file architecture for core modules**: Each component (WhatsApp, Call, Audio, Register) is self-contained, no subdirectories
- **Device queries centralised**: All getprop/dumpsys helpers in bridgeservice.py top-section (reused by register.py import)
- **Shell scripts for bootstrap**: setup_bridgeservice.sh handles Termux package install + Python env prep
- **No config files**: All settings via environment variables or hardcoded reasonable defaults

---
**Last Updated**: 2026-04-01 | **Status**: Production Daemon | **Platform**: Termux (Android)
