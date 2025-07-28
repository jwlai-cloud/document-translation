"""Tests for base interfaces and factory classes."""

import pytest
from src.parsers.base import DocumentParserFactory, DocumentParser
from src.models.document import DocumentStructure


class MockParser(DocumentParser):
    """Mock parser for testing."""
    
    def parse(self, file_path: str) -> DocumentStructure:
        return DocumentStructure(format="mock", pages=[], metadata={})
    
    def reconstruct(self, structure: DocumentStructure) -> bytes:
        return b"mock content"
    
    def get_supported_formats(self) -> list[str]:
        return ["mock"]


class TestDocumentParserFactory:
    """Test cases for DocumentParserFactory."""
    
    def test_register_and_create_parser(self):
        """Test parser registration and creation."""
        factory = DocumentParserFactory()
        factory.register_parser("mock", MockParser)
        
        parser = factory.create_parser("mock")
        assert isinstance(parser, MockParser)
    
    def test_unsupported_format_raises_error(self):
        """Test that unsupported format raises ValueError."""
        factory = DocumentParserFactory()
        
        with pytest.raises(ValueError, match="Unsupported format"):
            factory.create_parser("unsupported")
    
    def test_get_supported_formats(self):
        """Test getting supported formats."""
        factory = DocumentParserFactory()
        factory.register_parser("mock", MockParser)
        
        formats = factory.get_supported_formats()
        assert "mock" in formats
    
    def test_case_insensitive_format(self):
        """Test that format matching is case insensitive."""
        factory = DocumentParserFactory()
        factory.register_parser("MOCK", MockParser)
        
        parser = factory.create_parser("mock")
        assert isinstance(parser, MockParser)
        
        parser = factory.create_parser(".MOCK")
        assert isinstance(parser, MockParser)