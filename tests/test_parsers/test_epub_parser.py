"""Tests for EPUB document parser."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path

from src.parsers.epub_parser import EPUBParser
from src.parsers.base import ParsingError, ReconstructionError
from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement,
    BoundingBox, Dimensions, TextFormatting, DocumentMetadata
)


class TestEPUBParser:
    """Test cases for EPUBParser."""
    
    def test_initialization(self):
        """Test EPUB parser initialization."""
        parser = EPUBParser()
        
        assert parser.get_supported_formats() == ["epub"]
        assert hasattr(parser, 'logger')
        assert parser.logger.name == 'EPUBParser'
        assert parser.default_page_width == 600
        assert parser.default_page_height == 800
    
    def test_get_supported_formats(self):
        """Test getting supported formats."""
        parser = EPUBParser()
        formats = parser.get_supported_formats()
        
        assert formats == ["epub"]
        assert isinstance(formats, list)
    
    @patch('ebooklib.epub.read_epub')
    def test_parse_success(self, mock_read_epub):
        """Test successful EPUB parsing."""
        parser = EPUBParser()
        
        # Mock EPUB book
        mock_book = Mock()
        mock_read_epub.return_value = mock_book
        
        # Mock metadata
        mock_book.get_metadata.side_effect = lambda ns, name: {
            ('DC', 'title'): [('Test Book',)],
            ('DC', 'creator'): [('Test Author',)],
            ('DC', 'subject'): [('Test Subject',)],
            ('DC', 'date'): [('2023-01-01',)]
        }.get((ns, name), [])
        
        # Mock document item
        mock_item = Mock()
        mock_item.get_type.return_value = 'application/xhtml+xml'  # ITEM_DOCUMENT
        mock_item.get_content.return_value = b'<html><body><p>Test content</p></body></html>'
        
        # Mock get_items to return our document
        with patch('ebooklib.ITEM_DOCUMENT', 'application/xhtml+xml'):
            mock_book.get_items.return_value = [mock_item]
            
            # Mock file stat
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 1024
                
                structure = parser.parse("test.epub")
        
        assert isinstance(structure, DocumentStructure)
        assert structure.format == "epub"
        assert len(structure.pages) == 1
        assert structure.metadata.title == "Test Book"
        assert structure.metadata.author == "Test Author"
        assert structure.metadata.file_size == 1024
    
    @patch('ebooklib.epub.read_epub')
    def test_parse_failure(self, mock_read_epub):
        """Test EPUB parsing failure."""
        parser = EPUBParser()
        
        # Mock exception during book reading
        mock_read_epub.side_effect = Exception("Failed to read EPUB")
        
        with pytest.raises(ParsingError, match="Failed to parse EPUB document"):
            parser.parse("invalid.epub")
    
    def test_extract_clean_text(self):
        """Test clean text extraction from HTML."""
        parser = EPUBParser()
        
        from bs4 import BeautifulSoup
        
        # Test with simple text
        html = '<p>Hello World</p>'
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('p')
        
        text = parser._extract_clean_text(element)
        assert text == "Hello World"
        
        # Test with HTML entities
        html = '<p>Hello &amp; World &lt;test&gt;</p>'
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('p')
        
        text = parser._extract_clean_text(element)
        assert text == "Hello & World <test>"
        
        # Test with extra whitespace
        html = '<p>  Hello   World  </p>'
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('p')
        
        text = parser._extract_clean_text(element)
        assert text == "Hello World"
    
    def test_extract_html_formatting(self):
        """Test HTML formatting extraction."""
        parser = EPUBParser()
        
        from bs4 import BeautifulSoup
        
        # Test header formatting
        html = '<h1>Header Text</h1>'
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('h1')
        
        formatting = parser._extract_html_formatting(element)
        assert formatting.font_size == 24
        assert formatting.is_bold is True
        
        # Test bold formatting
        html = '<b>Bold Text</b>'
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('b')
        
        formatting = parser._extract_html_formatting(element)
        assert formatting.is_bold is True
        
        # Test italic formatting
        html = '<i>Italic Text</i>'
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('i')
        
        formatting = parser._extract_html_formatting(element)
        assert formatting.is_italic is True
        
        # Test inline styles
        html = '<p style="font-size: 16px; color: red; font-weight: bold;">Styled Text</p>'
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('p')
        
        formatting = parser._extract_html_formatting(element)
        assert formatting.font_size == 12.0  # 16px * 0.75
        assert formatting.color == "#FF0000"
        assert formatting.is_bold is True
    
    def test_parse_css_style(self):
        """Test CSS style parsing."""
        parser = EPUBParser()
        
        style_str = "font-size: 14px; color: blue; font-weight: bold"
        style_dict = parser._parse_css_style(style_str)
        
        assert style_dict['font-size'] == '14px'
        assert style_dict['color'] == 'blue'
        assert style_dict['font-weight'] == 'bold'
    
    def test_parse_font_size(self):
        """Test font size parsing."""
        parser = EPUBParser()
        
        # Test pixels
        assert parser._parse_font_size("16px") == 12.0  # 16 * 0.75
        
        # Test points
        assert parser._parse_font_size("14pt") == 14.0
        
        # Test em
        assert parser._parse_font_size("1.5em") == 18.0  # 1.5 * 12
        
        # Test invalid
        assert parser._parse_font_size("invalid") == 12.0
    
    def test_parse_color(self):
        """Test color parsing."""
        parser = EPUBParser()
        
        # Test named colors
        assert parser._parse_color("red") == "#FF0000"
        assert parser._parse_color("blue") == "#0000FF"
        assert parser._parse_color("black") == "#000000"
        
        # Test hex colors
        assert parser._parse_color("#FF0000") == "#FF0000"
        assert parser._parse_color("#ff0000") == "#FF0000"
        
        # Test RGB colors
        assert parser._parse_color("rgb(255, 0, 0)") == "#FF0000"
        assert parser._parse_color("rgb(0,255,0)") == "#00FF00"
        
        # Test invalid
        assert parser._parse_color("invalid") == "#000000"
    
    def test_extract_text_from_html(self):
        """Test text extraction from HTML."""
        parser = EPUBParser()
        
        from bs4 import BeautifulSoup
        
        html = '''
        <html>
        <body>
            <h1>Chapter Title</h1>
            <p>First paragraph with some text.</p>
            <p style="font-weight: bold;">Bold paragraph.</p>
        </body>
        </html>
        '''
        
        soup = BeautifulSoup(html, 'html.parser')
        text_regions = parser._extract_text_from_html(soup, 1)
        
        assert len(text_regions) == 3
        assert text_regions[0].text_content == "Chapter Title"
        assert text_regions[1].text_content == "First paragraph with some text."
        assert text_regions[2].text_content == "Bold paragraph."
        
        # Check formatting
        assert text_regions[0].formatting.font_size == 24  # h1
        assert text_regions[0].formatting.is_bold is True
        assert text_regions[2].formatting.is_bold is True
    
    def test_extract_visual_elements_from_html(self):
        """Test visual element extraction from HTML."""
        parser = EPUBParser()
        
        from bs4 import BeautifulSoup
        
        html = '''
        <html>
        <body>
            <img src="image1.jpg" alt="Test Image" width="300" height="200" />
            <img src="image2.png" alt="Another Image" />
        </body>
        </html>
        '''
        
        soup = BeautifulSoup(html, 'html.parser')
        visual_elements = parser._extract_visual_elements_from_html(soup, 1)
        
        assert len(visual_elements) == 2
        
        # Check first image
        img1 = visual_elements[0]
        assert img1.element_type == "image"
        assert img1.alt_text == "Test Image"
        assert img1.metadata["src"] == "image1.jpg"
        assert img1.bounding_box.width == 300
        assert img1.bounding_box.height == 200
        
        # Check second image
        img2 = visual_elements[1]
        assert img2.element_type == "image"
        assert img2.alt_text == "Another Image"
        assert img2.metadata["src"] == "image2.png"
        assert img2.bounding_box.width == 200  # Default
        assert img2.bounding_box.height == 150  # Default
    
    def test_calculate_distance(self):
        """Test distance calculation between bounding boxes."""
        parser = EPUBParser()
        
        bbox1 = BoundingBox(x=0, y=0, width=10, height=10)
        bbox2 = BoundingBox(x=10, y=0, width=10, height=10)
        
        # Distance between centers: (5,5) and (15,5) = 10
        distance = parser._calculate_distance(bbox1, bbox2)
        assert distance == 10.0
        
        # Same box should have distance 0
        distance = parser._calculate_distance(bbox1, bbox1)
        assert distance == 0.0
    
    def test_build_spatial_map(self):
        """Test spatial map building."""
        parser = EPUBParser()
        
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
    
    def test_text_region_to_html(self):
        """Test converting text region to HTML."""
        parser = EPUBParser()
        
        # Test regular paragraph
        text_region = TextRegion(
            text_content="Hello World",
            formatting=TextFormatting(
                font_size=12,
                is_bold=False,
                color="#000000"
            )
        )
        
        html = parser._text_region_to_html(text_region)
        assert html == '<p>Hello World</p>'
        
        # Test header with formatting
        text_region = TextRegion(
            text_content="Chapter Title",
            formatting=TextFormatting(
                font_size=20,
                is_bold=True,
                color="#FF0000"
            )
        )
        
        html = parser._text_region_to_html(text_region)
        expected = '<h2 style="font-size: 20pt; font-weight: bold; color: #FF0000">Chapter Title</h2>'
        assert html == expected
        
        # Test with HTML entities
        text_region = TextRegion(
            text_content="Text with <tags> & entities",
            formatting=TextFormatting()
        )
        
        html = parser._text_region_to_html(text_region)
        assert html == '<p>Text with &lt;tags&gt; &amp; entities</p>'
    
    def test_visual_element_to_html(self):
        """Test converting visual element to HTML."""
        parser = EPUBParser()
        
        # Test image element
        visual_element = VisualElement(
            element_type="image",
            alt_text="Test Image",
            metadata={
                "src": "test.jpg",
                "original_width": "300",
                "original_height": "200"
            }
        )
        
        html = parser._visual_element_to_html(visual_element)
        expected = '<img src="test.jpg" alt="Test Image" width="300" height="200" />'
        assert html == expected
        
        # Test image without dimensions
        visual_element = VisualElement(
            element_type="image",
            alt_text="Simple Image",
            metadata={"src": "simple.png"}
        )
        
        html = parser._visual_element_to_html(visual_element)
        expected = '<img src="simple.png" alt="Simple Image" />'
        assert html == expected
    
    @patch('ebooklib.epub.EpubBook')
    @patch('ebooklib.epub.write_epub')
    def test_reconstruct_success(self, mock_write_epub, mock_epub_book):
        """Test successful EPUB reconstruction."""
        parser = EPUBParser()
        
        # Mock EpubBook
        mock_book = Mock()
        mock_epub_book.return_value = mock_book
        
        # Create test document structure
        structure = DocumentStructure(format="epub")
        metadata = DocumentMetadata(title="Test Book", author="Test Author")
        structure.metadata = metadata
        
        dims = Dimensions(width=600, height=800)
        page = PageStructure(page_number=1, dimensions=dims)
        
        # Add text region
        text_region = TextRegion(
            bounding_box=BoundingBox(x=50, y=50, width=200, height=20),
            text_content="Test content",
            formatting=TextFormatting()
        )
        page.text_regions.append(text_region)
        
        structure.add_page(page)
        
        # Mock write_epub to write to BytesIO
        def mock_write(output, book):
            output.write(b"epub content")
        
        mock_write_epub.side_effect = mock_write
        
        result = parser.reconstruct(structure)
        
        assert result == b"epub content"
        mock_book.set_title.assert_called_with("Test Book")
        mock_book.add_author.assert_called_with("Test Author")
    
    @patch('ebooklib.epub.EpubBook')
    def test_reconstruct_failure(self, mock_epub_book):
        """Test EPUB reconstruction failure."""
        parser = EPUBParser()
        
        # Mock exception during book creation
        mock_epub_book.side_effect = Exception("Reconstruction failed")
        
        structure = DocumentStructure(format="epub")
        dims = Dimensions(width=600, height=800)
        page = PageStructure(page_number=1, dimensions=dims)
        structure.add_page(page)
        
        with pytest.raises(ReconstructionError, match="Failed to reconstruct EPUB"):
            parser.reconstruct(structure)
    
    def test_build_html_content(self):
        """Test building HTML content from page structure."""
        parser = EPUBParser()
        
        # Create page structure
        dims = Dimensions(width=600, height=800)
        page = PageStructure(page_number=1, dimensions=dims)
        
        # Add text region
        text_region = TextRegion(
            text_content="Test paragraph",
            formatting=TextFormatting(font_size=12)
        )
        page.text_regions.append(text_region)
        
        # Add visual element
        visual_element = VisualElement(
            element_type="image",
            alt_text="Test image",
            metadata={"src": "test.jpg"}
        )
        page.visual_elements.append(visual_element)
        
        html_content = parser._build_html_content(page)
        
        assert '<?xml version="1.0" encoding="utf-8"?>' in html_content
        assert '<html xmlns="http://www.w3.org/1999/xhtml">' in html_content
        assert '<p>Test paragraph</p>' in html_content
        assert '<img src="test.jpg" alt="Test image" />' in html_content
        assert '</html>' in html_content