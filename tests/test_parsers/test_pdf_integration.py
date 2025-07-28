"""Integration tests for PDF parser with factory."""

import pytest
from unittest.mock import Mock, patch

from src.parsers import get_parser_factory, PDFParser
from src.parsers.base import ParsingError
from src.models.document import DocumentStructure


class TestPDFParserIntegration:
    """Integration tests for PDF parser with factory."""
    
    def test_pdf_parser_registered(self):
        """Test that PDF parser is registered in global factory."""
        factory = get_parser_factory()
        
        assert "pdf" in factory.get_supported_formats()
        assert factory.is_format_supported("pdf")
        assert factory.is_format_supported("PDF")
        assert factory.is_format_supported(".pdf")
    
    def test_create_pdf_parser_from_factory(self):
        """Test creating PDF parser from factory."""
        factory = get_parser_factory()
        
        parser = factory.create_parser("pdf")
        assert isinstance(parser, PDFParser)
        
        parser = factory.create_parser("PDF")
        assert isinstance(parser, PDFParser)
        
        parser = factory.create_parser(".pdf")
        assert isinstance(parser, PDFParser)
    
    def test_get_parser_for_pdf_file(self, temp_dir):
        """Test getting parser for PDF file."""
        factory = get_parser_factory()
        
        # Create a test PDF file
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")
        
        parser = factory.get_parser_for_file(str(pdf_file))
        assert isinstance(parser, PDFParser)
    
    @patch('fitz.open')
    def test_parse_pdf_through_factory(self, mock_fitz_open, temp_dir):
        """Test parsing PDF through factory."""
        factory = get_parser_factory()
        
        # Mock PyMuPDF document
        mock_doc = Mock()
        mock_doc.is_encrypted = False
        mock_doc.metadata = {'title': 'Test PDF'}
        mock_doc.__len__ = Mock(return_value=1)
        
        # Mock page
        mock_page = Mock()
        mock_page.number = 0
        mock_page.rect = Mock(width=612, height=792)
        mock_page.get_text.return_value = {"blocks": []}
        mock_page.get_images.return_value = []
        mock_page.get_drawings.return_value = []
        
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        mock_fitz_open.return_value = mock_doc
        
        # Create test file
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")
        
        # Mock file validation
        with patch('src.parsers.base.validate_file_format'), \
             patch('src.parsers.base.validate_file_size'), \
             patch('pathlib.Path.stat') as mock_stat:
            
            mock_stat.return_value.st_size = 1024
            
            # Parse through factory
            structure = factory.parse_document(str(pdf_file))
        
        assert isinstance(structure, DocumentStructure)
        assert structure.format == "pdf"
        assert len(structure.pages) == 1
        mock_doc.close.assert_called_once()
    
    @patch('fitz.open')
    def test_reconstruct_pdf_through_factory(self, mock_fitz_open):
        """Test reconstructing PDF through factory."""
        factory = get_parser_factory()
        
        # Mock new document for reconstruction
        mock_doc = Mock()
        mock_page = Mock()
        mock_doc.new_page.return_value = mock_page
        mock_doc.tobytes.return_value = b"reconstructed pdf"
        mock_fitz_open.return_value = mock_doc
        
        # Create test document structure
        from src.models.document import PageStructure, Dimensions
        
        structure = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        structure.add_page(page)
        
        # Reconstruct through factory
        content = factory.reconstruct_document(structure)
        
        assert content == b"reconstructed pdf"
        mock_doc.close.assert_called_once()
    
    def test_pdf_parser_error_handling(self):
        """Test PDF parser error handling through factory."""
        factory = get_parser_factory()
        
        # Test with non-existent file
        with pytest.raises(ParsingError):
            factory.parse_document("nonexistent.pdf")
    
    def test_multiple_pdf_parsers(self):
        """Test that factory creates separate parser instances."""
        factory = get_parser_factory()
        
        parser1 = factory.create_parser("pdf")
        parser2 = factory.create_parser("pdf")
        
        # Should be different instances
        assert parser1 is not parser2
        assert isinstance(parser1, PDFParser)
        assert isinstance(parser2, PDFParser)
    
    def test_pdf_parser_supported_formats(self):
        """Test PDF parser supported formats."""
        factory = get_parser_factory()
        parser = factory.create_parser("pdf")
        
        formats = parser.get_supported_formats()
        assert formats == ["pdf"]
        assert len(formats) == 1