# =========================================================================
# Python Code: Receive ESP32 Audio & IMU, Filter, Downsample, Plot Time & FFT
# =========================================================================
import serial
import time
import struct # For unpacking binary data
import sys    # For sys.exit
import matplotlib.pyplot as plt # Import plotting library
from scipy import signal      # Import signal processing library
import numpy as np            # Import numpy for array operations
import numpy.fft as fft       # Import numpy's FFT module

# --- Configuration ---
SERIAL_PORT = 'COM3'          # !!! CHANGE THIS to your ESP32's serial port !!!
BAUD_RATE = 2000000           # !!! MUST MATCH the ESP32's SERIAL_BAUD_RATE !!!
DURATION_SECONDS = 10         # How long to record data

# Audio Processing Config
# Note: ORIGINAL_SAMPLE_RATE is estimated based on ESP32 sending rate.
# Actual rate might vary slightly. If needed, adjust based on collected data count and duration.
ORIGINAL_AUDIO_SAMPLE_RATE = 48000 # Nominal rate from ESP32 config
AUDIO_BYTES_PER_SAMPLE = 4       # int32_t from ESP32
AUDIO_SAMPLE_FORMAT = '<i'       # Little-endian signed integer

AUDIO_DOWNSAMPLE_RATE = 50       # Downsample factor for audio plots/analysis
TARGET_AUDIO_NYQUIST_FREQ = (ORIGINAL_AUDIO_SAMPLE_RATE / AUDIO_DOWNSAMPLE_RATE) / 2.0
AUDIO_FILTER_ORDER = 6
AUDIO_AAF_CUTOFF_HZ = TARGET_AUDIO_NYQUIST_FREQ * 0.9 # Anti-aliasing filter cutoff

# IMU Data Config
IMU_MARKER = b'\xFF\xFE\xFD\xFC'  # Must match the marker sent by ESP32
IMU_PACKET_FORMAT = '<ffffff'     # 6 little-endian floats (ax,ay,az,gx,gy,gz)
IMU_PACKET_SIZE_BYTES = struct.calcsize(IMU_PACKET_FORMAT) # Should be 24

# --- Data storage & Initialization ---
all_audio_samples = []
all_imu_samples = [] # List to store tuples of (ax, ay, az, gx, gy, gz)
data_buffer = bytearray() # Buffer for incoming serial data
ser = None
start_time = None

print("--- Python ESP32 Audio & IMU Receiver & Plotter ---")
print(f"Serial Port: {SERIAL_PORT}, Baud Rate: {BAUD_RATE}")
print(f"Recording Duration: {DURATION_SECONDS} seconds")
print(f"Expected Audio Rate: {ORIGINAL_AUDIO_SAMPLE_RATE} Hz")
print(f"IMU Marker: {IMU_MARKER.hex().upper()}")
print(f"IMU Packet Size: {IMU_PACKET_SIZE_BYTES} bytes")

