"""Tests for base parser functionality."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.parsers.base import (
    DocumentParser, DocumentParserFactory, ParsingError, ReconstructionError
)
from src.models.document import (
    DocumentStructure, PageStructure, Dimensions, TextRegion, BoundingBox
)


class TestDocumentParser:
    """Test cases for DocumentParser abstract base class."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that DocumentParser cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DocumentParser()
    
    def test_subclass_must_implement_abstract_methods(self):
        """Test that subclasses must implement all abstract methods."""
        
        class IncompleteParser(DocumentParser):
            def parse(self, file_path: str) -> DocumentStructure:
                pass
            # Missing reconstruct and get_supported_formats
        
        with pytest.raises(TypeError):
            IncompleteParser()


class ConcreteParser(DocumentParser):
    """Concrete parser implementation for testing."""
    
    def __init__(self, should_fail_parse=False, should_fail_reconstruct=False):
        super().__init__()
        self.should_fail_parse = should_fail_parse
        self.should_fail_reconstruct = should_fail_reconstruct
        self.parse_called = False
        self.reconstruct_called = False
    
    def parse(self, file_path: str) -> DocumentStructure:
        self.parse_called = True
        
        if self.should_fail_parse:
            raise Exception("Intentional parsing failure")
        
        # Create a valid document structure
        doc = DocumentStructure(format="test")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        
        # Add some text content
        text_region = TextRegion(
            bounding_box=BoundingBox(x=50, y=50, width=500, height=20),
            text_content="Sample text content",
            language="en"
        )
        page.text_regions.append(text_region)
        
        doc.add_page(page)
        return doc
    
    def reconstruct(self, structure: DocumentStructure) -> bytes:
        self.reconstruct_called = True
        
        if self.should_fail_reconstruct:
            raise Exception("Intentional reconstruction failure")
        
        return b"reconstructed document content"
    
    def get_supported_formats(self) -> list[str]:
        return ["test", "example"]


