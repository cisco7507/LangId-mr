import wave
import numpy as np
from langid_service.app.services.audio_io import load_audio_mono_16k, InvalidAudioError

def load_audio_mono_16k(file_path: str) -> np.ndarray:
    """
    Loads an audio file from the given path and returns a mono, 16kHz,
    32-bit float NumPy array in the range [-1.0, 1.0].

    For simple WAV files, this uses the Python standard library `wave`
    module directly. For other formats (MP3, AAC, G.711, etc.), it falls
    back to PyAV.

    Args:
        file_path: The path to the audio file.

    Returns:
        A NumPy array containing the audio waveform.

    Raises:
        InvalidAudioError: If the audio cannot be decoded or processed.
    """
    # First, try a lightweight path for WAV files using the standard library.
    try:
        if file_path.lower().endswith(".wav"):
            try:
                with wave.open(file_path, "rb") as wf:
                    sample_rate = wf.getframerate()
                    n_channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    n_frames = wf.getnframes()

                    if n_frames == 0:
                        raise InvalidAudioError("Audio file is empty.")

                    raw = wf.readframes(n_frames)

                # Map sample width to dtype and scaling.
                if sampwidth == 2:
                    # Signed 16-bit PCM.
                    dtype = np.int16
                    scale = 32768.0
                    audio = np.frombuffer(raw, dtype=dtype).astype(np.float32) / scale
                elif sampwidth == 1:
                    # Unsigned 8-bit PCM. Convert to signed float in [-1, 1].
                    dtype = np.uint8
                    audio_u8 = np.frombuffer(raw, dtype=dtype).astype(np.float32)
                    audio = (audio_u8 - 128.0) / 128.0
                else:
                    raise InvalidAudioError(f"Unsupported sample width: {sampwidth}")

                # Downmix to mono if needed.
                if n_channels > 1:
                    try:
                        audio = audio.reshape(-1, n_channels).mean(axis=1)
                    except ValueError as exc:
                        raise InvalidAudioError(f"Corrupt WAV channel data: {exc}") from exc

                # Naive resample to 16 kHz if the source rate is different.
                if sample_rate != 16000 and sample_rate > 0 and audio.size > 0:
                    # Simple linear interpolation; sufficient for tests and
                    # robust behavior without extra dependencies.
                    import math

                    target_len = int(math.ceil(len(audio) * 16000.0 / float(sample_rate)))
                    if target_len <= 0:
                        raise InvalidAudioError("Resampling produced no samples.")

                    x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False, dtype=np.float32)
                    x_new = np.linspace(0.0, 1.0, num=target_len, endpoint=False, dtype=np.float32)
                    audio = np.interp(x_new, x_old, audio).astype(np.float32)

                # Ensure final dtype is float32.
                return audio.astype(np.float32)

            except (wave.Error, OSError) as exc:
                # Fall through to the PyAV path below for anything `wave`
                # cannot handle. We do NOT wrap here so that the unified
                # handler below can convert to InvalidAudioError.
                pass

        # Fallback: use PyAV for general-purpose decoding.
        import av

        try:
            with av.open(file_path) as container:
                # Find the first audio stream.
                stream = None
                for s in container.streams:
                    if s.type == "audio":
                        stream = s
                        break

                if stream is None:
                    raise InvalidAudioError("No audio streams found in file.")

                resampler = av.AudioResampler(
                    format="s16",  # intermediate format
                    layout="mono",
                    rate=16000,
                )

                frames = []
                for frame in container.decode(stream):
                    frames.extend(resampler.resample(frame))

                if not frames:
                    raise InvalidAudioError("Audio file is empty or contains no valid frames.")

                # Concatenate resampled frames. `frame.to_ndarray()` should
                # already be int16 with shape (channels, samples) or (samples,).
                chunks = []
                for frame in frames:
                    arr = frame.to_ndarray()
                    arr = np.asarray(arr)
                    # Ensure 1D
                    if arr.ndim > 1:
                        arr = arr.reshape(-1)
                    chunks.append(arr.astype(np.int16))

                if not chunks:
                    raise InvalidAudioError("No audio data produced after resampling.")

                audio_i16 = np.concatenate(chunks)
                audio_f32 = audio_i16.astype(np.float32) / 32768.0
                return audio_f32

        except Exception as exc:
            # Any failure in PyAV decoding is normalized to InvalidAudioError.
            raise InvalidAudioError(f"Failed to decode audio via PyAV: {exc}") from exc

    except InvalidAudioError:
        # Pass through our own well-typed errors unchanged.
        raise
    except Exception as exc:
        # Any other unexpected exception is wrapped as InvalidAudioError so
        # callers and tests only ever see our domain-specific error type.
        raise InvalidAudioError(f"Unexpected error while loading audio: {exc}") from exc
