// =========================================================================
// ESP32 Code: I2S Audio Acquisition, IMU SPI Acquisition,
//             and TCP Wi-Fi Transmission (UART commented out)
// =========================================================================
#include <driver/i2s.h>
#include "esp_err.h"

// --- Additions for IMU ---
#include <SPI.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_LSM6DSOX.h>
// --- End Additions for IMU ---

// --- WiFi Addition ---
#include <WiFi.h>
// --- End WiFi Addition ---

// --- Pin Configuration ---
// I2S Pins (User Defined)
#define I2S_WS_PIN   9  // Word Select (LRCLK)
#define I2S_SD_PIN   8  // Serial Data In (DOUT from Mic)
#define I2S_SCK_PIN 10 // Bit Clock (BCLK)

// --- Additions for IMU ---
// SPI Pins (Chosen based on previous discussion, using GPIO 0-6)
// IMPORTANT: These pins MUST NOT conflict with your I2S pins!
// Your I2S pins (8, 9, 10) are different, so this configuration *should* be okay.
#define SPI_SCK_PIN  6  // Default SPI2 SCLK
#define SPI_MISO_PIN 2  // Default SPI2 MISO (Strapping Pin)
#define SPI_MOSI_PIN 5  // Remapped from default GPIO7
#define SPI_CS_PIN   4  // Remapped from default GPIO10
// --- End Additions for IMU ---

// --- I2S Configuration ---
#define I2S_SAMPLE_RATE 48000 // Target sample rate (e.g., 48kHz)
#define I2S_BUFFER_SAMPLES 1024 // Samples per DMA buffer (affects RAM usage and latency)
// Note: Reading 24-bit data into 32-bit int buffer
#define I2S_BITS_PER_SAMPLE_CONFIG I2S_BITS_PER_SAMPLE_24BIT
#define BYTES_PER_SAMPLE_BUFFER 4 // Using int32_t to store 24-bit sample

// --- Serial Configuration (Commented out, keep for reference) ---
// #define SERIAL_BAUD_RATE 2000000 // High baud rate (e.g., 2M). MUST MATCH PYTHON SCRIPT.

// --- I2S Port ---
#define I2S_PORT I2S_NUM_0

// --- Additions for IMU ---
// We will use the default SPI object and configure its pins

// Create an LSM6DSOX sensor object
Adafruit_LSM6DSOX lsm6ds;

// Define a structure to hold IMU data for sending
struct IMU_Data_Packet {
  float ax, ay, az; // Acceleration values (m/s^2)
  float gx, gy, gz; // Gyroscope values (rad/s)
};

// --- Define markers/IDs for TCP data stream ---
const uint8_t AUDIO_DATA_ID = 0x01;
const uint8_t IMU_DATA_ID   = 0x02;
// const uint8_t imu_marker[4] = {0xFF, 0xFE, 0xFD, 0xFC}; // Marker for UART, replaced by ID for TCP
// --- End Additions for IMU ---

// --- WiFi and TCP Server Additions ---
const char* ssid = "Oneplus Nord 2 Marco";         // <<< CHANGE THIS
const char* password = "987654321"; // <<< CHANGE THIS
const uint16_t serverPort = 8088; // TCP port to listen on
WiFiServer server(serverPort);
WiFiClient client; // Holds the current connected client
// --- End WiFi Additions ---

/**
 * @brief Configures and installs the I2S driver
 */
void setupI2S() {
    Serial.println("Configuring I2S...");

    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX), // Master, Receive data
        .sample_rate = I2S_SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_CONFIG,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,   // Mono microphone
        .communication_format = I2S_COMM_FORMAT_STAND_I2S, // Standard I2S
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,     // Interrupt priority
        .dma_buf_count = 8,                           // Number of DMA buffers
        .dma_buf_len = I2S_BUFFER_SAMPLES,            // Samples per DMA buffer
        .use_apll = true,                             // Use APLL clock source (try true for high rates if needed)
    };

    esp_err_t err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("!!! I2S Driver Install Failed: %d (%s) !!!\n", err, esp_err_to_name(err));
        while(1) delay(1000);
    } else {
         Serial.println("I2S Driver Installed.");
    }

    i2s_pin_config_t pin_config = {
        .bck_io_num = I2S_SCK_PIN,
        .ws_io_num = I2S_WS_PIN,
        .data_out_num = I2S_PIN_NO_CHANGE, // Not transmitting data
        .data_in_num = I2S_SD_PIN
    };

    err = i2s_set_pin(I2S_PORT, &pin_config);
    if (err != ESP_OK) {
        Serial.printf("!!! I2S Set Pin Failed: %d (%s) !!!\n", err, esp_err_to_name(err));
         while(1) delay(1000);
    } else {
         Serial.println("I2S Pins Set.");
    }
     Serial.println("I2S Configuration Complete.");
}

