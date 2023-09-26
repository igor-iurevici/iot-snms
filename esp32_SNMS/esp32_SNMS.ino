#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>

// MAX4466 setup
#define MICPIN 35
#define SAMPLING_WINDOW 50 // 20 Hz

// WIFI setup
#define WIFI_SSID "YourWifiName"
#define WIFI_PASS "YourWifiPassword"

// MQTT setup
#define MQTT_SERVER "MQTT IP"
#define PORT 1883
#define MQTT_USER ""
#define MQTT_PASSWORD ""
#define CONFIG_TOPIC "snms/config"
#define CONNECT_TOPIC "snms/connect"

// HTTP setup
#define URL "FlaskServerUrl"
HTTPClient http;

// configuration
uint16_t samplingRate = 500;
uint16_t noiseThreshold = 35;
uint16_t alarmLevel = 50;
uint16_t alarmCounter = 10;

// values to send
float noise = 0.0; // dB
int16_t rssi = 0; // dBm
bool alarmFlag = false;

// others
uint16_t counter = 0;
bool configReceived = false;
uint16_t actualRate = samplingRate;
uint16_t latency = 0;

//uint16_t numSamples = 5;
//uint16_t currentDelay = 0;

 
/**
 * =======================
 * === WIFI CONNECTION ===
 * =======================
 */

// WiFi connection
void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection attempt...");
    delay(500);
  }
  Serial.println("WiFi connected!");
  Serial.println(WiFi.localIP());
}

/**
 * ========================
 * === MQTT CONNECTION ===
 * =======================
 */
WiFiClient espClient;
PubSubClient client(espClient);

// MQTT connection
void connectMQTT() {
  while (!client.connected()) {
    Serial.println("MQTT connection attempt...");
    if (client.connect("esp32-arduino")) {
      Serial.println("MQTT connected!");  
    } else {
      Serial.print("failed with state ");
      Serial.print(client.state());
      delay(2000);
    }
  }
}

// MQTT subscription
void subscribeTopic(const char* topic) {
  if (client.subscribe(topic)) {
    Serial.print("Subscribed to topic: ");
    Serial.println(topic);
  } else {
    Serial.print("Failed to subscribe to topic: ");
    Serial.println(topic);
  }
}

// MQTT configuration callback
void callbackConfig(char* topic, byte* payload, unsigned int length) {
  /**
  Serial.print("Received message on topic: ");
  Serial.println(topic);
  Serial.print("Message: ");
  for (int i = 0; i < length; i++) {
    Serial.print((char)payload[i]);
  }
  Serial.println();
  */

  // parse payload (sample_rating; noise_threshold; alarm_level; alarm_counter)
  const size_t capacity = JSON_OBJECT_SIZE(4) + 80;
  DynamicJsonDocument doc(capacity);

  DeserializationError error = deserializeJson(doc, payload, length);
  if (error) {
    Serial.print("Failed to parse JSON payload: ");
    Serial.println(error.c_str());
    return;
  }

  // consistency check
  if (doc["sampling_rate"] > 50 && doc["noise_threshold"] > 0 && doc["alarm_level"] > 0 && doc["alarm_counter"] > 0) {
    // extract configuration parameters from JSON
    samplingRate = doc["sampling_rate"];
    noiseThreshold = doc["noise_threshold"];
    alarmLevel = doc["alarm_level"];
    alarmCounter = doc["alarm_counter"];
    Serial.print("New configuration: ");
    Serial.print(samplingRate);
    Serial.print(";    ");
    Serial.print(noiseThreshold);
    Serial.print(";    ");
    Serial.print(alarmLevel);
    Serial.print(";    ");
    Serial.println(alarmCounter);
    
    configReceived = true;
    samplingRate -= SAMPLING_WINDOW;

    /**
    if (samplingRate < 250) {
      numSamples = (uint16_t)(samplingRate / SAMPLING_WINDOW);
      currentDelay = samplingRate - numSamples * SAMPLING_WINDOW;
    }
    else {
      currentDelay = samplingRate - SAMPLING_WINDOW * numSamples;
      numSamples = 5;
    }
    */
  } else {
    Serial.println("Invalid configuration values!");
  }
}

