# =========================================================================
# Python Code: Receive ESP32 Audio, Filter, Downsample, Plot Time & FFT
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

ORIGINAL_SAMPLE_RATE = 38400 #48000 scaled by 90/112.5 where 90 is the actual and 112.5 is the plotted freq.
SAMPLES_TO_RECEIVE_TOTAL = ORIGINAL_SAMPLE_RATE * 10 # Receive 10 seconds total
BYTES_PER_SAMPLE = 4
TOTAL_BYTES_TO_RECEIVE = SAMPLES_TO_RECEIVE_TOTAL * BYTES_PER_SAMPLE
DOWNSAMPLE_RATE = 50 # 100

TARGET_NYQUIST_FREQ = (ORIGINAL_SAMPLE_RATE / DOWNSAMPLE_RATE) / 2.0
FILTER_ORDER = 6
AAF_CUTOFF_HZ = TARGET_NYQUIST_FREQ * 0.9 # Anti-aliasing filter cutoff

# --- Data storage & Initialization ---
all_audio_samples = []
incomplete_sample_bytes = bytearray()
ser = None

print("--- Python ESP32 Audio Receiver & FFT Plotter ---")
# ... (Print config messages) ...

try:
    # --- Serial Connection & Data Collection Loop (remains the same) ---
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
    print(f"\nSuccessfully connected to {SERIAL_PORT}. Receiving data stream...")
    bytes_collected = 0
    start_time = time.time()

    while bytes_collected < TOTAL_BYTES_TO_RECEIVE:
        bytes_remaining = TOTAL_BYTES_TO_RECEIVE - bytes_collected
        bytes_to_read_now = min(4096, bytes_remaining)
        data_chunk = ser.read(bytes_to_read_now)
        if data_chunk:
            bytes_collected += len(data_chunk)
            incomplete_sample_bytes.extend(data_chunk)
            while len(incomplete_sample_bytes) >= BYTES_PER_SAMPLE:
                sample_bytes = incomplete_sample_bytes[:BYTES_PER_SAMPLE]
                incomplete_sample_bytes = incomplete_sample_bytes[BYTES_PER_SAMPLE:]
                try:
                    sample_value = struct.unpack('<i', sample_bytes)[0]
                    all_audio_samples.append(sample_value) # Store ALL samples
                except struct.error as e:
                    print(f"\nError unpacking sample bytes: {sample_bytes!r}. Error: {e}")
        else:
            print("\nWarning: Read timeout.")
            # break # Optional: Stop if timeout persists

    end_time = time.time()
    # ... (Print collection summary) ...
    duration = end_time - start_time
    print(f"\nFinished receiving.")
    print(f"Total Bytes Received: {bytes_collected} (Target was {TOTAL_BYTES_TO_RECEIVE})")
    print(f"Total Samples Received: {len(all_audio_samples)}")
    print(f"Duration: {duration:.2f} seconds")
    if duration > 0:
        print(f"Average Data Rate: {bytes_collected / duration / 1024:.2f} KB/s")


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


