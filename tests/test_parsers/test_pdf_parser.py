"""Tests for PDF document parser."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path

from src.parsers.pdf_parser import PDFParser
from src.parsers.base import ParsingError, ReconstructionError
from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement,
    BoundingBox, Dimensions, TextFormatting
)


class TestPDFParser:
    """Test cases for PDFParser."""
    
    def test_initialization(self):
        """Test PDF parser initialization."""
        parser = PDFParser()
        
        assert parser.get_supported_formats() == ["pdf"]
        assert hasattr(parser, 'logger')
        assert parser.logger.name == 'PDFParser'
    
    def test_get_supported_formats(self):
        """Test getting supported formats."""
        parser = PDFParser()
        formats = parser.get_supported_formats()
        
        assert formats == ["pdf"]
        assert isinstance(formats, list)
    
    @patch('fitz.open')
    def test_parse_success(self, mock_fitz_open):
        """Test successful PDF parsing."""
        parser = PDFParser()
        
        # Mock PyMuPDF document
        mock_doc = Mock()
        mock_doc.is_encrypted = False
        mock_doc.metadata = {
            'title': 'Test Document',
            'author': 'Test Author',
            'subject': 'Test Subject'
        }
        mock_doc.__len__ = Mock(return_value=2)  # 2 pages
        
        # Mock pages
        mock_page1 = Mock()
        mock_page1.number = 0
        mock_page1.rect = Mock(width=612, height=792)
        mock_page1.get_text.return_value = {"blocks": []}
        mock_page1.get_images.return_value = []
        mock_page1.get_drawings.return_value = []
        
        mock_page2 = Mock()
        mock_page2.number = 1
        mock_page2.rect = Mock(width=612, height=792)
        mock_page2.get_text.return_value = {"blocks": []}
        mock_page2.get_images.return_value = []
        mock_page2.get_drawings.return_value = []
        
        mock_doc.__getitem__ = Mock(side_effect=[mock_page1, mock_page2])
        mock_fitz_open.return_value = mock_doc
        
        # Mock file stat
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024
            
            structure = parser.parse("test.pdf")
        
        assert isinstance(structure, DocumentStructure)
        assert structure.format == "pdf"
        assert len(structure.pages) == 2
        assert structure.metadata.title == "Test Document"
        assert structure.metadata.author == "Test Author"
        assert structure.metadata.page_count == 2
        
        mock_doc.close.assert_called_once()
    
    @patch('fitz.open')
    def test_parse_encrypted_pdf(self, mock_fitz_open):
        """Test parsing encrypted PDF."""
        parser = PDFParser()
        
        # Mock encrypted document
        mock_doc = Mock()
        mock_doc.is_encrypted = True
        mock_fitz_open.return_value = mock_doc
        
        with pytest.raises(ParsingError, match="PDF is encrypted"):
            parser.parse("encrypted.pdf")
        
        mock_doc.close.assert_called_once()
    
    @patch('fitz.open')
    def test_parse_corrupted_pdf(self, mock_fitz_open):
        """Test parsing corrupted PDF."""
        parser = PDFParser()
        
        # Mock file data error
        import fitz
        mock_fitz_open.side_effect = fitz.FileDataError("Corrupted file")
        
        with pytest.raises(ParsingError, match="Invalid or corrupted PDF"):
            parser.parse("corrupted.pdf")
    
    @patch('fitz.open')
    def test_parse_file_not_found(self, mock_fitz_open):
        """Test parsing non-existent PDF."""
        parser = PDFParser()
        
        # Mock file not found error
        import fitz
        mock_fitz_open.side_effect = fitz.FileNotFoundError("File not found")
        
        with pytest.raises(ParsingError, match="PDF file not found"):
            parser.parse("nonexistent.pdf")
    
    def test_extract_text_formatting(self):
        """Test text formatting extraction."""
        parser = PDFParser()
        
        # Test span with formatting flags
        span = {
            'font': 'Times-Roman',
            'size': 14.0,
            'flags': 2**4 | 2**1,  # Bold and italic flags
            'color': 0xFF0000  # Red color
        }
        
        formatting = parser._extract_text_formatting(span)
        
        assert formatting.font_family == 'Times-Roman'
        assert formatting.font_size == 14.0
        assert formatting.is_bold is True
        assert formatting.is_italic is True
        assert formatting.color == "#FF0000"
    
    def test_convert_color(self):
        """Test color conversion from integer to hex."""
        parser = PDFParser()
        
        # Test black color
        assert parser._convert_color(0) == "#000000"
        
        # Test red color
        assert parser._convert_color(0xFF0000) == "#FF0000"
        
        # Test green color
        assert parser._convert_color(0x00FF00) == "#00FF00"
        
        # Test blue color
        assert parser._convert_color(0x0000FF) == "#0000FF"
        
        # Test white color
        assert parser._convert_color(0xFFFFFF) == "#FFFFFF"
    
    def test_hex_to_rgb(self):
        """Test hex color to RGB conversion."""
        parser = PDFParser()
        
        # Test black
        assert parser._hex_to_rgb("#000000") == (0.0, 0.0, 0.0)
        
        # Test white
        assert parser._hex_to_rgb("#FFFFFF") == (1.0, 1.0, 1.0)
        
        # Test red
        assert parser._hex_to_rgb("#FF0000") == (1.0, 0.0, 0.0)
        
        # Test invalid color (should default to black)
        assert parser._hex_to_rgb("invalid") == (0.0, 0.0, 0.0)
        
        # Test color without #
        assert parser._hex_to_rgb("FF0000") == (1.0, 0.0, 0.0)
    
    def test_calculate_distance(self):
        """Test distance calculation between bounding boxes."""
        parser = PDFParser()
        
        bbox1 = BoundingBox(x=0, y=0, width=10, height=10)
        bbox2 = BoundingBox(x=10, y=0, width=10, height=10)
        
        # Distance between centers: (5,5) and (15,5) = 10
        distance = parser._calculate_distance(bbox1, bbox2)
        assert distance == 10.0
        
        # Same box should have distance 0
        distance = parser._calculate_distance(bbox1, bbox1)
        assert distance == 0.0
    
    @patch('fitz.open')
    def test_reconstruct_success(self, mock_fitz_open):
        """Test successful PDF reconstruction."""
        parser = PDFParser()
        
        # Mock new document
        mock_doc = Mock()
        mock_page = Mock()
        mock_doc.new_page.return_value = mock_page
        mock_doc.tobytes.return_value = b"reconstructed pdf content"
        mock_fitz_open.return_value = mock_doc
        
        # Create test document structure
        structure = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        
        # Add text region
        text_region = TextRegion(
            bounding_box=BoundingBox(x=50, y=50, width=200, height=20),
            text_content="Test text",
            formatting=TextFormatting(font_size=12.0, color="#000000")
        )
        page.text_regions.append(text_region)
        
        # Add visual element
        visual_element = VisualElement(
            element_type="image",
            bounding_box=BoundingBox(x=100, y=100, width=50, height=50),
            content=b"fake image data"
        )
        page.visual_elements.append(visual_element)
        
        structure.add_page(page)
        
        # Test reconstruction
        result = parser.reconstruct(structure)
        
        assert result == b"reconstructed pdf content"
        mock_doc.new_page.assert_called_once_with(width=612, height=792)
        mock_page.insert_text.assert_called_once()
        mock_page.insert_image.assert_called_once()
        mock_doc.close.assert_called_once()
    
    @patch('fitz.open')
    def test_reconstruct_failure(self, mock_fitz_open):
        """Test PDF reconstruction failure."""
        parser = PDFParser()
        
        # Mock exception during reconstruction
        mock_fitz_open.side_effect = Exception("Reconstruction failed")
        
        structure = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        structure.add_page(page)
        
        with pytest.raises(ReconstructionError, match="Failed to reconstruct PDF"):
            parser.reconstruct(structure)
    
    def test_extract_text_regions_with_mock_data(self):
        """Test text region extraction with mock data."""
        parser = PDFParser()
        
        # Mock page with text data
        mock_page = Mock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "Hello World",
                                    "bbox": [10, 20, 100, 40],
                                    "font": "Arial",
                                    "size": 12.0,
                                    "flags": 0,
                                    "color": 0
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        text_regions = parser._extract_text_regions(mock_page)
        
        assert len(text_regions) == 1
        region = text_regions[0]
        assert region.text_content == "Hello World"
        assert region.bounding_box.x == 10
        assert region.bounding_box.y == 20
        assert region.bounding_box.width == 90
        assert region.bounding_box.height == 20
        assert region.formatting.font_family == "Arial"
        assert region.formatting.font_size == 12.0
    
    def test_extract_visual_elements_with_mock_data(self):
        """Test visual element extraction with mock data."""
        parser = PDFParser()
        
        # Mock page with image data
        mock_page = Mock()
        mock_page.number = 0
        mock_page.parent = Mock()
        mock_page.get_images.return_value = [(123, 0, 100, 100, 8, "DeviceRGB", "", "")]
        mock_page.get_image_rects.return_value = [Mock(x0=50, y0=60, width=100, height=80)]
        mock_page.get_drawings.return_value = []
        
        # Mock pixmap
        mock_pixmap = Mock()
        mock_pixmap.n = 4  # RGB + alpha
        mock_pixmap.alpha = 1
        mock_pixmap.width = 100
        mock_pixmap.height = 80
        mock_pixmap.colorspace.name = "DeviceRGB"
        mock_pixmap.tobytes.return_value = b"fake png data"
        
        with patch('fitz.Pixmap', return_value=mock_pixmap):
            visual_elements = parser._extract_visual_elements(mock_page)
        
        assert len(visual_elements) == 1
        element = visual_elements[0]
        assert element.element_type == "image"
        assert element.bounding_box.x == 50
        assert element.bounding_box.y == 60
        assert element.bounding_box.width == 100
        assert element.bounding_box.height == 80
        assert element.content == b"fake png data"
        assert element.metadata["width"] == 100
        assert element.metadata["height"] == 80
    
    def test_build_spatial_map(self):
        """Test spatial map building."""
        parser = PDFParser()
        
        # Create test elements
        text_region1 = TextRegion(
            id="text1",
            bounding_box=BoundingBox(x=10, y=10, width=50, height=20)
        )
        text_region2 = TextRegion(
            id="text2",
            bounding_box=BoundingBox(x=10, y=40, width=50, height=20)
        )
        visual_element = VisualElement(
            id="image1",
            element_type="image",
            bounding_box=BoundingBox(x=70, y=10, width=30, height=30)
        )
        
        spatial_map = parser._build_spatial_map(
            [text_region1, text_region2],
            [visual_element]
        )
        
        # Check reading order (sorted by y, then x)
        assert spatial_map.reading_order == ["text1", "image1", "text2"]
        
        # Check relationships (elements within distance threshold)
        assert "text1" in spatial_map.element_relationships
        assert "text2" in spatial_map.element_relationships["text1"]