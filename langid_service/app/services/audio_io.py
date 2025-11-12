# langid_service/app/services/audio_io.py
import numpy as np
import av
import soundfile as sf
from io import BytesIO

class InvalidAudioError(ValueError):
    """Custom exception for audio processing errors."""
    pass

def load_audio_mono_16k(file_path: str) -> np.ndarray:
    """
    Loads an audio file from the given path, converts it to a 16kHz,
    mono, 32-bit float NumPy array. This function provides a robust
    decoding path with fallbacks.

    Supported formats include WAV, MP3, AAC, and G.711 A-Law.

    Args:
        file_path: The path to the audio file.

    Returns:
        A NumPy array containing the audio waveform.

    Raises:
        InvalidAudioError: If the audio cannot be decoded or processed.
    """
    try:
        # PyAV is the most robust and handles the most formats
        with av.open(file_path) as container:
            stream = container.streams.audio[0]
            # Set up the resampler to convert to 16kHz mono float32
            resampler = av.AudioResampler(
                format="s16",  # A common intermediate format
                layout="mono",
                rate=16000,
            )
            frames = []
            for frame in container.decode(stream):
                frames.extend(resampler.resample(frame))

            if not frames:
                 raise InvalidAudioError("Audio file is empty or contains no valid frames.")

            # Concatenate resampled frames
            audio_data = np.concatenate([np.frombuffer(frame.to_ndarray(), dtype=np.int16) for frame in frames])
            # Convert to float32 and normalize
            return audio_data.astype(np.float32) / 32768.0

    except (av.AVError, IndexError, StopIteration) as e:
        # Fallback to soundfile for tricky WAVs
        try:
            with open(file_path, "rb") as f:
                data, samplerate = sf.read(BytesIO(f.read()))

            # If stereo, convert to mono
            if data.ndim > 1:
                data = data.mean(axis=1)

            # If not 16kHz, this will fail here, which is intended
            if samplerate != 16000:
                 raise InvalidAudioError(
                    f"Unsupported sample rate: {samplerate}. Must be 16kHz."
                )

            return data.astype(np.float32)

        except Exception as sf_e:
            raise InvalidAudioError(
                f"Failed to decode audio with all available backends. "
                f"PyAV error: {e}. SoundFile error: {sf_e}"
            )
    except Exception as e:
        raise InvalidAudioError(f"An unexpected error occurred during audio processing: {e}")
