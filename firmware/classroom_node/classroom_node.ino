#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ===== WIFI & MQTT CONFIG =====
#define WIFI_SSID     "Test1234"
#define WIFI_PASSWORD "test1234"
#define MQTT_HOST     "10.169.33.142"   // ← your laptop LAN IP
#define MQTT_PORT     1883
#define ROOM_ID       "room1"

// ===== LCD =====
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ===== DHT11 =====
#define DHTPIN 4
#define DHTTYPE DHT11   // DHT21 / AM2301 uses the DHT22 protocol in the Adafruit library
DHT dht(DHTPIN, DHTTYPE);

// ===== MQ135 =====
#define MQ135_PIN 34

// ===== SOUND SENSOR =====
#define SOUND_PIN 35

// ===== ACTUATORS =====
#define RELAY_PIN 26
#define LED_PIN 25

// ===== THRESHOLDS =====
#define TEMP_THRESHOLD  26
#define AIR_THRESHOLD   1200
#define SOUND_THRESHOLD 450

// ===== TIMING =====
#define SENSOR_INTERVAL   5000   // publish sensors every 5s
#define HEARTBEAT_INTERVAL 30000 // publish heartbeat every 30s

// ===== CUSTOM CHAR (Speaker) =====
byte SpeakerChar[] = {
  B00001, B00011, B00111, B11111,
  B11111, B00111, B00011, B00001
};

// ===== MQTT & WIFI CLIENTS =====
WiFiClient   espClient;
PubSubClient mqtt(espClient);

unsigned long lastSensorMs    = 0;
unsigned long lastHeartbeatMs = 0;

// ===== WIFI CONNECT =====
void connectWiFi() {
  Serial.print("[WiFi] Connecting to ");
  Serial.println(WIFI_SSID);

  WiFi.persistent(false);
  WiFi.setAutoReconnect(false);
  WiFi.mode(WIFI_STA);
  delay(500);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\n[WiFi] Connected, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WiFi] FAILED — check SSID/password");
  }
}

// ===== MQTT CONNECT =====
void connectMQTT() {
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  int tries = 0;
  while (!mqtt.connected() && tries < 5) {
    Serial.print("[MQTT] Connecting...");
    String clientId = "esp32-" + String(random(0xffff), HEX);
    if (mqtt.connect(clientId.c_str())) {
      Serial.println(" connected.");
    } else {
      Serial.print(" failed, rc=");
      Serial.print(mqtt.state());
      Serial.println(" — retry in 3s");
      delay(3000);
      tries++;
    }
  }
}

// ===== PUBLISH SENSOR =====
void publishSensor(const char* type, float value, const char* unit) {
  char topic[64];
  snprintf(topic, sizeof(topic), "classroom/%s/sensors/%s", ROOM_ID, type);

  StaticJsonDocument<128> doc;
  doc["value"] = value;
  doc["unit"]  = unit;
  doc["ts"]    = millis();

  char payload[128];
  serializeJson(doc, payload);

  mqtt.publish(topic, payload);
  Serial.print("[MQTT] ");
  Serial.print(topic);
  Serial.print(" → ");
  Serial.println(payload);
}

// ===== PUBLISH HEARTBEAT =====
void publishHeartbeat() {
  char topic[64];
  snprintf(topic, sizeof(topic), "classroom/%s/status", ROOM_ID);

  StaticJsonDocument<64> doc;
  doc["online"] = true;
  doc["ts"]     = millis();

  char payload[64];
  serializeJson(doc, payload);
  mqtt.publish(topic, payload);
  Serial.println("[MQTT] Heartbeat sent");
}

// ===== SETUP =====
void setup() {
  Serial.begin(115200);

  // LCD
  lcd.init();
  lcd.backlight();
  lcd.createChar(0, SpeakerChar);

  // Sensors
  dht.begin();

  // Actuators
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); // Relay OFF (active LOW)
  digitalWrite(LED_PIN, LOW);

  // MQ135 warm-up
  for (int i = 30; i > 0; i--) {
    lcd.clear();
    lcd.setCursor(0, 0); lcd.print("MQ135 Warming");
    lcd.setCursor(0, 1); lcd.print("Time: "); lcd.print(i); lcd.print("s");
    delay(1000);
  }
  lcd.clear();

  // Network
  connectWiFi();
  connectMQTT();
}

// ===== LOOP =====
void loop() {
  // Keep MQTT alive — reconnect if dropped
  if (!mqtt.connected()) {
    connectMQTT();
  }
  mqtt.loop();

  unsigned long now = millis();

  // ===== SENSOR READ & PUBLISH every 5s =====
  if (now - lastSensorMs >= SENSOR_INTERVAL) {
    lastSensorMs = now;

    float temp  = dht.readTemperature();
    float hum   = dht.readHumidity();
    int   air   = analogRead(MQ135_PIN);
    int   sound = analogRead(SOUND_PIN);

    // Serial debug
    Serial.print("Temp: "); Serial.print(temp);
    Serial.print(" C | Hum: "); Serial.print(hum);
    Serial.print(" % | Air: "); Serial.print(air);
    Serial.print(" | Sound: "); Serial.println(sound);

    // Publish to MQTT (backend expects these exact topic names)
    if (!isnan(temp)) {
      publishSensor("temperature", temp, "C");
    }
    if (!isnan(hum)) {
      publishSensor("humidity", hum, "%");
    }
    publishSensor("air_quality", (float)air, "ppm");
    publishSensor("sound",       (sound > SOUND_THRESHOLD) ? 1.0 : 0.0, "bool");

    // ===== CONDITIONS =====
    bool tempAlert  = temp > TEMP_THRESHOLD;
    bool airAlert   = air  > AIR_THRESHOLD;
    bool soundAlert = sound > SOUND_THRESHOLD;

    // ===== RELAY & LED CONTROL (unchanged) =====
    digitalWrite(RELAY_PIN, (tempAlert || airAlert) ? LOW : HIGH);
    digitalWrite(LED_PIN,   soundAlert ? HIGH : LOW);

    // ===== LCD DISPLAY (unchanged) =====
    lcd.setCursor(0, 0);
    if (tempAlert)      { lcd.print("Alert TEMP     "); }
    else if (airAlert)  { lcd.print("Alert Air QLTY "); }
    else                { lcd.print("Temp:"); lcd.print(temp); lcd.print("C      "); }

    lcd.setCursor(0, 1);
    if (airAlert) { lcd.print("AQ:"); lcd.print(air); lcd.print("       "); }
    else          { lcd.print("AQ:"); lcd.print(air); lcd.print("       "); }

    lcd.setCursor(15, 0);
    lcd.write(soundAlert ? byte(0) : byte(' '));
  }

  // ===== HEARTBEAT every 30s =====
  if (now - lastHeartbeatMs >= HEARTBEAT_INTERVAL) {
    lastHeartbeatMs = now;
    publishHeartbeat();
  }
}