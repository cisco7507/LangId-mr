# langid_service/tests/test_langid_golden.py
import pytest
from pathlib import Path
from langid_service.app.services.detector import detect_language

# Define the paths to the golden samples
GOLDEN_SAMPLES_DIR = Path(__file__).parent / "data/golden"
# Expected language and the minimum probability threshold
TEST_CASES = [
    ("en_1.wav", "en", 0.75),
    ("en_2.wav", "en", 0.75),
    ("en_3.wav", "en", 0.75),
    ("fr_1.wav", "fr", 0.75),
    ("fr_2.wav", "fr", 0.75),
    ("fr_3.wav", "fr", 0.75),
    ("es_1.wav", "es", 0.70),
    ("es_2.wav", "es", 0.70),
    ("es_3.wav", "es", 0.70),
]

# @pytest.mark.parametrize("filename, expected_lang, min_prob", TEST_CASES)
# def test_golden_sample(filename, expected_lang, min_prob):
#     """
#     Tests the language detection of a golden sample.
#     """
#     # Get the full path to the audio file
#     audio_path = GOLDEN_SAMPLES_DIR / filename
#     # Check that the file exists
#     assert audio_path.exists(), f"Golden sample not found: {filename}"
#     # Run language detection
#     result = detect_language(str(audio_path))
#     # Check for errors
#     assert "error" not in result, f"Language detection failed: {result.get('error_message')}"
#     # Check the language and probability
#     assert result["language_mapped"] == expected_lang
#     assert result["probability"] >= min_prob
