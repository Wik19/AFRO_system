import matplotlib.pyplot as plt
import numpy as np
import config

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
                  velocity, position, angular_position): # Updated signature
    """Generates plots for IMU data analysis, including integrated values."""
    if imu_data_np is None or imu_time_axis is None:
         print("No IMU samples available for plotting.")
         return None # Return None if no figure generated

    try:
        print("\nGenerating IMU plots...")
        # Increase figure height and number of subplots
        fig_imu, ax_imu = plt.subplots(4, 1, figsize=(12, 12), sharex=True) # 4 rows now
        fig_imu.suptitle("IMU Data Analysis (Includes Integrated Estimates)")

        # Plot 1: Accelerometer Data (Original)
        ax_imu[0].plot(imu_time_axis, imu_data_np[:, 0], label='Accel X', alpha=0.8)
        ax_imu[0].plot(imu_time_axis, imu_data_np[:, 1], label='Accel Y', alpha=0.8)
        ax_imu[0].plot(imu_time_axis, imu_data_np[:, 2], label='Accel Z', alpha=0.8)
        ax_imu[0].set_ylabel("Accel (m/s^2)")
        ax_imu[0].set_title(f"Accelerometer Data (Est. Rate: {effective_imu_sample_rate:.1f} Hz)")
        ax_imu[0].grid(True)
        ax_imu[0].legend()

        # Plot 2: Estimated Position (Integrated Acceleration)
        if position is not None:
            ax_imu[1].plot(imu_time_axis, position[:, 0], label='Position X (est.)', alpha=0.8)
            ax_imu[1].plot(imu_time_axis, position[:, 1], label='Position Y (est.)', alpha=0.8)
            ax_imu[1].plot(imu_time_axis, position[:, 2], label='Position Z (est.)', alpha=0.8)
            ax_imu[1].set_ylabel("Position (m)")
            ax_imu[1].set_title("Estimated Position (from Accel Integration - Prone to Drift)")
            ax_imu[1].grid(True)
            ax_imu[1].legend()
        else:
             ax_imu[1].text(0.5, 0.5, 'Position data not available', horizontalalignment='center', verticalalignment='center')
             ax_imu[1].set_title("Estimated Position")

        # Plot 3: Gyroscope Data (Original)
        ax_imu[2].plot(imu_time_axis, imu_data_np[:, 3], label='Gyro X', alpha=0.8)
        ax_imu[2].plot(imu_time_axis, imu_data_np[:, 4], label='Gyro Y', alpha=0.8)
        ax_imu[2].plot(imu_time_axis, imu_data_np[:, 5], label='Gyro Z', alpha=0.8)
        ax_imu[2].set_ylabel("Gyro (rad/s)")
        ax_imu[2].set_title("Gyroscope Data")
        ax_imu[2].grid(True)
        ax_imu[2].legend()

        # Plot 4: Estimated Angular Position (Integrated Gyro)
        if angular_position is not None:
            ax_imu[3].plot(imu_time_axis, angular_position[:, 0], label='Angle X (est.)', alpha=0.8)
            ax_imu[3].plot(imu_time_axis, angular_position[:, 1], label='Angle Y (est.)', alpha=0.8)
            ax_imu[3].plot(imu_time_axis, angular_position[:, 2], label='Angle Z (est.)', alpha=0.8)
            ax_imu[3].set_ylabel("Angle (rad)")
            ax_imu[3].set_title("Estimated Angular Position (from Gyro Integration - Prone to Drift)")
            ax_imu[3].grid(True)
            ax_imu[3].legend()
        else:
             ax_imu[3].text(0.5, 0.5, 'Angular Position data not available', horizontalalignment='center', verticalalignment='center')
             ax_imu[3].set_title("Estimated Angular Position")

        # Common X label for the bottom plot
        ax_imu[3].set_xlabel("Time (s)")

        fig_imu.tight_layout(rect=[0, 0.03, 1, 0.96]) # Adjust rect for suptitle
        return fig_imu

    except Exception as plot_error:
         print(f"Error generating IMU plot: {plot_error}")
         return None

def show_plots():
    """Displays all generated Matplotlib plots."""
    print("\nDisplaying plot window(s)...")
    plt.show()
    print("Plot window(s) closed.")