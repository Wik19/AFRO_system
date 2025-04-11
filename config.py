import struct

# --- Serial Configuration ---
SERIAL_PORT = 'COM3'          # !!! CHANGE THIS to your ESP32's serial port !!!
BAUD_RATE = 2000000           # !!! MUST MATCH the ESP32's SERIAL_BAUD_RATE !!!
DURATION_SECONDS = 10         # How long to record data

# --- Audio Processing Configuration ---
# Note: ORIGINAL_SAMPLE_RATE is estimated based on ESP32 sending rate.
# Actual rate might vary slightly. If needed, adjust based on collected data count and duration.
ORIGINAL_AUDIO_SAMPLE_RATE = 48000 # Nominal rate from ESP32 config
AUDIO_BYTES_PER_SAMPLE = 4       # int32_t from ESP32
AUDIO_SAMPLE_FORMAT = '<i'       # Little-endian signed integer

AUDIO_DOWNSAMPLE_RATE = 50       # Downsample factor for audio plots/analysis
TARGET_AUDIO_NYQUIST_FREQ = (ORIGINAL_AUDIO_SAMPLE_RATE / AUDIO_DOWNSAMPLE_RATE) / 2.0
AUDIO_FILTER_ORDER = 6
AUDIO_AAF_CUTOFF_HZ = TARGET_AUDIO_NYQUIST_FREQ * 0.9 # Anti-aliasing filter cutoff

# --- IMU Data Configuration ---
IMU_MARKER = b'\xFF\xFE\xFD\xFC'  # Must match the marker sent by ESP32
IMU_PACKET_FORMAT = '<ffffff'     # 6 little-endian floats (ax,ay,az,gx,gy,gz)
IMU_PACKET_SIZE_BYTES = struct.calcsize(IMU_PACKET_FORMAT) # Should be 24

# --- Output Files ---
OUTPUT_FILENAME_AUDIO = "collected_data/final_audio_data.txt"
OUTPUT_FILENAME_IMU = "collected_data/imu_data.csv"