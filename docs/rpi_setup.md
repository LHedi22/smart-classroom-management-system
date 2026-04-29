# Raspberry Pi Setup Runbook — Smart Classroom Management System

> Last updated: Phase 12. Tested on Raspberry Pi 4 Model B 4GB, Raspberry Pi OS Bookworm 64-bit.

---

## 1. OS Setup

**Flash Raspberry Pi OS Lite 64-bit (Bookworm) with Raspberry Pi Imager.**

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Choose **Raspberry Pi OS Lite (64-bit)** as the OS.
3. Before flashing, click the gear icon (⚙) and configure:
   - Hostname: `smartclassroom.local`
   - Enable SSH (use password or public key authentication)
   - Set your Wi-Fi SSID and password (ESP32 must be on the same network)
4. Flash to your microSD card.

**First boot:**

```bash
ssh pi@smartclassroom.local

sudo apt update && sudo apt upgrade -y
```

**Enable the camera interface:**

```bash
sudo raspi-config
# Navigate to: Interface Options → Camera → Enable
# Reboot when prompted
sudo reboot
```

---

## 2. Install Docker & Docker Compose

Use the official convenience script — this installs both Docker Engine and Docker Compose v2:

```bash
curl -fsSL https://get.docker.com | sh
```

Add your user to the `docker` group so you can run Docker without `sudo`:

```bash
sudo usermod -aG docker $USER
# Log out and back in for the group change to take effect
exit
# Re-SSH into the Pi
ssh pi@smartclassroom.local
```

Verify the installation:

```bash
docker --version
docker compose version
```

Expected output (versions may differ):

```
Docker version 24.x.x, build ...
Docker Compose version v2.x.x
```

---

## 3. Clone the Repository and Configure the Environment

```bash
git clone <repo-url> smart-classroom
cd smart-classroom
cp .env.example .env
nano .env
```

**Variables that must be changed for Pi deployment:**

| Variable | Value for Pi | Note |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://smartcam:smartcam@postgres:5432/smartclassroom` | Use Docker service name `postgres`, not `localhost` |
| `REDIS_URL` | `redis://redis:6379` | Use Docker service name `redis`, not `localhost` |
| `MQTT_BROKER_HOST` | `mosquitto` | Use Docker service name `mosquitto`, not `localhost` |
| `MQTT_BROKER_PORT` | `1883` | No change needed |
| `ROOM_ID` | `room1` | Must match `config.h` in the ESP32 firmware |
| `MOCK_MODE` | `false` (real hardware) or `true` (testing without ESP32) | |
| `SECRET_KEY` | Change from `changeme` to a random string | |

Example complete `.env` for Pi with real hardware:

```env
DATABASE_URL=postgresql+asyncpg://smartcam:smartcam@postgres:5432/smartclassroom
REDIS_URL=redis://redis:6379
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883
MOODLE_URL=http://localhost:8080
MOODLE_TOKEN=your_moodle_token_here
SECRET_KEY=replace-with-a-random-secret
ROOM_ID=room1
MOCK_MODE=false
TEMP_AC_ON_THRESHOLD=28
TEMP_AC_OFF_THRESHOLD=22
AIR_QUALITY_ALERT_THRESHOLD=500
FACE_RECOGNITION_THRESHOLD=0.6
RECOGNITION_FPS=2
```

---

## 4. Start the Stack

```bash
docker compose up -d
```

This pulls images and starts all services: `postgres`, `redis`, `mosquitto`, `backend`, and `frontend`.

**Follow logs in real time:**

```bash
docker compose logs -f backend
```

**Check that all containers are healthy:**

```bash
docker compose ps
```

All containers should show `running` or `healthy` status. The backend container runs Alembic migrations automatically on startup — wait ~30 seconds for it to reach `healthy`.

**Access the dashboard:**

Open a browser and navigate to `http://<pi-ip>:3000`

Find the Pi's IP address with:

```bash
hostname -I
```

---

## 5. Verify Mosquitto is Reachable

Install the Mosquitto CLI client tools on the Pi:

```bash
sudo apt install -y mosquitto-clients
```

**Test publish (Terminal 1):**

```bash
mosquitto_pub -h localhost -p 1883 -t "test/hello" -m "world"
```

**Test subscribe (Terminal 2 — run this first, then run the publish above):**

```bash
mosquitto_sub -h localhost -p 1883 -t "test/hello"
```

You should see `world` printed in Terminal 2 within a second of the publish. If nothing appears, see the Troubleshooting table below.

---

## 6. Flash the ESP32

**Prerequisites (on a laptop, not the Pi):**

