import sys
import config
import serial_handler
import audio_processing
import imu_processing
import plotting

def main():
    """
    Main function to orchestrate the data receiving, processing, and plotting.
    """
    all_audio_samples = []
    all_imu_samples = []
    actual_duration = 0
    audio_fig = None
    imu_fig = None

    try:
        # --- Step 1: Receive Data ---
        all_audio_samples, all_imu_samples, actual_duration = serial_handler.receive_data(
            config.SERIAL_PORT,
            config.BAUD_RATE,
            config.DURATION_SECONDS
        )

        # --- Step 2: Process Audio Data ---
        (original_audio_samples_np,
         final_audio_samples,
         effective_audio_rate,
         fft_audio_freq,
         fft_audio_mag) = audio_processing.process_audio(all_audio_samples)

        # --- Step 3: Process IMU Data ---
        # Unpack the new return values from process_imu
        (imu_data_np,
         imu_time_axis,
         effective_imu_rate,
         fft_imu_freq,
         fft_imu_mag_z,
         imu_velocity,          # New
         imu_position,          # New
         imu_angular_position   # New
         ) = imu_processing.process_imu(all_imu_samples, actual_duration)

        # --- Step 4: Plotting ---
        if final_audio_samples is not None:
            audio_fig = plotting.plot_audio_data(
                original_audio_samples_np,
                final_audio_samples,
                effective_audio_rate,
                fft_audio_freq,
                fft_audio_mag
            )

        if imu_data_np is not None:
            # Pass the new integrated data to plot_imu_data
            imu_fig = plotting.plot_imu_data(
                imu_data_np,
                imu_time_axis,
                effective_imu_rate,
                fft_imu_freq,
                fft_imu_mag_z,
                imu_velocity,         # Pass velocity (optional, not plotted by default now)
                imu_position,         # Pass position
                imu_angular_position  # Pass angular position
            )

        # --- Step 5: Show Plots ---
        if audio_fig or imu_fig:
            plotting.show_plots()

    except KeyboardInterrupt:
        print("\nScript interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"\nAn unexpected error occurred in the main script: {e}")
        # Consider adding traceback for debugging
        import traceback
        traceback.print_exc()
    finally:
        print("\nScript finished.")
        # Consider removing sys.exit(0) if running interactively or within a larger app
        # sys.exit(0)

if __name__ == "__main__":
    # Ensure you have scipy installed: pip install scipy
    main()