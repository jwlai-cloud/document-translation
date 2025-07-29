"""Enhanced translation service with context awareness."""

from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from typing import List, Dict, Optional, Tuple
import logging
import re
from datetime import datetime
import torch

from .base import TranslationService
from .language_detection import LanguageDetectionService
from src.models.translation import (
    LanguageDetection,
    TranslationContext,
    TranslationResult,
    FormattedText,
    TranslatedRegion,
    LanguagePair,
    TranslationBatch,
    TranslationProgress,
)
from src.models.layout import TextRegion
from src.config import SUPPORTED_LANGUAGES, LANGUAGE_NAMES


class ContextAwareTranslationService(TranslationService):
    """Enhanced translation service with context awareness and formatting preservation."""

    def __init__(self, device: str = "cpu", model_cache_dir: Optional[str] = None):
        """Initialize the translation service.

        Args:
            device: Device to run models on ("cpu" or "cuda")
            model_cache_dir: Directory to cache models
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.device = device
        self.model_cache_dir = model_cache_dir

        # Translation pipelines cache
        self._translation_pipelines: Dict[str, any] = {}
        self._tokenizers: Dict[str, any] = {}

        # Language detection service
        self.language_detector = LanguageDetectionService()

        # Translation settings
        self.max_length = 512  # Maximum tokens per translation
        self.batch_size = 8  # Batch size for processing
        self.context_window = 2  # Number of surrounding regions for context

        # Supported language pairs
        self._supported_pairs = self._initialize_supported_pairs()

        self.logger.info(f"Translation service initialized on {device}")

    def detect_language(self, text: str) -> LanguageDetection:
        """Detect the language of the given text.

        Args:
            text: Text to analyze

        Returns:
            LanguageDetection with detected language and confidence
        """
        return self.language_detector.detect_language(text)

    def translate_with_context(
        self, regions: List[TextRegion], source_lang: str, target_lang: str
    ) -> List[TranslatedRegion]:
        """Translate text regions with context awareness.

        Args:
            regions: List of text regions to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of translated regions with confidence scores
        """
        try:
            self.logger.info(
                f"Starting context-aware translation: {source_lang} -> {target_lang} "
                f"({len(regions)} regions)"
            )

            # Validate language pair
            if not self.validate_language_pair(source_lang, target_lang):
                raise ValueError(
                    f"Unsupported language pair: {source_lang} -> {target_lang}"
                )

            # Get translation pipeline
            pipeline = self._get_translation_pipeline(source_lang, target_lang)

            # Process regions in batches with context
            translated_regions = []

            for i in range(0, len(regions), self.batch_size):
                batch_regions = regions[i : i + self.batch_size]
                batch_results = self._translate_batch_with_context(
                    batch_regions, regions, i, pipeline, source_lang, target_lang
                )
                translated_regions.extend(batch_results)

            self.logger.info(
                f"Translation completed: {len(translated_regions)} regions processed"
            )

            return translated_regions

        except Exception as e:
            self.logger.error(f"Translation failed: {str(e)}")
            raise

    def preserve_formatting(
        self, original: TextRegion, translated: str
    ) -> FormattedText:
        """Preserve formatting in translated text.

        Args:
            original: Original text region with formatting
            translated: Translated text content

        Returns:
            FormattedText with preserved formatting
        """
        try:
            # Extract formatting tags from original text
            formatting_tags = self._extract_formatting_tags(original)

            # Apply formatting to translated text
            formatted_text = self._apply_formatting_tags(translated, formatting_tags)

            # Create style mapping
            style_mapping = self._create_style_mapping(original.formatting)

            return FormattedText(
                content=formatted_text,
                formatting_tags=formatting_tags,
                style_mapping=style_mapping,
            )

        except Exception as e:
            self.logger.warning(f"Formatting preservation failed: {str(e)}")
            # Return unformatted text as fallback
            return FormattedText(content=translated)

    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes.

        Returns:
            List of supported language codes
        """
        return SUPPORTED_LANGUAGES.copy()

    def validate_language_pair(self, source_lang: str, target_lang: str) -> bool:
        """Validate if a language pair is supported.

        Args:
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            True if language pair is supported
        """
        if source_lang == target_lang:
            return False

        pair_key = f"{source_lang}-{target_lang}"
        return pair_key in self._supported_pairs

    def get_supported_language_pairs(self) -> List[LanguagePair]:
        """Get all supported language pairs.

        Returns:
            List of supported LanguagePair objects
        """
        pairs = []
        for pair_key, model_info in self._supported_pairs.items():
            source, target = pair_key.split("-")
            pair = LanguagePair(
                source_language=source,
                target_language=target,
                is_supported=True,
                model_name=model_info["model"],
                quality_rating=model_info.get("quality", 0.8),
            )
            pairs.append(pair)

        return pairs

    def create_translation_batch(
        self,
        regions: List[TextRegion],
        language_pair: LanguagePair,
        context: TranslationContext,
    ) -> TranslationBatch:
        """Create a translation batch for processing.

        Args:
            regions: Text regions to translate
            language_pair: Source-target language pair
            context: Translation context information

        Returns:
            TranslationBatch ready for processing
        """
        return TranslationBatch(
            regions=regions,
            language_pair=language_pair,
            context=context,
            priority=0,
            created_at=datetime.now(),
        )

    def _initialize_supported_pairs(self) -> Dict[str, Dict[str, any]]:
        """Initialize supported language pairs with model information.

        Returns:
            Dictionary of supported pairs with model details
        """
        # Define supported translation models
        # Using Helsinki-NLP models which are well-supported
        pairs = {}

        # English to other languages
        pairs.update(
            {
                "en-fr": {"model": "Helsinki-NLP/opus-mt-en-fr", "quality": 0.9},
                "en-de": {"model": "Helsinki-NLP/opus-mt-en-de", "quality": 0.85},
                "en-es": {"model": "Helsinki-NLP/opus-mt-en-es", "quality": 0.9},
                "en-it": {"model": "Helsinki-NLP/opus-mt-en-it", "quality": 0.85},
                "en-pt": {"model": "Helsinki-NLP/opus-mt-en-pt", "quality": 0.85},
                "en-ru": {"model": "Helsinki-NLP/opus-mt-en-ru", "quality": 0.8},
                "en-zh": {"model": "Helsinki-NLP/opus-mt-en-zh", "quality": 0.75},
                "en-ja": {"model": "Helsinki-NLP/opus-mt-en-jap", "quality": 0.75},
                "en-ko": {"model": "Helsinki-NLP/opus-mt-en-ko", "quality": 0.7},
            }
        )

        # Other languages to English
        pairs.update(
            {
                "fr-en": {"model": "Helsinki-NLP/opus-mt-fr-en", "quality": 0.9},
                "de-en": {"model": "Helsinki-NLP/opus-mt-de-en", "quality": 0.85},
                "es-en": {"model": "Helsinki-NLP/opus-mt-es-en", "quality": 0.9},
                "it-en": {"model": "Helsinki-NLP/opus-mt-it-en", "quality": 0.85},
                "pt-en": {"model": "Helsinki-NLP/opus-mt-pt-en", "quality": 0.85},
                "ru-en": {"model": "Helsinki-NLP/opus-mt-ru-en", "quality": 0.8},
                "zh-en": {"model": "Helsinki-NLP/opus-mt-zh-en", "quality": 0.75},
                "ja-en": {"model": "Helsinki-NLP/opus-mt-jap-en", "quality": 0.75},
                "ko-en": {"model": "Helsinki-NLP/opus-mt-ko-en", "quality": 0.7},
            }
        )

        # Some direct pairs (non-English)
        pairs.update(
            {
                "fr-de": {"model": "Helsinki-NLP/opus-mt-fr-de", "quality": 0.8},
                "de-fr": {"model": "Helsinki-NLP/opus-mt-de-fr", "quality": 0.8},
                "es-fr": {"model": "Helsinki-NLP/opus-mt-es-fr", "quality": 0.8},
                "fr-es": {"model": "Helsinki-NLP/opus-mt-fr-es", "quality": 0.8},
            }
        )

        return pairs

    def _get_translation_pipeline(self, source_lang: str, target_lang: str):
        """Get or create translation pipeline for language pair.

        Args:
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Translation pipeline
        """
        pair_key = f"{source_lang}-{target_lang}"

        if pair_key in self._translation_pipelines:
            return self._translation_pipelines[pair_key]

        if pair_key not in self._supported_pairs:
            raise ValueError(f"Unsupported language pair: {pair_key}")

        model_name = self._supported_pairs[pair_key]["model"]

        try:
            self.logger.info(f"Loading translation model: {model_name}")

            # Create pipeline with specific model
            translator = pipeline(
                "translation",
                model=model_name,
                device=0 if self.device == "cuda" and torch.cuda.is_available() else -1,
                model_kwargs={"cache_dir": self.model_cache_dir}
                if self.model_cache_dir
                else {},
            )

            # Cache the pipeline
            self._translation_pipelines[pair_key] = translator

            # Also cache tokenizer for context processing
            tokenizer = AutoTokenizer.from_pretrained(
                model_name, cache_dir=self.model_cache_dir
            )
            self._tokenizers[pair_key] = tokenizer

            self.logger.info(f"Model loaded successfully: {model_name}")
            return translator

        except Exception as e:
            self.logger.error(f"Failed to load model {model_name}: {str(e)}")
            raise

    def _translate_batch_with_context(
        self,
        batch_regions: List[TextRegion],
        all_regions: List[TextRegion],
        batch_start_idx: int,
        pipeline,
        source_lang: str,
        target_lang: str,
    ) -> List[TranslatedRegion]:
        """Translate a batch of regions with context awareness.

        Args:
            batch_regions: Regions in current batch
            all_regions: All regions for context
            batch_start_idx: Starting index of batch in all_regions
            pipeline: Translation pipeline
            source_lang: Source language
            target_lang: Target language

        Returns:
            List of translated regions
        """
        translated_regions = []

        for i, region in enumerate(batch_regions):
            global_idx = batch_start_idx + i

            # Build context for this region
            context = self._build_translation_context(region, all_regions, global_idx)

            # Prepare text for translation with context
            text_with_context = self._prepare_text_with_context(
                region.text_content, context
            )

            # Translate
            try:
                translation_result = pipeline(
                    text_with_context,
                    max_length=self.max_length,
                    num_return_sequences=1,
                )

                # Extract translated text (remove context if added)
                translated_text = self._extract_translation_from_context(
                    translation_result[0]["translation_text"], region.text_content
                )

                # Calculate confidence (simplified)
                confidence = min(
                    0.9,
                    max(0.5, len(translated_text) / max(len(region.text_content), 1)),
                )

                # Create translation result
                result = TranslationResult(
                    original_text=region.text_content,
                    translated_text=translated_text,
                    source_language=source_lang,
                    target_language=target_lang,
                    confidence=confidence,
                    translation_method="context_aware_neural",
                )

                # Preserve formatting
                formatted_text = self.preserve_formatting(region, translated_text)

                # Create translated region
                translated_region = TranslatedRegion(
                    original_region=region,
                    translation_result=result,
                    context=context,
                    formatted_text=formatted_text,
                    quality_score=confidence,
                )

                translated_regions.append(translated_region)

            except Exception as e:
                self.logger.warning(
                    f"Translation failed for region {region.id}: {str(e)}"
                )

                # Create fallback translation
                fallback_result = TranslationResult(
                    original_text=region.text_content,
                    translated_text=region.text_content,  # Keep original as fallback
                    source_language=source_lang,
                    target_language=target_lang,
                    confidence=0.0,
                    translation_method="fallback",
                )

                translated_region = TranslatedRegion(
                    original_region=region,
                    translation_result=fallback_result,
                    context=context,
                    quality_score=0.0,
                )

                translated_regions.append(translated_region)

        return translated_regions

    def _build_translation_context(
        self, region: TextRegion, all_regions: List[TextRegion], region_idx: int
    ) -> TranslationContext:
        """Build translation context for a region.

        Args:
            region: Current region to translate
            all_regions: All regions in document
            region_idx: Index of current region

        Returns:
            TranslationContext with surrounding information
        """
        # Get preceding context
        preceding_text = ""
        start_idx = max(0, region_idx - self.context_window)
        for i in range(start_idx, region_idx):
            preceding_text += all_regions[i].text_content + " "

        # Get following context
        following_text = ""
        end_idx = min(len(all_regions), region_idx + self.context_window + 1)
        for i in range(region_idx + 1, end_idx):
            following_text += all_regions[i].text_content + " "

        return TranslationContext(
            preceding_text=preceding_text.strip(),
            following_text=following_text.strip(),
            element_type="text",  # Could be enhanced based on region properties
            page_number=1,  # Could be extracted from region metadata
        )

    def _prepare_text_with_context(self, text: str, context: TranslationContext) -> str:
        """Prepare text for translation with context.

        Args:
            text: Main text to translate
            context: Translation context

        Returns:
            Text prepared with context for better translation
        """
        # For now, we'll use the text as-is
        # In a more advanced implementation, we could:
        # 1. Add context markers
        # 2. Include surrounding sentences
        # 3. Add document-level context

        return text

    def _extract_translation_from_context(
        self, translated_with_context: str, original_text: str
    ) -> str:
        """Extract the main translation from context-aware result.

        Args:
            translated_with_context: Translation result with context
            original_text: Original text that was translated

        Returns:
            Extracted main translation
        """
        # For now, return the full translation
        # In a more advanced implementation, we could:
        # 1. Remove context markers
        # 2. Extract only the main sentence
        # 3. Clean up formatting artifacts

        return translated_with_context.strip()

    def _extract_formatting_tags(self, region: TextRegion) -> List[Dict[str, any]]:
        """Extract formatting tags from text region.

        Args:
            region: Text region with formatting

        Returns:
            List of formatting tag dictionaries
        """
        tags = []
        formatting = region.formatting

        # Add font formatting
        if formatting.is_bold:
            tags.append({"type": "bold", "start": 0, "end": len(region.text_content)})

        if formatting.is_italic:
            tags.append({"type": "italic", "start": 0, "end": len(region.text_content)})

        if formatting.is_underlined:
            tags.append(
                {"type": "underline", "start": 0, "end": len(region.text_content)}
            )

        # Add color formatting
        if formatting.color != "#000000":
            tags.append(
                {
                    "type": "color",
                    "value": formatting.color,
                    "start": 0,
                    "end": len(region.text_content),
                }
            )

        return tags

    def _apply_formatting_tags(self, text: str, tags: List[Dict[str, any]]) -> str:
        """Apply formatting tags to translated text.

        Args:
            text: Translated text
            tags: Formatting tags to apply

        Returns:
            Text with formatting applied
        """
        # For now, return text as-is
        # In a more advanced implementation, we could:
        # 1. Apply HTML/markdown formatting
        # 2. Preserve rich text formatting
        # 3. Handle overlapping tags

        return text

    def _create_style_mapping(self, formatting) -> Dict[str, str]:
        """Create style mapping from text formatting.

        Args:
            formatting: TextFormatting object

        Returns:
            Dictionary mapping style properties
        """
        style_map = {}

        if formatting.font_family:
            style_map["font-family"] = formatting.font_family

        if formatting.font_size:
            style_map["font-size"] = f"{formatting.font_size}pt"

        if formatting.is_bold:
            style_map["font-weight"] = "bold"

        if formatting.is_italic:
            style_map["font-style"] = "italic"

        if formatting.is_underlined:
            style_map["text-decoration"] = "underline"

        if formatting.color:
            style_map["color"] = formatting.color

        if formatting.alignment:
            style_map["text-align"] = formatting.alignment

        return style_map

    def get_translation_progress(
        self, total_regions: int, completed_regions: int
    ) -> TranslationProgress:
        """Get translation progress information.

        Args:
            total_regions: Total number of regions to translate
            completed_regions: Number of completed regions

        Returns:
            TranslationProgress object
        """
        return TranslationProgress(
            total_regions=total_regions,
            completed_regions=completed_regions,
            current_operation="translating",
            estimated_time_remaining=0.0,  # Could be calculated based on processing speed
        )

    def cleanup_models(self):
        """Clean up loaded models to free memory."""
        self.logger.info("Cleaning up translation models")
        self._translation_pipelines.clear()
        self._tokenizers.clear()

        # Force garbage collection
        import gc

        gc.collect()

        # Clear CUDA cache if using GPU
        if self.device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
