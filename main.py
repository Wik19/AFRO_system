import sys
import config
import serial_handler
import audio_processing
import imu_processing
import plotting
import traceback

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
        # Unpack the return values from process_imu, including fused_angles
        (imu_data_np,
         imu_time_axis,
         effective_imu_rate,
         fft_imu_freq,
         fft_imu_mag_z,
         imu_velocity,          # Still returned, even if not plotted
         imu_position,          # Still returned, even if not plotted
         imu_angular_position,  # Raw integrated angles (still returned)
         imu_fused_angles       # Fused angles from Complementary Filter
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
            # Pass the correct arguments to plot_imu_data, including fused_angles
            imu_fig = plotting.plot_imu_data(
                imu_data_np,
                imu_time_axis,
                effective_imu_rate,
                fft_imu_freq,
                fft_imu_mag_z,
                imu_velocity,         # Pass velocity (ignored by plotting function now)
                imu_position,         # Pass position (ignored by plotting function now)
                imu_angular_position, # Pass raw angles (ignored by plotting function now)
                imu_fused_angles      # Pass fused angles (used by plotting function)
            )

        # --- Step 5: Show Plots ---
        if audio_fig or imu_fig:
            plotting.show_plots()

    except KeyboardInterrupt:
        print("\nScript interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"\nAn unexpected error occurred in the main script: {e}")
        traceback.print_exc()  # Print detailed traceback
    finally:
        print("\nScript finished.")

if __name__ == "__main__":
    # Ensure you have necessary libraries installed:
    # pip install pyserial numpy scipy matplotlib
    main()