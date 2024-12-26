#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <EEPROM.h>
#include <WebServer.h>
#include <DNSServer.h>

// EEPROM layout
#define EEPROM_SIZE 512
#define ID_ADDRESS 0
#define WIFI_SSID_ADDRESS 40
#define WIFI_PASS_ADDRESS 120

// LED settings
#define LED_PIN     5
#define LED_COUNT   45
#define INITIAL_BRIGHTNESS  50

// MQTT settings (these could also be made configurable via the portal)
const char* mqtt_server = "test.mosquitto.org";
const int mqtt_port = 1883;
const char* mqtt_user = "";
const char* mqtt_password = "";

void setupMQTT();
void reconnectMQTT();
void callback(char* topic, byte* payload, unsigned int length);
void publishStatus();
void publishHeartbeat();


// AP Mode settings
const char* AP_SSID = "ESP32_LED_Setup";
const byte DNS_PORT = 53;

// Objects
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
WiFiClient espClient;
PubSubClient mqtt(espClient);
WebServer webServer(80);
DNSServer dnsServer;

// Global variables
String boardId;
char topicBuffer[50];
bool isConfigMode = false;

// HTML page
const char* config_html = R"(
<!DOCTYPE html>
<html>
<head>
    <title>ESP32 LED Configuration</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f0f0f0;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 400px;
            margin: 0 auto;
        }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 8px;
            margin: 8px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        input[type="submit"] {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            width: 100%;
        }
        input[type="submit"]:hover {
            background-color: #45a049;
        }
        .status {
            margin-top: 20px;
            padding: 10px;
            border-radius: 4px;
        }
        .success { background-color: #dff0d8; }
        .error { background-color: #f2dede; }
    </style>
</head>
<body>
    <div class="container">
        <h2>WiFi Setup</h2>
        <form action="/save" method="POST">
            <label for="ssid">WiFi Name:</label><br>
            <input type="text" id="ssid" name="ssid" required><br>
            <label for="password">Password:</label><br>
            <input type="password" id="password" name="password" required><br><br>
            <input type="submit" value="Save and Connect">
        </form>
    </div>
</body>
</html>
)";

void initializeBoardId() {
  // Try to read board ID from EEPROM
  String storedId = "";
  bool validStoredId = true;
  
  // Read stored ID from EEPROM
  for (int i = 0; i < 36; i++) {  // Max ID length
    char c = EEPROM.read(ID_ADDRESS + i);
    if (c == 0) break;
    // Check if character is valid hexadecimal
    if (!isHexadecimalChar(c)) {
      validStoredId = false;
      break;
    }
    storedId += c;
  }
  
  // Generate new ID if stored ID is invalid or too short
  if (!validStoredId || storedId.length() < 8) {
    // Clear the storedId
    storedId = "";
    
    // Generate new random ID using ESP32's MAC address
    uint64_t chipid = ESP.getEfuseMac();
    char tempId[13]; // Temporary buffer for ID
    sprintf(tempId, "%012llX", chipid); // Format as 12-character hex string
    boardId = String(tempId);
    
    // Store in EEPROM
    for (uint i = 0; i < boardId.length(); i++) {
      EEPROM.write(ID_ADDRESS + i, boardId[i]);
    }
    EEPROM.write(ID_ADDRESS + boardId.length(), 0);  // Null terminator
    EEPROM.commit();
    
    Serial.println("Generated new Board ID: " + boardId);
  } else {
    boardId = storedId;
    Serial.println("Using stored Board ID: " + boardId);
  }
}

// Helper function to check if character is valid hexadecimal
bool isHexadecimalChar(char c) {
  return (c >= '0' && c <= '9') || 
         (c >= 'A' && c <= 'F') || 
         (c >= 'a' && c <= 'f');
}

void setup() {
  Serial.begin(115200);


  Serial.println("Connected");
  EEPROM.begin(EEPROM_SIZE);
  
  strip.begin();
  strip.setBrightness(INITIAL_BRIGHTNESS);
  strip.show();
  
  initializeBoardId();
  
  // Try to connect to stored WiFi
  if (!connectToStoredWiFi()) {
    startConfigPortal();
  } else {
    setupMQTT();
  }
}

unsigned long lastHeartbeat = 0;
const unsigned long heartbeatInterval = 100000;  // 10 seconds
void loop() {
  if (isConfigMode) {
    dnsServer.processNextRequest();
    webServer.handleClient();
  } else {
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("WiFi connection lost");
      if (!connectToStoredWiFi()) {
        startConfigPortal();
      }
    }
    if (!isConfigMode && !mqtt.connected()) {
      reconnectMQTT();
    }
    mqtt.loop();

    unsigned long now = millis();
    if (now - lastHeartbeat >= heartbeatInterval) {
        lastHeartbeat = now;
        publishHeartbeat();
    }
    
  }
}

