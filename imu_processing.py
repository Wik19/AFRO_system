import numpy as np
import numpy.fft as fft
from scipy.integrate import cumulative_trapezoid # Import integration function
import config

def process_imu(all_imu_samples, duration):
    """
    Processes raw IMU samples: converts to numpy array, estimates sample rate,
    calculates FFT (example on Accel Z), integrates accel/gyro, and saves data.
    """
    imu_data_np = None
    imu_time_axis = None
    effective_imu_sample_rate = None
    fft_imu_freq = None
    fft_imu_magnitude_z = None
    velocity = None # Added
    position = None # Added
    angular_position = None # Added

    if not all_imu_samples:
        print("\nNo IMU samples received for processing.")
        return None, None, None, None, None, None, None, None # Updated return

    print(f"\nProcessing {len(all_imu_samples)} collected IMU samples...")
    try:
        imu_data_np = np.array(all_imu_samples) # Shape: (N_samples, 6)
    except Exception as e:
        print(f"Error converting IMU samples to numpy array: {e}")
        return None, None, None, None, None, None, None, None # Updated return

    # Estimate effective IMU sample rate
    if duration > 0 and len(all_imu_samples) > 1:
        effective_imu_sample_rate = len(all_imu_samples) / duration
        print(f"Estimated Effective IMU Rate: {effective_imu_sample_rate:.2f} Hz")
        imu_time_axis = np.arange(len(all_imu_samples)) / effective_imu_sample_rate
        dt = 1.0 / effective_imu_sample_rate

        # --- Integrate Acceleration to get Velocity and Position ---
        try:
            print("Integrating acceleration...")
            # Integrate accel to get velocity (initial velocity assumed 0)
            vel_x = cumulative_trapezoid(imu_data_np[:, 0], dx=dt, initial=0)
            vel_y = cumulative_trapezoid(imu_data_np[:, 1], dx=dt, initial=0)
            vel_z = cumulative_trapezoid(imu_data_np[:, 2], dx=dt, initial=0)
            velocity = np.column_stack((vel_x, vel_y, vel_z))

            # Integrate velocity to get position (initial position assumed 0)
            pos_x = cumulative_trapezoid(vel_x, dx=dt, initial=0)
            pos_y = cumulative_trapezoid(vel_y, dx=dt, initial=0)
            pos_z = cumulative_trapezoid(vel_z, dx=dt, initial=0)
            position = np.column_stack((pos_x, pos_y, pos_z))
            print("Integration for position complete.")
        except Exception as integ_accel_error:
            print(f"Error during acceleration integration: {integ_accel_error}")
            velocity = None
            position = None

        # --- Integrate Angular Velocity to get Angular Position ---
        try:
            print("Integrating angular velocity...")
            # Integrate gyro to get angular position (initial angle assumed 0)
            ang_pos_x = cumulative_trapezoid(imu_data_np[:, 3], dx=dt, initial=0)
            ang_pos_y = cumulative_trapezoid(imu_data_np[:, 4], dx=dt, initial=0)
            ang_pos_z = cumulative_trapezoid(imu_data_np[:, 5], dx=dt, initial=0)
            angular_position = np.column_stack((ang_pos_x, ang_pos_y, ang_pos_z))
            print("Integration for angular position complete.")
        except Exception as integ_gyro_error:
            print(f"Error during angular velocity integration: {integ_gyro_error}")
            angular_position = None

        # --- Calculate IMU FFT (Example: Accelerometer Z-axis) ---
        try:
            print("Calculating IMU FFT (Accel Z)...")
            accel_z = imu_data_np[:, 2]
            N_imu = len(accel_z)
            fft_imu_result = fft.fft(accel_z)
            fft_imu_freq = fft.fftfreq(N_imu, d=dt) # Use dt here
            fft_imu_magnitude_z = np.abs(fft_imu_result)
            print("IMU FFT calculation complete.")
        except Exception as fft_error:
            print(f"Error during IMU FFT calculation: {fft_error}")
            fft_imu_freq = None
            fft_imu_magnitude_z = None

    else:
        print("Not enough IMU data or duration to estimate sample rate, integrate, or calculate FFT.")
        effective_imu_sample_rate = None
        imu_time_axis = None

    # --- Save IMU data ---
    try:
        np.savetxt(config.OUTPUT_FILENAME_IMU, imu_data_np, delimiter=',',
                   header='accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z', comments='')
        print(f"IMU data saved to '{config.OUTPUT_FILENAME_IMU}'")
    except Exception as save_error:
        print(f"Error saving IMU data: {save_error}")

    # Return all processed data, including integrated values
    return (imu_data_np, imu_time_axis, effective_imu_sample_rate,
            fft_imu_freq, fft_imu_magnitude_z,
            velocity, position, angular_position) # Updated return