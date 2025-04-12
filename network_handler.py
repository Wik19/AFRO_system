import socket
import time
import struct
import config # Import configuration constants

def receive_data_tcp(host, port, duration_seconds):
    """
    Connects to a TCP server (ESP32), receives data for a specified duration,
    and parses it into audio and IMU samples.
    """
    all_audio_samples = []
    all_imu_samples = []
    data_buffer = bytearray()
    sock = None
    start_time = None
    actual_duration = 0
    bytes_received_total = 0

    print("--- Python ESP32 Audio & IMU Receiver (TCP) ---")
    print(f"Connecting to Server: {host}:{port}")
    print(f"Recording Duration: {duration_seconds} seconds")
    print(f"Expected Audio Rate: {config.ORIGINAL_AUDIO_SAMPLE_RATE} Hz")
    print(f"IMU Marker: {config.IMU_MARKER.hex().upper()}")
    print(f"IMU Packet Size: {config.IMU_PACKET_SIZE_BYTES} bytes")

    try:
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Set a timeout for blocking operations (e.g., connect, recv)
        sock.settimeout(5.0) # 5 second timeout for connection and reads

        # Connect the socket to the server's address and port
        server_address = (host, port)
        print(f"\nAttempting to connect to {host}:{port}...")
        sock.connect(server_address)
        print(f"Successfully connected to {host}:{port}. Receiving data stream for {duration_seconds} seconds...")
        # Set timeout for subsequent recv calls (can be shorter)
        sock.settimeout(1.0)

        start_time = time.time()
        last_status_time = start_time

        while (time.time() - start_time) < duration_seconds:
            current_time = time.time()
            if current_time - last_status_time >= 1.0:
                elapsed = current_time - start_time
                rate_kbps = (bytes_received_total / elapsed / 1024) if elapsed > 0 else 0
                print(f"Receiving... Time: {elapsed:.1f}s / {duration_seconds}s | Rate: {rate_kbps:.2f} KB/s", end='\r')
                last_status_time = current_time

            try:
                # Receive data from the server
                # Use a reasonably large buffer size
                data_chunk = sock.recv(4096)
                if data_chunk:
                    data_buffer.extend(data_chunk)
                    bytes_received_total += len(data_chunk)
                else:
                    # Connection closed by server
                    print("\nConnection closed by the server.")
                    break
            except socket.timeout:
                # No data received within the timeout period, continue loop
                # print("Socket timeout, continuing...") # Optional debug print
                time.sleep(0.001) # Avoid busy-waiting
                continue
            except socket.error as e:
                print(f"\nSocket error during receive: {e}")
                break # Exit loop on socket error

            # --- Parsing Logic (Identical to serial_handler) ---
            processed_bytes_this_pass = 0
            while True:
                marker_pos = data_buffer.find(config.IMU_MARKER, processed_bytes_this_pass)
                search_limit = marker_pos if marker_pos != -1 else len(data_buffer)

                # Process audio samples before the next marker (or end of buffer)
                while processed_bytes_this_pass + config.AUDIO_BYTES_PER_SAMPLE <= search_limit:
                    sample_bytes = data_buffer[processed_bytes_this_pass : processed_bytes_this_pass + config.AUDIO_BYTES_PER_SAMPLE]
                    try:
                        sample_value = struct.unpack(config.AUDIO_SAMPLE_FORMAT, sample_bytes)[0]
                        all_audio_samples.append(sample_value)
                    except struct.error as e:
                        print(f"\nError unpacking audio sample: {e}, bytes: {sample_bytes!r}")
                    processed_bytes_this_pass += config.AUDIO_BYTES_PER_SAMPLE

                # If no marker found, stop processing this chunk
                if marker_pos == -1:
                    break

                # Check if the complete IMU packet (marker + data) is in the buffer
                if marker_pos + len(config.IMU_MARKER) + config.IMU_PACKET_SIZE_BYTES <= len(data_buffer):
                    packet_start_index = marker_pos + len(config.IMU_MARKER)
                    packet_end_index = packet_start_index + config.IMU_PACKET_SIZE_BYTES
                    packet_bytes = data_buffer[packet_start_index:packet_end_index]
                    try:
                        imu_values = struct.unpack(config.IMU_PACKET_FORMAT, packet_bytes)
                        all_imu_samples.append(imu_values)
                    except struct.error as e:
                         print(f"\nError unpacking IMU packet: {e}, bytes: {packet_bytes!r}")
                    # Update processed bytes index to the end of the IMU packet
                    processed_bytes_this_pass = packet_end_index
                else:
                    # Marker found, but full IMU packet not yet received, wait for more data
                    break

            # Remove processed data from the buffer
            if processed_bytes_this_pass > 0:
                data_buffer = data_buffer[processed_bytes_this_pass:]
        # --- End of While Loop ---

        end_time = time.time()
        actual_duration = end_time - start_time if start_time else 0
        print("\nFinished receiving.")
        print(f"Total Duration: {actual_duration:.2f} seconds")
        print(f"Total Bytes Received: {bytes_received_total} ({bytes_received_total/1024:.2f} KB)")
        print(f"Audio Samples Received: {len(all_audio_samples)}")
        print(f"IMU Samples Received: {len(all_imu_samples)}")
        if actual_duration > 0:
            print(f"Average Audio Rate: {len(all_audio_samples) / actual_duration:.2f} Hz")
            print(f"Average IMU Rate: {len(all_imu_samples) / actual_duration:.2f} Hz")
            print(f"Average Data Rate: {(bytes_received_total / actual_duration / 1024):.2f} KB/s")

    except socket.timeout:
        print(f"\nCONNECTION TIMEOUT: Could not connect to {host}:{port} within the timeout period.")
    except socket.error as e:
        print(f"\nSOCKET ERROR: {e}")
    except KeyboardInterrupt:
        print("\n\nStopping data reception due to Ctrl+C.")
        if start_time: # Calculate duration if started
            actual_duration = time.time() - start_time
    except Exception as e:
        print(f"\nAn unexpected error occurred during network communication: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if sock:
            sock.close()
            print(f"Socket connection to {host}:{port} closed.")

    return all_audio_samples, all_imu_samples, actual_duration