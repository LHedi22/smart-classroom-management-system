# ESP32 Classroom Node Firmware

## What it does

- Reads temperature/humidity (DHT21), air quality (MQ-135 ADC), and sound (ACP014 digital)
- Publishes sensor data to the MQTT broker every 5 seconds
- Sends a heartbeat every 30 seconds
- Subscribes to relay topics and controls AC + lighting via GPIO relays
- Displays room status on a 16×2 I2C LCD

---

## Prerequisites

### 1. Install Arduino IDE

Download from [arduino.cc](https://www.arduino.cc/en/software) (version 2.x recommended).

### 2. Add ESP32 board support

1. Open **File → Preferences**
2. In *Additional boards manager URLs* paste:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Open **Tools → Board → Boards Manager**
4. Search for `esp32` and install **esp32 by Espressif Systems** (v2.x)

### 3. Install required libraries

Open **Sketch → Include Library → Manage Libraries** and install:

| Library | Author | Version |
|---|---|---|
| **PubSubClient** | Nick O'Leary | ≥ 2.8 |
| **DHT sensor library** | Adafruit | ≥ 1.4 |
| **Adafruit Unified Sensor** | Adafruit | ≥ 1.1 |
| **LiquidCrystal_I2C** | Frank de Brabander | ≥ 1.1 |
| **ArduinoJson** | Benoit Blanchon | 6.x (NOT 7.x) |

> `WiFi.h` is included with the ESP32 board package — no separate install needed.

---

## Configure before flashing

Edit `config.h` and set your values:

```cpp
#define WIFI_SSID     "your_network_name"
#define WIFI_PASSWORD "your_network_password"
#define MQTT_HOST     "192.168.x.x"   // IP address of your Raspberry Pi
```

Everything else (pins, room ID, thresholds) can stay as-is for the default hardware layout.

> **LCD I2C address:** The default is `0x27`. If your LCD doesn't light up, try `0x3F` in `config.h`.

---

## Board and upload settings

1. Connect the ESP32 via USB
2. Select board: **Tools → Board → esp32 → ESP32 Dev Module**
3. Set upload speed: **Tools → Upload Speed → 115200**
4. Select the correct port: **Tools → Port → COMx** (Windows) or `/dev/ttyUSB0` (Linux)
5. Click **Upload** (the arrow button)

> If upload fails with "connecting..." hold the **BOOT** button on the ESP32 during the first few seconds of upload, then release.

---

## Serial Monitor

After flashing, open **Tools → Serial Monitor** at **115200 baud**.

You should see:
```
[Boot] Smart Classroom Node
[WiFi] Connecting to your_ssid....
[WiFi] Connected, IP: 192.168.1.xxx
[MQTT] Connecting... connected.
[Boot] Ready
[Sensor] T:24.5°C H:61.2% AQ:318 Snd:0
[Heartbeat] sent
```

---

## MQTT topics published

| Topic | Payload example |
|---|---|
| `classroom/room1/sensors/temperature` | `{"value":24.5,"unit":"C","ts":12340}` |
| `classroom/room1/sensors/humidity` | `{"value":61.2,"unit":"%","ts":12340}` |
| `classroom/room1/sensors/air_quality` | `{"value":318,"unit":"ppm","ts":12340}` |
| `classroom/room1/sensors/sound` | `{"value":1,"unit":"bool","ts":12340}` |
| `classroom/room1/status` | `{"online":true,"ts":30000}` |

## MQTT topics subscribed

| Topic | Payload | Effect |
|---|---|---|
| `classroom/room1/relay/ac` | `{"action":"on"}` | AC relay HIGH |
| `classroom/room1/relay/ac` | `{"action":"off"}` | AC relay LOW |
| `classroom/room1/relay/ac` | `{"action":"auto"}` | threshold-based auto-control |
| `classroom/room1/relay/lighting` | `{"action":"on/off/auto"}` | lighting relay |

---

## Wiring summary

| Component | ESP32 GPIO |
|---|---|
| DHT21 data | GPIO 4 |
| MQ-135 AOUT | GPIO 34 |
| Sound DOUT | GPIO 35 |
| AC relay signal | GPIO 26 |
| Lighting relay signal | GPIO 27 |
| LCD SDA | GPIO 21 (default I2C) |
| LCD SCL | GPIO 22 (default I2C) |
