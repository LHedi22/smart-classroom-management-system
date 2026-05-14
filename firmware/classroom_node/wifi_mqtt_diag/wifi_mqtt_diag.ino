/*
 * WiFi + MQTT Diagnostic Sketch — ESP32 WROOM-DA
 * ─────────────────────────────────────────────────────────────────────────
 * Purpose: isolate the root cause of connection failures without any
 *          sensor/LCD/relay code interfering.
 *
 * How to use:
 *   1. Open THIS file as a separate sketch in Arduino IDE
 *   2. Tools → Board → "ESP32 Dev Module"   (try this first)
 *      If step 1 of the output shows the phy_comm error → also try
 *      "ESP32 WROOM-DA Module" to compare
 *   3. Upload → open Serial Monitor at 115200 baud
 *   4. Read the numbered steps — the first one that says FAIL is root cause
 *
 * No libraries needed beyond the ESP32 core and PubSubClient.
 * ─────────────────────────────────────────────────────────────────────────
 */

#include <WiFi.h>
#include <PubSubClient.h>

// ── CHANGE THESE ─────────────────────────────────────────────────────────
const char* WIFI_SSID     = "Ooredoo-327065";
const char* WIFI_PASSWORD = "BFB68D59Er@07";
const char* MQTT_HOST     = "192.168.0.168";
const int   MQTT_PORT     = 1883;
// ─────────────────────────────────────────────────────────────────────────

WiFiClient   espClient;
PubSubClient mqtt(espClient);

// ── Helpers ───────────────────────────────────────────────────────────────

void sep(const char* title) {
  Serial.println();
  Serial.println("════════════════════════════════════════");
  Serial.println(title);
  Serial.println("════════════════════════════════════════");
}

void pass(const char* msg) {
  Serial.print("  [PASS] ");
  Serial.println(msg);
}

void fail(const char* msg) {
  Serial.print("  [FAIL] ");
  Serial.println(msg);
}

void info(const char* label, const char* value) {
  Serial.print("  ");
  Serial.print(label);
  Serial.print(": ");
  Serial.println(value);
}

void info(const char* label, long value) {
  Serial.print("  ");
  Serial.print(label);
  Serial.print(": ");
  Serial.println(value);
}

// Returns human-readable WiFi status
const char* wifiStatusStr(wl_status_t s) {
  switch (s) {
    case WL_IDLE_STATUS:      return "IDLE";
    case WL_NO_SSID_AVAIL:   return "NO_SSID_AVAIL — router not seen";
    case WL_SCAN_COMPLETED:  return "SCAN_COMPLETED";
    case WL_CONNECTED:       return "CONNECTED";
    case WL_CONNECT_FAILED:  return "CONNECT_FAILED — wrong password";
    case WL_CONNECTION_LOST: return "CONNECTION_LOST";
    case WL_DISCONNECTED:    return "DISCONNECTED";
    default:                 return "UNKNOWN";
  }
}

// ── Step 1: Hardware info ─────────────────────────────────────────────────

void stepHardwareInfo() {
  sep("STEP 1 — Hardware info");
  char buf[32];

  uint64_t chipid = ESP.getEfuseMac();
  snprintf(buf, sizeof(buf), "%04X%08X",
           (uint16_t)(chipid >> 32), (uint32_t)chipid);
  info("Chip ID (MAC)", buf);

  info("CPU freq (MHz)", (long)ESP.getCpuFreqMHz());
  info("Free heap (B)",  (long)ESP.getFreeHeap());
  info("Flash size (B)", (long)ESP.getFlashChipSize());
  info("SDK version",    ESP.getSdkVersion());

  // WiFi MAC
  info("WiFi MAC", WiFi.macAddress().c_str());

  pass("Hardware info collected — check values above look sane");
}

// ── Step 2: SSID scan ─────────────────────────────────────────────────────

