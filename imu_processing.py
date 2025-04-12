import numpy as np
import numpy.fft as fft
from scipy.integrate import cumulative_trapezoid
import math # Import math for atan2, sqrt
import config

def process_imu(all_imu_samples, duration):
    """
    Processes raw IMU samples: converts to numpy array, estimates sample rate,
    calculates FFT, integrates accel/gyro, performs sensor fusion (Complementary Filter),
    and saves data. Ensures 9 values are always returned.
    """
    # Initialize all potential return values to None
    imu_data_np = None
    imu_time_axis = None
    effective_imu_sample_rate = None
    fft_imu_freq = None
    fft_imu_magnitude_z = None
    velocity = None
    position = None
    angular_position = None
    fused_angles = None # Added for fused Roll, Pitch, Yaw

    # Complementary Filter coefficient
    COMP_FILTER_ALPHA = 0.98

    # --- Initial Check ---
    if not all_imu_samples:
        print("\nNo IMU samples received for processing.")
        # Return 9 Nones if no samples
        return None, None, None, None, None, None, None, None, None

    print(f"\nProcessing {len(all_imu_samples)} collected IMU samples...")
    try:
        imu_data_np = np.array(all_imu_samples) # Shape: (N_samples, 6)
    except Exception as e:
        print(f"Error converting IMU samples to numpy array: {e}")
        # Return 9 Nones on conversion error
        return None, None, None, None, None, None, None, None, None

    num_samples = len(imu_data_np)

    # --- Check for sufficient data and duration ---
    if duration <= 0 or num_samples <= 1:
        print("Not enough IMU data or duration for processing.")
        # Save raw data if available, but return Nones for processed values
        if imu_data_np is not None:
            try:
                np.savetxt(config.OUTPUT_FILENAME_IMU, imu_data_np, delimiter=',',
                           header='accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z', comments='')
                print(f"IMU data saved to '{config.OUTPUT_FILENAME_IMU}'")
            except Exception as save_error:
                print(f"Error saving IMU data: {save_error}")
        # Return 9 Nones as processing cannot proceed
        return imu_data_np, None, None, None, None, None, None, None, None # Return raw data + 8 Nones

    # --- Proceed with processing if data is sufficient ---
    effective_imu_sample_rate = num_samples / duration
    print(f"Estimated Effective IMU Rate: {effective_imu_sample_rate:.2f} Hz")
    imu_time_axis = np.arange(num_samples) / effective_imu_sample_rate
    dt = 1.0 / effective_imu_sample_rate

    # --- Sensor Fusion (Complementary Filter) ---
    print("Performing sensor fusion (Complementary Filter)...")
    fused_roll = 0.0
    fused_pitch = 0.0
    fused_yaw = 0.0
    fused_angles_list = []
    try:
        for i in range(num_samples):
            ax, ay, az, gx, gy, gz = imu_data_np[i]
            accel_roll = math.atan2(ay, math.sqrt(ax**2 + az**2))
            accel_pitch = math.atan2(-ax, math.sqrt(ay**2 + az**2))
            gyro_roll_delta = gx * dt
            gyro_pitch_delta = gy * dt
            gyro_yaw_delta = gz * dt
            fused_roll = COMP_FILTER_ALPHA * (fused_roll + gyro_roll_delta) + (1 - COMP_FILTER_ALPHA) * accel_roll
            fused_pitch = COMP_FILTER_ALPHA * (fused_pitch + gyro_pitch_delta) + (1 - COMP_FILTER_ALPHA) * accel_pitch
            fused_yaw += gyro_yaw_delta
            fused_angles_list.append((fused_roll, fused_pitch, fused_yaw))
        fused_angles = np.array(fused_angles_list)
        print("Sensor fusion complete.")
    except Exception as fusion_error:
        print(f"Error during sensor fusion: {fusion_error}")
        fused_angles = None # Keep fused_angles as None on error

    # --- Integrate Acceleration (Optional) ---
    try:
        print("Integrating acceleration...")
        vel_x = cumulative_trapezoid(imu_data_np[:, 0], dx=dt, initial=0)
        vel_y = cumulative_trapezoid(imu_data_np[:, 1], dx=dt, initial=0)
        vel_z = cumulative_trapezoid(imu_data_np[:, 2], dx=dt, initial=0)
        velocity = np.column_stack((vel_x, vel_y, vel_z))
        pos_x = cumulative_trapezoid(vel_x, dx=dt, initial=0)
        pos_y = cumulative_trapezoid(vel_y, dx=dt, initial=0)
        pos_z = cumulative_trapezoid(vel_z, dx=dt, initial=0)
        position = np.column_stack((pos_x, pos_y, pos_z))
        print("Integration for position complete.")
    except Exception as integ_accel_error:
        print(f"Error during acceleration integration: {integ_accel_error}")
        velocity = None # Keep as None on error
        position = None # Keep as None on error

    # --- Integrate Angular Velocity (Optional) ---
    try:
        print("Integrating angular velocity (raw)...")
        ang_pos_x = cumulative_trapezoid(imu_data_np[:, 3], dx=dt, initial=0)
        ang_pos_y = cumulative_trapezoid(imu_data_np[:, 4], dx=dt, initial=0)
        ang_pos_z = cumulative_trapezoid(imu_data_np[:, 5], dx=dt, initial=0)
        angular_position = np.column_stack((ang_pos_x, ang_pos_y, ang_pos_z))
        print("Integration for raw angular position complete.")
    except Exception as integ_gyro_error:
        print(f"Error during angular velocity integration: {integ_gyro_error}")
        angular_position = None # Keep as None on error

    # --- Calculate IMU FFT (Example: Accel Z) ---
    try:
        print("Calculating IMU FFT (Accel Z)...")
        accel_z = imu_data_np[:, 2]
        N_imu = len(accel_z)
        fft_imu_result = fft.fft(accel_z)
        fft_imu_freq = fft.fftfreq(N_imu, d=dt)
        fft_imu_magnitude_z = np.abs(fft_imu_result)
        print("IMU FFT calculation complete.")
    except Exception as fft_error:
        print(f"Error during IMU FFT calculation: {fft_error}")
        fft_imu_freq = None # Keep as None on error
        fft_imu_magnitude_z = None # Keep as None on error

    # --- Save IMU data ---
    try:
        # Ensure directory exists if specified in config
        # import os
        # output_dir = os.path.dirname(config.OUTPUT_FILENAME_IMU)
        # if output_dir and not os.path.exists(output_dir):
        #     os.makedirs(output_dir)
        np.savetxt(config.OUTPUT_FILENAME_IMU, imu_data_np, delimiter=',',
                   header='accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z', comments='')
        print(f"IMU data saved to '{config.OUTPUT_FILENAME_IMU}'")
    except Exception as save_error:
        print(f"Error saving IMU data: {save_error}")

    # --- Final Return ---
    # This is the main return path when processing completes (or partially completes)
    # It will always return 9 values, some might be None if errors occurred above
    return (imu_data_np, imu_time_axis, effective_imu_sample_rate,
            fft_imu_freq, fft_imu_magnitude_z,
            velocity, position, angular_position,
            fused_angles)