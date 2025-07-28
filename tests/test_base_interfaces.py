"""Tests for base interfaces and factory classes."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.parsers.base import (
    DocumentParserFactory, DocumentParser, ParsingError, ReconstructionError,
    get_parser_factory, register_parser
)
from src.models.document import (
    DocumentStructure, PageStructure, Dimensions, DocumentMetadata
)


class MockParser(DocumentParser):
    """Mock parser for testing."""
    
    def parse(self, file_path: str) -> DocumentStructure:
        # Create a valid document structure
        doc = DocumentStructure(format="mock")
        dims = Dimensions(width=100, height=100)
        page = PageStructure(page_number=1, dimensions=dims)
        doc.add_page(page)
        return doc
    
    def reconstruct(self, structure: DocumentStructure) -> bytes:
        return b"mock content"
    
    def get_supported_formats(self) -> list[str]:
        return ["mock"]


class FailingParser(DocumentParser):
    """Parser that fails for testing error handling."""
    
    def parse(self, file_path: str) -> DocumentStructure:
        raise Exception("Parsing failed")
    
    def reconstruct(self, structure: DocumentStructure) -> bytes:
        raise Exception("Reconstruction failed")
    
    def get_supported_formats(self) -> list[str]:
        return ["fail"]


class TestDocumentParser:
    """Test cases for DocumentParser base class."""
    
    def test_validate_file_nonexistent(self):
        """Test validation of non-existent file."""
        parser = MockParser()
        
        with pytest.raises(ParsingError, match="File not found"):
            parser.validate_file("nonexistent.mock")
    
    def test_validate_file_valid(self, temp_dir):
        """Test validation of valid file."""
        parser = MockParser()
        
        # Create a temporary file
        test_file = temp_dir / "test.mock"
        test_file.write_text("test content")
        
        # Mock the validation functions to avoid import issues
        with patch('src.parsers.base.validate_file_format'), \
             patch('src.parsers.base.validate_file_size'):
            assert parser.validate_file(str(test_file))
    
    def test_extract_metadata(self, temp_dir):
        """Test metadata extraction."""
        parser = MockParser()
        
        # Create a temporary file
        test_file = temp_dir / "test_document.mock"
        test_file.write_text("test content")
        
        metadata = parser.extract_metadata(str(test_file))
        
        assert metadata.title == "test_document"
        assert metadata.file_size > 0
        assert metadata.creation_date is not None
    
    def test_parse_with_validation_success(self, temp_dir):
        """Test successful parsing with validation."""
        parser = MockParser()
        
        # Create a temporary file
        test_file = temp_dir / "test.mock"
        test_file.write_text("test content")
        
        # Mock validation functions
        with patch('src.parsers.base.validate_file_format'), \
             patch('src.parsers.base.validate_file_size'):
            
            structure = parser.parse_with_validation(str(test_file))
            
            assert isinstance(structure, DocumentStructure)
            assert structure.format == "mock"
            assert len(structure.pages) == 1
    
    def test_parse_with_validation_failure(self, temp_dir):
        """Test parsing failure with validation."""
        parser = FailingParser()
        
        # Create a temporary file
        test_file = temp_dir / "test.fail"
        test_file.write_text("test content")
        
        # Mock validation functions
        with patch('src.parsers.base.validate_file_format'), \
             patch('src.parsers.base.validate_file_size'):
            
            with pytest.raises(ParsingError, match="Unexpected error during parsing"):
                parser.parse_with_validation(str(test_file))
    
    def test_reconstruct_with_validation_success(self):
        """Test successful reconstruction with validation."""
        parser = MockParser()
        
        # Create a valid document structure
        doc = DocumentStructure(format="mock")
        dims = Dimensions(width=100, height=100)
        page = PageStructure(page_number=1, dimensions=dims)
        doc.add_page(page)
        
        content = parser.reconstruct_with_validation(doc)
        
        assert content == b"mock content"
    
    def test_reconstruct_with_validation_empty_pages(self):
        """Test reconstruction with empty pages."""
        parser = MockParser()
        
        # Create document with no pages
        doc = DocumentStructure(format="mock")
        
        with pytest.raises(ReconstructionError, match="Cannot reconstruct document with no pages"):
            parser.reconstruct_with_validation(doc)
    
    def test_reconstruct_with_validation_unsupported_format(self):
        """Test reconstruction with unsupported format."""
        parser = MockParser()
        
        # Create document with unsupported format
        doc = DocumentStructure(format="unsupported")
        dims = Dimensions(width=100, height=100)
        page = PageStructure(page_number=1, dimensions=dims)
        doc.add_page(page)
        
        with pytest.raises(ReconstructionError, match="Format unsupported not supported"):
            parser.reconstruct_with_validation(doc)


class TestDocumentParserFactory:
    """Test cases for DocumentParserFactory."""
    
    def test_register_and_create_parser(self):
        """Test parser registration and creation."""
        factory = DocumentParserFactory()
        factory.register_parser("mock", MockParser)
        
        parser = factory.create_parser("mock")
        assert isinstance(parser, MockParser)
    
    def test_register_invalid_parser_class(self):
        """Test registering invalid parser class."""
        factory = DocumentParserFactory()
        
        class NotAParser:
            pass
        
        with pytest.raises(ValueError, match="Parser class must be a subclass of DocumentParser"):
            factory.register_parser("invalid", NotAParser)
    
    def test_unregister_parser(self):
        """Test unregistering a parser."""
        factory = DocumentParserFactory()
        factory.register_parser("mock", MockParser)
        
        # Verify parser is registered
        assert "mock" in factory.get_supported_formats()
        
        # Unregister parser
        result = factory.unregister_parser("mock")
        assert result is True
        assert "mock" not in factory.get_supported_formats()
        
        # Try to unregister non-existent parser
        result = factory.unregister_parser("nonexistent")
        assert result is False
    
    def test_unsupported_format_raises_error(self):
        """Test that unsupported format raises ValueError."""
        factory = DocumentParserFactory()
        
        with pytest.raises(ValueError, match="Unsupported format"):
            factory.create_parser("unsupported")
    
    def test_get_supported_formats(self):
        """Test getting supported formats."""
        factory = DocumentParserFactory()
        factory.register_parser("mock", MockParser)
        factory.register_parser("fail", FailingParser)
        
        formats = factory.get_supported_formats()
        assert "mock" in formats
        assert "fail" in formats
        assert len(formats) == 2
    
    def test_case_insensitive_format(self):
        """Test that format matching is case insensitive."""
        factory = DocumentParserFactory()
        factory.register_parser("MOCK", MockParser)
        
        parser = factory.create_parser("mock")
        assert isinstance(parser, MockParser)
        
        parser = factory.create_parser(".MOCK")
        assert isinstance(parser, MockParser)
    
    def test_is_format_supported(self):
        """Test format support checking."""
        factory = DocumentParserFactory()
        factory.register_parser("mock", MockParser)
        
        assert factory.is_format_supported("mock")
        assert factory.is_format_supported("MOCK")
        assert factory.is_format_supported(".mock")
        assert not factory.is_format_supported("unsupported")
    
    def test_get_parser_for_file(self, temp_dir):
        """Test getting parser for a specific file."""
        factory = DocumentParserFactory()
        factory.register_parser("mock", MockParser)
        
        # Create a test file
        test_file = temp_dir / "test.mock"
        test_file.write_text("test content")
        
        parser = factory.get_parser_for_file(str(test_file))
        assert isinstance(parser, MockParser)
    
    def test_get_parser_for_file_unsupported(self, temp_dir):
        """Test getting parser for unsupported file format."""
        factory = DocumentParserFactory()
        
        # Create a test file with unsupported extension
        test_file = temp_dir / "test.unsupported"
        test_file.write_text("test content")
        
        with pytest.raises(ValueError, match="Unsupported format"):
            factory.get_parser_for_file(str(test_file))
    
    def test_parse_document(self, temp_dir):
        """Test parsing document through factory."""
        factory = DocumentParserFactory()
        factory.register_parser("mock", MockParser)
        
        # Create a test file
        test_file = temp_dir / "test.mock"
        test_file.write_text("test content")
        
        # Mock validation functions
        with patch('src.parsers.base.validate_file_format'), \
             patch('src.parsers.base.validate_file_size'):
            
            structure = factory.parse_document(str(test_file))
            
            assert isinstance(structure, DocumentStructure)
            assert structure.format == "mock"
    
    def test_reconstruct_document(self):
        """Test reconstructing document through factory."""
        factory = DocumentParserFactory()
        factory.register_parser("mock", MockParser)
        
        # Create a valid document structure
        doc = DocumentStructure(format="mock")
        dims = Dimensions(width=100, height=100)
        page = PageStructure(page_number=1, dimensions=dims)
        doc.add_page(page)
        
        content = factory.reconstruct_document(doc)
        assert content == b"mock content"


class TestGlobalFactory:
    """Test cases for global factory functions."""
    
    def test_get_parser_factory(self):
        """Test getting global parser factory."""
        factory1 = get_parser_factory()
        factory2 = get_parser_factory()
        
        # Should return the same instance
        assert factory1 is factory2
        assert isinstance(factory1, DocumentParserFactory)
    
    def test_register_parser_global(self):
        """Test registering parser in global factory."""
        register_parser("mock", MockParser)
        
        factory = get_parser_factory()
        assert "mock" in factory.get_supported_formats()
        
        parser = factory.create_parser("mock")
        assert isinstance(parser, MockParser)