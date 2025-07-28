"""Tests for validation functions."""

import pytest
from pathlib import Path
import tempfile

from src.models.validation import (
    ValidationError,
    validate_file_format,
    validate_file_size,
    validate_language_code,
    validate_language_pair,
    validate_document_structure,
    validate_text_content,
    validate_processing_config,
)
from src.models.document import DocumentStructure, PageStructure, Dimensions, TextRegion
from src.models.quality import QualityScore, QualityMetrics, QualityThreshold


class TestFileValidation:
    """Test cases for file validation functions."""
    
    def test_validate_file_format_valid(self):
        """Test validation of valid file formats."""
        assert validate_file_format("document.pdf")
        assert validate_file_format("document.docx")
        assert validate_file_format("document.epub")
        assert validate_file_format("DOCUMENT.PDF")  # Case insensitive
    
    def test_validate_file_format_invalid(self):
        """Test validation of invalid file formats."""
        with pytest.raises(ValidationError, match="Unsupported file format"):
            validate_file_format("document.txt")
        
        with pytest.raises(ValidationError, match="Unsupported file format"):
            validate_file_format("document.jpg")
    
    def test_validate_file_size_valid(self):
        """Test validation of valid file sizes."""
        assert validate_file_size(1024)  # 1KB
        assert validate_file_size(1024 * 1024)  # 1MB
        assert validate_file_size(10 * 1024 * 1024)  # 10MB
    
    def test_validate_file_size_invalid(self):
        """Test validation of invalid file sizes."""
        max_size = 50 * 1024 * 1024  # 50MB
        large_size = 100 * 1024 * 1024  # 100MB
        
        with pytest.raises(ValidationError, match="File size.*exceeds maximum"):
            validate_file_size(large_size, max_size)


class TestLanguageValidation:
    """Test cases for language validation functions."""
    
    def test_validate_language_code_valid(self):
        """Test validation of valid language codes."""
        assert validate_language_code("en")
        assert validate_language_code("fr")
        assert validate_language_code("zh")
        assert validate_language_code("ja")
    
    def test_validate_language_code_invalid(self):
        """Test validation of invalid language codes."""
        with pytest.raises(ValidationError, match="Unsupported language"):
            validate_language_code("xx")
        
        with pytest.raises(ValidationError, match="Unsupported language"):
            validate_language_code("invalid")
    
    def test_validate_language_pair_valid(self):
        """Test validation of valid language pairs."""
        assert validate_language_pair("en", "fr")
        assert validate_language_pair("zh", "en")
        assert validate_language_pair("ja", "ko")
    
    def test_validate_language_pair_invalid(self):
        """Test validation of invalid language pairs."""
        # Same source and target
        with pytest.raises(ValidationError, match="Source and target languages must be different"):
            validate_language_pair("en", "en")
        
        # Invalid source language
        with pytest.raises(ValidationError, match="Unsupported language"):
            validate_language_pair("xx", "en")
        
        # Invalid target language
        with pytest.raises(ValidationError, match="Unsupported language"):
            validate_language_pair("en", "xx")


class TestDocumentValidation:
    """Test cases for document validation functions."""
    
    def test_validate_document_structure_valid(self):
        """Test validation of valid document structure."""
        # Create valid document
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612.0, height=792.0)
        page = PageStructure(page_number=1, dimensions=dims)
        page.text_regions.append(TextRegion(text_content="Test content", language="en"))
        doc.add_page(page)
        
        assert validate_document_structure(doc)
    
    def test_validate_document_structure_no_pages(self):
        """Test validation of document with no pages."""
        doc = DocumentStructure(format="pdf")
        
        with pytest.raises(ValidationError, match="Document must contain at least one page"):
            validate_document_structure(doc)
    
    def test_validate_document_structure_invalid_page_numbers(self):
        """Test validation of document with invalid page numbers."""
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612.0, height=792.0)
        
        # Add pages with non-sequential numbers
        page1 = PageStructure(page_number=1, dimensions=dims)
        page3 = PageStructure(page_number=3, dimensions=dims)  # Skip page 2
        
        doc.pages = [page1, page3]
        doc.metadata.page_count = 2
        
        with pytest.raises(ValidationError, match="Page numbers must be sequential"):
            validate_document_structure(doc)


class TestTextValidation:
    """Test cases for text validation functions."""
    
    def test_validate_text_content_valid(self):
        """Test validation of valid text content."""
        assert validate_text_content("Hello, world!")
        assert validate_text_content("This is a longer text with multiple sentences.")
        assert validate_text_content("Text with numbers 123 and symbols @#$%")
    
    def test_validate_text_content_empty(self):
        """Test validation of empty text content."""
        with pytest.raises(ValidationError, match="Text content cannot be empty"):
            validate_text_content("")
        
        with pytest.raises(ValidationError, match="Text content cannot be empty"):
            validate_text_content("   ")  # Only whitespace
    
    def test_validate_text_content_too_long(self):
        """Test validation of text that's too long."""
        long_text = "a" * 10001  # Exceeds default max length of 10000
        
        with pytest.raises(ValidationError, match="Text content too long"):
            validate_text_content(long_text)
    
    def test_validate_text_content_malicious(self):
        """Test validation of potentially malicious text content."""
        malicious_texts = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<div onclick='alert()'>Click me</div>",
        ]
        
        for text in malicious_texts:
            with pytest.raises(ValidationError, match="potentially malicious code"):
                validate_text_content(text)


class TestConfigValidation:
    """Test cases for configuration validation functions."""
    
    def test_validate_processing_config_valid(self):
        """Test validation of valid processing configuration."""
        config = {
            'supported_formats': ['pdf', 'docx', 'epub'],
            'max_file_size': 50 * 1024 * 1024,
            'temp_storage_duration': 3600,
            'concurrent_processing': True
        }
        
        assert validate_processing_config(config)
    
    def test_validate_processing_config_missing_keys(self):
        """Test validation of configuration with missing keys."""
        config = {
            'supported_formats': ['pdf', 'docx'],
            # Missing max_file_size and temp_storage_duration
        }
        
        with pytest.raises(ValidationError, match="Missing required configuration key"):
            validate_processing_config(config)
    
    def test_validate_processing_config_invalid_format(self):
        """Test validation of configuration with invalid format."""
        config = {
            'supported_formats': ['pdf', 'txt'],  # txt not supported
            'max_file_size': 50 * 1024 * 1024,
            'temp_storage_duration': 3600,
        }
        
        with pytest.raises(ValidationError, match="Unsupported format in configuration"):
            validate_processing_config(config)
    
    def test_validate_processing_config_invalid_values(self):
        """Test validation of configuration with invalid values."""
        # Invalid max_file_size
        config1 = {
            'supported_formats': ['pdf', 'docx'],
            'max_file_size': -1,  # Negative value
            'temp_storage_duration': 3600,
        }
        
        with pytest.raises(ValidationError, match="max_file_size must be positive"):
            validate_processing_config(config1)
        
        # Invalid temp_storage_duration
        config2 = {
            'supported_formats': ['pdf', 'docx'],
            'max_file_size': 50 * 1024 * 1024,
            'temp_storage_duration': 0,  # Zero value
        }
        
        with pytest.raises(ValidationError, match="temp_storage_duration must be positive"):
            validate_processing_config(config2)