bool connectToStoredWiFi() {
  String stored_ssid = readFromEEPROM(WIFI_SSID_ADDRESS);
  String stored_pass = readFromEEPROM(WIFI_PASS_ADDRESS);
  
  Serial.println("Stored credentials:");
  Serial.println("SSID: " + stored_ssid);
  Serial.println("Password length: " + String(stored_pass.length()));
  
  if (stored_ssid.length() > 0) {
    Serial.println("Attempting to connect to stored WiFi");
    
    WiFi.disconnect();
    WiFi.mode(WIFI_STA);
    WiFi.begin(stored_ssid.c_str(), stored_pass.c_str());
    
    int attempts = 0;
    const int maxAttempts = 20;
    
    while (attempts < maxAttempts) {
      if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nConnected to WiFi");
        Serial.println("IP address: " + WiFi.localIP().toString());
        return true;
      }
      
      if (attempts % 5 == 0) {
        Serial.println("\nRetrying connection...");
        WiFi.begin(stored_ssid.c_str(), stored_pass.c_str());
      }
      
      delay(500);
      Serial.print(".");
      attempts++;
      
      if (attempts % 5 == 0) {
        Serial.println("\nWiFi status: " + String(WiFi.status()));
      }
    }
    
    Serial.println("\nFailed to connect after " + String(maxAttempts) + " attempts");
  } else {
    Serial.println("No stored WiFi credentials found");
  }
  return false;
}



void startConfigPortal() {
  isConfigMode = true;
  WiFi.disconnect();
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID);
  
  dnsServer.start(DNS_PORT, "*", WiFi.softAPIP());
  
  webServer.on("/", HTTP_GET, handleRoot);
  webServer.on("/save", HTTP_POST, handleSave);
  webServer.onNotFound(handleRoot);
  webServer.begin();
  
  // Set LED strip to indicate config mode (blue pulsing)
  configModeLEDIndicator();
}

void handleRoot() {
  webServer.send(200, "text/html", config_html);
}

void handleSave() {
  String new_ssid = webServer.arg("ssid");
  String new_pass = webServer.arg("password");
  
  writeToEEPROM(WIFI_SSID_ADDRESS, new_ssid);
  writeToEEPROM(WIFI_PASS_ADDRESS, new_pass);
  EEPROM.commit();
  
  webServer.send(200, "text/html", "Settings saved. ESP32 will now restart...");
  delay(2000);
  ESP.restart();
}

void writeToEEPROM(int startAddr, String data) {
  for (int i = 0; i < data.length(); i++) {
    EEPROM.write(startAddr + i, data[i]);
  }
  EEPROM.write(startAddr + data.length(), 0);
}

String readFromEEPROM(int startAddr) {
  String data = "";
  char c;
  int i = 0;
  while ((c = EEPROM.read(startAddr + i)) != 0 && i < 80) {
    data += c;
    i++;
  }
  return data;
}

void configModeLEDIndicator() {
  for(int i=0; i<strip.numPixels(); i++) {
    strip.setPixelColor(i, strip.Color(0, 0, 50));
  }
  strip.show();
}

void setupMQTT() {
    mqtt.setServer(mqtt_server, mqtt_port);
    mqtt.setCallback(callback);
    reconnectMQTT();
}

void reconnectMQTT() {
    while (!mqtt.connected() && WiFi.status() == WL_CONNECTED) {
        Serial.print("Connecting to MQTT...");
        String clientId = "ESP32Client-" + boardId;
        
        if (mqtt.connect(clientId.c_str(), mqtt_user, mqtt_password)) {
            sprintf(topicBuffer, "xVC5!GVcWEh4CF/neopixels/%s/control", boardId.c_str());
            mqtt.subscribe(topicBuffer);
            Serial.println("connected");
            publishStatus();  // Publish initial status
        } else {
            Serial.print(boardId);
            Serial.print(" : failed, rc=");
            Serial.print(mqtt.state());
            Serial.println(" retrying in 5 seconds");
            delay(5000);
        }
    }
}