try:
    # --- Serial Connection & Data Collection Loop ---
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) # Use a shorter timeout
    print(f"\nSuccessfully connected to {SERIAL_PORT}. Receiving data stream for {DURATION_SECONDS} seconds...")
    
    start_time = time.time()
    last_status_time = start_time
    
    while (time.time() - start_time) < DURATION_SECONDS:
        # Print status periodically
        current_time = time.time()
        if current_time - last_status_time >= 1.0:
            print(f"Receiving... Time elapsed: {current_time - start_time:.1f}s / {DURATION_SECONDS}s", end='\r')
            last_status_time = current_time
            
        # Read available data
        bytes_waiting = ser.in_waiting
        if bytes_waiting > 0:
            data_chunk = ser.read(bytes_waiting)
            data_buffer.extend(data_chunk)
        else:
            # Optional short sleep if no data to prevent busy-waiting
            time.sleep(0.001) 
            continue # Skip processing if no new data

        # Process the buffer to extract audio samples and IMU packets
        processed_bytes_this_pass = 0
        while True:
            # Try to find the IMU marker first
            marker_pos = data_buffer.find(IMU_MARKER, processed_bytes_this_pass)

            # Process audio data before the marker (or until end of buffer if no marker)
            search_limit = marker_pos if marker_pos != -1 else len(data_buffer)
            
            while processed_bytes_this_pass + AUDIO_BYTES_PER_SAMPLE <= search_limit:
                sample_bytes = data_buffer[processed_bytes_this_pass : processed_bytes_this_pass + AUDIO_BYTES_PER_SAMPLE]
                try:
                    sample_value = struct.unpack(AUDIO_SAMPLE_FORMAT, sample_bytes)[0]
                    all_audio_samples.append(sample_value)
                except struct.error as e:
                    print(f"\nError unpacking audio sample: {e}, bytes: {sample_bytes!r}")
                    # Decide how to handle corrupted data - skipping sample
                processed_bytes_this_pass += AUDIO_BYTES_PER_SAMPLE

            # If no marker found in the buffer segment we checked, break inner loop
            if marker_pos == -1:
                break 

            # Marker found at marker_pos, check if we have the complete packet after it
            if marker_pos + len(IMU_MARKER) + IMU_PACKET_SIZE_BYTES <= len(data_buffer):
                packet_start_index = marker_pos + len(IMU_MARKER)
                packet_end_index = packet_start_index + IMU_PACKET_SIZE_BYTES
                packet_bytes = data_buffer[packet_start_index:packet_end_index]
                
                try:
                    imu_values = struct.unpack(IMU_PACKET_FORMAT, packet_bytes)
                    all_imu_samples.append(imu_values) # Store tuple (ax,ay,az,gx,gy,gz)
                except struct.error as e:
                     print(f"\nError unpacking IMU packet: {e}, bytes: {packet_bytes!r}")
                     # Skip corrupted packet
                
                # Update processed pointer past the marker and the packet
                processed_bytes_this_pass = packet_end_index 
            else:
                # Found marker but not enough data for the full packet yet. 
                # Break inner loop, wait for more data. The marker will be found again next time.
                break
        
        # Remove processed data from the start of the buffer
        if processed_bytes_this_pass > 0:
            data_buffer = data_buffer[processed_bytes_this_pass:]

    # --- End of collection loop ---
    end_time = time.time()
    duration = end_time - start_time
    print("\nFinished receiving.")
    print(f"Total Duration: {duration:.2f} seconds")
    print(f"Audio Samples Received: {len(all_audio_samples)}")
    print(f"IMU Samples Received: {len(all_imu_samples)}")
    if duration > 0:
        print(f"Average Audio Rate: {len(all_audio_samples) / duration:.2f} Hz")
        print(f"Average IMU Rate: {len(all_imu_samples) / duration:.2f} Hz")


except serial.SerialException as e:
    print(f"\nSERIAL ERROR: {e}")
except KeyboardInterrupt:
    print("\n\nStopping script due to Ctrl+C.")
except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")
finally:
    if ser and ser.is_open:
        ser.close()
        print(f"Serial port {SERIAL_PORT} closed.")


# --- Post-Processing: Audio ---
final_audio_samples = None
fft_audio_freq = None
fft_audio_magnitude = None
effective_audio_sample_rate = None

if all_audio_samples:
    print(f"\nProcessing {len(all_audio_samples)} collected audio samples...")
    samples_np = np.array(all_audio_samples)
    filtered_samples = None

    # --- Step 1: Apply Anti-Aliasing Filter ---
    try:
        print(f"Applying Audio Anti-Aliasing Filter (Lowpass < {AUDIO_AAF_CUTOFF_HZ:.2f} Hz)...")
        original_nyquist = 0.5 * ORIGINAL_AUDIO_SAMPLE_RATE
        if AUDIO_AAF_CUTOFF_HZ < original_nyquist:
            normalized_aaf_cutoff = AUDIO_AAF_CUTOFF_HZ / original_nyquist
            b, a = signal.butter(AUDIO_FILTER_ORDER, normalized_aaf_cutoff, btype='low', analog=False)
            filtered_samples = signal.filtfilt(b, a, samples_np)
            print("Audio anti-aliasing filter applied.")
        else:
            print("!!! Warning: Audio anti-aliasing cutoff frequency is too high. Skipping filter. !!!")
            filtered_samples = samples_np
    except Exception as filter_error:
        print(f"Error during audio filtering: {filter_error}. Using unfiltered data.")
        filtered_samples = samples_np

    # --- Step 2: Downsample the FILTERED audio data ---
    try:
        print(f"Downsampling filtered audio data by factor {AUDIO_DOWNSAMPLE_RATE}...")
        final_audio_samples = filtered_samples[::AUDIO_DOWNSAMPLE_RATE]
        effective_audio_sample_rate = ORIGINAL_AUDIO_SAMPLE_RATE / AUDIO_DOWNSAMPLE_RATE
        print(f"Audio downsampling complete. Final sample count: {len(final_audio_samples)}, Effective Rate: {effective_audio_sample_rate:.1f} Hz")
    except Exception as downsample_error:
        print(f"Error during audio downsampling: {downsample_error}")
        final_audio_samples = None # Indicate failure

    # --- Step 3: Calculate Audio FFT ---
    if final_audio_samples is not None and len(final_audio_samples) > 0:
        try:
            print("Calculating Audio FFT...")
            N = len(final_audio_samples) # Number of samples for FFT
            fft_result = fft.fft(final_audio_samples)
            fft_audio_freq = fft.fftfreq(N, d=1.0/effective_audio_sample_rate)
            fft_audio_magnitude = np.abs(fft_result)
            print("Audio FFT calculation complete.")

            # --- Optional: Save final audio data ---
            output_filename_audio = "final_audio_data.txt"
            np.savetxt(output_filename_audio, final_audio_samples, fmt='%d')
            print(f"Final audio data saved to '{output_filename_audio}'")

        except Exception as fft_error:
             print(f"Error during audio FFT calculation: {fft_error}")