void stepSSIDScan() {
  sep("STEP 2 — Scanning for target SSID");

  Serial.println("  Scanning (takes ~3s) ...");
  int n = WiFi.scanNetworks();

  if (n == 0) {
    fail("No networks found at all — check antenna / power");
    return;
  }

  Serial.print("  Found ");
  Serial.print(n);
  Serial.println(" network(s):");

  bool found = false;
  for (int i = 0; i < n; i++) {
    bool isTarget = (WiFi.SSID(i) == String(WIFI_SSID));
    Serial.print(isTarget ? "  >>> " : "      ");
    Serial.print(WiFi.SSID(i));
    Serial.print("  RSSI=");
    Serial.print(WiFi.RSSI(i));
    Serial.print(" dBm  CH=");
    Serial.print(WiFi.channel(i));
    Serial.print("  ENC=");
    switch (WiFi.encryptionType(i)) {
      case WIFI_AUTH_OPEN:            Serial.print("OPEN");     break;
      case WIFI_AUTH_WEP:             Serial.print("WEP");      break;
      case WIFI_AUTH_WPA_PSK:         Serial.print("WPA");      break;
      case WIFI_AUTH_WPA2_PSK:        Serial.print("WPA2");     break;
      case WIFI_AUTH_WPA_WPA2_PSK:    Serial.print("WPA/WPA2"); break;
      case WIFI_AUTH_WPA2_ENTERPRISE: Serial.print("WPA2-ENT"); break;
      case WIFI_AUTH_WPA3_PSK:        Serial.print("WPA3");     break;
      case WIFI_AUTH_WPA2_WPA3_PSK:   Serial.print("WPA2/WPA3");break;
      default:                        Serial.print("OTHER");    break;
    }
    Serial.println();
    if (isTarget) found = true;
  }

  WiFi.scanDelete();

  if (found) {
    pass("Target SSID visible — if ENC shows WPA3, that may be the issue");
  } else {
    fail("Target SSID not found in scan — wrong SSID name or out of range");
  }
}

// ── Step 3: Connect at different TX power levels ──────────────────────────

