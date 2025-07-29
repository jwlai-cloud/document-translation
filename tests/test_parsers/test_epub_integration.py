"""Integration tests for EPUB parser with factory."""

import pytest
from unittest.mock import Mock, patch

from src.parsers import get_parser_factory, EPUBParser
from src.parsers.base import ParsingError
from src.models.document import DocumentStructure


class TestEPUBParserIntegration:
    """Integration tests for EPUB parser with factory."""
    
    def test_epub_parser_registered(self):
        """Test that EPUB parser is registered in global factory."""
        factory = get_parser_factory()
        
        assert "epub" in factory.get_supported_formats()
        assert factory.is_format_supported("epub")
        assert factory.is_format_supported("EPUB")
        assert factory.is_format_supported(".epub")
    
    def test_create_epub_parser_from_factory(self):
        """Test creating EPUB parser from factory."""
        factory = get_parser_factory()
        
        parser = factory.create_parser("epub")
        assert isinstance(parser, EPUBParser)
        
        parser = factory.create_parser("EPUB")
        assert isinstance(parser, EPUBParser)
        
        parser = factory.create_parser(".epub")
        assert isinstance(parser, EPUBParser)
    
    def test_get_parser_for_epub_file(self, temp_dir):
        """Test getting parser for EPUB file."""
        factory = get_parser_factory()
        
        # Create a test EPUB file
        epub_file = temp_dir / "test.epub"
        epub_file.write_bytes(b"fake epub content")
        
        parser = factory.get_parser_for_file(str(epub_file))
        assert isinstance(parser, EPUBParser)
    
    @patch('ebooklib.epub.read_epub')
    def test_parse_epub_through_factory(self, mock_read_epub, temp_dir):
        """Test parsing EPUB through factory."""
        factory = get_parser_factory()
        
        # Mock EPUB book
        mock_book = Mock()
        mock_read_epub.return_value = mock_book
        
        # Mock metadata
        mock_book.get_metadata.side_effect = lambda ns, name: {
            ('DC', 'title'): [('Test EPUB',)],
            ('DC', 'creator'): [('Test Author',)],
            ('DC', 'subject'): [('Test Subject',)],
            ('DC', 'date'): [('2023-01-01',)]
        }.get((ns, name), [])
        
        # Mock document item
        mock_item = Mock()
        mock_item.get_type.return_value = 'application/xhtml+xml'
        mock_item.get_content.return_value = b'<html><body><h1>Chapter 1</h1><p>Content here.</p></body></html>'
        
        # Mock get_items
        with patch('ebooklib.ITEM_DOCUMENT', 'application/xhtml+xml'):
            mock_book.get_items.return_value = [mock_item]
            
            # Create test file
            epub_file = temp_dir / "test.epub"
            epub_file.write_bytes(b"fake epub content")
            
            # Mock file validation
            with patch('src.parsers.base.validate_file_format'), \
                 patch('src.parsers.base.validate_file_size'), \
                 patch('pathlib.Path.stat') as mock_stat:
                
                mock_stat.return_value.st_size = 2048
                
                # Parse through factory
                structure = factory.parse_document(str(epub_file))
        
        assert isinstance(structure, DocumentStructure)
        assert structure.format == "epub"
        assert len(structure.pages) == 1
        assert structure.metadata.title == "Test EPUB"
        assert structure.metadata.author == "Test Author"
        
        # Check that content was parsed
        page = structure.pages[0]
        assert len(page.text_regions) >= 1
        text_contents = [region.text_content for region in page.text_regions]
        assert any("Chapter 1" in content for content in text_contents)
    
    @patch('ebooklib.epub.EpubBook')
    @patch('ebooklib.epub.write_epub')
    def test_reconstruct_epub_through_factory(self, mock_write_epub, mock_epub_book):
        """Test reconstructing EPUB through factory."""
        factory = get_parser_factory()
        
        # Mock EpubBook
        mock_book = Mock()
        mock_epub_book.return_value = mock_book
        
        # Create test document structure
        from src.models.document import PageStructure, Dimensions, DocumentMetadata
        
        structure = DocumentStructure(format="epub")
        structure.metadata = DocumentMetadata(title="Test Book")
        dims = Dimensions(width=600, height=800)
        page = PageStructure(page_number=1, dimensions=dims)
        structure.add_page(page)
        
        # Mock write_epub
        def mock_write(output, book):
            output.write(b"reconstructed epub")
        
        mock_write_epub.side_effect = mock_write
        
        # Reconstruct through factory
        content = factory.reconstruct_document(structure)
        
        assert content == b"reconstructed epub"
        mock_book.set_title.assert_called_with("Test Book")
    
    def test_epub_parser_error_handling(self):
        """Test EPUB parser error handling through factory."""
        factory = get_parser_factory()
        
        # Test with non-existent file
        with pytest.raises(ParsingError):
            factory.parse_document("nonexistent.epub")
    
    def test_multiple_epub_parsers(self):
        """Test that factory creates separate parser instances."""
        factory = get_parser_factory()
        
        parser1 = factory.create_parser("epub")
        parser2 = factory.create_parser("epub")
        
        # Should be different instances
        assert parser1 is not parser2
        assert isinstance(parser1, EPUBParser)
        assert isinstance(parser2, EPUBParser)
    
    def test_epub_parser_supported_formats(self):
        """Test EPUB parser supported formats."""
        factory = get_parser_factory()
        parser = factory.create_parser("epub")
        
        formats = parser.get_supported_formats()
        assert formats == ["epub"]
        assert len(formats) == 1
    
    @patch('ebooklib.epub.read_epub')
    def test_epub_with_multiple_chapters(self, mock_read_epub):
        """Test EPUB parsing with multiple chapters."""
        factory = get_parser_factory()
        
        # Mock EPUB book
        mock_book = Mock()
        mock_read_epub.return_value = mock_book
        
        # Mock metadata
        mock_book.get_metadata.side_effect = lambda ns, name: {
            ('DC', 'title'): [('Multi-Chapter Book',)],
            ('DC', 'creator'): [('Author Name',)],
        }.get((ns, name), [])
        
        # Mock multiple document items (chapters)
        mock_item1 = Mock()
        mock_item1.get_type.return_value = 'application/xhtml+xml'
        mock_item1.get_content.return_value = b'<html><body><h1>Chapter 1</h1><p>First chapter content.</p></body></html>'
        
        mock_item2 = Mock()
        mock_item2.get_type.return_value = 'application/xhtml+xml'
        mock_item2.get_content.return_value = b'<html><body><h1>Chapter 2</h1><p>Second chapter content.</p></body></html>'
        
        mock_item3 = Mock()
        mock_item3.get_type.return_value = 'text/css'  # CSS file, should be ignored
        mock_item3.get_content.return_value = b'body { font-family: serif; }'
        
        # Mock get_items
        with patch('ebooklib.ITEM_DOCUMENT', 'application/xhtml+xml'):
            mock_book.get_items.return_value = [mock_item1, mock_item2, mock_item3]
            
            # Mock file stat
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 4096
                
                structure = factory.parse_document("multi_chapter.epub")
        
        assert isinstance(structure, DocumentStructure)
        assert structure.format == "epub"
        assert len(structure.pages) == 2  # Only document items, not CSS
        
        # Check chapter content
        page1 = structure.pages[0]
        page2 = structure.pages[1]
        
        page1_texts = [region.text_content for region in page1.text_regions]
        page2_texts = [region.text_content for region in page2.text_regions]
        
        assert any("Chapter 1" in text for text in page1_texts)
        assert any("First chapter content" in text for text in page1_texts)
        assert any("Chapter 2" in text for text in page2_texts)
        assert any("Second chapter content" in text for text in page2_texts)
    
    @patch('ebooklib.epub.read_epub')
    def test_epub_with_images(self, mock_read_epub):
        """Test EPUB parsing with images."""
        factory = get_parser_factory()
        
        # Mock EPUB book
        mock_book = Mock()
        mock_read_epub.return_value = mock_book
        
        # Mock metadata
        mock_book.get_metadata.side_effect = lambda ns, name: {
            ('DC', 'title'): [('Book with Images',)],
        }.get((ns, name), [])
        
        # Mock document item with images
        mock_item = Mock()
        mock_item.get_type.return_value = 'application/xhtml+xml'
        mock_item.get_content.return_value = b'''
        <html>
        <body>
            <h1>Chapter with Images</h1>
            <p>Some text before image.</p>
            <img src="image1.jpg" alt="First Image" width="300" height="200" />
            <p>Text between images.</p>
            <img src="image2.png" alt="Second Image" />
            <p>Text after images.</p>
        </body>
        </html>
        '''
        
        # Mock get_items
        with patch('ebooklib.ITEM_DOCUMENT', 'application/xhtml+xml'):
            mock_book.get_items.return_value = [mock_item]
            
            # Mock file stat
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 2048
                
                structure = factory.parse_document("book_with_images.epub")
        
        assert isinstance(structure, DocumentStructure)
        assert len(structure.pages) == 1
        
        page = structure.pages[0]
        
        # Should have text regions and visual elements
        assert len(page.text_regions) >= 3  # At least 3 text elements
        assert len(page.visual_elements) == 2  # 2 images
        
        # Check text content
        text_contents = [region.text_content for region in page.text_regions]
        assert any("Chapter with Images" in text for text in text_contents)
        assert any("Some text before image" in text for text in text_contents)
        
        # Check images
        images = page.visual_elements
        assert images[0].element_type == "image"
        assert images[0].alt_text == "First Image"
        assert images[0].metadata["src"] == "image1.jpg"
        assert images[0].bounding_box.width == 300
        assert images[0].bounding_box.height == 200
        
        assert images[1].element_type == "image"
        assert images[1].alt_text == "Second Image"
        assert images[1].metadata["src"] == "image2.png"
    
    def test_factory_supports_all_three_formats(self):
        """Test that factory supports PDF, DOCX, and EPUB formats."""
        factory = get_parser_factory()
        
        supported_formats = factory.get_supported_formats()
        assert "pdf" in supported_formats
        assert "docx" in supported_formats
        assert "epub" in supported_formats
        
        # Should be able to create all three parsers
        pdf_parser = factory.create_parser("pdf")
        docx_parser = factory.create_parser("docx")
        epub_parser = factory.create_parser("epub")
        
        assert pdf_parser.__class__.__name__ == "PDFParser"
        assert docx_parser.__class__.__name__ == "DOCXParser"
        assert epub_parser.__class__.__name__ == "EPUBParser"
    
    @patch('ebooklib.epub.read_epub')
    def test_epub_with_complex_formatting(self, mock_read_epub):
        """Test EPUB parsing with complex HTML formatting."""
        factory = get_parser_factory()
        
        # Mock EPUB book
        mock_book = Mock()
        mock_read_epub.return_value = mock_book
        
        # Mock metadata
        mock_book.get_metadata.return_value = []
        
        # Mock document item with complex formatting
        mock_item = Mock()
        mock_item.get_type.return_value = 'application/xhtml+xml'
        mock_item.get_content.return_value = b'''
        <html>
        <body>
            <h1 style="color: red; font-size: 24pt;">Styled Header</h1>
            <p style="font-weight: bold; font-style: italic;">Bold and italic text.</p>
            <p style="text-align: center; color: blue;">Centered blue text.</p>
            <div style="font-family: Arial; font-size: 14px;">Custom font text.</div>
        </body>
        </html>
        '''
        
        # Mock get_items
        with patch('ebooklib.ITEM_DOCUMENT', 'application/xhtml+xml'):
            mock_book.get_items.return_value = [mock_item]
            
            # Mock file stat
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 1024
                
                structure = factory.parse_document("styled_book.epub")
        
        assert isinstance(structure, DocumentStructure)
        page = structure.pages[0]
        
        # Check that formatting was preserved
        regions = page.text_regions
        assert len(regions) >= 4
        
        # Find the styled header
        header_region = next((r for r in regions if "Styled Header" in r.text_content), None)
        assert header_region is not None
        assert header_region.formatting.color == "#FF0000"  # Red
        assert header_region.formatting.font_size == 24
        
        # Find the bold italic text
        bold_italic_region = next((r for r in regions if "Bold and italic" in r.text_content), None)
        assert bold_italic_region is not None
        assert bold_italic_region.formatting.is_bold is True
        assert bold_italic_region.formatting.is_italic is True
        
        # Find the centered text
        centered_region = next((r for r in regions if "Centered blue" in r.text_content), None)
        assert centered_region is not None
        assert centered_region.formatting.alignment == "center"
        assert centered_region.formatting.color == "#0000FF"  # Blue