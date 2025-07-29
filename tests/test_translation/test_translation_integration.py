"""Integration tests for translation service with document processing."""

import pytest
from unittest.mock import Mock, patch

from src.translation.translation_service import ContextAwareTranslationService
from src.translation.language_detection import LanguageDetectionService
from src.models.document import DocumentStructure, PageStructure, TextRegion, Dimensions, BoundingBox, TextFormatting
from src.models.translation import LanguageDetection, TranslatedRegion


class TestTranslationServiceIntegration:
    """Integration tests for translation service with document processing."""
    
    def test_translation_service_creation(self):
        """Test creating translation service."""
        service = ContextAwareTranslationService()
        
        assert isinstance(service, ContextAwareTranslationService)
        assert hasattr(service, 'language_detector')
        assert isinstance(service.language_detector, LanguageDetectionService)
    
    def test_service_integration_with_language_detection(self):
        """Test integration with language detection service."""
        service = ContextAwareTranslationService()
        
        # Test that language detection works through translation service
        with patch('src.translation.language_detection.detect_langs') as mock_detect:
            mock_lang = Mock()
            mock_lang.lang = 'en'
            mock_lang.prob = 0.9
            mock_detect.return_value = [mock_lang]
            
            detection = service.detect_language("This is English text.")
            
            assert isinstance(detection, LanguageDetection)
            assert detection.detected_language == 'en'
            assert detection.confidence == 0.9
    
    @patch('src.translation.translation_service.pipeline')
    @patch('src.translation.translation_service.AutoTokenizer')
    def test_document_translation_workflow(self, mock_tokenizer, mock_pipeline):
        """Test complete document translation workflow."""
        service = ContextAwareTranslationService()
        
        # Mock translation pipeline
        mock_translator = Mock()
        mock_translator.side_effect = [
            [{"translation_text": "Première phrase traduite."}],
            [{"translation_text": "Deuxième phrase traduite."}],
            [{"translation_text": "Troisième phrase traduite."}]
        ]
        mock_pipeline.return_value = mock_translator
        mock_tokenizer.from_pretrained.return_value = Mock()
        
        # Create document structure (as would come from parser)
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        
        # Add text regions with different formatting
        regions = [
            TextRegion(
                bounding_box=BoundingBox(x=50, y=50, width=500, height=20),
                text_content="First sentence to translate.",
                formatting=TextFormatting(is_bold=True)
            ),
            TextRegion(
                bounding_box=BoundingBox(x=50, y=80, width=500, height=20),
                text_content="Second sentence for translation.",
                formatting=TextFormatting(is_italic=True, color="#FF0000")
            ),
            TextRegion(
                bounding_box=BoundingBox(x=50, y=110, width=500, height=20),
                text_content="Third sentence in the document.",
                formatting=TextFormatting(font_size=14.0)
            )
        ]
        
        for region in regions:
            page.text_regions.append(region)
        
        doc.add_page(page)
        
        # Translate all regions
        translated_regions = service.translate_with_context(
            page.text_regions, "en", "fr"
        )
        
        # Verify results
        assert len(translated_regions) == 3
        
        for i, translated_region in enumerate(translated_regions):
            assert isinstance(translated_region, TranslatedRegion)
            assert translated_region.original_region == regions[i]
            assert translated_region.translation_result.source_language == "en"
            assert translated_region.translation_result.target_language == "fr"
            assert translated_region.translation_result.translation_method == "context_aware_neural"
            
            # Check that formatting was preserved
            assert translated_region.formatted_text is not None
            assert len(translated_region.formatted_text.formatting_tags) > 0
    
    def test_context_awareness_with_document_structure(self):
        """Test that context is properly built from document structure."""
        service = ContextAwareTranslationService()
        
        # Create regions that should provide context for each other
        regions = [
            TextRegion(text_content="The document discusses artificial intelligence."),
            TextRegion(text_content="Machine learning is a subset of AI."),
            TextRegion(text_content="Neural networks are powerful tools."),  # This will be translated
            TextRegion(text_content="They can process complex patterns."),
            TextRegion(text_content="Applications include image recognition.")
        ]
        
        # Test context building for middle region
        context = service._build_translation_context(regions[2], regions, 2)
        
        # Should include surrounding context
        assert "artificial intelligence" in context.preceding_text
        assert "Machine learning" in context.preceding_text
        assert "complex patterns" in context.following_text
        assert "Applications include" in context.following_text
    
    def test_formatting_preservation_integration(self):
        """Test formatting preservation with realistic document content."""
        service = ContextAwareTranslationService()
        
        # Create region with complex formatting (as would come from parser)
        formatting = TextFormatting(
            font_family="Times New Roman",
            font_size=16.0,
            is_bold=True,
            is_italic=False,
            is_underlined=True,
            color="#0000FF",
            alignment="center"
        )
        
        region = TextRegion(
            bounding_box=BoundingBox(x=100, y=200, width=400, height=30),
            text_content="Chapter 1: Introduction to Machine Translation",
            formatting=formatting
        )
        
        # Test formatting preservation
        formatted_text = service.preserve_formatting(region, "Chapitre 1: Introduction à la Traduction Automatique")
        
        # Verify formatting was extracted and preserved
        assert formatted_text.content == "Chapitre 1: Introduction à la Traduction Automatique"
        
        # Check formatting tags
        tag_types = [tag['type'] for tag in formatted_text.formatting_tags]
        assert 'bold' in tag_types
        assert 'underline' in tag_types
        assert 'color' in tag_types
        
        # Check style mapping
        assert formatted_text.style_mapping['font-family'] == "Times New Roman"
        assert formatted_text.style_mapping['font-size'] == "16.0pt"
        assert formatted_text.style_mapping['font-weight'] == "bold"
        assert formatted_text.style_mapping['text-decoration'] == "underline"
        assert formatted_text.style_mapping['color'] == "#0000FF"
        assert formatted_text.style_mapping['text-align'] == "center"
    
    @patch('src.translation.translation_service.pipeline')
    @patch('src.translation.translation_service.AutoTokenizer')
    def test_batch_processing_efficiency(self, mock_tokenizer, mock_pipeline):
        """Test batch processing with multiple regions."""
        service = ContextAwareTranslationService(batch_size=3)  # Small batch for testing
        
        # Mock translation pipeline
        mock_translator = Mock()
        mock_translator.side_effect = [
            [{"translation_text": f"Texte traduit {i}"}] for i in range(1, 8)
        ]
        mock_pipeline.return_value = mock_translator
        mock_tokenizer.from_pretrained.return_value = Mock()
        
        # Create 7 regions (will be processed in batches of 3)
        regions = [
            TextRegion(text_content=f"Text to translate {i}")
            for i in range(1, 8)
        ]
        
        # Translate all regions
        translated_regions = service.translate_with_context(regions, "en", "fr")
        
        # Verify all regions were translated
        assert len(translated_regions) == 7
        
        # Verify batch processing occurred (should have made 7 translation calls)
        assert mock_translator.call_count == 7
        
        # Verify results
        for i, translated_region in enumerate(translated_regions):
            expected_translation = f"Texte traduit {i + 1}"
            assert translated_region.translation_result.translated_text == expected_translation
    
    def test_language_pair_validation_integration(self):
        """Test language pair validation with realistic scenarios."""
        service = ContextAwareTranslationService()
        
        # Test common valid pairs
        common_pairs = [
            ("en", "fr"), ("en", "de"), ("en", "es"), ("en", "it"),
            ("fr", "en"), ("de", "en"), ("es", "en"), ("it", "en")
        ]
        
        for source, target in common_pairs:
            assert service.validate_language_pair(source, target), f"Should support {source}->{target}"
        
        # Test invalid pairs
        invalid_pairs = [
            ("en", "en"),    # Same language
            ("xyz", "abc"),  # Unsupported languages
            ("en", "xyz"),   # Unsupported target
            ("xyz", "en"),   # Unsupported source
        ]
        
        for source, target in invalid_pairs:
            assert not service.validate_language_pair(source, target), f"Should not support {source}->{target}"
    
    def test_error_recovery_integration(self):
        """Test error recovery in integrated translation workflow."""
        service = ContextAwareTranslationService()
        
        # Test with unsupported language pair
        regions = [TextRegion(text_content="Test text")]
        
        with pytest.raises(ValueError, match="Unsupported language pair"):
            service.translate_with_context(regions, "xyz", "abc")
        
        # Test with empty regions
        empty_regions = []
        
        # Should handle gracefully
        try:
            result = service.translate_with_context(empty_regions, "en", "fr")
            assert result == []
        except Exception as e:
            pytest.fail(f"Should handle empty regions gracefully, but got: {e}")
    
    @patch('src.translation.translation_service.pipeline')
    @patch('src.translation.translation_service.AutoTokenizer')
    def test_translation_quality_assessment(self, mock_tokenizer, mock_pipeline):
        """Test translation quality assessment integration."""
        service = ContextAwareTranslationService()
        
        # Mock translation with varying quality
        mock_translator = Mock()
        mock_translator.side_effect = [
            [{"translation_text": "Excellent translation with good length"}],  # Good quality
            [{"translation_text": "Short"}],  # Lower quality (too short)
            [{"translation_text": ""}],  # Very poor quality (empty)
        ]
        mock_pipeline.return_value = mock_translator
        mock_tokenizer.from_pretrained.return_value = Mock()
        
        regions = [
            TextRegion(text_content="This is a comprehensive sentence with good content."),
            TextRegion(text_content="This is another sentence."),
            TextRegion(text_content="Final sentence for testing.")
        ]
        
        translated_regions = service.translate_with_context(regions, "en", "fr")
        
        # Check quality scores
        assert len(translated_regions) == 3
        
        # First translation should have higher quality (good length ratio)
        assert translated_regions[0].quality_score > translated_regions[1].quality_score
        
        # Third translation should have lowest quality (empty result)
        assert translated_regions[2].quality_score < translated_regions[1].quality_score
    
    def test_memory_management_integration(self):
        """Test memory management and model cleanup."""
        service = ContextAwareTranslationService()
        
        # Simulate loading models
        service._translation_pipelines["en-fr"] = Mock()
        service._translation_pipelines["en-de"] = Mock()
        service._tokenizers["en-fr"] = Mock()
        service._tokenizers["en-de"] = Mock()
        
        # Verify models are loaded
        assert len(service._translation_pipelines) == 2
        assert len(service._tokenizers) == 2
        
        # Test cleanup
        with patch('src.translation.translation_service.gc') as mock_gc, \
             patch('src.translation.translation_service.torch') as mock_torch:
            
            mock_torch.cuda.is_available.return_value = False  # CPU mode
            
            service.cleanup_models()
            
            # Verify cleanup
            assert len(service._translation_pipelines) == 0
            assert len(service._tokenizers) == 0
            mock_gc.collect.assert_called_once()
    
    def test_progress_tracking_integration(self):
        """Test progress tracking during translation."""
        service = ContextAwareTranslationService()
        
        # Test progress calculation
        total_regions = 100
        
        # Test various completion stages
        stages = [0, 25, 50, 75, 100]
        
        for completed in stages:
            progress = service.get_translation_progress(total_regions, completed)
            
            expected_percentage = (completed / total_regions) * 100
            assert progress.completion_percentage == expected_percentage
            assert progress.total_regions == total_regions
            assert progress.completed_regions == completed
            
            # Success rate should be 100% when no failures
            assert progress.success_rate == 100.0
    
    def test_supported_language_pairs_completeness(self):
        """Test that supported language pairs cover expected combinations."""
        service = ContextAwareTranslationService()
        
        pairs = service.get_supported_language_pairs()
        pair_strings = [f"{p.source_language}-{p.target_language}" for p in pairs]
        
        # Check that we have English to/from major languages
        major_languages = ['fr', 'de', 'es', 'it', 'pt', 'ru', 'zh', 'ja', 'ko']
        
        for lang in major_languages:
            en_to_lang = f"en-{lang}"
            lang_to_en = f"{lang}-en"
            
            # At least one direction should be supported
            assert en_to_lang in pair_strings or lang_to_en in pair_strings, \
                f"Should support translation between English and {lang}"
        
        # Verify all pairs have quality ratings
        for pair in pairs:
            assert 0.0 <= pair.quality_rating <= 1.0
            assert pair.is_supported is True
            assert pair.model_name is not None