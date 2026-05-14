## 4.2 IoT Layer — ESP32 Firmware

The ESP32 development board (ESP-WROOM-32 with CP2102 USB-UART) serves as the classroom sensor node. It runs a continuous acquisition loop implemented in C++ using the Arduino IDE framework and communicates with the Raspberry Pi backend exclusively over WiFi via MQTT. This section covers hardware selection and wiring, followed by the firmware architecture and control logic.

---

### 4.2.1 Sensor Selection

Three environmental parameters are monitored continuously: temperature and humidity, air quality, and occupancy-proxy sound. Each sensor was selected after evaluating alternatives against the accuracy requirements, hardware constraints, and budget of the project.

**Temperature and Humidity — DHT21 (AM2301).** Two candidate sensors were evaluated: the DHT11 and the DHT21. Both use a single-wire serial protocol compatible with the ESP32 and the Arduino DHT library, minimizing firmware complexity. The DHT11 is lower cost (~$1) but has a rated accuracy of ±2°C for temperature and ±5% for relative humidity — insufficient for threshold-based AC control, where a ±2°C measurement error could cause the system to actuate or suppress the relay at the wrong point. The DHT21 offers ±0.3°C and ±3% RH accuracy at a modest cost increase (~$3), and was therefore selected. Validation against a calibrated reference thermometer across ten measurements confirmed a mean absolute error of ±0.4°C for temperature and ±2.5% RH for humidity — both within specification and acceptable for the alerting use case.

**TABLE IV-A. DHT11 vs. DHT21 — Evaluation Summary**

| Criterion | DHT11 | DHT21 (AM2301) | Selected |
|---|---|---|---|
| Temperature accuracy | ±2°C | ±0.3°C | DHT21 |
| Humidity accuracy | ±5% RH | ±3% RH | DHT21 |
| Temperature range | 0–50°C | −40–80°C | DHT21 |
| Unit cost (approx.) | ~$1 | ~$3 | DHT21 |
| Protocol | Single-wire | Single-wire | Tie |
| Arduino library | DHT.h | DHT.h | Tie |
| Decision rationale | Accuracy insufficient for relay thresholds | Meets threshold control requirements | — |

**Air Quality — MQ-135.** The MQ-135 is a low-cost (~$2) metal-oxide semiconductor (MOS) gas sensor whose analog output voltage varies with the concentration of CO₂, ammonia, benzene, and other volatile organic compounds (VOCs). It was selected primarily for cost and availability, with one acknowledged limitation: the sensor is not factory-calibrated to certified SI units. The ADC reading is converted to a comparative PPM proxy using an empirical formula, rather than a traceable concentration measurement. The alert threshold of 500 PPM was set empirically by observing readings in a well-ventilated, unoccupied room (~200–280 PPM) versus a room occupied by five people with windows closed (~480–560 PPM), and placing the threshold midway between the two conditions. The MQ-135 is therefore suitable for detecting relative deterioration in air quality (increased occupancy, insufficient ventilation) but not for absolute concentration measurement. A calibrated CO₂ sensor (SCD30 or MH-Z19) is identified in Chapter 10 as a future upgrade. The MQ-135 also requires a warm-up period of approximately 20 seconds after power-on before readings stabilize; the firmware discards the first sensor read cycle to account for this.

**Sound — ACP014 Digital Sound Detection Module.** The ACP014 module outputs a digital HIGH/LOW signal (HIGH = sound detected above threshold) via an onboard comparator with an adjustable sensitivity potentiometer. It was selected as a low-cost occupancy proxy — a sustained absence of sound during an active session may indicate an unexpectedly empty classroom and warrants an attendance anomaly alert. The onboard potentiometer was tuned to suppress false positives from low-level HVAC and ventilation background noise, while reliably detecting speech at distances up to approximately 2 meters. The principal limitation is the binary output: the module does not provide amplitude or frequency data, so it cannot distinguish between a quiet individual study session and a genuinely unoccupied room. This is acceptable for the current use case (anomaly alerting) but limits more nuanced acoustic analysis.

**TABLE IV-B. Sensor Summary**

| Sensor | Model | Measured Parameter | Output Type | Key Limitation | Alert Threshold |
|---|---|---|---|---|---|
| Temp/Humidity | DHT21 (AM2301) | Temperature, Relative Humidity | Single-wire serial | None significant for use case | Temp > 28°C (AC on) / < 22°C (AC off) |
| Air Quality | MQ-135 | CO₂/VOC proxy (PPM) | Analog (ADC) | Uncalibrated; comparative only | 500 PPM |
| Sound | ACP014 | Presence detection (binary) | Digital HIGH/LOW | No amplitude; binary only | Sustained silence during session |

---

### 4.2.2 Hardware Wiring and Voltage Compatibility

The ESP32-WROOM-32 operates at 3.3V logic on all its GPIO pins. The 4-channel opto-isolated relay module, however, requires 5V logic-level input signals to reliably switch its optocouplers — the HIGH/LOW threshold of the relay's input stage is referenced to a 5V supply. Without voltage translation, the 3.3V HIGH output of the ESP32 GPIO falls below the relay module's switching threshold, resulting in erratic or no actuation.

A bidirectional Logic Level Converter (3.3V ↔ 5V) was therefore inserted between the ESP32 GPIO output pins (relay control lines) and the relay module input channels IN1 and IN2 (AC and lighting, respectively). Channels IN3 and IN4 are wired but unused, reserved for future actuators. The opto-isolation in the relay module additionally provides electrical isolation between the ESP32's low-voltage control side and the mains-voltage load side, protecting the microcontroller from transient voltages induced by the AC load switching.