// --- Additions for IMU ---
/**
 * @brief Configures SPI and initializes the IMU sensor
 */
void setupIMU() {
    Serial.println("Configuring SPI and IMU...");

    // Begin SPI communication using the default SPI object with remapped pins
    SPI.begin(SPI_SCK_PIN, SPI_MISO_PIN, SPI_MOSI_PIN, -1);

    // Try to initialize LSM6DSOX sensor with the specific CS pin and the default SPI object pointer
    if (!lsm6ds.begin_SPI(SPI_CS_PIN, &SPI)) {
        Serial.println("!!! Failed to find LSM6DSOX chip over SPI !!!");
        while (1) { delay(10); }
    }
    Serial.println("LSM6DSOX Found!");

    // Set Accelerometer Range (Example: +/- 16G)
    lsm6ds.setAccelRange(LSM6DS_ACCEL_RANGE_16_G);
    Serial.print("Accelerometer range set to: ");
    switch (lsm6ds.getAccelRange()) {
        case LSM6DS_ACCEL_RANGE_2_G: Serial.println("+-2G"); break;
        case LSM6DS_ACCEL_RANGE_4_G: Serial.println("+-4G"); break;
        case LSM6DS_ACCEL_RANGE_8_G: Serial.println("+-8G"); break;
        case LSM6DS_ACCEL_RANGE_16_G: Serial.println("+-16G"); break;
    }

    // Set Accelerometer Output Data Rate (ODR) for vibration analysis (Example: 6.66 KHz)
    lsm6ds.setAccelDataRate(LSM6DS_RATE_6_66K_HZ); // Use underscore version
    Serial.print("Accelerometer data rate set to: ");
    switch (lsm6ds.getAccelDataRate()) {
        case LSM6DS_RATE_SHUTDOWN: Serial.println("Shutdown"); break;
        case LSM6DS_RATE_12_5_HZ: Serial.println("12.5 Hz"); break;
        case LSM6DS_RATE_26_HZ: Serial.println("26 Hz"); break;
        case LSM6DS_RATE_52_HZ: Serial.println("52 Hz"); break;
        case LSM6DS_RATE_104_HZ: Serial.println("104 Hz"); break;
        case LSM6DS_RATE_208_HZ: Serial.println("208 Hz"); break;
        case LSM6DS_RATE_416_HZ: Serial.println("416 Hz"); break;
        case LSM6DS_RATE_833_HZ: Serial.println("833 Hz"); break;
        case LSM6DS_RATE_1_66K_HZ: Serial.println("1.66 KHz"); break; // Use underscore version
        case LSM6DS_RATE_6_66K_HZ: Serial.println("6.66 KHz"); break; // Use underscore version
         default: Serial.println("Unknown Rate"); break;
    }


    // Set Gyro Range (Example: +/- 2000 degrees/sec)
    lsm6ds.setGyroRange(LSM6DS_GYRO_RANGE_2000_DPS);
    Serial.print("Gyro range set to: ");
     switch (lsm6ds.getGyroRange()) {
        case LSM6DS_GYRO_RANGE_125_DPS: Serial.println("125 dps"); break;
        case LSM6DS_GYRO_RANGE_250_DPS: Serial.println("250 dps"); break;
        case LSM6DS_GYRO_RANGE_500_DPS: Serial.println("500 dps"); break;
        case LSM6DS_GYRO_RANGE_1000_DPS: Serial.println("1000 dps"); break;
        case LSM6DS_GYRO_RANGE_2000_DPS: Serial.println("2000 dps"); break;
         default: Serial.println("Unknown Range"); break;
    }

    // Set Gyro Output Data Rate (ODR) (Example: match accelerometer 6.66 KHz)
    lsm6ds.setGyroDataRate(LSM6DS_RATE_6_66K_HZ); // Use underscore version
    Serial.print("Gyro data rate set to: ");
     switch (lsm6ds.getGyroDataRate()) {
        case LSM6DS_RATE_SHUTDOWN: Serial.println("Shutdown"); break;
        case LSM6DS_RATE_12_5_HZ: Serial.println("12.5 Hz"); break;
        case LSM6DS_RATE_26_HZ: Serial.println("26 Hz"); break;
        case LSM6DS_RATE_52_HZ: Serial.println("52 Hz"); break;
        case LSM6DS_RATE_104_HZ: Serial.println("104 Hz"); break;
        case LSM6DS_RATE_208_HZ: Serial.println("208 Hz"); break;
        case LSM6DS_RATE_416_HZ: Serial.println("416 Hz"); break;
        case LSM6DS_RATE_833_HZ: Serial.println("833 Hz"); break;
        case LSM6DS_RATE_1_66K_HZ: Serial.println("1.66 KHz"); break; // Use underscore version
        case LSM6DS_RATE_6_66K_HZ: Serial.println("6.66 KHz"); break; // Use underscore version
         default: Serial.println("Unknown Rate"); break;
    }

    Serial.println("IMU Configuration Complete.");
    delay(100); // Short delay after configuration
}
// --- End Additions for IMU ---


