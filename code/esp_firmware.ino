#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

BLEServer *pServer = nullptr;
BLECharacteristic *pCharacteristic = nullptr;
bool deviceConnected = false;

class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      Serial.println("Device connected");
      deviceConnected = true;
    };

    void onDisconnect(BLEServer* pServer) {
      Serial.println("Device disconnected");
      deviceConnected = false;
    }
};

const int currAnalogInPin = 14;
const int volAnalogInPin = 12;
int currSensorValue = 0;
int volSensorValue = 0;
float currVoltage = 0;
float current = 0;
float voltage = 0;
float power = 0;

// Global variable to store the received command
String command = "";
String response = "";

// // Function to process the received command
// String processCommand(String command) {
//   if (command == "On") {
//     // Code to turn on the appliance
//     digitalWrite(35,LOW);
//     delay(2000);
//     return "Appliance On!";
//   } else if (command == "Off") {
//     // Code to turn off the appliance
//     digitalWrite(35,HIGH);
//     delay(2000);
//     return "Appliance Off!";
//   }
//   return "Invalid Command";
// }

void setup() {
  Serial.begin(115200);
  BLEDevice::init("ESP32_BLE");
  pinMode(35, OUTPUT);

  // Create the BLE Server
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  // Create the BLE Service
  BLEService *pService = pServer->createService(SERVICE_UUID);

  // Create a BLE Characteristic
  pCharacteristic = pService->createCharacteristic(
                      CHARACTERISTIC_UUID,
                      BLECharacteristic::PROPERTY_READ   |
                      BLECharacteristic::PROPERTY_WRITE  |
                      BLECharacteristic::PROPERTY_NOTIFY
                    );

  // Start the service
  pService->start();

  // Start advertising
  pServer->getAdvertising()->start();
  Serial.println("Waiting for a client connection...");

  delay(1000);
  digitalWrite(35,HIGH);
}

void loop() {
  if (deviceConnected) {
    currSensorValue = analogRead(currAnalogInPin);
    volSensorValue = analogRead(volAnalogInPin);
    currVoltage = (currSensorValue * (5.0/ 1024));
    current = (2.5 - (currVoltage)) / 0.185;
    voltage = (volSensorValue / 4095.0) * 3.3;
    power = current * voltage;

    // Update the BLE characteristic with the power value
    pCharacteristic->setValue(String(power).c_str());
    pCharacteristic->notify();

    // Check if there is a command from the client
    if (pCharacteristic->getValue().length() > 0) {
      delay(1000);
      command = pCharacteristic->getValue().c_str();
      Serial.println(command);
      if (command == "On") {
        Serial.println("Turning Appliance On...");
        digitalWrite(35,LOW);
        Serial.println("After Digitalwrite");
        delay(200);
        Serial.println("Appliance On!");
        response = "Appliance On!";
      } else if (command == "Off") {
        // Code to turn off the appliance
        Serial.println("Turning Appliance Off...");
        digitalWrite(35,HIGH);
        Serial.println("After Digitalwrite");
        delay(200);
        Serial.println("Appliance Off!");
        response = "Appliance Off!";
      }
      else{
        Serial.println("Appliance Off!");
        response = "Invalid Command";
      } 
      delay(1000);
      pCharacteristic->setValue(response.c_str());
      pCharacteristic->notify();
      delay(1000);
      // Clear the characteristic value
      pCharacteristic->setValue("");
    }

    // Print the sensor and power values to Serial for debugging
    Serial.print("Current Sensor Value: ");
    Serial.print(currSensorValue);
    Serial.print(", Voltage Sensor Value: ");
    Serial.print(volSensorValue);
    Serial.print(", Voltage: ");
    Serial.print(voltage);
    Serial.print("V, Current: ");
    Serial.print(current);
    Serial.print("A, Power: ");
    Serial.println(power);

    delay(1000);
  }
}
