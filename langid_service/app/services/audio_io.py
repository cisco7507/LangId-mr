# langid_service/app/services/audio_io.py
import numpy as np
try:
    import av
except Exception:
    # PyAV is optional; the loader will fall back to the stdlib `wave`
    # and `soundfile` backends when PyAV is not available in the
    # environment (e.g. during lightweight local testing).
    av = None
import wave
import soundfile as sf
from io import BytesIO

class InvalidAudioError(ValueError):
    """Custom exception for audio processing errors."""
    pass

def load_audio_mono_16k(file_path: str) -> np.ndarray:
    """
    Loads an audio file from the given path and returns a mono, 16kHz,
    32-bit float NumPy array in the range [-1.0, 1.0].

    This function first tries to parse the file as a simple WAV using the
    standard library `wave` module (which does not care about file extension),
    and falls back to PyAV for more complex formats.

    Raises:
        InvalidAudioError: If the audio cannot be decoded or processed.
    """
    try:
        # --- Fast path: standard WAV via wave ---
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
            elif sampwidth == 3:
                # 24-bit PCM (3 bytes per sample) — not directly supported by
                # NumPy dtypes. Convert from packed little-endian 3-byte words
                # into signed 32-bit integers, then normalize to [-1, 1].
                # Layout: little-endian bytes [b0, b1, b2] => value = b0 | b1<<8 | b2<<16
                b = np.frombuffer(raw, dtype=np.uint8)
                if b.size % 3 != 0:
                    raise InvalidAudioError("Corrupt WAV: unexpected byte length for 24-bit samples")
                # reshape to (n_samples * n_channels, 3)
                b = b.reshape(-1, 3)
                # assemble little-endian 24-bit values into 32-bit ints
                vals = (b[:, 0].astype(np.int32)
                        | (b[:, 1].astype(np.int32) << 8)
                        | (b[:, 2].astype(np.int32) << 16))
                # sign-extend 24-bit to 32-bit
                sign_mask = 1 << 23
                vals = np.where(vals & sign_mask, vals - (1 << 24), vals).astype(np.int32)
                audio = vals.astype(np.float32) / float(1 << 23)
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
                import math

                target_len = int(math.ceil(len(audio) * 16000.0 / float(sample_rate)))
                if target_len <= 0:
                    raise InvalidAudioError("Resampling produced no samples.")

                x_old = np.linspace(
                    0.0, 1.0, num=len(audio), endpoint=False, dtype=np.float32
                )
                x_new = np.linspace(
                    0.0, 1.0, num=target_len, endpoint=False, dtype=np.float32
                )
                audio = np.interp(x_new, x_old, audio).astype(np.float32)

            # Ensure final dtype is float32.
            return audio.astype(np.float32)

        except (wave.Error, OSError):
            # Not a simple WAV, fall through to PyAV.
            pass

        # --- Fallback: PyAV for general formats ---
        try:
            with av.open(file_path) as container:
                # Find first audio stream.
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
                    raise InvalidAudioError(
                        "Audio file is empty or contains no valid frames."
                    )

                chunks = []
                for frame in frames:
                    arr = frame.to_ndarray()
                    arr = np.asarray(arr)
                    if arr.ndim > 1:
                        arr = arr.reshape(-1)
                    chunks.append(arr.astype(np.int16))

                if not chunks:
                    raise InvalidAudioError("No audio data produced after resampling.")

                audio_i16 = np.concatenate(chunks)
                audio_f32 = audio_i16.astype(np.float32) / 32768.0
                return audio_f32

        except Exception as exc:
            # Any failure in PyAV decoding is normalized.
            raise InvalidAudioError(f"Failed to decode audio via PyAV: {exc}") from exc

    except InvalidAudioError:
        # Pass through domain-specific errors unchanged.
        raise
    except Exception as exc:
        # Normalize unexpected exceptions into InvalidAudioError for callers.
        raise InvalidAudioError(f"Unexpected error while loading audio: {exc}") from exc
