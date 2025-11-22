import pytest
from langid_service.app.models.languages import (
    Language,
    LanguageCodeFormat,
    to_iso_code,
    from_iso_code,
    get_language_label,
)

def test_to_iso_code():
    # English
    assert to_iso_code("en", LanguageCodeFormat.ISO639_1) == "en"
    assert to_iso_code("en", LanguageCodeFormat.ISO639_2B) == "eng"
    assert to_iso_code("en", LanguageCodeFormat.ISO639_2T) == "eng"
    assert to_iso_code("en", LanguageCodeFormat.ISO639_3) == "eng"
    
    # French
    assert to_iso_code("fr", LanguageCodeFormat.ISO639_1) == "fr"
    assert to_iso_code("fr", LanguageCodeFormat.ISO639_2B) == "fre"
    assert to_iso_code("fr", LanguageCodeFormat.ISO639_2T) == "fra"
    assert to_iso_code("fr", LanguageCodeFormat.ISO639_3) == "fra"
    
    # Unknown
    assert to_iso_code("unknown", LanguageCodeFormat.ISO639_1) == "unknown"

def test_from_iso_code():
    # English
    assert from_iso_code("en", LanguageCodeFormat.ISO639_1) == "en"
    assert from_iso_code("eng", LanguageCodeFormat.ISO639_2B) == "en"
    
    # French
    assert from_iso_code("fr", LanguageCodeFormat.ISO639_1) == "fr"
    assert from_iso_code("fre", LanguageCodeFormat.ISO639_2B) == "fr"
    assert from_iso_code("fra", LanguageCodeFormat.ISO639_2T) == "fr"
    
    # Unknown
    assert from_iso_code("xyz", LanguageCodeFormat.ISO639_1) is None

def test_get_language_label():
    assert get_language_label("en") == "English"
    assert get_language_label("fr") == "French"
    assert get_language_label("unknown") == "Unknown"
