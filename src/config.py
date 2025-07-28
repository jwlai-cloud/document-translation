"""Configuration settings for the multimodal document translator."""

from dataclasses import dataclass
from typing import List


@dataclass
class TranslationConfig:
    """Configuration for translation settings."""
    source_language: str
    target_language: str
    preserve_formatting: bool = True
    quality_threshold: float = 0.8
    max_layout_adjustment: float = 0.1


@dataclass
class ProcessingConfig:
    """Configuration for document processing."""
    supported_formats: List[str]
    max_file_size: int
    temp_storage_duration: int
    concurrent_processing: bool = True


# Default configuration values
DEFAULT_SUPPORTED_FORMATS = ['pdf', 'docx', 'epub']
DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
DEFAULT_TEMP_STORAGE_DURATION = 3600  # 1 hour in seconds

# Supported languages
SUPPORTED_LANGUAGES = [
    'en',  # English
    'fr',  # French
    'zh',  # Simplified Chinese
    'ja',  # Japanese
    'es',  # Spanish
    'de',  # German
    'it',  # Italian
    'pt',  # Portuguese
    'ru',  # Russian
    'ko',  # Korean
]

# Language names mapping
LANGUAGE_NAMES = {
    'en': 'English',
    'fr': 'French',
    'zh': 'Simplified Chinese',
    'ja': 'Japanese',
    'es': 'Spanish',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ko': 'Korean',
}


def get_default_processing_config() -> ProcessingConfig:
    """Get default processing configuration."""
    return ProcessingConfig(
        supported_formats=DEFAULT_SUPPORTED_FORMATS,
        max_file_size=DEFAULT_MAX_FILE_SIZE,
        temp_storage_duration=DEFAULT_TEMP_STORAGE_DURATION,
        concurrent_processing=True
    )


def get_default_translation_config(source_lang: str, target_lang: str) -> TranslationConfig:
    """Get default translation configuration."""
    return TranslationConfig(
        source_language=source_lang,
        target_language=target_lang,
        preserve_formatting=True,
        quality_threshold=0.8,
        max_layout_adjustment=0.1
    )