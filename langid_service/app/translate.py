# langid_service/app/translate.py
from typing import Dict
from loguru import logger
from transformers import MarianMTModel, MarianTokenizer
from .config import CT2_TRANSLATORS_CACHE

_models: Dict[str, MarianMTModel] = {}
_tokenizers: Dict[str, MarianTokenizer] = {}

def _load_model(model_name: str):
    """Lazy-loads a MarianMT model and tokenizer."""
    if model_name not in _models:
        logger.info(f"Loading translation model: {model_name}")
        cache_dir = CT2_TRANSLATORS_CACHE or None
        _tokenizers[model_name] = MarianTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        _models[model_name] = MarianMTModel.from_pretrained(model_name, cache_dir=cache_dir)
        logger.info(f"Model {model_name} loaded.")
    return _models[model_name], _tokenizers[model_name]

def translate_en_fr_only(text: str, source_lang: str, target_lang: str) -> str:
    """
    Translates text between English and French.
    """
    if source_lang == target_lang:
        return text

    if source_lang == "en" and target_lang == "fr":
        model_name = "Helsinki-NLP/opus-mt-en-fr"
    elif source_lang == "fr" and target_lang == "en":
        model_name = "Helsinki-NLP/opus-mt-fr-en"
    else:
        raise ValueError(f"Translation from '{source_lang}' to '{target_lang}' is not supported.")

    model, tokenizer = _load_model(model_name)

    # Perform translation
    translated_tokens = model.generate(**tokenizer(text, return_tensors="pt", padding=True))
    return tokenizer.decode(translated_tokens[0], skip_special_tokens=True)
