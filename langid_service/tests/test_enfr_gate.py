# langid_service/tests/test_enfr_gate.py
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from langid_service.app.lang_gate import detect_lang_en_fr_only, pick_en_or_fr_by_scoring
from langid_service.app.translate import translate_en_fr_only
from langid_service.app.guards import ensure_allowed

TEST_DATA_DIR = Path(__file__).parent / "data" / "golden"

# Create a dummy audio array for testing
dummy_audio = np.random.rand(16000 * 5)

@patch("langid_service.app.lang_gate.get_model")
def test_detect_autodetect_accepts_en(mock_get_model):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock(language="en", language_probability=0.9))
    mock_get_model.return_value = mock_model

    result = detect_lang_en_fr_only(dummy_audio)
    assert result["language"] == "en"
    assert result["method"] == "autodetect"

@patch("langid_service.app.lang_gate.get_model")
def test_detect_autodetect_accepts_fr(mock_get_model):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock(language="fr", language_probability=0.9))
    mock_get_model.return_value = mock_model

    result = detect_lang_en_fr_only(dummy_audio)
    assert result["language"] == "fr"
    assert result["method"] == "autodetect"

@patch("langid_service.app.lang_gate.pick_en_or_fr_by_scoring")
@patch("langid_service.app.lang_gate.get_model")
def test_detect_fallback_picks_en_or_fr(mock_get_model, mock_scoring):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock(language="es", language_probability=0.4))
    mock_get_model.return_value = mock_model
    mock_scoring.return_value = "en"

    result = detect_lang_en_fr_only(dummy_audio)
    assert result["language"] == "en"
    assert result["method"] == "fallback"

@patch("langid_service.app.lang_gate.get_model")
def test_strict_reject_blocks_non_en_fr(mock_get_model, monkeypatch):
    from fastapi import HTTPException
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock(language="es", language_probability=0.42))
    mock_get_model.return_value = mock_model
    monkeypatch.setattr("langid_service.app.lang_gate.ENFR_STRICT_REJECT", True)

    with pytest.raises(HTTPException, match="Only English/French audio supported"):
        detect_lang_en_fr_only(dummy_audio)

def test_translate_only_allows_en_fr_directions():
    with pytest.raises(ValueError):
        translate_en_fr_only("hello", "es", "en")
    with pytest.raises(ValueError):
        translate_en_fr_only("hello", "en", "es")

def test_api_rejects_unsupported_target_lang():
    with pytest.raises(Exception):
        ensure_allowed("es")

@patch("langid_service.app.main.load_audio_mono_16k", return_value=np.zeros(16000, dtype=np.float32))
@patch("langid_service.app.services.detector.get_model")
def test_api_strict_rejects_non_en_fr(mock_get_model, mock_load_audio, monkeypatch):
    from fastapi.testclient import TestClient
    from langid_service.app.main import app

    monkeypatch.setattr("langid_service.app.main.ENFR_STRICT_REJECT", True)

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock(language="es", language_probability=0.42))
    mock_get_model.return_value = mock_model

    with TestClient(app) as client, open(TEST_DATA_DIR / "en_1.wav", "rb") as f:
        response = client.post("/jobs", files={"file": f})

    assert response.status_code == 400
    assert "Only English/French audio supported" in response.text

@patch("langid_service.app.lang_gate.get_model")
def test_detect_vad_retry(mock_get_model):
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = [
        ([], MagicMock(language="en", language_probability=0.3)),
        ([], MagicMock(language="fr", language_probability=0.8)),
    ]
    mock_get_model.return_value = mock_model

    result = detect_lang_en_fr_only(dummy_audio)
    assert result["language"] == "fr"
    assert result["method"] == "autodetect-vad"

@patch("langid_service.app.lang_gate.get_model")
def test_scoring_uses_cheap_settings(mock_get_model):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock())
    mock_get_model.return_value = mock_model

    pick_en_or_fr_by_scoring(dummy_audio)

    # Verify that transcribe was called with cheaper settings for the probes
    for call in mock_model.transcribe.call_args_list:
        assert call.kwargs["beam_size"] == 1
        assert call.kwargs["best_of"] == 1