The LCD 16×2 display communicates via I2C (SDA/SCL, address 0x27 on the I2C backpack module). Because the I2C backpack module accepts 3.3–5V supply and the ESP32's I2C lines operate at 3.3V with sufficient drive strength for short bus distances, no level conversion is required for this interface.

The complete wiring topology is summarized below and shown in the wiring diagram (Figure 5, Appendix E for the full annotated schematic).

**TABLE IV-C. ESP32 Pin Assignment**

| ESP32 GPIO | Connected To | Signal | Notes |
|---|---|---|---|
| GPIO 4 | DHT21 Data | Single-wire serial | 10kΩ pull-up to 3.3V |
| GPIO 34 (ADC1_6) | MQ-135 Analog Out | Analog voltage (0–3.3V) | ADC input only; no pull-up |
| GPIO 35 | ACP014 Digital Out | Digital HIGH/LOW | No pull-up needed (module has internal) |
| GPIO 26 | LLC → Relay IN1 | AC relay control | Via Logic Level Converter LV1→HV1 |
| GPIO 27 | LLC → Relay IN2 | Lighting relay control | Via Logic Level Converter LV2→HV2 |
| GPIO 21 (SDA) | LCD I2C Backpack SDA | I2C data | — |
| GPIO 22 (SCL) | LCD I2C Backpack SCL | I2C clock | — |
| 3.3V | LLC LV, DHT21 VCC | 3.3V rail | — |
| 5V (USB VBUS) | LLC HV, Relay VCC, LCD VCC | 5V rail | From ESP32 USB connector |
| GND | All module GND pins | Common ground | — |

*LLC = Logic Level Converter; LV = low-voltage side (3.3V); HV = high-voltage side (5V)*

**Power supply.** The ESP32 development board is powered via its USB connector (5V from the USB host or a dedicated USB wall adapter). The 5V VBUS pin on the board supplies the relay module VCC and LLC high-voltage side. The onboard 3.3V LDO regulator on the ESP32 board supplies the LLC low-voltage side and the DHT21. In a permanent classroom installation, a dedicated 5V USB power supply (minimum 2A to accommodate relay coil current at switching) is used in place of the development USB connection.

*[Figure 5: ESP32 node wiring diagram — annotated pinout showing ESP32, Logic Level Converter, 4-channel relay module, DHT21, MQ-135, ACP014, and LCD 16×2. Full schematic in Appendix E.]*

*[Photo: Fig. 13 — assembled breadboard with ESP32, sensors, relay module, and logic level converter]*

*[Photo: Fig. 14 — close-up of relay module and logic level converter wiring]*

---

### 4.2.3 Firmware Architecture

The ESP32 firmware is a single Arduino sketch (`firmware/classroom_node/classroom_node.ino`) with a companion configuration header (`config.h`). All deployment-specific parameters — WiFi SSID and password, MQTT broker IP address, room ID, sensor thresholds, and the `acAutoMode` flag — are defined in `config.h` and excluded from version control. This separation keeps credentials out of the source tree and allows the same firmware binary logic to be redeployed to a different room by modifying only `config.h`.

The firmware depends on five Arduino libraries: `WiFi.h` (built-in) for network connectivity, `PubSubClient` for MQTT client functionality, `DHT` for DHT21 sensor communication, `LiquidCrystal_I2C` for the LCD display, and `ArduinoJson` for JSON payload serialization.

**Main loop.** The Arduino `loop()` function executes the following sequence on every iteration:

1. Check WiFi and MQTT connection status; reconnect with exponential backoff if either is lost.
2. Call `mqttClient.loop()` to process incoming MQTT messages (relay commands) and maintain the broker keep-alive.
3. If 5 seconds have elapsed since the last sensor read: read DHT21 (temperature + humidity), read MQ-135 ADC (air quality), read ACP014 digital pin (sound); serialize each as `{"value": <float>, "unit": "<string>", "ts": <unix_ms>}`; publish to `classroom/{room_id}/sensors/{type}`.
4. If 30 seconds have elapsed since the last heartbeat: publish `{"online": true, "ts": <ms>}` to `classroom/{room_id}/status`.
5. If `acAutoMode=true`: compare the most recent temperature reading against `TEMP_AC_ON_THRESHOLD` (28°C) and `TEMP_AC_OFF_THRESHOLD` (22°C); actuate relay channel 1 (AC) via `digitalWrite` accordingly.

**MQTT callback.** The `mqttCallback()` function, registered with `PubSubClient`, handles incoming messages on the relay command topics. It deserializes the JSON payload using `ArduinoJson`, reads the `action` field (`"on"`, `"off"`, or `"auto"`), and sets the corresponding GPIO pin HIGH or LOW. Receipt of `"auto"` sets the `acAutoMode` flag to `true`, transferring control to the main loop temperature logic.

**On-device auto-control.** The `acAutoMode` feature is a deliberate resilience mechanism. The backend alert engine independently evaluates temperature thresholds every 30 seconds and sends relay commands via MQTT — so under normal operation, the backend and the device are aligned. However, if the WiFi connection drops or the Mosquitto broker restarts, the backend loses the ability to send relay commands. With `acAutoMode` enabled, the ESP32 continues to enforce temperature thresholds locally and independently, ensuring the classroom remains thermally safe without any network dependency. This two-layer actuation design (backend alert engine + on-device fallback) was a deliberate architectural decision to improve resilience of the control path.

**LCD display.** After each sensor read cycle, the firmware updates the 16×2 LCD: row 0 displays temperature (°C) and humidity (%); row 1 displays air quality (PPM) and sound detection status (ON/OFF). The display address (0x27) is set in `config.h`. This provides local, real-time environmental feedback in the classroom without any network or dashboard dependency.

---
