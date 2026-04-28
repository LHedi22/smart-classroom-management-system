/*
 * Smart Classroom Node — ESP32 Firmware
 * SMU Mediterranean Institute of Technology
 *
 * Required libraries (install via Arduino IDE Library Manager):
 *   - PubSubClient       by Nick O'Leary   (MQTT client)
 *   - DHT sensor library by Adafruit       (DHT21/AM2301)
 *   - Adafruit Unified Sensor              (DHT dependency)
 *   - LiquidCrystal_I2C  by Frank de Brabander
 *   - ArduinoJson        by Benoit Blanchon (v6.x)
 *   - WiFi               (built-in ESP32 core)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>

#include "config.h"

// ── MQTT topic strings ────────────────────────────────────────────────────
#define TOPIC_TEMP       "classroom/" ROOM_ID "/sensors/temperature"
#define TOPIC_HUMIDITY   "classroom/" ROOM_ID "/sensors/humidity"
#define TOPIC_AIR        "classroom/" ROOM_ID "/sensors/air_quality"
#define TOPIC_SOUND      "classroom/" ROOM_ID "/sensors/sound"
#define TOPIC_STATUS     "classroom/" ROOM_ID "/status"
#define TOPIC_RELAY_AC   "classroom/" ROOM_ID "/relay/ac"
#define TOPIC_RELAY_LIGHT "classroom/" ROOM_ID "/relay/lighting"

// ── Global objects ────────────────────────────────────────────────────────
WiFiClient        espClient;
PubSubClient      mqtt(espClient);
DHT               dht(DHT_PIN, DHT21);
LiquidCrystal_I2C lcd(LCD_ADDR, LCD_COLS, LCD_ROWS);

// ── Relay auto-mode flags ─────────────────────────────────────────────────
bool acAutoMode    = false;
bool lightAutoMode = false;

// ── Timing state ──────────────────────────────────────────────────────────
unsigned long lastSensorPublish = 0;
unsigned long lastHeartbeat     = 0;

// ─────────────────────────────────────────────────────────────────────────
// WiFi
// ─────────────────────────────────────────────────────────────────────────
void connectWiFi() {
  Serial.print("[WiFi] Connecting to ");
  Serial.print(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(WIFI_RETRY_MS);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("[WiFi] Connected, IP: ");
  Serial.println(WiFi.localIP());
}

// ─────────────────────────────────────────────────────────────────────────
// MQTT callback — handles incoming relay commands
// ─────────────────────────────────────────────────────────────────────────
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Null-terminate the payload so we can treat it as a C-string
  char buf[length + 1];
  memcpy(buf, payload, length);
  buf[length] = '\0';

  Serial.print("[MQTT] Received on ");
  Serial.print(topic);
  Serial.print(": ");
  Serial.println(buf);

  StaticJsonDocument<128> doc;
  DeserializationError err = deserializeJson(doc, buf);
  if (err) {
    Serial.print("[MQTT] JSON parse error: ");
    Serial.println(err.c_str());
    return;
  }

  const char* action = doc["action"];
  if (!action) return;

  // ── AC relay ─────────────────────────────────────────────────────────
  if (strcmp(topic, TOPIC_RELAY_AC) == 0) {
    if (strcmp(action, "on") == 0) {
      acAutoMode = false;
      digitalWrite(RELAY_AC_PIN, HIGH);
      Serial.println("[Relay] AC → ON");
    } else if (strcmp(action, "off") == 0) {
      acAutoMode = false;
      digitalWrite(RELAY_AC_PIN, LOW);
      Serial.println("[Relay] AC → OFF");
    } else if (strcmp(action, "auto") == 0) {
      acAutoMode = true;
      Serial.println("[Relay] AC → AUTO");
    }
  }

  // ── Lighting relay ────────────────────────────────────────────────────
  if (strcmp(topic, TOPIC_RELAY_LIGHT) == 0) {
    if (strcmp(action, "on") == 0) {
      lightAutoMode = false;
      digitalWrite(RELAY_LIGHT_PIN, HIGH);
      Serial.println("[Relay] Light → ON");
    } else if (strcmp(action, "off") == 0) {
      lightAutoMode = false;
      digitalWrite(RELAY_LIGHT_PIN, LOW);
      Serial.println("[Relay] Light → OFF");
    } else if (strcmp(action, "auto") == 0) {
      lightAutoMode = true;
      Serial.println("[Relay] Light → AUTO");
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────
// MQTT connect + subscribe
// ─────────────────────────────────────────────────────────────────────────
void connectMQTT() {
  while (!mqtt.connected()) {
    Serial.print("[MQTT] Connecting...");
    if (mqtt.connect(MQTT_CLIENT_ID)) {
      Serial.println(" connected.");
      mqtt.subscribe(TOPIC_RELAY_AC);
      mqtt.subscribe(TOPIC_RELAY_LIGHT);
      lcd.setCursor(0, 1);
      lcd.print("Online          ");
    } else {
      Serial.print(" failed, rc=");
      Serial.print(mqtt.state());
      Serial.println(" — retry in 5s");
      delay(5000);
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Publish a single float sensor reading
// ─────────────────────────────────────────────────────────────────────────
void publishFloat(const char* topic, float value, const char* unit) {
  StaticJsonDocument<128> doc;
  doc["value"] = value;
  doc["unit"]  = unit;
  doc["ts"]    = millis();

  char payload[128];
  serializeJson(doc, payload);
  mqtt.publish(topic, payload);
}

// ─────────────────────────────────────────────────────────────────────────
// Publish a single int sensor reading
// ─────────────────────────────────────────────────────────────────────────
void publishInt(const char* topic, int value, const char* unit) {
  StaticJsonDocument<128> doc;
  doc["value"] = value;
  doc["unit"]  = unit;
  doc["ts"]    = millis();

  char payload[128];
  serializeJson(doc, payload);
  mqtt.publish(topic, payload);
}

// ─────────────────────────────────────────────────────────────────────────
// Read sensors → publish → handle auto-control
// ─────────────────────────────────────────────────────────────────────────
void publishSensors() {
  float temp = dht.readTemperature();
  float hum  = dht.readHumidity();
  int   aq   = analogRead(MQ135_PIN);
  int   snd  = digitalRead(SOUND_PIN);

  // Validate DHT reading
  if (isnan(temp) || isnan(hum)) {
    Serial.println("[DHT] Read error — skipping publish");
    return;
  }

  // Publish to MQTT
  publishFloat(TOPIC_TEMP,     temp, "C");
  publishFloat(TOPIC_HUMIDITY, hum,  "%");
  publishInt  (TOPIC_AIR,      aq,   "ppm");
  publishInt  (TOPIC_SOUND,    snd,  "bool");

  Serial.printf("[Sensor] T:%.1f°C H:%.1f%% AQ:%d Snd:%d\n",
                temp, hum, aq, snd);

  // ── Auto-control: AC threshold logic ─────────────────────────────────
  if (acAutoMode) {
    if (temp > TEMP_AC_ON_THRESHOLD) {
      digitalWrite(RELAY_AC_PIN, HIGH);
    } else if (temp < TEMP_AC_OFF_THRESHOLD) {
      digitalWrite(RELAY_AC_PIN, LOW);
    }
  }

  // ── Update LCD ────────────────────────────────────────────────────────
  char line1[17], line2[17];
  snprintf(line1, sizeof(line1), "T:%.1fC H:%.0f%%  ", temp, hum);
  snprintf(line2, sizeof(line2), "AQ:%-4d Snd:%d   ", aq, snd);

  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}

// ─────────────────────────────────────────────────────────────────────────
// Heartbeat
// ─────────────────────────────────────────────────────────────────────────
void publishHeartbeat() {
  StaticJsonDocument<64> doc;
  doc["online"] = true;
  doc["ts"]     = millis();

  char payload[64];
  serializeJson(doc, payload);
  mqtt.publish(TOPIC_STATUS, payload);
  Serial.println("[Heartbeat] sent");
}

// ─────────────────────────────────────────────────────────────────────────
// SETUP
// ─────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("\n[Boot] Smart Classroom Node");

  // Relay pins — default LOW (off)
  pinMode(RELAY_AC_PIN,    OUTPUT);
  pinMode(RELAY_LIGHT_PIN, OUTPUT);
  digitalWrite(RELAY_AC_PIN,    LOW);
  digitalWrite(RELAY_LIGHT_PIN, LOW);

  // Analog sensor pins are input-only by default on ESP32; no pinMode needed
  pinMode(SOUND_PIN, INPUT);

  // LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Smart Classroom ");
  lcd.setCursor(0, 1);
  lcd.print("Connecting...   ");

  // DHT21
  dht.begin();

  // WiFi
  connectWiFi();

  // MQTT
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(512);  // enough for incoming relay payloads
  connectMQTT();

  Serial.println("[Boot] Ready");
}

// ─────────────────────────────────────────────────────────────────────────
// MAIN LOOP
// ─────────────────────────────────────────────────────────────────────────
void loop() {
  // Reconnect if MQTT dropped
  if (!mqtt.connected()) {
    connectMQTT();
  }
  mqtt.loop();  // process incoming messages + keepalive

  unsigned long now = millis();

  // Sensor publish every 5 s
  if (now - lastSensorPublish >= SENSOR_INTERVAL_MS) {
    lastSensorPublish = now;
    publishSensors();
  }

  // Heartbeat every 30 s
  if (now - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
    lastHeartbeat = now;
    publishHeartbeat();
  }
}