void callback(char* topic, byte* payload, unsigned int length) {
    StaticJsonDocument<2048> doc;
    DeserializationError error = deserializeJson(doc, payload, length);
    if (error) {
        Serial.print("deserializeJson() failed: ");
        Serial.println(error.c_str());
        return;
    }

    sprintf(topicBuffer, "xVC5!GVcWEh4CF/neopixels/%s/control", boardId.c_str());
    if (strcmp(topic, topicBuffer) == 0) {
        // Handle commands
        if (doc.containsKey("cmd")) {
            const char* cmd = doc["cmd"];
            
            if (strcmp(cmd, "all_off") == 0) {
                for (int i = 0; i < LED_COUNT; i++) {
                    strip.setPixelColor(i, strip.Color(0, 0, 0));
                }
                strip.show();
                publishStatus();
                return;
            }
            
            if (strcmp(cmd, "all_on") == 0) {
                uint8_t r = doc["r"] | 255;  // Default to white if no color specified
                uint8_t g = doc["g"] | 255;
                uint8_t b = doc["b"] | 255;
                for (int i = 0; i < LED_COUNT; i++) {
                    strip.setPixelColor(i, strip.Color(r, g, b));
                }
                strip.show();
                publishStatus();
                return;
            }
        }

        // Handle brightness
        if (doc.containsKey("brightness")) {
            int brightness = doc["brightness"];
            strip.setBrightness(brightness);
        }

        // Handle compact "leds_hex" scheme
        if (doc.containsKey("leds_hex")) {
            JsonArray leds_hex = doc["leds_hex"];
            for (JsonArray led_pair : leds_hex) {
                int index = led_pair[0]; // First element is led_id
                uint32_t color = strtoul(led_pair[1], NULL, 16); // Second element is hex color as a string
                if (index >= 0 && index < LED_COUNT) {
                    strip.setPixelColor(index, color);
                }
            }
        }

        // Handle original "leds" scheme (RGB values)
        if (doc.containsKey("leds")) {
            JsonArray leds = doc["leds"];
            for (JsonObject led : leds) {
                int index = led["i"];
                int r = led["r"] | 0;
                int g = led["g"] | 0;
                int b = led["b"] | 0;
                if (index >= 0 && index < LED_COUNT) {
                    strip.setPixelColor(index, strip.Color(r, g, b));
                }
            }
        }

        strip.show();
        publishStatus();
    }
}

void publishStatus() {
    StaticJsonDocument<2048> doc;

    // Compact "leds_hex" status reporting
    JsonArray leds_hex = doc.createNestedArray("leds_hex");
    for (int i = 0; i < LED_COUNT; i++) {
        uint32_t color = strip.getPixelColor(i);
        char hexColor[7]; // Format: RRGGBB (6 characters + null terminator)
        sprintf(hexColor, "%02X%02X%02X", (uint8_t)(color >> 16), (uint8_t)(color >> 8), (uint8_t)color);
        
        JsonArray led_pair = leds_hex.createNestedArray();
        led_pair.add(i);           // LED index
        led_pair.add(hexColor);    // Hex color as a string
    }
    
    // Optional: Add additional fields (e.g., brightness, boardId)
    doc["brightness"] = strip.getBrightness();
    doc["boardId"] = boardId;

    char buffer[2048];
    serializeJson(doc, buffer);

    sprintf(topicBuffer, "xVC5!GVcWEh4CF/neopixels/%s/status", boardId.c_str());
    mqtt.publish(topicBuffer, buffer);
}

void publishHeartbeat() {
    StaticJsonDocument<256> doc;  // Smaller buffer since heartbeat is lightweight
    doc["boardId"] = boardId;
    doc["status"] = "online";  // Indicates the device is operational
    doc["timestamp"] = millis();  // Use device uptime in milliseconds

    char buffer[256];
    serializeJson(doc, buffer);

    sprintf(topicBuffer, "xVC5!GVcWEh4CF/neopixels/%s/heartbeat", boardId.c_str());
    mqtt.publish(topicBuffer, buffer);
}
