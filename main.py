import sys
import config
import network_handler
import audio_processing
import imu_processing
import plotting
import traceback
import numpy as np

def main():
    """
    Main function to orchestrate the data receiving (via TCP), processing, and plotting.
    """
    all_audio_samples = []
    all_imu_samples = []
    actual_duration = 0
    audio_fig = None
    imu_fig = None

    # Initialize processing results to None
    original_audio_samples_np = None
    final_audio_samples = None
    effective_audio_rate = None
    fft_audio_freq = None
    fft_audio_mag = None
    imu_data_np = None
    imu_time_axis = None
    effective_imu_rate = None
    fft_imu_freq = None
    fft_imu_mag_z = None
    imu_velocity = None
    imu_position = None
    imu_angular_position = None
    imu_fused_angles = None

    try:
        # --- Step 1: Receive Data (Using TCP Handler) ---
        all_audio_samples, all_imu_samples, actual_duration = network_handler.receive_data_tcp(
            config.ESP32_TCP_HOST,
            config.ESP32_TCP_PORT,
            config.DURATION_SECONDS
        )

        # --- Step 2: Process Audio Data (Only if data exists) ---
        if all_audio_samples:
            (original_audio_samples_np,
             final_audio_samples,
             effective_audio_rate,
             fft_audio_freq,
             fft_audio_mag) = audio_processing.process_audio(all_audio_samples)
        else:
            print("No audio samples received for processing.")

        # --- Step 3: Process IMU Data (Only if data exists) ---
        if all_imu_samples:
            (imu_data_np,
             imu_time_axis,
             effective_imu_rate,
             fft_imu_freq,
             fft_imu_mag_z,
             imu_velocity,
             imu_position,
             imu_angular_position,
             imu_fused_angles
             ) = imu_processing.process_imu(all_imu_samples, actual_duration)
        else:
            print("No IMU samples received for processing.")

        # --- Step 4: Plotting ---
        # Check if final_audio_samples is not None (it might be None if processing was skipped)
        if final_audio_samples is not None:
            audio_fig = plotting.plot_audio_data(
                original_audio_samples_np,
                final_audio_samples,
                effective_audio_rate,
                fft_audio_freq,
                fft_audio_mag
            )

        # Check if imu_data_np is not None (it might be None if processing was skipped)
        if imu_data_np is not None:
            imu_fig = plotting.plot_imu_data(
                imu_data_np,
                imu_time_axis,
                effective_imu_rate,
                fft_imu_freq,
                fft_imu_mag_z,
                imu_velocity,
                imu_position,
                imu_angular_position,
                imu_fused_angles
            )

        # --- Step 5: Show Plots ---
        if audio_fig or imu_fig:
            plotting.show_plots()

    except KeyboardInterrupt:
        print("\nScript interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"\nAn unexpected error occurred in the main script: {e}")
        traceback.print_exc()
    finally:
        print("\nScript finished.")

if __name__ == "__main__":
    # Ensure you have necessary libraries installed:
    # pip install numpy scipy matplotlib pyserial (pyserial no longer strictly needed if only using TCP)
    main()