# --- Post-Processing ---
if all_audio_samples:
    print(f"\nProcessing {len(all_audio_samples)} collected samples...")
    samples_np = np.array(all_audio_samples)
    filtered_samples = None
    final_samples = None

    # --- Step 1: Apply Anti-Aliasing Filter ---
    try:
        print(f"Applying Anti-Aliasing Filter (Lowpass < {AAF_CUTOFF_HZ:.2f} Hz)...")
        original_nyquist = 0.5 * ORIGINAL_SAMPLE_RATE
        if AAF_CUTOFF_HZ < original_nyquist:
            normalized_aaf_cutoff = AAF_CUTOFF_HZ / original_nyquist
            b, a = signal.butter(FILTER_ORDER, normalized_aaf_cutoff, btype='low', analog=False)
            filtered_samples = signal.filtfilt(b, a, samples_np)
            print("Anti-aliasing filter applied.")
        else:
            print("!!! Warning: Anti-aliasing cutoff frequency is too high. Skipping filter. !!!")
            filtered_samples = samples_np
    except Exception as filter_error:
        print(f"Error during filtering: {filter_error}. Using unfiltered data.")
        filtered_samples = samples_np

    # --- Step 2: Downsample the FILTERED data ---
    try:
        print(f"Downsampling filtered data by factor {DOWNSAMPLE_RATE}...")
        final_samples = filtered_samples[::DOWNSAMPLE_RATE]
        print(f"Downsampling complete. Final sample count: {len(final_samples)}")
    except Exception as downsample_error:
        print(f"Error during downsampling: {downsample_error}")
        # Decide how to handle: maybe exit, maybe use filtered_samples?
        final_samples = None # Indicate failure

    # --- Step 3: Calculate FFT and Prepare for Plotting ---
    fft_freq = None
    fft_magnitude = None
    effective_sample_rate = ORIGINAL_SAMPLE_RATE / DOWNSAMPLE_RATE # For FFT freq axis

    if final_samples is not None and len(final_samples) > 0:
        try:
            print("Calculating FFT...")
            N = len(final_samples) # Number of samples for FFT
            # Calculate FFT - result is complex
            fft_result = fft.fft(final_samples)
            # Calculate frequency bins corresponding to FFT result
            # d is the sample spacing (1 / sample_rate)
            fft_freq = fft.fftfreq(N, d=1.0/effective_sample_rate)
            # Calculate magnitude (absolute value of complex FFT result)
            fft_magnitude = np.abs(fft_result)
            print("FFT calculation complete.")

            # --- Optional: Save final data ---
            output_filename = "final_audio_data.txt"
            np.savetxt(output_filename, final_samples, fmt='%d')
            print(f"Final data saved to '{output_filename}'")

        except Exception as fft_error:
             print(f"Error during FFT calculation: {fft_error}")

    # --- Step 4: Plotting ---
    if final_samples is not None and len(final_samples) > 0:
        try:
            print("\nGenerating plots...")
            # Create 3 subplots vertically aligned
            fig, ax = plt.subplots(3, 1, figsize=(12, 9)) # Width, Height in inches

            # Plot 1: Original Full Rate Data (or a snippet) - Optional but informative
            # To avoid plotting millions of points, let's plot a small segment
            plot_limit = min(len(samples_np), ORIGINAL_SAMPLE_RATE * 1) # Plot up to 1 sec original
            ax[0].plot(samples_np[:plot_limit], label='Original (Snippet)', color='cyan', alpha=0.8)
            ax[0].set_ylabel("Raw Value")
            ax[0].set_title(f"Audio Data (Original Sample Rate: {ORIGINAL_SAMPLE_RATE} Hz)")
            ax[0].grid(True)
            ax[0].legend()

            # Plot 2: Filtered and Downsampled Data (Time Domain)
            ax[1].plot(final_samples, label=f'Filtered (<{AAF_CUTOFF_HZ:.1f} Hz) & Downsampled', color='blue')
            ax[1].set_ylabel("Sample Value")
            ax[1].set_title(f"Processed Waveform (Effective Sample Rate: {effective_sample_rate:.1f} Hz)")
            ax[1].grid(True)
            ax[1].legend()

            # Plot 3: FFT Magnitude Spectrum
            if fft_freq is not None and fft_magnitude is not None:
                # Plot only the positive frequencies (up to Nyquist)
                positive_freq_indices = np.where(fft_freq >= 0)[0]
                # Find the index corresponding roughly to the Nyquist frequency
                nyquist_index = len(positive_freq_indices) // 2 + 1 # Usually N/2 point

                ax[2].plot(fft_freq[positive_freq_indices[:nyquist_index]],
                           fft_magnitude[positive_freq_indices[:nyquist_index]],
                           label='FFT Magnitude', color='red')
                ax[2].set_xlabel("Frequency (Hz)")
                ax[2].set_ylabel("Magnitude")
                ax[2].set_title("Frequency Spectrum of Processed Signal")
                ax[2].grid(True)
                ax[2].legend()
                # Optional: Limit x-axis if needed, e.g., plt.xlim(0, TARGET_NYQUIST_FREQ * 1.1)
            else:
                 ax[2].text(0.5, 0.5, 'FFT data not available', horizontalalignment='center', verticalalignment='center')


            fig.tight_layout() # Adjust layout to prevent labels overlapping
            print("Displaying plot window...")
            plt.show() # Display the plots
            print("Plot window closed.")

        except Exception as plot_error:
            print(f"Error generating plot: {plot_error}")
    else:
         print("No final samples available for plotting.")

else:
    print("\nNo audio samples were received.")

print("\nScript finished.")
sys.exit(0)
# =========================================================================