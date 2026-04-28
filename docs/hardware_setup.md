# Hardware Setup Guide — Raspberry Pi 4

This guide walks through setting up the Raspberry Pi 4 from a fresh OS installation to a fully running Smart Classroom backend.

---

## Step 1 — OS Installation

1. Download **Raspberry Pi Imager** from https://www.raspberrypi.com/software/
2. Insert a microSD card (16GB minimum, Class 10 recommended).
3. In the imager, choose:
   - **OS:** Raspberry Pi OS Lite (64-bit) — no desktop needed
   - **Storage:** your microSD card
4. Click the gear icon (⚙) to pre-configure:
   - Enable SSH
   - Set hostname: `smartclassroom.local`
   - Set username/password
   - Configure WiFi SSID and password
5. Write the image, insert the card into the Pi, and power on.
6. Connect via SSH: `ssh pi@smartclassroom.local`

---

## Step 2 — Enable Camera Interface

The Raspberry Pi Camera Module v2 uses the MIPI CSI-2 interface.

```bash
sudo raspi-config
# Navigate to: Interface Options → Camera → Enable
# Reboot when prompted
sudo reboot
```

Verify camera is detected after reboot:
```bash
vcgencmd get_camera
# Expected output: supported=1 detected=1
```

---

## Step 3 — Install Python 3.11

Raspberry Pi OS Lite (Bookworm) ships with Python 3.11. Verify:

```bash
python3 --version
# Python 3.11.x
```

If not available (Bullseye), install from deadsnakes PPA:

```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

Install pip:
```bash
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11
```

---

## Step 4 — Install System Dependencies for face_recognition

The `face_recognition` library is built on `dlib`, which requires CMake and a C++ compiler. Building dlib from source on a Pi 4 takes ~20 minutes.

```bash
sudo apt update
sudo apt install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    python3-dev \
    libboost-all-dev \
    libssl-dev \
    libjpeg-dev \
    libpng-dev
```

Install OpenCV system dependencies:
```bash
sudo apt install -y \
    libgstreamer1.0-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libatlas-base-dev \
    gfortran
```

---

## Step 5 — Install Mosquitto MQTT Broker

```bash
sudo apt install -y mosquitto mosquitto-clients

# Enable and start as a system service
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Verify broker is running
mosquitto_pub -h localhost -t test -m "hello"
mosquitto_sub -h localhost -t test &
# Should print "hello"
```

Default configuration allows unauthenticated local connections. For classroom use this is acceptable. The config file is at `/etc/mosquitto/mosquitto.conf`.

---

## Step 6 — Install Docker and Docker Compose

Docker hosts PostgreSQL, Redis, and Moodle.

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose plugin
sudo apt install -y docker-compose-plugin
docker compose version
```

---

## Step 7 — Clone Repository and Install Python Requirements

```bash
cd ~
git clone <your-repo-url> smart-classroom
cd smart-classroom

# Create a virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies (dlib build takes ~20 min on first run)
pip install --upgrade pip
pip install -r backend/requirements.txt
```

---

## Step 8 — Configure Environment

```bash
cp .env.example .env
nano .env
```

Update these values at minimum:

```
DATABASE_URL=postgresql+asyncpg://smartcam:smartcam@localhost:5432/smartclassroom
REDIS_URL=redis://localhost:6379
MQTT_BROKER_HOST=localhost
MOODLE_URL=http://localhost:8080
MOODLE_TOKEN=<your-moodle-webservice-token>
SECRET_KEY=<generate-with: python3 -c "import secrets; print(secrets.token_hex(32))">
```

---

## Step 9 — Start Infrastructure Services

```bash
cd ~/smart-classroom
docker compose up -d postgres redis moodle
```

Wait for Moodle to finish initialising (~3 minutes on first start):
```bash
docker compose logs -f moodle
# Wait for: "Apache/2.4.x Server at localhost Port 80"
```

---

## Step 10 — Run Database Migrations

```bash
cd ~/smart-classroom/backend
source ../venv/bin/activate
alembic upgrade head
```

---

## Step 11 — Test Camera

Verify the camera opens correctly before starting the backend:

```bash
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Camera open:', cap.isOpened()); cap.release()"
# Expected: Camera open: True
```

If `False`, check:
- CSI cable is seated firmly in the camera port
- Camera was enabled in `raspi-config`
- `vcgencmd get_camera` shows `detected=1`

---

## Step 12 — Start the Backend

```bash
cd ~/smart-classroom/backend
source ../venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend auto-runs Alembic migrations on startup. Check the health endpoint:

```bash
curl http://localhost:8000/health
# {"status":"ok","redis":true,"db":true}
```

---

## Running as a System Service (Production)

Create `/etc/systemd/system/smartclassroom.service`:

```ini
[Unit]
Description=Smart Classroom Backend
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/smart-classroom/backend
Environment=PATH=/home/pi/smart-classroom/venv/bin:/usr/bin:/bin
ExecStart=/home/pi/smart-classroom/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable smartclassroom
sudo systemctl start smartclassroom
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `dlib` build fails | Missing cmake or build tools | Re-run Step 4 |
| Camera returns `False` | CSI not enabled or cable loose | Step 2 |
| Redis connection refused | Docker not running | `docker compose up -d redis` |
| Moodle sync fails | Wrong token or Moodle not ready | Check `MOODLE_TOKEN` in `.env` |
| MQTT messages not received | Mosquitto not started | `sudo systemctl start mosquitto` |
| `alembic upgrade` fails | DB not ready | Wait for Postgres to start: `docker compose logs postgres` |
