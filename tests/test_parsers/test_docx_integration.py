"""Integration tests for DOCX parser with factory."""

import pytest
from unittest.mock import Mock, patch

from src.parsers import get_parser_factory, DOCXParser
from src.parsers.base import ParsingError
from src.models.document import DocumentStructure


class TestDOCXParserIntegration:
    """Integration tests for DOCX parser with factory."""
    
    def test_docx_parser_registered(self):
        """Test that DOCX parser is registered in global factory."""
        factory = get_parser_factory()
        
        assert "docx" in factory.get_supported_formats()
        assert factory.is_format_supported("docx")
        assert factory.is_format_supported("DOCX")
        assert factory.is_format_supported(".docx")
    
    def test_create_docx_parser_from_factory(self):
        """Test creating DOCX parser from factory."""
        factory = get_parser_factory()
        
        parser = factory.create_parser("docx")
        assert isinstance(parser, DOCXParser)
        
        parser = factory.create_parser("DOCX")
        assert isinstance(parser, DOCXParser)
        
        parser = factory.create_parser(".docx")
        assert isinstance(parser, DOCXParser)
    
    def test_get_parser_for_docx_file(self, temp_dir):
        """Test getting parser for DOCX file."""
        factory = get_parser_factory()
        
        # Create a test DOCX file
        docx_file = temp_dir / "test.docx"
        docx_file.write_bytes(b"fake docx content")
        
        parser = factory.get_parser_for_file(str(docx_file))
        assert isinstance(parser, DOCXParser)
    
    @patch('docx.Document')
    def test_parse_docx_through_factory(self, mock_document_class, temp_dir):
        """Test parsing DOCX through factory."""
        factory = get_parser_factory()
        
        # Mock Document object
        mock_doc = Mock()
        mock_document_class.return_value = mock_doc
        
        # Mock core properties
        mock_core_props = Mock()
        mock_core_props.title = "Test DOCX"
        mock_core_props.author = "Test Author"
        mock_core_props.subject = None
        mock_core_props.creator = None
        mock_core_props.created = None
        mock_core_props.modified = None
        mock_doc.core_properties = mock_core_props
        
        # Mock empty content
        mock_doc.paragraphs = []
        mock_doc.tables = []
        mock_doc.part.rels.values.return_value = []
        
        # Create test file
        docx_file = temp_dir / "test.docx"
        docx_file.write_bytes(b"fake docx content")
        
        # Mock file validation
        with patch('src.parsers.base.validate_file_format'), \
             patch('src.parsers.base.validate_file_size'), \
             patch('pathlib.Path.stat') as mock_stat:
            
            mock_stat.return_value.st_size = 2048
            
            # Parse through factory
            structure = factory.parse_document(str(docx_file))
        
        assert isinstance(structure, DocumentStructure)
        assert structure.format == "docx"
        assert len(structure.pages) == 1
        assert structure.metadata.title == "Test DOCX"
        assert structure.metadata.author == "Test Author"
    
    @patch('docx.Document')
    def test_reconstruct_docx_through_factory(self, mock_document_class):
        """Test reconstructing DOCX through factory."""
        factory = get_parser_factory()
        
        # Mock new document for reconstruction
        mock_doc = Mock()
        mock_document_class.return_value = mock_doc
        
        # Mock core properties
        mock_core_props = Mock()
        mock_doc.core_properties = mock_core_props
        
        # Mock paragraph creation
        mock_paragraph = Mock()
        mock_run = Mock()
        mock_run.font = Mock()
        mock_paragraph.add_run.return_value = mock_run
        mock_doc.add_paragraph.return_value = mock_paragraph
        
        # Create test document structure
        from src.models.document import PageStructure, Dimensions, DocumentMetadata
        
        structure = DocumentStructure(format="docx")
        structure.metadata = DocumentMetadata(title="Test")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        structure.add_page(page)
        
        # Mock document_to_bytes
        with patch('io.BytesIO') as mock_bytes_io:
            mock_bytes_io.return_value.read.return_value = b"reconstructed docx"
            
            # Reconstruct through factory
            content = factory.reconstruct_document(structure)
        
        assert content == b"reconstructed docx"
    
    def test_docx_parser_error_handling(self):
        """Test DOCX parser error handling through factory."""
        factory = get_parser_factory()
        
        # Test with non-existent file
        with pytest.raises(ParsingError):
            factory.parse_document("nonexistent.docx")
    
    def test_multiple_docx_parsers(self):
        """Test that factory creates separate parser instances."""
        factory = get_parser_factory()
        
        parser1 = factory.create_parser("docx")
        parser2 = factory.create_parser("docx")
        
        # Should be different instances
        assert parser1 is not parser2
        assert isinstance(parser1, DOCXParser)
        assert isinstance(parser2, DOCXParser)
    
    def test_docx_parser_supported_formats(self):
        """Test DOCX parser supported formats."""
        factory = get_parser_factory()
        parser = factory.create_parser("docx")
        
        formats = parser.get_supported_formats()
        assert formats == ["docx"]
        assert len(formats) == 1
    
    @patch('docx.Document')
    def test_docx_with_complex_content(self, mock_document_class):
        """Test DOCX parsing with complex content."""
        factory = get_parser_factory()
        
        # Mock Document with complex content
        mock_doc = Mock()
        mock_document_class.return_value = mock_doc
        
        # Mock core properties
        mock_core_props = Mock()
        mock_core_props.title = "Complex Document"
        mock_core_props.author = "Author"
        mock_core_props.subject = "Subject"
        mock_core_props.creator = "Creator"
        mock_core_props.created = None
        mock_core_props.modified = None
        mock_doc.core_properties = mock_core_props
        
        # Mock paragraph with multiple runs
        mock_paragraph = Mock()
        mock_paragraph.text = "Hello World"
        
        mock_run1 = Mock()
        mock_run1.text = "Hello "
        mock_run1.font = Mock()
        mock_run1.font.size = None
        mock_run1.font.name = "Arial"
        mock_run1.font.bold = False
        mock_run1.font.italic = False
        mock_run1.font.underline = False
        mock_run1.font.color = None
        
        mock_run2 = Mock()
        mock_run2.text = "World"
        mock_run2.font = Mock()
        mock_run2.font.size = Mock()
        mock_run2.font.size.pt = 14
        mock_run2.font.name = "Times"
        mock_run2.font.bold = True
        mock_run2.font.italic = True
        mock_run2.font.underline = False
        mock_run2.font.color = None
        
        mock_paragraph.runs = [mock_run1, mock_run2]
        mock_paragraph.alignment = None
        mock_doc.paragraphs = [mock_paragraph]
        
        # Mock table
        mock_cell = Mock()
        mock_cell.text = "Cell content"
        mock_row = Mock()
        mock_row.cells = [mock_cell]
        mock_table = Mock()
        mock_table.rows = [mock_row]
        mock_doc.tables = [mock_table]
        
        # Mock image relationship
        mock_rel = Mock()
        mock_rel.target_ref = "image1.png"
        mock_rel.target_part.blob = b"image data"
        mock_rel.target_part.content_type = "image/png"
        mock_doc.part.rels.values.return_value = [mock_rel]
        
        # Create test file
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 4096
            
            structure = factory.parse_document("complex.docx")
        
        assert isinstance(structure, DocumentStructure)
        assert structure.format == "docx"
        assert len(structure.pages) == 1
        
        page = structure.pages[0]
        # Should have text regions from paragraph and table
        assert len(page.text_regions) >= 2
        # Should have visual elements from image
        assert len(page.visual_elements) == 1
        
        # Check text content
        text_contents = [region.text_content for region in page.text_regions]
        assert "Hello " in text_contents
        assert "World" in text_contents
        assert "Cell content" in text_contents
        
        # Check visual element
        image_element = page.visual_elements[0]
        assert image_element.element_type == "image"
        assert image_element.content == b"image data"
    
    def test_factory_supports_both_pdf_and_docx(self):
        """Test that factory supports both PDF and DOCX formats."""
        factory = get_parser_factory()
        
        supported_formats = factory.get_supported_formats()
        assert "pdf" in supported_formats
        assert "docx" in supported_formats
        
        # Should be able to create both parsers
        pdf_parser = factory.create_parser("pdf")
        docx_parser = factory.create_parser("docx")
        
        assert pdf_parser.__class__.__name__ == "PDFParser"
        assert docx_parser.__class__.__name__ == "DOCXParser"