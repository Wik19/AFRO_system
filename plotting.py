import matplotlib.pyplot as plt
import numpy as np
import config
import math # For converting radians to degrees if desired

def plot_audio_data(original_samples, final_audio_samples, effective_audio_sample_rate, fft_audio_freq, fft_audio_magnitude):
    """Generates plots for audio data analysis."""
    if final_audio_samples is None or len(final_audio_samples) == 0:
        print("No final audio samples available for plotting.")
        return

    try:
        print("\nGenerating Audio plots...")
        fig_audio, ax_audio = plt.subplots(3, 1, figsize=(12, 9), sharex=False)
        fig_audio.suptitle("Audio Data Analysis")

        # Plot 1: Original Full Rate Data Snippet
        plot_limit = min(len(original_samples), int(config.ORIGINAL_AUDIO_SAMPLE_RATE * 1)) # Plot up to 1 sec original
        time_axis_original = np.arange(plot_limit) / config.ORIGINAL_AUDIO_SAMPLE_RATE
        ax_audio[0].plot(time_axis_original, original_samples[:plot_limit], label='Original (Snippet)', color='cyan', alpha=0.8)
        ax_audio[0].set_ylabel("Raw Value")
        ax_audio[0].set_xlabel("Time (s)")
        ax_audio[0].set_title(f"Original Audio (First {plot_limit/config.ORIGINAL_AUDIO_SAMPLE_RATE:.1f}s @ {config.ORIGINAL_AUDIO_SAMPLE_RATE} Hz)")
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
            ax_audio[2].set_xlim(0, config.TARGET_AUDIO_NYQUIST_FREQ * 1.1)
        else:
            ax_audio[2].text(0.5, 0.5, 'FFT data not available', horizontalalignment='center', verticalalignment='center')

        fig_audio.tight_layout(rect=[0, 0.03, 1, 0.95])
        return fig_audio # Return the figure object

    except Exception as plot_error:
        print(f"Error generating audio plot: {plot_error}")
        return None

def plot_imu_data(imu_data_np, imu_time_axis, effective_imu_sample_rate,
                  fft_imu_freq, fft_imu_magnitude_z,
                  velocity, position, angular_position, # Raw integrated angles (still received but not plotted)
                  fused_angles): # Added fused angles
    """Generates plots for IMU data analysis, focusing on raw data and fused orientation."""
    # Check if essential data is missing
    if imu_data_np is None:
         print("No IMU samples available for plotting (imu_data_np is None).")
         return None
    if imu_time_axis is None:
         print("IMU time axis not available, cannot plot time-series data.")
         # Optionally, could plot just raw data vs sample index if needed
         # For now, return None if time axis is missing
         return None

    try:
        print("\nGenerating IMU plots...")
        fig_imu, ax_imu = plt.subplots(3, 1, figsize=(12, 9), sharex=True) # 3 rows
        fig_imu.suptitle("IMU Data Analysis (Raw Data & Fused Orientation)")

        rate_text = f"{effective_imu_sample_rate:.1f} Hz" if effective_imu_sample_rate is not None else "N/A"

        # Plot 1: Accelerometer Data
        ax_imu[0].plot(imu_time_axis, imu_data_np[:, 0], label='Accel X', alpha=0.8)
        ax_imu[0].plot(imu_time_axis, imu_data_np[:, 1], label='Accel Y', alpha=0.8)
        ax_imu[0].plot(imu_time_axis, imu_data_np[:, 2], label='Accel Z', alpha=0.8)
        ax_imu[0].set_ylabel("Accel (m/s^2)")
        ax_imu[0].set_title(f"Accelerometer Data (Est. Rate: {rate_text})")
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

        # Plot 3: Fused Orientation Angles (Complementary Filter)
        # Check if fused_angles data is valid before plotting
        if fused_angles is not None and isinstance(fused_angles, np.ndarray) and fused_angles.shape[0] == len(imu_time_axis):
            fused_angles_deg = np.degrees(fused_angles)
            ax_imu[2].plot(imu_time_axis, fused_angles_deg[:, 0], label='Fused Roll', alpha=0.8)
            ax_imu[2].plot(imu_time_axis, fused_angles_deg[:, 1], label='Fused Pitch', alpha=0.8)
            ax_imu[2].plot(imu_time_axis, fused_angles_deg[:, 2], label='Fused Yaw (Drifts)', alpha=0.6, linestyle='--')
            ax_imu[2].set_ylabel("Angle (degrees)")
            ax_imu[2].set_title("Fused Orientation (Complementary Filter)")
            ax_imu[2].grid(True)
            ax_imu[2].legend()
        else:
             # Display message if fused angles cannot be plotted
             ax_imu[2].text(0.5, 0.5, 'Fused angle data not available or invalid',
                            horizontalalignment='center', verticalalignment='center', transform=ax_imu[2].transAxes)
             ax_imu[2].set_title("Fused Orientation")
             print("--- Skipping Fused Angle plot: Data not available or invalid. ---") # Debug print

        # Common X label for the bottom plot
        ax_imu[2].set_xlabel("Time (s)")

        fig_imu.tight_layout(rect=[0, 0.03, 1, 0.96])
        return fig_imu

    except Exception as plot_error:
         print(f"Error generating IMU plot: {plot_error}")
         import traceback
         traceback.print_exc() # Print detailed traceback for plotting errors
         return None

def show_plots():
    """Displays all generated Matplotlib plots."""
    print("\nDisplaying plot window(s)...")
    plt.show()
    print("Plot window(s) closed.")