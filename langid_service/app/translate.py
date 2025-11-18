from typing import Any

try:
    from transformers import MarianMTModel, MarianTokenizer  # type: ignore
except ImportError:  # pragma: no cover - optional in lightweight environments
    MarianMTModel = None  # type: ignore
    MarianTokenizer = None  # type: ignore

from loguru import logger
from .config import ALLOWED_LANGS

_models = {}
_tokenizers = {}

def _load_model(model_name):
    if MarianMTModel is None or MarianTokenizer is None:
        raise ImportError(
            "transformers is not installed. Install translation dependencies to use translation features."
        )
    if model_name not in _models:
        logger.info(f"Loading translation model: {model_name}")
        _models[model_name] = MarianMTModel.from_pretrained(model_name)
        _tokenizers[model_name] = MarianTokenizer.from_pretrained(model_name)
    return _models[model_name], _tokenizers[model_name]

def translate_en_fr_only(text: str, source_lang: str, target_lang: str) -> str:
    if source_lang not in ALLOWED_LANGS or target_lang not in ALLOWED_LANGS:
        raise ValueError(f"Translation from '{source_lang}' to '{target_lang}' is not supported.")

    if source_lang == "en" and target_lang == "fr":
        model_name = "Helsinki-NLP/opus-mt-en-fr"
    elif source_lang == "fr" and target_lang == "en":
        model_name = "Helsinki-NLP/opus-mt-fr-en"
    else:
        raise ValueError(f"Translation from '{source_lang}' to '{target_lang}' is not supported.")

    model, tokenizer = _load_model(model_name)
    translated = model.generate(**tokenizer(text, return_tensors="pt", padding=True))
    return tokenizer.decode(translated[0], skip_special_tokens=True)