- [Arduino IDE 2.x](https://www.arduino.cc/en/software)
- ESP32 board support — add this URL in Arduino IDE Preferences → Additional Boards Manager URLs:
  ```
  https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
  ```
  Then install **esp32 by Espressif Systems** via Tools → Board → Boards Manager.
- Required libraries (install via Sketch → Include Library → Manage Libraries):
  - `PubSubClient` by Nick O'Leary
  - `DHT sensor library` by Adafruit
  - `LiquidCrystal_I2C` by Frank de Brabander

**Configure the firmware:**

Open `firmware/classroom_node/config.h` and set these values:

```c
// Wi-Fi — must be the same network the Pi is on
#define WIFI_SSID     "YourNetworkName"
#define WIFI_PASSWORD "YourNetworkPassword"

// MQTT — use the Pi's local IP address (find with: hostname -I on the Pi)
#define MQTT_SERVER   "192.168.x.x"
#define MQTT_PORT     1883

// Room ID — must match ROOM_ID in .env
#define ROOM_ID       "room1"
```

**Upload:**

1. Connect the ESP32 to your laptop via USB.
2. In Arduino IDE: Tools → Board → ESP32 Dev Module
3. Tools → Port → select the correct COM port (e.g., `COM3` on Windows, `/dev/ttyUSB0` on Linux/Mac)
4. Click Upload (→).
5. Open Serial Monitor (Tools → Serial Monitor) at **115200 baud**.

Within 10 seconds you should see:

```
Connecting to WiFi...
WiFi connected. IP: 192.168.x.x
Connecting to MQTT...
MQTT connected.
Publishing sensor data...
```

---

## 7. Verify End-to-End Data Flow

**Step 1 — Watch raw MQTT messages on the Pi:**

```bash
mosquitto_sub -h localhost -p 1883 -t "classroom/room1/sensors/#" -v
```

You should see JSON payloads every 5 seconds, e.g.:

```
classroom/room1/sensors/temperature {"value": 24.5, "unit": "C", "ts": 1712345678}
classroom/room1/sensors/humidity {"value": 62.1, "unit": "%", "ts": 1712345678}
```

**Step 2 — Confirm the backend is ingesting:**

```bash
docker compose logs --tail=20 backend
```

Look for lines like:

```
INFO app.services.mqtt_bridge: [MQTT] sensor received: room1 temperature 24.5
```

**Step 3 — Confirm Redis has the latest values:**

```bash
docker exec $(docker compose ps -q redis) redis-cli GET "room1:temperature"
```

Should return a JSON string with `value` and `unit`.

**Step 4 — Open the dashboard:**

Navigate to `http://<pi-ip>:3000` in a browser. The sensor cards should show live values. If the demo mode banner appears (amber warning), the backend is not yet receiving MQTT data — re-check Steps 1–3.

---

## 8. Enabling Face Recognition (Raspberry Pi only)

Face recognition does not run inside the Docker backend image. Install DeepFace
directly into the Pi's Python environment:

```bash
pip install deepface==0.0.93 tf-keras==2.16.0 opencv-python-headless==4.9.0.80
```

Then set the flag in your `.env`:

```env
FACE_RECOGNITION_ENABLED=true
```

Restart the backend container to pick up the new setting:

```bash
docker compose restart backend
```

The backend detects `FACE_RECOGNITION_ENABLED=true` at startup and loads
DeepFace from the Pi's native Python installation. The first start after
enabling this will download the Facenet model weights (~90 MB) to
`~/.deepface/` — subsequent restarts are instant.

> **Without this flag** (the default), the backend runs a lightweight stub:
> enrollment stores a zeroed placeholder vector, and the recognition loop
> emits a synthetic attendance event every 45 seconds for a randomly chosen
> enrolled student. This keeps the dashboard live without any camera hardware.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| ESP32 Serial shows `MQTT connect failed` | Wrong `MQTT_SERVER` IP or firewall blocking port 1883 | Verify the Pi's IP with `hostname -I`; ensure the ESP32 and Pi are on the same Wi-Fi subnet; check that port 1883 is not blocked by a firewall on the Pi |
| `mosquitto_sub` receives nothing after publish | Mosquitto not configured for anonymous connections | Check `mosquitto/mosquitto.conf` contains `allow_anonymous true` and `listener 1883`; restart with `docker compose restart mosquitto` |
| Dashboard shows amber "Demo Mode" banner | Backend not receiving MQTT messages | Repeat Steps 5–7; alternatively set `MOCK_MODE=true` in `.env` and `docker compose up -d` for a hardware-free demo |
| Backend container keeps restarting | Wrong `DATABASE_URL` / `REDIS_URL`, or DB not ready | Check `docker compose logs backend` for the error; most common cause is using `localhost` instead of the Docker service name (`postgres`, `redis`); the backend retries automatically but check for typos |
| DeepFace download hangs on first start | TensorFlow model weights (~90 MB) downloading | This is normal on first run — wait 2–3 minutes. Subsequent starts are instant because weights are cached in the container. Mount a named volume at `~/.deepface` to persist across container rebuilds |
| `docker compose ps` shows containers as `Exited` | Port conflict or missing `.env` | Run `docker compose logs <service>` for the specific container; ensure `.env` exists and `MOCK_MODE` is set |
