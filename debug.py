import socket
import struct
import time
import config
import numpy as np

# Define the single-byte identifiers from the ESP32 code
AUDIO_DATA_ID = 0x01
IMU_DATA_ID = 0x02

def receive_data_tcp(host, port, duration_seconds):
    """
    Receives audio and IMU data from the ESP32 via TCP for a specified duration.

    Args:
        host (str): The IP address of the ESP32 TCP server.
        port (int): The port number of the ESP32 TCP server.
        duration_seconds (int): The duration to receive data in seconds.

    Returns:
        tuple: (list of audio samples, list of IMU samples, actual duration)
               Returns ([], [], 0) on connection failure or immediate error.
    """
    audio_samples = []
    imu_samples = []
    start_time = time.time()
    actual_duration = 0
    buffer = b''
    expected_audio_packet_size = config.AUDIO_CHUNK_SIZE * 2  # 2 bytes per sample
    # struct format for IMU data: 6 floats (ax, ay, az, gx, gy, gz) + 1 uint32_t (timestamp)
    # 6 * 4 bytes (float) + 1 * 4 bytes (uint32_t) = 28 bytes
    expected_imu_packet_size = 28

    print(f"Attempting to connect to TCP server at {host}:{port}...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((host, port))
            sock.settimeout(2.0) # Set a timeout for blocking operations
            print("TCP connection established.")
            start_time = time.time() # Reset start time after connection

            while time.time() - start_time < duration_seconds:
                try:
                    # Receive data in chunks
                    data = sock.recv(4096) # Increased buffer size
                    if not data:
                        print("Connection closed by server.")
                        break
                    buffer += data

                    # Process the buffer
                    while True:
                        # Check if we have at least one byte for the ID
                        if len(buffer) < 1:
                            break # Need more data for ID

                        data_id = buffer[0]

                        if data_id == AUDIO_DATA_ID:
                            # Check if we have the ID + full audio packet
                            if len(buffer) >= 1 + expected_audio_packet_size:
                                # Extract audio packet (excluding the ID byte)
                                audio_packet = buffer[1 : 1 + expected_audio_packet_size]
                                # Unpack audio samples (signed 16-bit integers)
                                num_samples = len(audio_packet) // 2
                                format_string = f'<{num_samples}h' # Little-endian short integers
                                unpacked_samples = struct.unpack(format_string, audio_packet)
                                audio_samples.extend(unpacked_samples)
                                # Remove the processed data (ID + packet) from buffer
                                buffer = buffer[1 + expected_audio_packet_size:]
                            else:
                                break # Need more data for the full audio packet

                        elif data_id == IMU_DATA_ID:
                            # Check if we have the ID + full IMU packet
                            if len(buffer) >= 1 + expected_imu_packet_size:
                                # Extract IMU packet (excluding the ID byte)
                                imu_packet = buffer[1 : 1 + expected_imu_packet_size]
                                try:
                                     # Unpack IMU data: 6 floats, 1 uint32_t (little-endian)
                                    unpacked_imu = struct.unpack('<ffffffI', imu_packet)
                                    imu_samples.append(unpacked_imu)
                                    # Remove the processed data (ID + packet) from buffer
                                    buffer = buffer[1 + expected_imu_packet_size:]
                                except struct.error as e:
                                    print(f"Error unpacking IMU data: {e}. Packet len: {len(imu_packet)}. Skipping.")
                                    buffer = buffer[1:] # Discard the problematic ID byte
                            else:
                                break # Need more data for the full IMU packet

                        else:
                            # Unknown data ID, discard the byte and continue searching
                            buffer = buffer[1:]

                except socket.timeout:
                    pass
                except BlockingIOError:
                     time.sleep(0.01)
                     pass

            actual_duration = time.time() - start_time
            print(f"\nData receiving finished after {actual_duration:.2f} seconds.")
            print(f"Total audio samples received: {len(audio_samples)}")
            print(f"Total IMU readings received: {len(imu_samples)}")

    except socket.timeout:
        print("Connection attempt timed out.")
        return [], [], 0
    except ConnectionRefusedError:
        print(f"Connection refused by the server at {host}:{port}. Is the ESP32 server running?")
        return [], [], 0
    except OSError as e:
        print(f"Network error: {e}")
        return [], [], 0
    except Exception as e:
        print(f"An unexpected error occurred during TCP communication: {e}")
        import traceback
        traceback.print_exc()
        return [], [], 0

    return audio_samples, imu_samples, actual_duration

receive_data_tcp("192.168.78.42", 8088, 10)