class TestConcreteParser:
    """Test cases for concrete parser implementation."""
    
    def test_parser_initialization(self):
        """Test parser initialization."""
        parser = ConcreteParser()
        
        assert hasattr(parser, 'logger')
        assert parser.logger.name == 'ConcreteParser'
        assert not parser.parse_called
        assert not parser.reconstruct_called
    
    def test_get_supported_formats(self):
        """Test getting supported formats."""
        parser = ConcreteParser()
        formats = parser.get_supported_formats()
        
        assert formats == ["test", "example"]
    
    def test_extract_metadata(self, temp_dir):
        """Test metadata extraction from file."""
        parser = ConcreteParser()
        
        # Create a test file
        test_file = temp_dir / "sample_document.test"
        test_content = "This is a sample document for testing."
        test_file.write_text(test_content)
        
        metadata = parser.extract_metadata(str(test_file))
        
        assert metadata.title == "sample_document"
        assert metadata.file_size == len(test_content)
        assert metadata.creation_date is not None
        assert metadata.modification_date is not None
    
    @patch('src.parsers.base.validate_file_format')
    @patch('src.parsers.base.validate_file_size')
    def test_validate_file_success(self, mock_validate_size, mock_validate_format, temp_dir):
        """Test successful file validation."""
        parser = ConcreteParser()
        
        # Create a test file
        test_file = temp_dir / "test.test"
        test_file.write_text("test content")
        
        # Mock validation functions to pass
        mock_validate_format.return_value = True
        mock_validate_size.return_value = True
        
        result = parser.validate_file(str(test_file))
        
        assert result is True
        mock_validate_format.assert_called_once_with(str(test_file))
        mock_validate_size.assert_called_once()
    
    def test_validate_file_not_found(self):
        """Test file validation with non-existent file."""
        parser = ConcreteParser()
        
        with pytest.raises(ParsingError, match="File not found"):
            parser.validate_file("nonexistent.test")
    
    def test_validate_file_not_a_file(self, temp_dir):
        """Test file validation with directory instead of file."""
        parser = ConcreteParser()
        
        # Create a directory
        test_dir = temp_dir / "test_directory"
        test_dir.mkdir()
        
        with pytest.raises(ParsingError, match="Path is not a file"):
            parser.validate_file(str(test_dir))
    
    @patch('src.parsers.base.validate_file_format')
    @patch('src.parsers.base.validate_file_size')
    def test_validate_file_unsupported_format(self, mock_validate_size, mock_validate_format, temp_dir):
        """Test file validation with unsupported format."""
        parser = ConcreteParser()
        
        # Create a file with unsupported extension
        test_file = temp_dir / "test.unsupported"
        test_file.write_text("test content")
        
        # Mock validation functions to pass
        mock_validate_format.return_value = True
        mock_validate_size.return_value = True
        
        with pytest.raises(ParsingError, match="Format unsupported not supported"):
            parser.validate_file(str(test_file))
    
    @patch('src.parsers.base.validate_file_format')
    @patch('src.parsers.base.validate_file_size')
    def test_parse_with_validation_success(self, mock_validate_size, mock_validate_format, temp_dir):
        """Test successful parsing with validation."""
        parser = ConcreteParser()
        
        # Create a test file
        test_file = temp_dir / "test.test"
        test_file.write_text("test content")
        
        # Mock validation functions
        mock_validate_format.return_value = True
        mock_validate_size.return_value = True
        
        structure = parser.parse_with_validation(str(test_file))
        
        assert isinstance(structure, DocumentStructure)
        assert structure.format == "test"
        assert len(structure.pages) == 1
        assert len(structure.pages[0].text_regions) == 1
        assert parser.parse_called
    
    @patch('src.parsers.base.validate_file_format')
    @patch('src.parsers.base.validate_file_size')
    def test_parse_with_validation_parsing_failure(self, mock_validate_size, mock_validate_format, temp_dir):
        """Test parsing failure during validation."""
        parser = ConcreteParser(should_fail_parse=True)
        
        # Create a test file
        test_file = temp_dir / "test.test"
        test_file.write_text("test content")
        
        # Mock validation functions
        mock_validate_format.return_value = True
        mock_validate_size.return_value = True
        
        with pytest.raises(ParsingError, match="Unexpected error during parsing"):
            parser.parse_with_validation(str(test_file))
        
        assert parser.parse_called
    
    def test_reconstruct_with_validation_success(self):
        """Test successful reconstruction with validation."""
        parser = ConcreteParser()
        
        # Create a valid document structure
        doc = DocumentStructure(format="test")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        doc.add_page(page)
        
        content = parser.reconstruct_with_validation(doc)
        
        assert content == b"reconstructed document content"
        assert parser.reconstruct_called
    
    def test_reconstruct_with_validation_no_pages(self):
        """Test reconstruction with document containing no pages."""
        parser = ConcreteParser()
        
        # Create document with no pages
        doc = DocumentStructure(format="test")
        
        with pytest.raises(ReconstructionError, match="Cannot reconstruct document with no pages"):
            parser.reconstruct_with_validation(doc)
        
        assert not parser.reconstruct_called
    
    def test_reconstruct_with_validation_unsupported_format(self):
        """Test reconstruction with unsupported format."""
        parser = ConcreteParser()
        
        # Create document with unsupported format
        doc = DocumentStructure(format="unsupported")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        doc.add_page(page)
        
        with pytest.raises(ReconstructionError, match="Format unsupported not supported"):
            parser.reconstruct_with_validation(doc)
        
        assert not parser.reconstruct_called
    
    def test_reconstruct_with_validation_reconstruction_failure(self):
        """Test reconstruction failure during validation."""
        parser = ConcreteParser(should_fail_reconstruct=True)
        
        # Create a valid document structure
        doc = DocumentStructure(format="test")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        doc.add_page(page)
        
        with pytest.raises(ReconstructionError, match="Unexpected error during reconstruction"):
            parser.reconstruct_with_validation(doc)
        
        assert parser.reconstruct_called


class TestParsingError:
    """Test cases for ParsingError exception."""
    
    def test_parsing_error_creation(self):
        """Test creating ParsingError."""
        error = ParsingError("Test error", "test.pdf", "TEST_ERROR")
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.file_path == "test.pdf"
        assert error.error_code == "TEST_ERROR"
    
    def test_parsing_error_defaults(self):
        """Test ParsingError with default values."""
        error = ParsingError("Test error")
        
        assert error.message == "Test error"
        assert error.file_path == ""
        assert error.error_code == "PARSING_ERROR"


class TestReconstructionError:
    """Test cases for ReconstructionError exception."""
    
    def test_reconstruction_error_creation(self):
        """Test creating ReconstructionError."""
        error = ReconstructionError("Test error", "pdf", "TEST_ERROR")
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.format_type == "pdf"
        assert error.error_code == "TEST_ERROR"
    
    def test_reconstruction_error_defaults(self):
        """Test ReconstructionError with default values."""
        error = ReconstructionError("Test error")
        
        assert error.message == "Test error"
        assert error.format_type == ""
        assert error.error_code == "RECONSTRUCTION_ERROR"