else:
    print("\nNo audio samples received for processing.")


# --- Post-Processing: IMU ---
imu_data_np = None
imu_time_axis = None
effective_imu_sample_rate = None
fft_imu_freq = None
fft_imu_magnitude_z = None # Example: FFT for Accel Z

if all_imu_samples:
    print(f"\nProcessing {len(all_imu_samples)} collected IMU samples...")
    imu_data_np = np.array(all_imu_samples) # Shape: (N_samples, 6)
    
    # Estimate effective IMU sample rate
    if duration > 0 and len(all_imu_samples) > 1:
        effective_imu_sample_rate = len(all_imu_samples) / duration
        print(f"Estimated Effective IMU Rate: {effective_imu_sample_rate:.2f} Hz")
        # Create a time axis based on this estimated rate
        imu_time_axis = np.arange(len(all_imu_samples)) / effective_imu_sample_rate
        
        # --- Calculate IMU FFT (Example: Accelerometer Z-axis) ---
        try:
            print("Calculating IMU FFT (Accel Z)...")
            accel_z = imu_data_np[:, 2] # Get the 3rd column (index 2)
            N_imu = len(accel_z)
            fft_imu_result = fft.fft(accel_z)
            fft_imu_freq = fft.fftfreq(N_imu, d=1.0/effective_imu_sample_rate)
            fft_imu_magnitude_z = np.abs(fft_imu_result)
            print("IMU FFT calculation complete.")
        except Exception as fft_error:
            print(f"Error during IMU FFT calculation: {fft_error}")
            
    else:
        print("Not enough IMU data or duration to estimate sample rate or calculate FFT.")

    # --- Save IMU data ---
    try:
        output_filename_imu = "imu_data.csv"
        # Save as CSV with header for clarity
        np.savetxt(output_filename_imu, imu_data_np, delimiter=',', 
                   header='accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z', comments='')
        print(f"IMU data saved to '{output_filename_imu}'")
    except Exception as save_error:
        print(f"Error saving IMU data: {save_error}")
        
else:
     print("\nNo IMU samples received for processing.")


# --- Plotting ---
# Plot Audio Data (if available)
if final_audio_samples is not None and len(final_audio_samples) > 0:
    try:
        print("\nGenerating Audio plots...")
        fig_audio, ax_audio = plt.subplots(3, 1, figsize=(12, 9), sharex=False) 
        fig_audio.suptitle("Audio Data Analysis")

        # Plot 1: Original Full Rate Data Snippet
        plot_limit = min(len(samples_np), int(ORIGINAL_AUDIO_SAMPLE_RATE * 1)) # Plot up to 1 sec original
        time_axis_original = np.arange(plot_limit) / ORIGINAL_AUDIO_SAMPLE_RATE
        ax_audio[0].plot(time_axis_original, samples_np[:plot_limit], label='Original (Snippet)', color='cyan', alpha=0.8)
        ax_audio[0].set_ylabel("Raw Value")
        ax_audio[0].set_xlabel("Time (s)")
        ax_audio[0].set_title(f"Original Audio (First {plot_limit/ORIGINAL_AUDIO_SAMPLE_RATE:.1f}s @ {ORIGINAL_AUDIO_SAMPLE_RATE} Hz)")
        ax_audio[0].grid(True)
        ax_audio[0].legend()

        # Plot 2: Filtered and Downsampled Audio Data (Time Domain)
        time_axis_processed = np.arange(len(final_audio_samples)) / effective_audio_sample_rate
        ax_audio[1].plot(time_axis_processed, final_audio_samples, label=f'Filtered & Downsampled', color='blue')
        ax_audio[1].set_ylabel("Sample Value")
        ax_audio[1].set_xlabel("Time (s)")
        ax_audio[1].set_title(f"Processed Audio Waveform (Effective Rate: {effective_audio_sample_rate:.1f} Hz)")
        ax_audio[1].grid(True)
        ax_audio[1].legend()

        # Plot 3: Audio FFT Magnitude Spectrum
        if fft_audio_freq is not None and fft_audio_magnitude is not None:
            positive_freq_indices = np.where(fft_audio_freq >= 0)[0]
            ax_audio[2].plot(fft_audio_freq[positive_freq_indices],
                             fft_audio_magnitude[positive_freq_indices],
                             label='FFT Magnitude', color='red')
            ax_audio[2].set_xlabel("Frequency (Hz)")
            ax_audio[2].set_ylabel("Magnitude")
            ax_audio[2].set_title("Audio Frequency Spectrum")
            ax_audio[2].grid(True)
            ax_audio[2].legend()
            # Optional: Zoom on relevant frequency range
            ax_audio[2].set_xlim(0, TARGET_AUDIO_NYQUIST_FREQ * 1.1) 
        else:
            ax_audio[2].text(0.5, 0.5, 'FFT data not available', horizontalalignment='center', verticalalignment='center')

        fig_audio.tight_layout(rect=[0, 0.03, 1, 0.95]) # Adjust layout to prevent title overlap
        
    except Exception as plot_error:
        print(f"Error generating audio plot: {plot_error}")
