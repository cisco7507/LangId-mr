from enum import Enum
from typing import Optional, Dict

class Language(str, Enum):
    EN = "en"
    FR = "fr"

class LanguageCodeFormat(str, Enum):
    ISO639_1 = "iso639-1"
    ISO639_2B = "iso639-2b"
    ISO639_2T = "iso639-2t"
    ISO639_3 = "iso639-3"

# Mapping tables
_MAPPING: Dict[Language, Dict[LanguageCodeFormat, str]] = {
    Language.EN: {
        LanguageCodeFormat.ISO639_1: "en",
        LanguageCodeFormat.ISO639_2B: "eng",
        LanguageCodeFormat.ISO639_2T: "eng",
        LanguageCodeFormat.ISO639_3: "eng",
    },
    Language.FR: {
        LanguageCodeFormat.ISO639_1: "fr",
        LanguageCodeFormat.ISO639_2B: "fre",
        LanguageCodeFormat.ISO639_2T: "fra",
        LanguageCodeFormat.ISO639_3: "fra",
    },
}

_LABELS: Dict[Language, str] = {
    Language.EN: "English",
    Language.FR: "French",
}

def to_iso_code(canonical: str, format: LanguageCodeFormat) -> str:
    """
    Convert a canonical language code (en/fr) to the specified ISO format.
    If the canonical code is unknown, returns it as-is.
    """
    try:
        lang = Language(canonical.lower())
        return _MAPPING[lang][format]
    except (ValueError, KeyError):
        return canonical

def from_iso_code(code: str, format: LanguageCodeFormat) -> Optional[str]:
    """
    Convert an ISO code in the specified format back to canonical (en/fr).
    Returns None if not found.
    """
    code = code.lower()
    for lang, formats in _MAPPING.items():
        if formats[format] == code:
            return lang.value
    return None

def get_language_label(canonical: str) -> str:
    """
    Get the human-readable label for a canonical language code.
    """
    try:
        lang = Language(canonical.lower())
        return _LABELS[lang]
    except ValueError:
        return canonical.title()
