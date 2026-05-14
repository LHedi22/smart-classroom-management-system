#pragma once

// ── WiFi ─────────────────────────────────────────────────────────────────
#define WIFI_SSID     "Ooredoo-327065-5G"
#define WIFI_PASSWORD "BFB68D59Er@07"

// ─── LAPTOP MODE ──────────────────────────────────────────────────────────────
// To run the system from a laptop instead of the Raspberry Pi:
//   1. Find your laptop's local IP:  (macOS) ifconfig | grep "inet "
//                                    (Linux)  ip addr show
//                                    (Windows) ipconfig
//   2. Change MQTT_HOST below to that IP address.
//   3. Re-flash this firmware to the ESP32.
//   4. Make sure your laptop's firewall allows inbound TCP on port 1883.
// ─────────────────────────────────────────────────────────────────────────────
#define MQTT_HOST "192.168.0.168"
#define MQTT_PORT 1883
#define MQTT_CLIENT_ID "esp32-room1"

// ── Room identifier ───────────────────────────────────────────────────────
#define ROOM_ID "room1"

// ── Sensor pins ───────────────────────────────────────────────────────────
#define DHT_PIN   4   // DHT21 (AM2301) data pin
#define MQ135_PIN 34  // MQ-135 analog output (ADC1_CH6, input-only)
#define SOUND_PIN 35  // ACP014 digital output (ADC1_CH7, input-only)

// ── Relay pins ────────────────────────────────────────────────────────────
#define RELAY_AC_PIN      26  // Channel 1 — AC unit
#define RELAY_LIGHT_PIN   27  // Channel 2 — Lighting

// ── LCD ───────────────────────────────────────────────────────────────────
#define LCD_ADDR    0x27  // I2C address (try 0x3F if 0x27 doesn't work)
#define LCD_COLS    16
#define LCD_ROWS    2

// ── Auto-control thresholds ───────────────────────────────────────────────
#define TEMP_AC_ON_THRESHOLD  28.0f  // °C — turn AC on when above this
#define TEMP_AC_OFF_THRESHOLD 22.0f  // °C — turn AC off when below this

// ── Timing ────────────────────────────────────────────────────────────────
#define SENSOR_INTERVAL_MS    5000UL   // 5 s sensor publish interval
#define HEARTBEAT_INTERVAL_MS 30000UL  // 30 s heartbeat interval
#define WIFI_RETRY_MS         5000UL   // 5 s between WiFi retries