else:
    print("No final audio samples available for plotting.")

# Plot IMU Data (if available)
if imu_data_np is not None and imu_time_axis is not None:
    try:
        print("\nGenerating IMU plots...")
        fig_imu, ax_imu = plt.subplots(3, 1, figsize=(12, 9), sharex=True) # Share time axis
        fig_imu.suptitle("IMU Data Analysis")

        # Plot 1: Accelerometer Data
        ax_imu[0].plot(imu_time_axis, imu_data_np[:, 0], label='Accel X', alpha=0.8)
        ax_imu[0].plot(imu_time_axis, imu_data_np[:, 1], label='Accel Y', alpha=0.8)
        ax_imu[0].plot(imu_time_axis, imu_data_np[:, 2], label='Accel Z', alpha=0.8)
        ax_imu[0].set_ylabel("Accel (m/s^2)")
        ax_imu[0].set_title(f"Accelerometer Data (Estimated Rate: {effective_imu_sample_rate:.1f} Hz)")
        ax_imu[0].grid(True)
        ax_imu[0].legend()

        # Plot 2: Gyroscope Data
        ax_imu[1].plot(imu_time_axis, imu_data_np[:, 3], label='Gyro X', alpha=0.8)
        ax_imu[1].plot(imu_time_axis, imu_data_np[:, 4], label='Gyro Y', alpha=0.8)
        ax_imu[1].plot(imu_time_axis, imu_data_np[:, 5], label='Gyro Z', alpha=0.8)
        ax_imu[1].set_ylabel("Gyro (rad/s)")
        ax_imu[1].set_title("Gyroscope Data")
        ax_imu[1].grid(True)
        ax_imu[1].legend()
        
        # Plot 3: IMU FFT (Example: Accel Z)
        if fft_imu_freq is not None and fft_imu_magnitude_z is not None:
             positive_freq_indices_imu = np.where(fft_imu_freq >= 0)[0]
             ax_imu[2].plot(fft_imu_freq[positive_freq_indices_imu],
                             fft_imu_magnitude_z[positive_freq_indices_imu],
                             label='Accel Z FFT Mag', color='purple')
             ax_imu[2].set_xlabel("Frequency (Hz)")
             ax_imu[2].set_ylabel("Magnitude")
             ax_imu[2].set_title("IMU Accel Z Frequency Spectrum")
             ax_imu[2].grid(True)
             ax_imu[2].legend()
             # Optional: Zoom on relevant frequency range (e.g., up to half the estimated sample rate)
             if effective_imu_sample_rate:
                 ax_imu[2].set_xlim(0, effective_imu_sample_rate / 2) 
        else:
             ax_imu[2].text(0.5, 0.5, 'IMU FFT data not available', horizontalalignment='center', verticalalignment='center')


        fig_imu.tight_layout(rect=[0, 0.03, 1, 0.95]) # Adjust layout

    except Exception as plot_error:
         print(f"Error generating IMU plot: {plot_error}")
else:
     print("No IMU samples available for plotting.")


# Show all plots created
if (final_audio_samples is not None and len(final_audio_samples) > 0) or \
   (imu_data_np is not None and imu_time_axis is not None):
    print("\nDisplaying plot window(s)...")
    plt.show()
    print("Plot window(s) closed.")

print("\nScript finished.")
sys.exit(0)
# =========================================================================