import numpy as np
from scipy.signal import butter, filtfilt, detrend
from scipy.integrate import cumulative_trapezoid
import config
import math

# ... (butter_lowpass, butter_lowpass_filter functions remain the same) ...

def process_imu(imu_samples_raw, duration):
    """
    Processes the raw IMU data including filtering, integration, and FFT.

    Args:
        imu_samples_raw (list): List of raw IMU samples (tuples with 7 elements: ax,ay,az,gx,gy,gz,timestamp).
        duration (float): The actual duration over which data was collected.

    Returns:
        tuple: Processed IMU data including numpy array, time axis, rates, FFT, etc.
               Returns None for components if processing fails or input is empty.
    """
    if not imu_samples_raw:
        print("IMU processing skipped: No raw samples provided.")
        return (None,) * 9 # Return tuple of Nones matching expected output count

    print(f"\nProcessing {len(imu_samples_raw)} collected IMU samples...")

    try:
        # Convert list of tuples (7 elements each) to a NumPy array
        # Keep all 7 columns for now
        imu_data_full_np = np.array(imu_samples_raw, dtype=np.float32)

        # Separate timestamps and sensor data
        timestamps_ms = imu_data_full_np[:, 6] # Timestamps are the 7th column (index 6)
        imu_data_np = imu_data_full_np[:, :6]  # Sensor data is the first 6 columns

        # Validate shape after selecting sensor data
        if imu_data_np.shape[1] != 6:
             raise ValueError(f"IMU sensor data has incorrect shape after extraction: {imu_data_np.shape}, expected (N, 6)")

        print(f"Successfully converted IMU samples to numpy array. Shape: {imu_data_np.shape}")

    except Exception as e:
        # Print shape of raw data if conversion fails
        raw_shape_info = "Unknown"
        if isinstance(imu_samples_raw, list) and len(imu_samples_raw) > 0:
             raw_shape_info = f"({len(imu_samples_raw)}, {len(imu_samples_raw[0])})" if isinstance(imu_samples_raw[0], tuple) else "Irregular"
        print(f"Error converting IMU samples to numpy array: {e}. Raw data info: List length {len(imu_samples_raw)}, First element shape: {raw_shape_info}")
        return (None,) * 9

    num_samples = imu_data_np.shape[0]
    if num_samples == 0:
        print("IMU processing skipped: No samples after conversion.")
        return (None,) * 9

    # --- Calculate Effective Sample Rate ---
    # Use actual duration if available and sensible, otherwise estimate from timestamps
    if duration > 0.1 and num_samples > 1:
         effective_imu_rate = num_samples / duration
         print(f"Calculated Effective IMU Rate (from duration): {effective_imu_rate:.2f} Hz")
         # Generate time axis based on duration
         imu_time_axis = np.linspace(0, duration, num_samples, endpoint=False)
    elif num_samples > 1:
        # Estimate rate from timestamps (convert ms to s)
        # Use diff on timestamps, handle potential issues like duplicate timestamps
        time_diffs = np.diff(timestamps_ms) / 1000.0
        valid_diffs = time_diffs[time_diffs > 0] # Avoid division by zero or negative time steps
        if len(valid_diffs) > 0:
            avg_time_step = np.mean(valid_diffs)
            effective_imu_rate = 1.0 / avg_time_step
            print(f"Calculated Effective IMU Rate (from timestamps): {effective_imu_rate:.2f} Hz")
        else:
            effective_imu_rate = config.IMU_SAMPLE_RATE # Fallback if timestamps are unusable
            print(f"Warning: Could not calculate rate from timestamps. Falling back to config rate: {effective_imu_rate} Hz")
        # Generate time axis from timestamps (convert ms to s)
        imu_time_axis = (timestamps_ms - timestamps_ms[0]) / 1000.0
    else:
         effective_imu_rate = config.IMU_SAMPLE_RATE # Fallback for single sample
         imu_time_axis = np.array([0.0])
         print(f"Warning: Only one IMU sample. Using config rate: {effective_imu_rate} Hz")


    # --- Filtering (Optional - Apply if needed) ---
    # Example: Apply low-pass filter to accelerometer Z data
    # cutoff_freq = effective_imu_rate * 0.4 # Example cutoff
    # order = 4
    # accel_z_filtered = butter_lowpass_filter(imu_data_np[:, 2], cutoff_freq, effective_imu_rate, order)
    # imu_data_np[:, 2] = accel_z_filtered # Replace original with filtered

    # --- Detrending (Remove linear drift) ---
    # Detrend accelerometer and gyroscope data separately
    try:
        imu_data_np[:, :3] = detrend(imu_data_np[:, :3], axis=0, type='linear') # Accelerometer
        imu_data_np[:, 3:] = detrend(imu_data_np[:, 3:], axis=0, type='linear') # Gyroscope
        print("IMU data detrended.")
    except ValueError as e:
        print(f"Warning: Could not detrend IMU data (possibly too few samples): {e}")


    # --- Integration for Velocity and Position (from Accelerometer) ---
    imu_velocity = np.zeros_like(imu_data_np[:, :3])
    imu_position = np.zeros_like(imu_data_np[:, :3])
    if num_samples > 1:
        # Integrate acceleration to get velocity (m/s) - assumes initial velocity is 0
        # Acceleration is in G's, convert to m/s^2 by multiplying by 9.81
        accel_mps2 = imu_data_np[:, :3] * 9.81
        imu_velocity = cumulative_trapezoid(accel_mps2, x=imu_time_axis, initial=0, axis=0)

        # Integrate velocity to get position (m) - assumes initial position is 0
        imu_position = cumulative_trapezoid(imu_velocity, x=imu_time_axis, initial=0, axis=0)
        print("IMU velocity and position calculated.")
    else:
        print("Skipping IMU integration: requires more than one sample.")


    # --- Integration for Angular Position (from Gyroscope) ---
    imu_angular_position = np.zeros_like(imu_data_np[:, 3:])
    if num_samples > 1:
        # Gyro data is in degrees per second (dps), convert to radians per second
        gyro_radps = np.radians(imu_data_np[:, 3:])
        # Integrate angular velocity to get angular position (radians) - assumes initial angle is 0
        imu_angular_position = cumulative_trapezoid(gyro_radps, x=imu_time_axis, initial=0, axis=0)
        # Convert back to degrees for easier interpretation if desired
        imu_angular_position = np.degrees(imu_angular_position)
        print("IMU angular position calculated.")
    else:
        print("Skipping IMU angular integration: requires more than one sample.")

    # --- Simple Complementary Filter for Orientation (Example) ---
    imu_fused_angles = np.zeros((num_samples, 2)) # Roll, Pitch
    if num_samples > 1 and effective_imu_rate > 0:
        dt = 1.0 / effective_imu_rate
        alpha = 0.98 # Complementary filter coefficient (adjust as needed)

        accel_roll_rad = np.arctan2(imu_data_np[:, 1], imu_data_np[:, 2]) # atan2(ay, az)
        accel_pitch_rad = np.arctan2(-imu_data_np[:, 0], np.sqrt(imu_data_np[:, 1]**2 + imu_data_np[:, 2]**2)) # atan2(-ax, sqrt(ay^2 + az^2))

        gyro_radps = np.radians(imu_data_np[:, 3:]) # gx, gy, gz in rad/s

        # Initialize first angle estimate
        imu_fused_angles[0, 0] = np.degrees(accel_roll_rad[0])
        imu_fused_angles[0, 1] = np.degrees(accel_pitch_rad[0])

        for i in range(1, num_samples):
            # Gyro integration step
            gyro_angle_x = imu_fused_angles[i-1, 0] + np.degrees(gyro_radps[i, 0]) * dt # Roll from gx
            gyro_angle_y = imu_fused_angles[i-1, 1] + np.degrees(gyro_radps[i, 1]) * dt # Pitch from gy

            # Complementary filter
            imu_fused_angles[i, 0] = alpha * gyro_angle_x + (1 - alpha) * np.degrees(accel_roll_rad[i]) # Roll
            imu_fused_angles[i, 1] = alpha * gyro_angle_y + (1 - alpha) * np.degrees(accel_pitch_rad[i]) # Pitch
        print("IMU fused angles (Roll, Pitch) calculated using complementary filter.")
    else:
        print("Skipping complementary filter: requires multiple samples and valid rate.")


    # --- FFT Calculation (Example: Accelerometer Z-axis) ---
    fft_imu_freq = None
    fft_imu_mag_z = None
    if num_samples > 1:
        try:
            accel_z = imu_data_np[:, 2] # Z-axis acceleration
            fft_result = np.fft.fft(accel_z)
            fft_freq = np.fft.fftfreq(num_samples, d=1.0/effective_imu_rate)

            # Only take the positive frequencies
            positive_freq_indices = np.where(fft_freq >= 0)
            fft_imu_freq = fft_freq[positive_freq_indices]
            # Calculate magnitude (and normalize if needed, e.g., by num_samples)
            fft_imu_mag_z = np.abs(fft_result[positive_freq_indices]) / num_samples
            print("IMU FFT calculated for Accelerometer Z-axis.")
        except Exception as e:
            print(f"Error calculating IMU FFT: {e}")
    else:
        print("Skipping IMU FFT: requires more than one sample.")


    print("IMU processing complete.")
    # Return the sensor data (N, 6), not the full data with timestamp
    return (imu_data_np, imu_time_axis, effective_imu_rate, fft_imu_freq, fft_imu_mag_z,
            imu_velocity, imu_position, imu_angular_position, imu_fused_angles)

# ... (rest of the file, if any) ...