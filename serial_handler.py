import serial
import time
import struct
import config

def receive_data(port, baud_rate, duration_seconds):
    """
    Connects to the serial port, receives data for a specified duration,
    and parses it into audio and IMU samples.
    """
    all_audio_samples = []
    all_imu_samples = []
    data_buffer = bytearray()
    ser = None
    start_time = None
    actual_duration = 0

    print("--- Python ESP32 Audio & IMU Receiver ---")
    print(f"Serial Port: {port}, Baud Rate: {baud_rate}")
    print(f"Recording Duration: {duration_seconds} seconds")
    print(f"Expected Audio Rate: {config.ORIGINAL_AUDIO_SAMPLE_RATE} Hz")
    print(f"IMU Marker: {config.IMU_MARKER.hex().upper()}")
    print(f"IMU Packet Size: {config.IMU_PACKET_SIZE_BYTES} bytes")

    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        print(f"\nSuccessfully connected to {port}. Receiving data stream for {duration_seconds} seconds...")

        start_time = time.time()
        last_status_time = start_time

        while (time.time() - start_time) < duration_seconds:
            current_time = time.time()
            if current_time - last_status_time >= 1.0:
                print(f"Receiving... Time elapsed: {current_time - start_time:.1f}s / {duration_seconds}s", end='\r')
                last_status_time = current_time

            bytes_waiting = ser.in_waiting
            if bytes_waiting > 0:
                data_chunk = ser.read(bytes_waiting)
                data_buffer.extend(data_chunk)
            else:
                time.sleep(0.001)
                continue

            processed_bytes_this_pass = 0
            while True:
                marker_pos = data_buffer.find(config.IMU_MARKER, processed_bytes_this_pass)
                search_limit = marker_pos if marker_pos != -1 else len(data_buffer)

                while processed_bytes_this_pass + config.AUDIO_BYTES_PER_SAMPLE <= search_limit:
                    sample_bytes = data_buffer[processed_bytes_this_pass : processed_bytes_this_pass + config.AUDIO_BYTES_PER_SAMPLE]
                    try:
                        sample_value = struct.unpack(config.AUDIO_SAMPLE_FORMAT, sample_bytes)[0]
                        all_audio_samples.append(sample_value)
                    except struct.error as e:
                        print(f"\nError unpacking audio sample: {e}, bytes: {sample_bytes!r}")
                    processed_bytes_this_pass += config.AUDIO_BYTES_PER_SAMPLE

                if marker_pos == -1:
                    break

                if marker_pos + len(config.IMU_MARKER) + config.IMU_PACKET_SIZE_BYTES <= len(data_buffer):
                    packet_start_index = marker_pos + len(config.IMU_MARKER)
                    packet_end_index = packet_start_index + config.IMU_PACKET_SIZE_BYTES
                    packet_bytes = data_buffer[packet_start_index:packet_end_index]
                    try:
                        imu_values = struct.unpack(config.IMU_PACKET_FORMAT, packet_bytes)
                        all_imu_samples.append(imu_values)
                    except struct.error as e:
                         print(f"\nError unpacking IMU packet: {e}, bytes: {packet_bytes!r}")
                    processed_bytes_this_pass = packet_end_index
                else:
                    break

            if processed_bytes_this_pass > 0:
                data_buffer = data_buffer[processed_bytes_this_pass:]

        end_time = time.time()
        actual_duration = end_time - start_time
        print("\nFinished receiving.")
        print(f"Total Duration: {actual_duration:.2f} seconds")
        print(f"Audio Samples Received: {len(all_audio_samples)}")
        print(f"IMU Samples Received: {len(all_imu_samples)}")
        if actual_duration > 0:
            print(f"Average Audio Rate: {len(all_audio_samples) / actual_duration:.2f} Hz")
            print(f"Average IMU Rate: {len(all_imu_samples) / actual_duration:.2f} Hz")

    except serial.SerialException as e:
        print(f"\nSERIAL ERROR: {e}")
        # Re-raise or handle differently if needed in main
    except KeyboardInterrupt:
        print("\n\nStopping data reception due to Ctrl+C.")
        if start_time: # Calculate duration if started
            actual_duration = time.time() - start_time
    except Exception as e:
        print(f"\nAn unexpected error occurred during serial communication: {e}")
        # Re-raise or handle differently if needed in main
    finally:
        if ser and ser.is_open:
            ser.close()
            print(f"Serial port {port} closed.")

    return all_audio_samples, all_imu_samples, actual_duration