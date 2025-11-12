# langid_service/tests/test_enfr_gate.py
import pytest
from unittest.mock import patch, MagicMock
from langid_service.app.lang_gate import detect_lang_en_fr_only, pick_en_or_fr_by_scoring
from langid_service.app.translate import translate_en_fr_only
from langid_service.app.guards import ensure_allowed

@patch("langid_service.app.lang_gate.load_audio_mono_16k")
@patch("langid_service.app.lang_gate.get_model")
def test_detect_autodetect_accepts_en(mock_get_model, mock_load_audio):
    # Mock the model's transcribe method
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock(language="en", language_probability=0.9))
    mock_get_model.return_value = mock_model
    mock_load_audio.return_value = "dummy_audio"

    result = detect_lang_en_fr_only("dummy_path")
    assert result["language"] == "en"
    assert result["method"] == "autodetect"

@patch("langid_service.app.lang_gate.load_audio_mono_16k")
@patch("langid_service.app.lang_gate.get_model")
def test_detect_autodetect_accepts_fr(mock_get_model, mock_load_audio):
    # Mock the model's transcribe method
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock(language="fr", language_probability=0.9))
    mock_get_model.return_value = mock_model
    mock_load_audio.return_value = "dummy_audio"

    result = detect_lang_en_fr_only("dummy_path")
    assert result["language"] == "fr"
    assert result["method"] == "autodetect"

@patch("langid_service.app.lang_gate.load_audio_mono_16k")
@patch("langid_service.app.lang_gate.pick_en_or_fr_by_scoring")
@patch("langid_service.app.lang_gate.get_model")
def test_detect_fallback_picks_en_or_fr(mock_get_model, mock_scoring, mock_load_audio):
    # Mock the model's transcribe method to simulate a low-confidence detection
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock(language="es", language_probability=0.4))
    mock_get_model.return_value = mock_model
    mock_scoring.return_value = "en"
    mock_load_audio.return_value = "dummy_audio"

    result = detect_lang_en_fr_only("dummy_path")
    assert result["language"] == "en"
    assert result["method"] == "fallback"

@patch("langid_service.app.lang_gate.load_audio_mono_16k")
@patch("langid_service.app.lang_gate.get_model")
def test_strict_reject_blocks_non_en_fr(mock_get_model, mock_load_audio, monkeypatch):
    # Mock the model's transcribe method to simulate a low-confidence non-EN/FR detection
    from fastapi import HTTPException
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock(language="es", language_probability=0.42))
    mock_get_model.return_value = mock_model
    mock_load_audio.return_value = "dummy_audio"
    monkeypatch.setattr("langid_service.app.lang_gate.ENFR_STRICT_REJECT", True)

    with pytest.raises(HTTPException, match="Only English/French audio supported"):
        detect_lang_en_fr_only("dummy_path")

def test_translate_only_allows_en_fr_directions():
    with pytest.raises(ValueError, match="Translation from 'es' to 'en' is not supported."):
        translate_en_fr_only("hello", "es", "en")

    with pytest.raises(ValueError, match="Translation from 'en' to 'es' is not supported."):
        translate_en_fr_only("hello", "en", "es")

def test_api_rejects_unsupported_target_lang():
    with pytest.raises(Exception, match="Unsupported language 'es'"):
        ensure_allowed("es")

@patch("langid_service.app.main.validate_language_strict")
def test_api_strict_rejects_non_en_fr(mock_validate, monkeypatch):
    # Mock the validation function to raise an exception
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from langid_service.app.main import app

    monkeypatch.setattr("langid_service.app.main.ENFR_STRICT_REJECT", True)
    mock_validate.side_effect = HTTPException(status_code=400, detail="Test error")

    with open("dummy.wav", "wb") as f:
        f.write(b"dummy audio")

    with open("dummy.wav", "rb") as f:
        client = TestClient(app)
        response = client.post("/jobs", files={"file": f})

    assert response.status_code == 400
    assert "Test error" in response.text

@patch("langid_service.app.lang_gate.load_audio_mono_16k")
@patch("langid_service.app.lang_gate.get_model")
def test_detect_vad_retry(mock_get_model, mock_load_audio):
    # Mock the model's transcribe method to simulate a VAD retry
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = [
        ([], MagicMock(language="en", language_probability=0.3)),
        ([], MagicMock(language="fr", language_probability=0.8)),
    ]
    mock_get_model.return_value = mock_model
    mock_load_audio.return_value = "dummy_audio"

    result = detect_lang_en_fr_only("dummy_path")
    assert result["language"] == "fr"
    assert result["method"] == "autodetect-vad"
