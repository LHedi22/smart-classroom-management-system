# Wiring Diagram — ESP32 Classroom Node

## Component Pin Map

### DHT21 (AM2301) Temperature/Humidity Sensor

| DHT21 Pin | Wire Color | ESP32 Pin     | Notes                                  |
|-----------|------------|---------------|----------------------------------------|
| VCC       | Red        | 3.3V          | Sensor operates at 3.3–5.5V           |
| DATA      | Yellow     | GPIO 4        | Single-wire protocol; 10kΩ pull-up to 3.3V |
| GND       | Black      | GND           |                                        |

Pull-up resistor: 10kΩ between DATA and VCC.

---

### MQ-135 Air Quality Sensor

| MQ-135 Pin | Wire Color | ESP32 Pin     | Notes                                            |
|------------|------------|---------------|--------------------------------------------------|
| VCC        | Red        | 5V (USB)      | Heater requires 5V; ESP32 VBUS from USB          |
| GND        | Black      | GND           |                                                  |
| AOUT       | Yellow     | GPIO 34       | Analog output → ADC1 channel 6 (input-only pin)  |
| DOUT       | Orange     | Not connected | Digital threshold output not used                |

Note: GPIO 34 is input-only; ADC1 is used to avoid conflicts with WiFi (ADC2 is disabled during WiFi).

---

### ACP014 Sound Sensor

| ACP014 Pin | Wire Color | ESP32 Pin     | Notes                                    |
|------------|------------|---------------|------------------------------------------|
| VCC        | Red        | 3.3V          |                                          |
| GND        | Black      | GND           |                                          |
| DOUT       | Yellow     | GPIO 35       | Digital output; HIGH = sound detected    |

GPIO 35 is input-only. Sound detection is binary (no analog level).

---

### 4-Channel Opto-Isolated Relay Module

The relay module requires a **Logic Level Converter (3.3V ↔ 5V)** between the ESP32 and the relay input pins, because the relay expects 5V TTL signals and the ESP32 outputs 3.3V logic.

**Logic Level Converter wiring:**

| LLC Pin (Low Side 3.3V) | ESP32 Pin | LLC Pin (High Side 5V) | Relay Pin |
|-------------------------|-----------|------------------------|-----------|
| LV1                     | GPIO 26   | HV1                    | IN1 (AC)  |
| LV2                     | GPIO 27   | HV2                    | IN2 (Lighting) |
| LV3                     | GPIO 14   | HV3                    | IN3 (Spare) |
| LV4                     | GPIO 12   | HV4                    | IN4 (Spare) |
| LV (reference)          | 3.3V      | HV (reference)         | 5V         |
| GND                     | GND       | GND                    | GND        |

**Relay Module Power:**

| Relay Pin | Connection      | Notes                          |
|-----------|-----------------|--------------------------------|
| VCC       | 5V (USB)        | Must be 5V for opto-isolators  |
| GND       | GND             | Shared with ESP32 GND          |
| JD-VCC    | 5V (USB)        | Disconnect jumper for isolation; reconnect for simplicity |

**Relay channel assignment:**

| Channel | IN Pin  | Load         |
|---------|---------|--------------|
| CH1     | GPIO 26 | AC unit      |
| CH2     | GPIO 27 | Room lights  |
| CH3     | GPIO 14 | Spare        |
| CH4     | GPIO 12 | Spare        |

**IMPORTANT:** Relay contacts carry mains voltage (220V AC). All mains wiring must be done by a qualified electrician and comply with local electrical safety codes.

---

### LCD 16×2 I2C Display

| LCD I2C Module Pin | Wire Color | ESP32 Pin   | Notes                                   |
|--------------------|------------|-------------|-----------------------------------------|
| VCC                | Red        | 3.3V or 5V  | Check module spec; most I2C backpacks are 5V tolerant |
| GND                | Black      | GND         |                                         |
| SDA                | Blue       | GPIO 21     | ESP32 default I2C SDA                   |
| SCL                | Yellow     | GPIO 22     | ESP32 default I2C SCL                   |

I2C address: `0x27` (default for most PCF8574-based backpacks; use an I2C scanner if display does not initialise).

---

## Full GPIO Summary

| GPIO | Direction | Component         | Signal Description          |
|------|-----------|-------------------|-----------------------------|
| 4    | Input     | DHT21             | Temperature/humidity data   |
| 34   | Input     | MQ-135            | Air quality ADC (0–4095)    |
| 35   | Input     | ACP014            | Sound detection (digital)   |
| 21   | I2C SDA   | LCD 16×2          | I2C data                    |
| 22   | I2C SCL   | LCD 16×2          | I2C clock                   |
| 26   | Output    | Relay CH1 (via LLC)| AC relay control           |
| 27   | Output    | Relay CH2 (via LLC)| Lighting relay control     |
| 14   | Output    | Relay CH3 (via LLC)| Spare                      |
| 12   | Output    | Relay CH4 (via LLC)| Spare                      |

---

## Power Rail Summary

| Voltage | Source                | Consumers                              |
|---------|-----------------------|----------------------------------------|
| 5V      | USB power bank / USB-C| ESP32 VBUS, MQ-135, Relay VCC/JD-VCC  |
| 3.3V    | ESP32 onboard LDO     | DHT21, ACP014, LLC LV side, LCD (if 3.3V) |
| GND     | Common                | All components                         |

---

## Notes

- GPIO 34, 35 are **input-only** — no internal pull-up/pull-down. Add external resistors if needed.
- Do not drive inductive loads (relay coils) directly from ESP32 GPIO — always use the opto-isolated relay module.
- All ground rails must be connected (ESP32 GND, logic level converter GND, relay module GND).