/**
 * @brief Main Setup Function
 */
void setup() {
    Serial.begin(115200);
    Serial.println("\n--- Debug Start ---"); // <<< ADDED

    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

    Serial.println("Attempting Wi-Fi connection..."); // <<< ADDED
    Serial.print("Connecting to SSID: ");          // <<< ADDED
    Serial.println(ssid);                         // <<< ADDED

    WiFi.begin(ssid, password);
    int wifi_attempts = 0; // <<< ADDED
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
        digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
        wifi_attempts++; // <<< ADDED
        if (wifi_attempts > 40) { // <<< ADDED: Timeout check (20 seconds)
            Serial.println("\nWi-Fi connection timed out!"); // <<< ADDED
            // Optional: Enter a loop or restart if connection fails repeatedly
            // while(1) delay(1000);
        }
    }
    // This part only runs if WiFi.status() == WL_CONNECTED
    digitalWrite(LED_BUILTIN, HIGH);
    Serial.println("\nWiFi connected!"); // <<< Confirmation
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP()); // <<< Target Output

    // Start TCP server
    server.begin();
    Serial.printf("TCP Server started on port %d\n", serverPort); // <<< ADDED

    Serial.println("Setting up I2S..."); // <<< ADDED
    setupI2S();
    Serial.println("Setting up IMU..."); // <<< ADDED
    setupIMU();

    Serial.println("Setup complete. Waiting for client connection..."); // Original message
}


/**
 * @brief Main Loop Function
 */
void loop() {

  // --- Check for and handle TCP client connection ---
  if (!client || !client.connected()) {
      // If no client is connected, check for a new one
      client = server.available();
      if (client) {
          Serial.println("\nNew client connected!");
      }
      // Optional: Slow down loop slightly if no client is connected
      // delay(100);
      // return; // Or just don't send data if no client
  }

  // --- If a client is connected, send data ---
  if (client && client.connected()) {

    // === I2S Audio Reading ===
    int32_t i2s_read_buffer[I2S_BUFFER_SAMPLES]; // Buffer for I2S data
    size_t bytes_read = 0;                       // Variable to store bytes read

    // Read data from I2S into the buffer
    esp_err_t result = i2s_read(I2S_PORT,
                               i2s_read_buffer,
                               I2S_BUFFER_SAMPLES * BYTES_PER_SAMPLE_BUFFER,
                               &bytes_read,
                               portMAX_DELAY); // Wait indefinitely for data

    // === Send Audio Data over TCP ===
    if (result == ESP_OK && bytes_read > 0) {
        // *** Send Audio Data via TCP ***
        client.write(AUDIO_DATA_ID); // Send the audio ID marker
        client.write((uint8_t*)i2s_read_buffer, bytes_read); // Send the raw audio data

        // --- Original Serial Write (Commented Out) ---
        // Serial.write((uint8_t*)i2s_read_buffer, bytes_read);
        // --- End Original ---
    }
    else if (result != ESP_OK) {
        // Handle I2S read error (optional: print error)
        // Serial.printf("I2S Read Error: %d\n", result);
    }

    // === IMU Reading ===
    sensors_event_t accel;
    sensors_event_t gyro;
    sensors_event_t temp; // Temperature data is available but not sent in this example
    lsm6ds.getEvent(&accel, &gyro, &temp); // Read sensor events

    // Populate the IMU data packet structure
    IMU_Data_Packet imu_packet;
    imu_packet.ax = accel.acceleration.x;
    imu_packet.ay = accel.acceleration.y;
    imu_packet.az = accel.acceleration.z;
    imu_packet.gx = gyro.gyro.x;
    imu_packet.gy = gyro.gyro.y;
    imu_packet.gz = gyro.gyro.z;

    // === Send IMU Data over TCP ===
    // *** Send IMU Data via TCP ***
    client.write(IMU_DATA_ID); // Send the IMU ID marker
    client.write((uint8_t*)&imu_packet, sizeof(IMU_Data_Packet)); // Send the raw IMU data

    // --- Original Serial Write (Commented Out) ---
    // Serial.write(imu_marker, sizeof(imu_marker));
    // Serial.write((uint8_t*)&imu_packet, sizeof(IMU_Data_Packet));
    // --- End Original ---

    // --- Optional: Add a small delay if needed to prevent flooding ---
    // delay(1); // Be cautious with delays in the main loop

  } // End if(client && client.connected())

}
// =========================================================================