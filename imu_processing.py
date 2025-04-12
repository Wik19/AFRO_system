import numpy as np
import numpy.fft as fft
from scipy.integrate import cumulative_trapezoid
import math
import config

def process_imu(all_imu_samples, duration):
    """
    Processes raw IMU samples: converts to numpy array, estimates sample rate,
    calculates FFT, integrates accel/gyro, performs sensor fusion (Complementary Filter),
    and saves data. Handles cases with few or no samples more robustly.
    """
    # Initialize all potential return values to None or empty equivalents
    imu_data_np = None
    imu_time_axis = None
    effective_imu_sample_rate = None
    fft_imu_freq = None
    fft_imu_magnitude_z = None
    velocity = None
    position = None
    angular_position = None
    fused_angles = None

    COMP_FILTER_ALPHA = 0.98

    # --- Initial Check ---
    if not all_imu_samples:
        print("\nNo IMU samples received for processing.")
        return None, None, None, None, None, None, None, None, None

    print(f"\nProcessing {len(all_imu_samples)} collected IMU samples...")
    try:
        # Convert to numpy array first
        imu_data_np = np.array(all_imu_samples)
        if imu_data_np.ndim == 1: # Handle case of only one sample
             imu_data_np = imu_data_np.reshape(1, -1)
        if imu_data_np.shape[1] != 6:
             raise ValueError(f"IMU data has incorrect shape: {imu_data_np.shape}, expected (N, 6)")
        print(f"Successfully converted IMU samples to numpy array with shape: {imu_data_np.shape}")
    except Exception as e:
        print(f"Error converting IMU samples to numpy array: {e}")
        # Return None for everything if conversion fails
        return None, None, None, None, None, None, None, None, None

    num_samples = len(imu_data_np)

    # --- Check for sufficient data and duration for rate calculation ---
    can_calculate_rate = duration > 0 and num_samples > 1
    if can_calculate_rate:
        effective_imu_sample_rate = num_samples / duration
        print(f"Estimated Effective IMU Rate: {effective_imu_sample_rate:.2f} Hz")
        imu_time_axis = np.arange(num_samples) / effective_imu_sample_rate
        dt = 1.0 / effective_imu_sample_rate
    else:
        print("Not enough IMU data or duration to estimate sample rate or perform time-dependent processing (integration, fusion, FFT).")
        # We have imu_data_np, but cannot calculate time axis or derived values
        # Save raw data if available
        try:
            np.savetxt(config.OUTPUT_FILENAME_IMU, imu_data_np, delimiter=',',
                       header='accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z', comments='')
            print(f"Raw IMU data saved to '{config.OUTPUT_FILENAME_IMU}'")
        except Exception as save_error:
            print(f"Error saving raw IMU data: {save_error}")
        # Return the raw data and None for everything else
        return imu_data_np, None, None, None, None, None, None, None, None

    # --- Proceed with time-dependent processing only if rate is valid ---
    if can_calculate_rate:
        # --- Sensor Fusion (Complementary Filter) ---
        print("Performing sensor fusion (Complementary Filter)...")
        fused_roll = 0.0
        fused_pitch = 0.0
        fused_yaw = 0.0
        fused_angles_list = []
        try:
            for i in range(num_samples):
                ax, ay, az, gx, gy, gz = imu_data_np[i]
                # Basic check for valid numbers, skip sample if invalid
                if not all(np.isfinite([ax, ay, az, gx, gy, gz])):
                    print(f"Warning: Non-finite value encountered in IMU sample {i}, skipping fusion step.")
                    # Append previous values or estimated values if possible
                    if i > 0: fused_angles_list.append(fused_angles_list[-1])
                    else: fused_angles_list.append((0.0, 0.0, 0.0)) # Append zeros if first sample is bad
                    continue

                # Use try-except for math operations that might fail (e.g., sqrt of negative)
                try:
                    accel_roll = math.atan2(ay, math.sqrt(ax**2 + az**2))
                    accel_pitch = math.atan2(-ax, math.sqrt(ay**2 + az**2))
                except ValueError: # Handle potential math domain errors
                     print(f"Warning: Math domain error calculating accel angles for sample {i}. Using previous angles.")
                     accel_roll = fused_roll # Use previous fused value as fallback
                     accel_pitch = fused_pitch

                gyro_roll_delta = gx * dt
                gyro_pitch_delta = gy * dt
                gyro_yaw_delta = gz * dt
                fused_roll = COMP_FILTER_ALPHA * (fused_roll + gyro_roll_delta) + (1 - COMP_FILTER_ALPHA) * accel_roll
                fused_pitch = COMP_FILTER_ALPHA * (fused_pitch + gyro_pitch_delta) + (1 - COMP_FILTER_ALPHA) * accel_pitch
                fused_yaw += gyro_yaw_delta
                fused_angles_list.append((fused_roll, fused_pitch, fused_yaw))

            if fused_angles_list: # Ensure list is not empty
                 fused_angles = np.array(fused_angles_list)
                 print("Sensor fusion complete.")
            else:
                 print("Sensor fusion could not be performed (no valid samples?).")
                 fused_angles = None

        except Exception as fusion_error:
            print(f"Error during sensor fusion: {fusion_error}")
            fused_angles = None

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
            velocity = None
            position = None

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
            angular_position = None

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
            fft_imu_freq = None
            fft_imu_magnitude_z = None

    # --- Save IMU data (always save raw if available) ---
    try:
        np.savetxt(config.OUTPUT_FILENAME_IMU, imu_data_np, delimiter=',',
                   header='accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z', comments='')
        print(f"IMU data saved to '{config.OUTPUT_FILENAME_IMU}'")
    except Exception as save_error:
        print(f"Error saving IMU data: {save_error}")

    # --- Final Return ---
    # Return whatever was successfully calculated
    return (imu_data_np, imu_time_axis, effective_imu_sample_rate,
            fft_imu_freq, fft_imu_magnitude_z,
            velocity, position, angular_position,
            fused_angles)