/*
 * MHARS rover firmware (ESP32)
 * See CONNECT.md in project root for setup.
 *
 * 1. Set WiFi + SERVER_URL (your laptop IP)
 * 2. Replace read*() with real sensor code
 * 3. Flash, power on — dashboard source becomes WIFI
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "YOUR_SSID";
const char* WIFI_PASS = "YOUR_PASSWORD";
// Example: http://192.168.1.10:8000/api/telemetry
const char* SERVER_URL = "http://192.168.1.10:8000/api/telemetry";

float posX = 0, posY = 0, heading = 0;

void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(400); Serial.print("."); }
  Serial.println("\nWiFi OK");
}

// --- plug your sensors here ---
float readCO()       { return 12.0; }   // MQ-7
float readCH4()      { return 150.0; }  // MQ-4
float readCO2()      { return 700.0; }  // MQ-135
float readTemp()     { return 29.5; }   // DHT22
float readHumidity() { return 60.0; }
float readFrontCm()  { return 100.0; }  // HC-SR04
float readLeftCm()   { return 90.0; }
float readRightCm()  { return 95.0; }
float readMicDb()    { return 45.0; }
float readThermalMax(){ return 32.0; }  // MLX90640

void loop() {
  StaticJsonDocument<768> doc;
  doc["type"] = "telemetry";
  doc["ts"] = millis() / 1000.0;

  JsonObject position = doc.createNestedObject("position");
  position["x"] = posX;
  position["y"] = posY;
  position["heading_deg"] = heading;
  position["relative_label"] = "Gallery-1";

  JsonObject gas = doc.createNestedObject("gas");
  gas["co_ppm"] = readCO();
  gas["ch4_ppm"] = readCH4();
  gas["co2_ppm"] = readCO2();
  gas["h2s_ppm"] = 0.0;

  JsonObject env = doc.createNestedObject("environment");
  env["temperature_c"] = readTemp();
  env["humidity_pct"] = readHumidity();

  JsonObject prox = doc.createNestedObject("proximity");
  prox["front_cm"] = readFrontCm();
  prox["left_cm"] = readLeftCm();
  prox["right_cm"] = readRightCm();

  JsonObject acoustic = doc.createNestedObject("acoustic");
  acoustic["level_db"] = readMicDb();
  acoustic["event"] = nullptr;
  acoustic["confidence"] = 0.0;

  JsonObject thermal = doc.createNestedObject("thermal");
  thermal["max_c"] = readThermalMax();
  thermal["avg_c"] = readTemp();
  thermal["min_c"] = readTemp() - 1;
  thermal["anomaly"] = false;

  doc["visual_available"] = false;

  JsonObject status = doc.createNestedObject("status");
  status["battery_pct"] = 88.0;
  status["mode"] = "auto";
  status["speed_mps"] = 0.3;
  status["connected"] = true;

  String payload;
  serializeJson(doc, payload);
  Serial.println(payload);  // USB option too

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    int code = http.POST(payload);
    Serial.printf("HTTP %d\n", code);
    http.end();
  }

  posX += 0.1;
  delay(400);
}
