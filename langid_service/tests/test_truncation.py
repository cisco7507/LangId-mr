# langid_service/tests/test_truncation.py
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from collections import namedtuple
from langid_service.app.utils import truncate_to_words
from langid_service.app.worker.runner import process_one_sync
from langid_service.app.models.models import Job, JobStatus
import json

def test_truncate_long_transcript():
    long_text = "one two three four five six seven eight nine ten eleven twelve"
    truncated = truncate_to_words(long_text)
    assert truncated == "one two three four five six seven eight nine ten ..."

def test_truncate_short_transcript():
    short_text = "one two three"
    truncated = truncate_to_words(short_text)
    assert truncated == "one two three"

@patch("langid_service.app.worker.runner.load_audio_mono_16k")
@patch("langid_service.app.worker.runner.translate_en_fr_only")
@patch("langid_service.app.worker.runner.get_model")
@patch("langid_service.app.worker.runner.detect_lang_en_fr_only")
def test_truncation_in_worker(mock_detect, mock_get_model, mock_translate, mock_load_audio, db_session):
    # Mock the audio loading to return a dummy array
    dummy_audio = np.random.rand(16000 * 5)
    mock_load_audio.return_value = dummy_audio

    # Mock the model's transcribe method
    mock_model = MagicMock()
    long_text = "one two three four five six seven eight nine ten eleven twelve"

    Segment = namedtuple("Segment", ["text"])
    TranscriptionInfo = namedtuple("TranscriptionInfo", ["language", "language_probability"])

    mock_segment = Segment(text=long_text)
    mock_info = TranscriptionInfo(language="en", language_probability=0.9)

    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    mock_get_model.return_value = mock_model

    mock_detect.return_value = {"language": "en"}
    mock_translate.return_value = "translated text"

    # Create a dummy job
    job = Job(id="test_job", status=JobStatus.queued, input_path="dummy.wav")
    db_session.add(job)
    db_session.commit()

    # Run the worker synchronously
    process_one_sync("test_job", db_session)

    # Refresh the job from the database
    db_session.refresh(job)

    # Check the stored result
    assert job.status == JobStatus.succeeded
    result = json.loads(job.result_json)

    # Verify that the 'text' field is truncated
    assert result["text"] == "one two three four five six seven eight nine ten ..."

    # The 'raw' field should contain the full text
    assert "raw" in result
    assert result["raw"]["text"] == long_text