bool stepConnectAtPower(const char* label, wifi_power_t power, int timeoutMs) {
  Serial.println();
  Serial.print("  Trying TX power = ");
  Serial.println(label);

  WiFi.mode(WIFI_OFF);
  delay(200);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(300);
  WiFi.setTxPower(power);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int elapsed = 0;
  while (WiFi.status() != WL_CONNECTED && elapsed < timeoutMs) {
    delay(500);
    elapsed += 500;
    Serial.print(".");
  }
  Serial.println();

  wl_status_t s = WiFi.status();
  Serial.print("  Final status: ");
  Serial.println(wifiStatusStr(s));

  if (s == WL_CONNECTED) {
    Serial.print("  IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("  RSSI: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    return true;
  }

  WiFi.disconnect(true);
  delay(500);
  return false;
}

void stepWiFiConnect() {
  sep("STEP 3 — WiFi connection (3 TX power levels)");

  // Try progressively lower TX power levels.
  // If a lower power connects but higher fails, it's a power-supply brownout.
  // If none connect, it's SSID/password/router rejecting.

  // 2 dBm ≈ 1.6 mW — barely enough but tests if PHY init works at all
  if (stepConnectAtPower("2 dBm (minimal)", WIFI_POWER_2dBm, 10000)) {
    pass("Connected at 2 dBm — power supply brownout is the issue at higher power");
    return;
  }

  // 8.5 dBm ≈ 7 mW — recommended for laptop USB power
  if (stepConnectAtPower("8.5 dBm (recommended)", WIFI_POWER_8_5dBm, 10000)) {
    pass("Connected at 8.5 dBm — use WIFI_POWER_8_5dBm in production firmware");
    return;
  }

  // 19.5 dBm — default / maximum
  if (stepConnectAtPower("19.5 dBm (default/max)", WIFI_POWER_19_5dBm, 15000)) {
    pass("Connected at full power — power supply is fine, lower power fix not needed");
    return;
  }

  fail("WiFi failed at ALL power levels");
  Serial.println();
  Serial.println("  Possible causes (check STEP 2 output):");
  Serial.println("  a) WPA3-only router — ESP32 needs WPA2 or WPA2/WPA3 mixed mode");
  Serial.println("  b) Wrong password");
  Serial.println("  c) MAC address filtering on router");
  Serial.println("  d) SSID hidden (not found in step 2 either)");
  Serial.println("  e) PHY hardware fault on the module itself");
}

// ── Step 4: MQTT reachability ─────────────────────────────────────────────

void stepMQTT() {
  sep("STEP 4 — MQTT broker reachability");

  if (WiFi.status() != WL_CONNECTED) {
    fail("Skipped — WiFi not connected (fix step 3 first)");
    return;
  }

  mqtt.setServer(MQTT_HOST, MQTT_PORT);

  Serial.print("  Connecting to ");
  Serial.print(MQTT_HOST);
  Serial.print(":");
  Serial.println(MQTT_PORT);

  if (mqtt.connect("diag-esp32")) {
    pass("MQTT connected — full pipeline is healthy");
    char topic[48];
    snprintf(topic, sizeof(topic), "classroom/room1/sensors/temperature");
    mqtt.publish(topic, "{\"value\":99.9,\"unit\":\"C\",\"ts\":0}");
    Serial.println("  Published test message to classroom/room1/sensors/temperature");
    Serial.println("  Check docker logs backend | grep sensor to confirm receipt");
    mqtt.disconnect();
  } else {
    int rc = mqtt.state();
    fail("MQTT connection failed");
    Serial.print("  PubSubClient state code: ");
    Serial.println(rc);
    Serial.println();
    Serial.println("  Code meanings:");
    Serial.println("   -4  MQTT_CONNECTION_TIMEOUT  — broker unreachable (firewall / Docker not running)");
    Serial.println("   -3  MQTT_CONNECTION_LOST");
    Serial.println("   -2  MQTT_CONNECT_FAILED      — TCP refused (Mosquitto not listening on 1883)");
    Serial.println("   -1  MQTT_DISCONNECTED");
    Serial.println("    1  MQTT_CONNECT_BAD_PROTOCOL");
    Serial.println("    2  MQTT_CONNECT_BAD_CLIENT_ID");
    Serial.println("    3  MQTT_CONNECT_UNAVAILABLE");
    Serial.println("    4  MQTT_CONNECT_BAD_CREDENTIALS");
    Serial.println("    5  MQTT_CONNECT_UNAUTHORIZED");
  }
}

// ── Step 5: Summary ───────────────────────────────────────────────────────

void stepSummary() {
  sep("STEP 5 — Summary");
  Serial.println("  Board selected in Arduino IDE: check Tools → Board name");
  Serial.println("  If step 3 passed at 2 dBm but not higher → power brownout");
  Serial.println("    Fix: power ESP32 from USB wall charger, not laptop USB port");
  Serial.println("  If step 2 shows WPA3 encryption → router issue");
  Serial.println("    Fix: router admin → change to WPA2 or WPA2/WPA3 mixed mode");
  Serial.println("  If step 3 failed at all levels → wrong password or MAC filter");
  Serial.println("  If step 4 failed → Docker stack not running or firewall blocking 1883");
  Serial.println();
  Serial.println("  Run 'docker compose ps' on your laptop to verify stack is up.");
  Serial.println("  Run 'python test_laptop_mode.py' from the project root to verify");
  Serial.println("  the MQTT→WebSocket pipeline from the laptop side.");
}

// ── Main ──────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1000);  // let Serial settle

  Serial.println();
  Serial.println("╔══════════════════════════════════════╗");
  Serial.println("║  ESP32 WiFi + MQTT Diagnostic Tool   ║");
  Serial.println("╚══════════════════════════════════════╝");

  stepHardwareInfo();
  stepSSIDScan();
  stepWiFiConnect();
  stepMQTT();
  stepSummary();

  Serial.println();
  Serial.println("════════════════════════════════════════");
  Serial.println("  Diagnostic complete. See output above.");
  Serial.println("════════════════════════════════════════");
}

void loop() {
  // Nothing — diagnostic is one-shot in setup()
  delay(10000);
}
