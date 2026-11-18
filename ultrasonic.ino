#include <WiFi.h>  // Use <ESP8266WiFi.h> if using ESP8266
#include <PubSubClient.h>

// --- EDIT THESE LINES ---
const char* ssid = "Karol Laptop";
const char* password = "KAROL123456";
const char* mqtt_server = "192.168.137.185"; // Put your Raspberry Pi IP here
// ------------------------
// ------------------- PIN DEFINITIONS -------------------
// Sensor 1
const int trigPin1 = 4;  // D4
const int echoPin1 = 2;  // D2

// Sensor 2
const int trigPin2 = 19; // D19
const int echoPin2 = 21; // D21

// ------------------- OBJECTS & VARIABLES -------------------
WiFiClient espClient;
PubSubClient client(espClient);
long lastMsgTime = 0; // Timer for non-blocking delay

void setup() {
  Serial.begin(115200);

  // Setup Pins
  pinMode(trigPin1, OUTPUT);
  pinMode(echoPin1, INPUT);
  pinMode(trigPin2, OUTPUT);
  pinMode(echoPin2, INPUT);

  setup_wifi();
  client.setServer(mqtt_server, 1883);
}

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    String clientId = "ESP32-Ultrasonic-";
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

// Helper function to get distance in CM
int getDistance(int trigPin, int echoPin) {
  // Clear the trigPin
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  
  // Trigger the sensor
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  // Read the echoPin
  long duration = pulseIn(echoPin, HIGH);
  
  // Calculate distance (Speed of sound is 0.034 cm/us)
  int distance = duration * 0.034 / 2;
  return distance;
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Send data every 1 second (1000ms)
  long now = millis();
  if (now - lastMsgTime > 1000) {
    lastMsgTime = now;

    // --- READ SENSORS ---
    int dist1 = getDistance(trigPin1, echoPin1);
    int dist2 = getDistance(trigPin2, echoPin2);

    // --- PREPARE MESSAGES ---
    // Convert numbers to strings (char arrays) for MQTT
    char msg1[10];
    char msg2[10];
    sprintf(msg1, "%d", dist1);
    sprintf(msg2, "%d", dist2);

    // --- PUBLISH TO MQTT ---
    // Topics: "sensor/ultra1" and "sensor/ultra2"
    client.publish("sensor/ultra1", msg1);
    client.publish("sensor/ultra2", msg2);

    // Debug to Serial Monitor
    Serial.print("Sensor 1: "); Serial.print(dist1); Serial.println(" cm");
    Serial.print("Sensor 2: "); Serial.print(dist2); Serial.println(" cm");
  }
}