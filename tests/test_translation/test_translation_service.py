"""Tests for context-aware translation service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.translation.translation_service import ContextAwareTranslationService
from src.models.translation import (
    LanguageDetection, TranslationContext, TranslationResult,
    FormattedText, TranslatedRegion, LanguagePair, TranslationBatch
)
from src.models.layout import TextRegion
from src.models.document import BoundingBox, TextFormatting


class TestContextAwareTranslationService:
    """Test cases for ContextAwareTranslationService."""
    
    def test_initialization(self):
        """Test translation service initialization."""
        service = ContextAwareTranslationService(device="cpu")
        
        assert hasattr(service, 'logger')
        assert service.device == "cpu"
        assert service.max_length == 512
        assert service.batch_size == 8
        assert service.context_window == 2
        assert hasattr(service, 'language_detector')
        assert len(service._supported_pairs) > 0
    
    def test_get_supported_languages(self):
        """Test getting supported languages."""
        service = ContextAwareTranslationService()
        
        languages = service.get_supported_languages()
        assert isinstance(languages, list)
        assert 'en' in languages
        assert 'fr' in languages
        assert 'de' in languages
        assert 'es' in languages
    
    def test_validate_language_pair(self):
        """Test language pair validation."""
        service = ContextAwareTranslationService()
        
        # Valid pairs
        assert service.validate_language_pair('en', 'fr') is True
        assert service.validate_language_pair('fr', 'en') is True
        assert service.validate_language_pair('en', 'de') is True
        
        # Invalid pairs
        assert service.validate_language_pair('en', 'en') is False  # Same language
        assert service.validate_language_pair('xyz', 'abc') is False  # Unsupported
    
    def test_get_supported_language_pairs(self):
        """Test getting supported language pairs."""
        service = ContextAwareTranslationService()
        
        pairs = service.get_supported_language_pairs()
        assert isinstance(pairs, list)
        assert len(pairs) > 0
        
        # Check that all pairs are LanguagePair objects
        for pair in pairs:
            assert isinstance(pair, LanguagePair)
            assert pair.is_supported is True
            assert pair.model_name is not None
            assert 0.0 <= pair.quality_rating <= 1.0
    
    def test_initialize_supported_pairs(self):
        """Test initialization of supported language pairs."""
        service = ContextAwareTranslationService()
        
        pairs = service._supported_pairs
        
        # Check some expected pairs
        assert 'en-fr' in pairs
        assert 'fr-en' in pairs
        assert 'en-de' in pairs
        assert 'de-en' in pairs
        
        # Check pair structure
        for pair_key, pair_info in pairs.items():
            assert 'model' in pair_info
            assert 'quality' in pair_info
            assert pair_info['model'].startswith('Helsinki-NLP/')
            assert 0.0 <= pair_info['quality'] <= 1.0
    
    @patch('src.translation.translation_service.pipeline')
    @patch('src.translation.translation_service.AutoTokenizer')
    def test_get_translation_pipeline(self, mock_tokenizer, mock_pipeline):
        """Test getting translation pipeline."""
        service = ContextAwareTranslationService()
        
        # Mock pipeline and tokenizer
        mock_translator = Mock()
        mock_pipeline.return_value = mock_translator
        mock_tokenizer.from_pretrained.return_value = Mock()
        
        # Test getting pipeline
        pipeline = service._get_translation_pipeline('en', 'fr')
        
        assert pipeline == mock_translator
        mock_pipeline.assert_called_once()
        mock_tokenizer.from_pretrained.assert_called_once()
        
        # Test caching - second call should not create new pipeline
        pipeline2 = service._get_translation_pipeline('en', 'fr')
        assert pipeline2 == mock_translator
        assert mock_pipeline.call_count == 1  # Still only called once
    
    def test_get_translation_pipeline_unsupported(self):
        """Test getting pipeline for unsupported language pair."""
        service = ContextAwareTranslationService()
        
        with pytest.raises(ValueError, match="Unsupported language pair"):
            service._get_translation_pipeline('xyz', 'abc')
    
    def test_build_translation_context(self):
        """Test building translation context."""
        service = ContextAwareTranslationService()
        
        # Create test regions
        regions = [
            TextRegion(text_content="First sentence."),
            TextRegion(text_content="Second sentence."),
            TextRegion(text_content="Third sentence."),  # Current region
            TextRegion(text_content="Fourth sentence."),
            TextRegion(text_content="Fifth sentence.")
        ]
        
        # Build context for middle region (index 2)
        context = service._build_translation_context(regions[2], regions, 2)
        
        assert isinstance(context, TranslationContext)
        assert "First sentence. Second sentence." in context.preceding_text
        assert "Fourth sentence. Fifth sentence." in context.following_text
        assert context.element_type == "text"
    
    def test_build_translation_context_edge_cases(self):
        """Test building context at document edges."""
        service = ContextAwareTranslationService()
        
        regions = [
            TextRegion(text_content="First sentence."),
            TextRegion(text_content="Second sentence."),
            TextRegion(text_content="Third sentence.")
        ]
        
        # Context for first region
        context_first = service._build_translation_context(regions[0], regions, 0)
        assert context_first.preceding_text == ""
        assert "Second sentence. Third sentence." in context_first.following_text
        
        # Context for last region
        context_last = service._build_translation_context(regions[2], regions, 2)
        assert "First sentence. Second sentence." in context_last.preceding_text
        assert context_last.following_text == ""
    
    def test_prepare_text_with_context(self):
        """Test preparing text with context."""
        service = ContextAwareTranslationService()
        
        context = TranslationContext(
            preceding_text="Previous sentence.",
            following_text="Next sentence.",
            element_type="text"
        )
        
        prepared_text = service._prepare_text_with_context("Current sentence.", context)
        
        # For now, should return original text
        assert prepared_text == "Current sentence."
    
    def test_extract_translation_from_context(self):
        """Test extracting translation from context-aware result."""
        service = ContextAwareTranslationService()
        
        translated = service._extract_translation_from_context(
            "Phrase traduite avec contexte.",
            "Original sentence with context."
        )
        
        # For now, should return the full translation
        assert translated == "Phrase traduite avec contexte."
    
    def test_extract_formatting_tags(self):
        """Test extracting formatting tags from text region."""
        service = ContextAwareTranslationService()
        
        # Create region with formatting
        formatting = TextFormatting(
            is_bold=True,
            is_italic=True,
            color="#FF0000"
        )
        
        region = TextRegion(
            text_content="Formatted text",
            formatting=formatting
        )
        
        tags = service._extract_formatting_tags(region)
        
        assert len(tags) >= 3  # bold, italic, color
        
        # Check for specific tags
        tag_types = [tag['type'] for tag in tags]
        assert 'bold' in tag_types
        assert 'italic' in tag_types
        assert 'color' in tag_types
        
        # Check color tag
        color_tag = next(tag for tag in tags if tag['type'] == 'color')
        assert color_tag['value'] == '#FF0000'
    
    def test_apply_formatting_tags(self):
        """Test applying formatting tags to text."""
        service = ContextAwareTranslationService()
        
        tags = [
            {"type": "bold", "start": 0, "end": 10},
            {"type": "italic", "start": 5, "end": 15}
        ]
        
        formatted_text = service._apply_formatting_tags("Sample text here", tags)
        
        # For now, should return original text
        assert formatted_text == "Sample text here"
    
    def test_create_style_mapping(self):
        """Test creating style mapping from formatting."""
        service = ContextAwareTranslationService()
        
        formatting = TextFormatting(
            font_family="Arial",
            font_size=14.0,
            is_bold=True,
            is_italic=True,
            color="#0000FF",
            alignment="center"
        )
        
        style_map = service._create_style_mapping(formatting)
        
        assert style_map["font-family"] == "Arial"
        assert style_map["font-size"] == "14.0pt"
        assert style_map["font-weight"] == "bold"
        assert style_map["font-style"] == "italic"
        assert style_map["color"] == "#0000FF"
        assert style_map["text-align"] == "center"
    
    def test_preserve_formatting(self):
        """Test formatting preservation."""
        service = ContextAwareTranslationService()
        
        formatting = TextFormatting(
            is_bold=True,
            color="#FF0000"
        )
        
        region = TextRegion(
            text_content="Original text",
            formatting=formatting
        )
        
        formatted_text = service.preserve_formatting(region, "Translated text")
        
        assert isinstance(formatted_text, FormattedText)
        assert formatted_text.content == "Translated text"
        assert len(formatted_text.formatting_tags) >= 2  # bold and color
        assert "font-weight" in formatted_text.style_mapping
        assert "color" in formatted_text.style_mapping
    
    def test_create_translation_batch(self):
        """Test creating translation batch."""
        service = ContextAwareTranslationService()
        
        regions = [
            TextRegion(text_content="First text"),
            TextRegion(text_content="Second text")
        ]
        
        language_pair = LanguagePair(
            source_language="en",
            target_language="fr"
        )
        
        context = TranslationContext()
        
        batch = service.create_translation_batch(regions, language_pair, context)
        
        assert isinstance(batch, TranslationBatch)
        assert batch.regions == regions
        assert batch.language_pair == language_pair
        assert batch.context == context
        assert isinstance(batch.created_at, datetime)
    
    def test_get_translation_progress(self):
        """Test getting translation progress."""
        service = ContextAwareTranslationService()
        
        progress = service.get_translation_progress(100, 25)
        
        assert progress.total_regions == 100
        assert progress.completed_regions == 25
        assert progress.completion_percentage == 25.0
        assert progress.current_operation == "translating"
    
    @patch('src.translation.translation_service.pipeline')
    @patch('src.translation.translation_service.AutoTokenizer')
    def test_translate_with_context_success(self, mock_tokenizer, mock_pipeline):
        """Test successful translation with context."""
        service = ContextAwareTranslationService()
        
        # Mock pipeline
        mock_translator = Mock()
        mock_translator.return_value = [{"translation_text": "Texte traduit"}]
        mock_pipeline.return_value = mock_translator
        mock_tokenizer.from_pretrained.return_value = Mock()
        
        # Create test regions
        regions = [
            TextRegion(
                text_content="Text to translate",
                formatting=TextFormatting()
            )
        ]
        
        # Test translation
        results = service.translate_with_context(regions, "en", "fr")
        
        assert len(results) == 1
        assert isinstance(results[0], TranslatedRegion)
        assert results[0].translation_result.translated_text == "Texte traduit"
        assert results[0].translation_result.source_language == "en"
        assert results[0].translation_result.target_language == "fr"
    
    def test_translate_with_context_invalid_pair(self):
        """Test translation with invalid language pair."""
        service = ContextAwareTranslationService()
        
        regions = [TextRegion(text_content="Test text")]
        
        with pytest.raises(ValueError, match="Unsupported language pair"):
            service.translate_with_context(regions, "xyz", "abc")
    
    @patch('src.translation.translation_service.pipeline')
    @patch('src.translation.translation_service.AutoTokenizer')
    def test_translate_batch_with_context(self, mock_tokenizer, mock_pipeline):
        """Test batch translation with context."""
        service = ContextAwareTranslationService()
        
        # Mock pipeline
        mock_translator = Mock()
        mock_translator.side_effect = [
            [{"translation_text": "Premier texte"}],
            [{"translation_text": "Deuxième texte"}]
        ]
        mock_pipeline.return_value = mock_translator
        mock_tokenizer.from_pretrained.return_value = Mock()
        
        # Create test regions
        batch_regions = [
            TextRegion(text_content="First text"),
            TextRegion(text_content="Second text")
        ]
        
        all_regions = batch_regions  # Same for this test
        
        results = service._translate_batch_with_context(
            batch_regions, all_regions, 0, mock_translator, "en", "fr"
        )
        
        assert len(results) == 2
        assert results[0].translation_result.translated_text == "Premier texte"
        assert results[1].translation_result.translated_text == "Deuxième texte"
    
    @patch('src.translation.translation_service.pipeline')
    @patch('src.translation.translation_service.AutoTokenizer')
    def test_translate_batch_with_error(self, mock_tokenizer, mock_pipeline):
        """Test batch translation with error handling."""
        service = ContextAwareTranslationService()
        
        # Mock pipeline that raises exception
        mock_translator = Mock()
        mock_translator.side_effect = Exception("Translation failed")
        mock_pipeline.return_value = mock_translator
        mock_tokenizer.from_pretrained.return_value = Mock()
        
        batch_regions = [TextRegion(text_content="Test text")]
        
        results = service._translate_batch_with_context(
            batch_regions, batch_regions, 0, mock_translator, "en", "fr"
        )
        
        assert len(results) == 1
        # Should create fallback translation
        assert results[0].translation_result.translated_text == "Test text"
        assert results[0].translation_result.confidence == 0.0
        assert results[0].translation_result.translation_method == "fallback"
    
    @patch('src.translation.translation_service.torch')
    @patch('src.translation.translation_service.gc')
    def test_cleanup_models(self, mock_gc, mock_torch):
        """Test model cleanup."""
        service = ContextAwareTranslationService(device="cuda")
        
        # Add some mock pipelines
        service._translation_pipelines["en-fr"] = Mock()
        service._tokenizers["en-fr"] = Mock()
        
        # Mock CUDA availability
        mock_torch.cuda.is_available.return_value = True
        
        service.cleanup_models()
        
        # Check that caches are cleared
        assert len(service._translation_pipelines) == 0
        assert len(service._tokenizers) == 0
        
        # Check that cleanup functions were called
        mock_gc.collect.assert_called_once()
        mock_torch.cuda.empty_cache.assert_called_once()
    
    @patch('src.translation.language_detection.detect_langs')
    def test_detect_language_integration(self, mock_detect_langs):
        """Test language detection integration."""
        service = ContextAwareTranslationService()
        
        # Mock language detection
        mock_lang = Mock()
        mock_lang.lang = 'en'
        mock_lang.prob = 0.9
        mock_detect_langs.return_value = [mock_lang]
        
        detection = service.detect_language("This is English text.")
        
        assert isinstance(detection, LanguageDetection)
        assert detection.detected_language == 'en'
        assert detection.confidence == 0.9