# langid_service/tests/test_enfr_gate.py
import pytest
import numpy as np
from pathlib import Path
from types import SimpleNamespace
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
    assert result["gate_decision"] == "accepted_high_conf"
    assert result["use_vad"] is False
    assert result["gate_meta"]["mid_zone"] is False
    assert result["music_only"] is False
    assert result["gate_meta"]["music_only"] is False

@patch("langid_service.app.lang_gate.get_model")
def test_detect_autodetect_accepts_fr(mock_get_model):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock(language="fr", language_probability=0.9))
    mock_get_model.return_value = mock_model

    result = detect_lang_en_fr_only(dummy_audio)
    assert result["language"] == "fr"
    assert result["method"] == "autodetect"
    assert result["gate_decision"] == "accepted_high_conf"
    assert result["use_vad"] is False
    assert result["gate_meta"]["mid_zone"] is False
    assert result["music_only"] is False
    assert result["gate_meta"]["music_only"] is False


@patch("langid_service.app.lang_gate.get_model")
def test_mid_zone_en_accepts_without_vad(mock_get_model):
    mock_model = MagicMock()
    en_transcript = "the and to of in you your for is on it that with this as at be are we our us"
    mock_model.transcribe.return_value = (
        [SimpleNamespace(text=en_transcript)],
        SimpleNamespace(language="en", language_probability=0.68),
    )
    mock_get_model.return_value = mock_model

    result = detect_lang_en_fr_only(dummy_audio)
    assert result["gate_decision"] == "accepted_mid_zone_en"
    assert result["use_vad"] is False
    assert result["method"] == "autodetect"
    assert result["gate_meta"]["mid_zone"] is True
    assert result["gate_meta"]["vad_used"] is False
    assert mock_model.transcribe.call_count == 1
    assert result["music_only"] is False


@patch("langid_service.app.lang_gate.get_model")
def test_mid_zone_fr_accepts_without_vad(mock_get_model):
    mock_model = MagicMock()
    fr_transcript = "le la les un une des et ou mais que qui pour avec sur pas ce cette est sont je tu il elle nous vous ils elles"
    mock_model.transcribe.return_value = (
        [SimpleNamespace(text=fr_transcript)],
        SimpleNamespace(language="fr", language_probability=0.70),
    )
    mock_get_model.return_value = mock_model

    result = detect_lang_en_fr_only(dummy_audio)
    assert result["gate_decision"] == "accepted_mid_zone_fr"
    assert result["use_vad"] is False
    assert result["gate_meta"]["mid_zone"] is True
    assert result["gate_meta"]["vad_used"] is False
    assert mock_model.transcribe.call_count == 1
    assert result["music_only"] is False


@patch("langid_service.app.lang_gate.get_model")
def test_mid_zone_sketchy_triggers_vad(mock_get_model):
    mock_model = MagicMock()
    first_transcript = "bonjour musique incroyable liberte soleil amour"  # few EN stopwords
    mock_model.transcribe.side_effect = [
        (
            [SimpleNamespace(text=first_transcript)],
            SimpleNamespace(language="en", language_probability=0.65),
        ),
        (
            [],
            SimpleNamespace(language="en", language_probability=0.82),
        ),
    ]
    mock_get_model.return_value = mock_model

    result = detect_lang_en_fr_only(dummy_audio)
    assert result["gate_decision"] == "vad_retry"
    assert result["use_vad"] is True
    assert result["method"] == "autodetect-vad"
    assert result["gate_meta"]["vad_used"] is True
    assert mock_model.transcribe.call_count == 2
    assert result["music_only"] is False

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
    assert result["gate_decision"] == "fallback"
    assert result["use_vad"] is True
    assert result["probability"] is None
    assert result["music_only"] is False

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

@patch("langid_service.app.lang_gate.get_model")
@patch("langid_service.app.main.load_audio_mono_16k", return_value=np.zeros(16000, dtype=np.float32))
def test_api_strict_rejects_non_en_fr(mock_load_audio, mock_get_model, monkeypatch):
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
    assert result["gate_decision"] == "vad_retry"
    assert result["use_vad"] is True
    assert result["gate_meta"]["vad_used"] is True
    assert result["music_only"] is False

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


@pytest.mark.parametrize("transcript", ["Music", "[music]", "musique"])
@patch("langid_service.app.lang_gate.get_model")
def test_detect_music_only(mock_get_model, transcript):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = (
        [SimpleNamespace(text=transcript)],
        SimpleNamespace(language="en", language_probability=0.92),
    )
    mock_get_model.return_value = mock_model

    result = detect_lang_en_fr_only(dummy_audio)
    assert result["gate_decision"] == "NO_SPEECH_MUSIC_ONLY"
    assert result["music_only"] is True
    assert result["language"] == "none"
    assert result["use_vad"] is False
    assert result["gate_meta"]["music_only"] is True
    assert result["gate_meta"]["mid_zone"] is False
    assert result["gate_meta"]["token_count"] <= 2


@pytest.mark.parametrize(
    "transcript",
    [
        "♪",
        "[♪]",
        "[♫ OUTRO MUSIC PLAYING ♫]",
        "♬ soft music ♬",
        "♪ musique ♪",
    ],
)
@patch("langid_service.app.lang_gate.get_model")
def test_detect_music_only_with_unicode_markers(mock_get_model, transcript):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = (
        [SimpleNamespace(text=transcript)],
        SimpleNamespace(language="en", language_probability=0.92),
    )
    mock_get_model.return_value = mock_model

    result = detect_lang_en_fr_only(dummy_audio)
    assert result["gate_decision"] == "NO_SPEECH_MUSIC_ONLY"
    assert result["music_only"] is True
    assert result["language"] == "none"
    assert result["use_vad"] is False
    assert result["gate_meta"]["music_only"] is True
    assert result["gate_meta"]["mid_zone"] is False
