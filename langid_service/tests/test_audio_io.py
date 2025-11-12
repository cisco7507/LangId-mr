# langid_service/tests/test_audio_io.py
import pytest
import numpy as np
from pathlib import Path
from langid_service.app.services.audio_io import load_audio_mono_16k, InvalidAudioError

# Create dummy audio files for testing
@pytest.fixture(scope="session")
def audio_files(tmpdir_factory):
    tmpdir = tmpdir_factory.mktemp("data")
    files = {
        "wav": tmpdir.join("test.wav"),
        "mp3": tmpdir.join("test.mp3"),
        "aac": tmpdir.join("test.m4a"),
        "alaw": tmpdir.join("test_alaw.wav"),
        "invalid": tmpdir.join("invalid.txt"),
    }
    # Create a dummy WAV file
    import wave
    with wave.open(str(files["wav"]), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(np.random.randint(-32768, 32767, 16000, dtype=np.int16).tobytes())
    # Create dummy MP3, AAC, and A-Law files (these will be empty, but the test will check for the error)
    for ext in ["mp3", "aac", "alaw"]:
        files[ext].write("")
    # Create an invalid file
    files["invalid"].write("this is not an audio file")
    return {k: Path(v) for k, v in files.items()}

def test_load_wav(audio_files):
    """
    Tests loading a valid WAV file.
    """
    audio = load_audio_mono_16k(str(audio_files["wav"]))
    assert isinstance(audio, np.ndarray)
    assert audio.dtype == np.float32
    assert audio.ndim == 1

def test_load_invalid_audio(audio_files):
    """
    Tests loading an invalid audio file.
    """
    with pytest.raises(InvalidAudioError):
        load_audio_mono_16k(str(audio_files["invalid"]))

def test_load_empty_audio(audio_files):
    """
    Tests loading an empty audio file.
    """
    with pytest.raises(InvalidAudioError):
        load_audio_mono_16k(str(audio_files["mp3"]))
    with pytest.raises(InvalidAudioError):
        load_audio_mono_16k(str(audio_files["aac"]))
    with pytest.raises(InvalidAudioError):
        load_audio_mono_16k(str(audio_files["alaw"]))
