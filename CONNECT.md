# Connect hardware → MHARS

Your rover sends sensor JSON to the PC. The dashboard shows it live.

```
[ Sensors on rover ] → [ ESP32 / Pi ] --WiFi or USB--> [ backend :8000 ] → [ dashboard ]
```

---

## 1. Same Wi‑Fi

1. Start the backend on your laptop (`cd backend` → `uvicorn main:app --host 0.0.0.0 --port 8000`)
2. Find laptop IP (PowerShell): `ipconfig` → look for `IPv4` (e.g. `192.168.1.10`)
3. Rover and laptop must be on the **same Wi‑Fi**

---

## 2. Pick one connection method

### A) Wi‑Fi HTTP (easiest)

Rover POSTs JSON every ~0.4s:

```
POST http://YOUR_PC_IP:8000/api/telemetry
Content-Type: application/json
```

Example sketch: `firmware/rover_telemetry.ino`  
Edit `WIFI_SSID`, `WIFI_PASS`, and `SERVER_URL`.

### B) Wi‑Fi WebSocket

```
ws://YOUR_PC_IP:8000/ws/rover
```

Send the same JSON as text. PC replies with drive commands:

```json
{"type":"control","command":"forward","speed":0.5}
```

`command` = `forward` | `backward` | `left` | `right` | `stop` | `auto`

### C) USB cable

1. Flash sketch that prints **one JSON line per sample** on Serial @ **115200**
2. Check COM port in Device Manager (e.g. `COM3`)
3. Start server:

```bash
cd backend
.\.venv\Scripts\activate
$env:MHARS_MODE="hardware"
$env:MHARS_SERIAL="COM3"
uvicorn main:app --host 0.0.0.0 --port 8000
```

List ports: open http://127.0.0.1:8000/api/serial/ports

---

## 3. JSON your MCU must send

One object = one sample. Field names must match.

```json
{
  "type": "telemetry",
  "ts": 1710000000.0,
  "position": { "x": 1.2, "y": 0.5, "heading_deg": 90, "relative_label": "Gallery-1" },
  "gas": { "co_ppm": 12, "ch4_ppm": 150, "co2_ppm": 700, "h2s_ppm": 0.2 },
  "environment": { "temperature_c": 29.5, "humidity_pct": 60 },
  "proximity": { "front_cm": 80, "left_cm": 100, "right_cm": 95 },
  "acoustic": { "level_db": 45, "event": null, "confidence": 0 },
  "thermal": { "max_c": 32, "avg_c": 30, "min_c": 28, "anomaly": false },
  "visual_available": false,
  "status": { "battery_pct": 88, "mode": "auto", "speed_mps": 0.3, "connected": true }
}
```

| Form-2 module | JSON field | Typical sensor |
|---------------|------------|----------------|
| 121 Gas | `gas` | MQ-7 CO, MQ-4 CH₄, MQ-135 CO₂ |
| 122 Temp/RH | `environment` | DHT22 / BME280 |
| 123 Camera | `visual_available` | ESP32-CAM (optional later) |
| 124 Thermal | `thermal` | MLX90640 / AMG8833 |
| 125 Mic | `acoustic` | MAX9814 / INMP441 |
| 126 Distance | `proximity` | HC-SR04 / VL53L0X |

You don’t need every sensor on day one. Missing fields use safe defaults. Start with **gas + DHT + ultrasonic**, then add the rest.

---

## 4. Checklist

- [ ] Backend running on port **8000**
- [ ] Dashboard open → status pill says **Link live**
- [ ] Rover on same Wi‑Fi (or USB plugged in)
- [ ] `SERVER_URL` / `MHARS_SERIAL` set to your PC
- [ ] JSON posts succeed → UI source changes to **WIFI** or **SERIAL**
- [ ] Demo scenarios still work in sim until hardware is online

---

## 5. Quick test without rover

```bash
curl -X POST http://127.0.0.1:8000/api/telemetry -H "Content-Type: application/json" -d "{\"type\":\"telemetry\",\"ts\":1,\"gas\":{\"co_ppm\":120},\"environment\":{\"temperature_c\":30,\"humidity_pct\":50},\"proximity\":{\"front_cm\":100,\"left_cm\":100,\"right_cm\":100},\"acoustic\":{\"level_db\":40},\"thermal\":{\"max_c\":32,\"avg_c\":30,\"min_c\":28,\"anomaly\":false},\"status\":{\"battery_pct\":90,\"mode\":\"auto\",\"speed_mps\":0,\"connected\":true}}"
```

Dashboard should show a CO hazard.
