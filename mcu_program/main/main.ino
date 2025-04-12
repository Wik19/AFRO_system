// =========================================================================
// ESP32 Code: I2S Audio Acquisition, IMU SPI Acquisition, 
//             and High-Speed Serial Transmission
// =========================================================================
#include <driver/i2s.h>
#include "esp_err.h"

// --- Additions for IMU ---
#include <SPI.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_LSM6DSOX.h>
// --- End Additions for IMU ---

// --- Pin Configuration ---
// I2S Pins (User Defined)
#define I2S_WS_PIN  9  // Word Select (LRCLK)
#define I2S_SD_PIN  8  // Serial Data In (DOUT from Mic)
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

// --- Serial Configuration ---
#define SERIAL_BAUD_RATE 2000000 // High baud rate (e.g., 2M). MUST MATCH PYTHON SCRIPT.

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

// Define a marker to identify IMU data packets in the serial stream
const uint8_t imu_marker[4] = {0xFF, 0xFE, 0xFD, 0xFC}; 
// --- End Additions for IMU ---


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
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,      // Interrupt priority
        .dma_buf_count = 8,                            // Number of DMA buffers
        .dma_buf_len = I2S_BUFFER_SAMPLES,             // Samples per DMA buffer
        .use_apll = true,                              // Use APLL clock source (try true for high rates if needed)
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
    // ** Correction: Use correct enum names like _6_66K_HZ **
    lsm6ds.setAccelDataRate(LSM6DS_RATE_6_66K_HZ); // Use underscore version
    Serial.print("Accelerometer data rate set to: ");
    switch (lsm6ds.getAccelDataRate()) {
        // ** Correction: Use correct enum names like _1_66K_HZ, remove _3K33 **
        case LSM6DS_RATE_SHUTDOWN: Serial.println("Shutdown"); break; 
        case LSM6DS_RATE_12_5_HZ: Serial.println("12.5 Hz"); break;
        case LSM6DS_RATE_26_HZ: Serial.println("26 Hz"); break;
        case LSM6DS_RATE_52_HZ: Serial.println("52 Hz"); break;
        case LSM6DS_RATE_104_HZ: Serial.println("104 Hz"); break;
        case LSM6DS_RATE_208_HZ: Serial.println("208 Hz"); break;
        case LSM6DS_RATE_416_HZ: Serial.println("416 Hz"); break;
        case LSM6DS_RATE_833_HZ: Serial.println("833 Hz"); break;
        case LSM6DS_RATE_1_66K_HZ: Serial.println("1.66 KHz"); break; // Use underscore version
        // case LSM6DS_RATE_3K33_HZ: Serial.println("3.33 KHz"); break; // Remove - likely invalid enum
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
    // ** Correction: Use correct enum names like _6_66K_HZ **
    lsm6ds.setGyroDataRate(LSM6DS_RATE_6_66K_HZ); // Use underscore version
    Serial.print("Gyro data rate set to: ");
     switch (lsm6ds.getGyroDataRate()) {
        // ** Correction: Use correct enum names like _1_66K_HZ, remove _3K33 **
        case LSM6DS_RATE_SHUTDOWN: Serial.println("Shutdown"); break;
        case LSM6DS_RATE_12_5_HZ: Serial.println("12.5 Hz"); break;
        case LSM6DS_RATE_26_HZ: Serial.println("26 Hz"); break;
        case LSM6DS_RATE_52_HZ: Serial.println("52 Hz"); break;
        case LSM6DS_RATE_104_HZ: Serial.println("104 Hz"); break;
        case LSM6DS_RATE_208_HZ: Serial.println("208 Hz"); break;
        case LSM6DS_RATE_416_HZ: Serial.println("416 Hz"); break;
        case LSM6DS_RATE_833_HZ: Serial.println("833 Hz"); break;
        case LSM6DS_RATE_1_66K_HZ: Serial.println("1.66 KHz"); break; // Use underscore version
        // case LSM6DS_RATE_3K33_HZ: Serial.println("3.33 KHz"); break; // Remove - likely invalid enum
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
    // Start Serial communication at the high baud rate
    Serial.begin(SERIAL_BAUD_RATE);
    // delay(1000); // Optional short delay
    Serial.println("\n--- ESP32 I2S+IMU Data Sender ---");
    Serial.printf("Serial Rate: %d\n", SERIAL_BAUD_RATE);
    Serial.printf("I2S Sample Rate: %d Hz\n", I2S_SAMPLE_RATE);
    Serial.printf("I2S Bits Config: %d\n", I2S_BITS_PER_SAMPLE_CONFIG); // Prints the enum value

    // Configure I2S
    setupI2S();

    // --- Additions for IMU ---
    // Configure SPI and IMU
    setupIMU(); 
    // --- End Additions for IMU ---

    Serial.println("Setup complete. Starting data transmission...");
}


/**
 * @brief Main Loop Function
 */
void loop() {
    // === I2S Audio Reading and Sending ===
    int32_t i2s_read_buffer[I2S_BUFFER_SAMPLES];
    size_t bytes_read = 0; 

    esp_err_t result = i2s_read(I2S_PORT,
                                i2s_read_buffer,                       
                                I2S_BUFFER_SAMPLES * BYTES_PER_SAMPLE_BUFFER, 
                                &bytes_read,                           
                                portMAX_DELAY);                        

    if (result == ESP_OK && bytes_read > 0) {
        Serial.write((uint8_t*)i2s_read_buffer, bytes_read);
    }
    else if (result != ESP_OK) {
        // Handle I2S read error (optional)
    }

    // === IMU Reading and Sending ===
    // IMPORTANT LIMITATION: See comment in previous version.

    sensors_event_t accel;
    sensors_event_t gyro;
    sensors_event_t temp; 
    lsm6ds.getEvent(&accel, &gyro, &temp); 

    IMU_Data_Packet imu_packet;
    imu_packet.ax = accel.acceleration.x;
    imu_packet.ay = accel.acceleration.y;
    imu_packet.az = accel.acceleration.z;
    imu_packet.gx = gyro.gyro.x;
    imu_packet.gy = gyro.gyro.y;
    imu_packet.gz = gyro.gyro.z;

    Serial.write(imu_marker, sizeof(imu_marker)); 
    Serial.write((uint8_t*)&imu_packet, sizeof(IMU_Data_Packet)); 
}
// =========================================================================