// check if config is initialiazed
void initConfig() {
  while(!configReceived) {
    if(!client.connected()) {
      connectMQTT();
      subscribeTopic(CONFIG_TOPIC);
    }
    client.publish(CONNECT_TOPIC, "ESP32 connected");
    client.loop();
    delay(2000);
  }
}

/**
 * ======================
 * === HTTP SEND DATA ===
 * ======================
 */

void sendData() {
  // Check if the HTTP connection is already established
  if (!http.connected()) {
    http.begin(URL);
    http.addHeader("Content-Type", "text/plain");
  }

  char payload[32];

  int payloadLen = snprintf(payload, sizeof(payload), "%d", rssi);

  if (noise > noiseThreshold) {
    payloadLen += snprintf(payload + payloadLen, sizeof(payload) - payloadLen, ";%.2f;%d", noise, static_cast<int>(alarmFlag));
  }

  uint16_t startTime = millis();
  int16_t httpCode = http.POST(payload);
  uint16_t endTime = millis();

  latency = endTime - startTime;

  if (httpCode > 0) {
    Serial.printf("HTTP POST request sent with status code: %d\n", httpCode);
    Serial.printf("RTT: %lu ms\n", latency);
  } else {
    Serial.printf("HTTP POST request failed with error: %s\n", http.errorToString(httpCode).c_str());
    http.end();
  }
}


/**
 * =========================
 * === ESP32 AND SENSORS ===
 * =========================
 */

// Data acquisition
void acquireData() {
  // Noise level acquisition
  uint16_t sample = 0;
  uint16_t signalMax = 0;  //minimum value
  uint16_t signalMin = 4095;  //maximum value
  
  //unsigned long start_time = millis(); 
  //while (millis() - start_time < SAMPLING_WINDOW) {
  for (int i = SAMPLING_WINDOW; i >= 0; i--) {
    sample = analogRead(MICPIN);  
    if (sample < 4095)  
    {
      if (sample > signalMax)
      {
        signalMax = sample;  
      }
      else if (sample < signalMin)
      {
        signalMin = sample; 
      }
    }
    delay(1);
  }
  float peakToPeak = abs(signalMax - signalMin - 100) + 1; // amplitude and denoising
  float volts = ((peakToPeak * 3.3) / 4095) * 0.707; // convert to RMS volt
  float spl = log10(volts/0.00631) * 20; // mic sensitivity is -44 +-2 dB converted to V RMS / PA is 0.000631
  noise = spl + 94 - 44 - 25; // gain range (25x to 125x), 94 PA expressed as dB SPL
  Serial.print("peak-to-peak: ");
  Serial.print(peakToPeak);
  Serial.print(";    dB: ");
  Serial.println(noise);

  // Alarm check and set
  if (noise > alarmLevel) {
    if (!alarmFlag){
      counter++;
      if (counter >= alarmCounter) {
        alarmFlag = true;
      }
    }
  } else {
    counter = 0;
  }
  
  if (alarmFlag && noise < alarmLevel) {
    alarmFlag = false;
  }
  Serial.print("Counter: ");
  Serial.print(counter);
  Serial.print(";    Alarm: ");
  Serial.println(alarmFlag);

  // WiFi strength acquisition
  rssi = WiFi.RSSI();
}

/**
 * ====================
 * === SETUP - LOOP ===
 * ====================
 */

void setup() {
  // ESP32 setup
  Serial.begin(115200);
  pinMode(MICPIN, INPUT);
  analogReadResolution(12);
  // WIFI setup
  connectWiFi();
  // MQTT setup
  client.setServer(MQTT_SERVER, PORT);
  client.setCallback(callbackConfig);
  connectMQTT();
  subscribeTopic(CONFIG_TOPIC);
  initConfig();  
}

void loop() { 
  // WiFi check
  if(WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  
  // MQTT
  client.loop();
  if(!client.connected()) {
    connectMQTT();
    subscribeTopic(CONFIG_TOPIC);
  }
  
  // Data acquisition
  acquireData();

  // HTTP
  sendData();

  // Correct samplingRate
  actualRate = ((samplingRate - latency) < 0) ? 0 : (samplingRate - latency);
  delay(actualRate);
}
