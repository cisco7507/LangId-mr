# langid_service/tests/test_audio_io.py
import pytest
import numpy as np
from langid_service.app.services.audio_io import load_audio_mono_16k, InvalidAudioError

def test_load_wav():
    audio = load_audio_mono_16k("langid_service/tests/data/golden/en_1.wav")
    assert isinstance(audio, np.ndarray)
    assert audio.ndim == 1
    assert len(audio) > 0

def test_load_invalid_audio():
    with open("dummy.txt", "w") as f:
        f.write("this is not an audio file")
    with pytest.raises(InvalidAudioError):
        load_audio_mono_16k("dummy.txt")

def test_load_empty_audio():
    with open("empty.wav", "w") as f:
        f.write("")
    with pytest.raises(InvalidAudioError):
        load_audio_mono_16k("empty.wav")
