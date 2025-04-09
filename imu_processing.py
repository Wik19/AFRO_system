import numpy as np
import numpy.fft as fft
import config # Import configuration constants

def process_imu(all_imu_samples, duration):
    """
    Processes raw IMU samples: converts to numpy array, estimates sample rate,
    calculates FFT (example on Accel Z), and saves data.
    """
    imu_data_np = None
    imu_time_axis = None
    effective_imu_sample_rate = None
    fft_imu_freq = None
    fft_imu_magnitude_z = None # Example: FFT for Accel Z

    if not all_imu_samples:
        print("\nNo IMU samples received for processing.")
        return None, None, None, None, None

    print(f"\nProcessing {len(all_imu_samples)} collected IMU samples...")
    try:
        imu_data_np = np.array(all_imu_samples) # Shape: (N_samples, 6)
    except Exception as e:
        print(f"Error converting IMU samples to numpy array: {e}")
        return None, None, None, None, None

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
            fft_imu_freq = None
            fft_imu_magnitude_z = None

    else:
        print("Not enough IMU data or duration to estimate sample rate or calculate FFT.")
        effective_imu_sample_rate = None
        imu_time_axis = None

    # --- Save IMU data ---
    try:
        # Save as CSV with header for clarity
        np.savetxt(config.OUTPUT_FILENAME_IMU, imu_data_np, delimiter=',',
                   header='accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z', comments='')
        print(f"IMU data saved to '{config.OUTPUT_FILENAME_IMU}'")
    except Exception as save_error:
        print(f"Error saving IMU data: {save_error}")

    return imu_data_np, imu_time_axis, effective_imu_sample_rate, fft_imu_freq, fft_imu_magnitude_z