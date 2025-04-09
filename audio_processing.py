import numpy as np
from scipy import signal
import numpy.fft as fft
import config # Import configuration constants

def process_audio(all_audio_samples):
    """
    Processes raw audio samples: applies anti-aliasing filter, downsamples,
    and calculates FFT.
    """
    final_audio_samples = None
    fft_audio_freq = None
    fft_audio_magnitude = None
    effective_audio_sample_rate = None

    if not all_audio_samples:
        print("\nNo audio samples received for processing.")
        return None, None, None, None

    print(f"\nProcessing {len(all_audio_samples)} collected audio samples...")
    samples_np = np.array(all_audio_samples)
    filtered_samples = None

    # --- Step 1: Apply Anti-Aliasing Filter ---
    try:
        print(f"Applying Audio Anti-Aliasing Filter (Lowpass < {config.AUDIO_AAF_CUTOFF_HZ:.2f} Hz)...")
        original_nyquist = 0.5 * config.ORIGINAL_AUDIO_SAMPLE_RATE
        if config.AUDIO_AAF_CUTOFF_HZ < original_nyquist:
            normalized_aaf_cutoff = config.AUDIO_AAF_CUTOFF_HZ / original_nyquist
            b, a = signal.butter(config.AUDIO_FILTER_ORDER, normalized_aaf_cutoff, btype='low', analog=False)
            filtered_samples = signal.filtfilt(b, a, samples_np)
            print("Audio anti-aliasing filter applied.")
        else:
            print("!!! Warning: Audio anti-aliasing cutoff frequency is too high. Skipping filter. !!!")
            filtered_samples = samples_np
    except Exception as filter_error:
        print(f"Error during audio filtering: {filter_error}. Using unfiltered data.")
        filtered_samples = samples_np

    # --- Step 2: Downsample the FILTERED audio data ---
    try:
        print(f"Downsampling filtered audio data by factor {config.AUDIO_DOWNSAMPLE_RATE}...")
        final_audio_samples = filtered_samples[::config.AUDIO_DOWNSAMPLE_RATE]
        effective_audio_sample_rate = config.ORIGINAL_AUDIO_SAMPLE_RATE / config.AUDIO_DOWNSAMPLE_RATE
        print(f"Audio downsampling complete. Final sample count: {len(final_audio_samples)}, Effective Rate: {effective_audio_sample_rate:.1f} Hz")
    except Exception as downsample_error:
        print(f"Error during audio downsampling: {downsample_error}")
        final_audio_samples = None # Indicate failure

    # --- Step 3: Calculate Audio FFT ---
    if final_audio_samples is not None and len(final_audio_samples) > 0:
        try:
            print("Calculating Audio FFT...")
            N = len(final_audio_samples) # Number of samples for FFT
            fft_result = fft.fft(final_audio_samples)
            fft_audio_freq = fft.fftfreq(N, d=1.0/effective_audio_sample_rate)
            fft_audio_magnitude = np.abs(fft_result)
            print("Audio FFT calculation complete.")

            # --- Optional: Save final audio data ---
            try:
                np.savetxt(config.OUTPUT_FILENAME_AUDIO, final_audio_samples, fmt='%d')
                print(f"Final audio data saved to '{config.OUTPUT_FILENAME_AUDIO}'")
            except Exception as save_error:
                 print(f"Error saving audio data: {save_error}")

        except Exception as fft_error:
             print(f"Error during audio FFT calculation: {fft_error}")
             fft_audio_freq = None
             fft_audio_magnitude = None
    else:
        print("No final audio samples after processing for FFT.")
        final_audio_samples = None # Ensure consistency

    return samples_np, final_audio_samples, effective_audio_sample_rate, fft_audio_freq, fft_audio_magnitude