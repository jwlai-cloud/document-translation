"""EPUB document parser using ebooklib."""

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
from datetime import datetime
import re
import html

from .base import DocumentParser, ParsingError, ReconstructionError
from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement,
    BoundingBox, Dimensions, TextFormatting, DocumentMetadata, SpatialMap
)


class EPUBParser(DocumentParser):
    """EPUB document parser using ebooklib for e-book processing."""
    
    def __init__(self):
        """Initialize the EPUB parser."""
        super().__init__()
        self.supported_formats = ["epub"]
        # Standard e-reader dimensions (approximate)
        self.default_page_width = 600  # points
        self.default_page_height = 800  # points
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats.
        
        Returns:
            List containing 'epub'
        """
        return self.supported_formats
    
    def parse(self, file_path: str) -> DocumentStructure:
        """Parse an EPUB document and extract its structure.
        
        Args:
            file_path: Path to the EPUB file
            
        Returns:
            DocumentStructure containing parsed content and layout
            
        Raises:
            ParsingError: If EPUB parsing fails
        """
        try:
            self.logger.info(f"Starting EPUB parsing: {file_path}")
            
            # Open the EPUB document
            book = epub.read_epub(file_path)
            
            # Extract document metadata
            metadata = self._extract_epub_metadata(book, file_path)
            
            # Create document structure
            document = DocumentStructure(format="epub", metadata=metadata)
            
            # Process each chapter/document in the EPUB
            page_number = 1
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    page_structure = self._parse_chapter(item, page_number)
                    if page_structure.text_regions or page_structure.visual_elements:
                        document.add_page(page_structure)
                        page_number += 1
            
            self.logger.info(
                f"Successfully parsed EPUB: {file_path} "
                f"({len(document.pages)} chapters, "
                f"{sum(len(p.text_regions) for p in document.pages)} text regions)"
            )
            
            return document
            
        except Exception as e:
            if isinstance(e, ParsingError):
                raise
            raise ParsingError(
                f"Failed to parse EPUB document: {str(e)}",
                file_path,
                "EPUB_PARSE_ERROR"
            )
    
    def reconstruct(self, structure: DocumentStructure) -> bytes:
        """Reconstruct an EPUB document from its structure.
        
        Args:
            structure: DocumentStructure to reconstruct
            
        Returns:
            Binary content of the reconstructed EPUB
            
        Raises:
            ReconstructionError: If EPUB reconstruction fails
        """
        try:
            self.logger.info(
                f"Starting EPUB reconstruction "
                f"({len(structure.pages)} chapters)"
            )
            
            # Create new EPUB book
            book = epub.EpubBook()
            
            # Set book metadata
            self._set_book_metadata(book, structure.metadata)
            
            # Reconstruct chapters from pages
            chapters = []
            for page_idx, page_structure in enumerate(structure.pages):
                chapter = self._reconstruct_chapter(page_structure, page_idx + 1)
                chapters.append(chapter)
                book.add_item(chapter)
            
            # Create table of contents
            book.toc = [(epub.Section('Chapters'), chapters)]
            
            # Add navigation files
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())
            
            # Create spine
            book.spine = ['nav'] + chapters
            
            # Write to bytes
            epub_bytes = self._book_to_bytes(book)
            
            self.logger.info(
                f"Successfully reconstructed EPUB "
                f"({len(epub_bytes)} bytes)"
            )
            
            return epub_bytes
            
        except Exception as e:
            raise ReconstructionError(
                f"Failed to reconstruct EPUB: {str(e)}",
                "epub",
                "EPUB_RECONSTRUCTION_ERROR"
            )
    
    def _extract_epub_metadata(self, book: epub.EpubBook, 
                              file_path: str) -> DocumentMetadata:
        """Extract metadata from EPUB book.
        
        Args:
            book: ebooklib EpubBook object
            file_path: Path to the EPUB file
            
        Returns:
            DocumentMetadata with extracted information
        """
        file_stat = Path(file_path).stat()
        
        # Extract metadata from book
        title = book.get_metadata('DC', 'title')
        title = title[0][0] if title else Path(file_path).stem
        
        author = book.get_metadata('DC', 'creator')
        author = author[0][0] if author else None
        
        subject = book.get_metadata('DC', 'subject')
        subject = subject[0][0] if subject else None
        
        # Try to get creation date
        date = book.get_metadata('DC', 'date')
        creation_date = None
        if date:
            try:
                date_str = date[0][0]
                # Try to parse various date formats
                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y']:
                    try:
                        creation_date = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
            except (IndexError, ValueError):
                pass
        
        return DocumentMetadata(
            title=title,
            author=author,
            subject=subject,
            creator=author,  # Use author as creator
            creation_date=creation_date,
            modification_date=None,
            page_count=0,  # Will be updated based on chapters
            file_size=file_stat.st_size
        )
    
    def _parse_chapter(self, item: ebooklib.epub.EpubHtml, 
                      page_number: int) -> PageStructure:
        """Parse a single chapter/document from EPUB.
        
        Args:
            item: EpubHtml item to parse
            page_number: Page number for this chapter
            
        Returns:
            PageStructure with extracted content
        """
        # Create page structure
        dimensions = Dimensions(
            width=self.default_page_width,
            height=self.default_page_height,
            unit="pt"
        )
        
        page_structure = PageStructure(
            page_number=page_number,
            dimensions=dimensions
        )
        
        # Parse HTML content
        try:
            content = item.get_content().decode('utf-8')
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract text regions from HTML elements
            text_regions = self._extract_text_from_html(soup, page_number)
            page_structure.text_regions.extend(text_regions)
            
            # Extract images and other visual elements
            visual_elements = self._extract_visual_elements_from_html(soup, page_number)
            page_structure.visual_elements.extend(visual_elements)
            
            # Build spatial map
            spatial_map = self._build_spatial_map(
                page_structure.text_regions,
                page_structure.visual_elements
            )
            page_structure.spatial_map = spatial_map
            
        except Exception as e:
            self.logger.warning(f"Failed to parse chapter content: {str(e)}")
        
        return page_structure
    
    def _extract_text_from_html(self, soup: BeautifulSoup, 
                               page_number: int) -> List[TextRegion]:
        """Extract text regions from HTML content.
        
        Args:
            soup: BeautifulSoup parsed HTML
            page_number: Page number for region IDs
            
        Returns:
            List of TextRegion objects
        """
        text_regions = []
        current_y = 50  # Start with top margin
        
        # Process text elements in order
        text_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span'])
        
        for elem_idx, element in enumerate(text_elements):
            text_content = self._extract_clean_text(element)
            if not text_content.strip():
                continue
            
            # Determine element type and formatting
            formatting = self._extract_html_formatting(element)
            
            # Estimate dimensions based on content and formatting
            estimated_width = min(len(text_content) * formatting.font_size * 0.6, 
                                self.default_page_width - 100)
            estimated_height = formatting.font_size * 1.2
            
            # Handle multi-line text
            if len(text_content) > 80:  # Approximate line length
                lines = len(text_content) // 80 + 1
                estimated_height *= lines
            
            bbox = BoundingBox(
                x=50,  # Left margin
                y=current_y,
                width=estimated_width,
                height=estimated_height
            )
            
            region_id = f"page_{page_number}_elem_{elem_idx}"
            text_region = TextRegion(
                id=region_id,
                bounding_box=bbox,
                text_content=text_content,
                formatting=formatting,
                language="en",  # Will be detected later
                confidence=1.0,
                reading_order=len(text_regions)
            )
            
            text_regions.append(text_region)
            current_y += estimated_height + 10  # Add spacing
        
        return text_regions
    
    def _extract_clean_text(self, element) -> str:
        """Extract clean text from HTML element.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            Clean text content
        """
        # Get text and clean it up
        text = element.get_text(separator=' ', strip=True)
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _extract_html_formatting(self, element) -> TextFormatting:
        """Extract formatting from HTML element and CSS.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            TextFormatting object
        """
        # Default formatting
        font_family = "serif"
        font_size = 12.0
        is_bold = False
        is_italic = False
        is_underlined = False
        color = "#000000"
        alignment = "left"
        
        # Check element tag for semantic formatting
        tag_name = element.name.lower()
        
        if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            # Headers are typically bold and larger
            is_bold = True
            header_sizes = {'h1': 24, 'h2': 20, 'h3': 18, 'h4': 16, 'h5': 14, 'h6': 12}
            font_size = header_sizes.get(tag_name, 16)
        elif tag_name in ['b', 'strong']:
            is_bold = True
        elif tag_name in ['i', 'em']:
            is_italic = True
        elif tag_name == 'u':
            is_underlined = True
        
        # Check for inline styles
        style = element.get('style', '')
        if style:
            style_dict = self._parse_css_style(style)
            
            if 'font-family' in style_dict:
                font_family = style_dict['font-family'].strip('\'"')
            
            if 'font-size' in style_dict:
                size_str = style_dict['font-size']
                font_size = self._parse_font_size(size_str)
            
            if 'font-weight' in style_dict:
                weight = style_dict['font-weight'].lower()
                is_bold = weight in ['bold', 'bolder', '700', '800', '900']
            
            if 'font-style' in style_dict:
                style_val = style_dict['font-style'].lower()
                is_italic = style_val == 'italic'
            
            if 'text-decoration' in style_dict:
                decoration = style_dict['text-decoration'].lower()
                is_underlined = 'underline' in decoration
            
            if 'color' in style_dict:
                color = self._parse_color(style_dict['color'])
            
            if 'text-align' in style_dict:
                alignment = style_dict['text-align'].lower()
        
        return TextFormatting(
            font_family=font_family,
            font_size=font_size,
            is_bold=is_bold,
            is_italic=is_italic,
            is_underlined=is_underlined,
            color=color,
            alignment=alignment
        )
    
    def _parse_css_style(self, style_str: str) -> Dict[str, str]:
        """Parse CSS style string into dictionary.
        
        Args:
            style_str: CSS style string
            
        Returns:
            Dictionary of style properties
        """
        style_dict = {}
        
        for declaration in style_str.split(';'):
            if ':' in declaration:
                prop, value = declaration.split(':', 1)
                style_dict[prop.strip().lower()] = value.strip()
        
        return style_dict
    
    def _parse_font_size(self, size_str: str) -> float:
        """Parse font size from CSS value.
        
        Args:
            size_str: Font size string (e.g., "14px", "1.2em")
            
        Returns:
            Font size in points
        """
        size_str = size_str.lower().strip()
        
        # Extract numeric value
        numeric_match = re.match(r'(\d+(?:\.\d+)?)', size_str)
        if not numeric_match:
            return 12.0  # Default
        
        value = float(numeric_match.group(1))
        
        # Convert based on unit
        if 'px' in size_str:
            return value * 0.75  # Convert px to pt (approximate)
        elif 'em' in size_str:
            return value * 12  # Assume base font size of 12pt
        elif 'pt' in size_str:
            return value
        else:
            return value  # Assume points
    
    def _parse_color(self, color_str: str) -> str:
        """Parse color from CSS value.
        
        Args:
            color_str: Color string (e.g., "red", "#FF0000", "rgb(255,0,0)")
            
        Returns:
            Color as hex string
        """
        color_str = color_str.strip().lower()
        
        # Named colors
        named_colors = {
            'black': '#000000', 'white': '#FFFFFF', 'red': '#FF0000',
            'green': '#008000', 'blue': '#0000FF', 'yellow': '#FFFF00',
            'cyan': '#00FFFF', 'magenta': '#FF00FF', 'gray': '#808080',
            'grey': '#808080', 'darkgray': '#A9A9A9', 'lightgray': '#D3D3D3'
        }
        
        if color_str in named_colors:
            return named_colors[color_str]
        
        # Hex colors
        if color_str.startswith('#'):
            return color_str.upper()
        
        # RGB colors
        rgb_match = re.match(r'rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', color_str)
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            return f"#{r:02X}{g:02X}{b:02X}"
        
        return "#000000"  # Default black
    
    def _extract_visual_elements_from_html(self, soup: BeautifulSoup, 
                                          page_number: int) -> List[VisualElement]:
        """Extract visual elements from HTML content.
        
        Args:
            soup: BeautifulSoup parsed HTML
            page_number: Page number for element IDs
            
        Returns:
            List of VisualElement objects
        """
        visual_elements = []
        
        # Extract images
        images = soup.find_all('img')
        for img_idx, img in enumerate(images):
            src = img.get('src', '')
            alt_text = img.get('alt', '')
            
            # Estimate image dimensions
            width = 200  # Default width
            height = 150  # Default height
            
            # Try to get dimensions from attributes
            if img.get('width'):
                try:
                    width = float(img['width'])
                except ValueError:
                    pass
            
            if img.get('height'):
                try:
                    height = float(img['height'])
                except ValueError:
                    pass
            
            bbox = BoundingBox(
                x=50,
                y=100 + img_idx * 200,  # Approximate positioning
                width=width,
                height=height
            )
            
            element_id = f"page_{page_number}_img_{img_idx}"
            visual_element = VisualElement(
                id=element_id,
                element_type="image",
                bounding_box=bbox,
                content=None,  # Would need to extract from EPUB
                alt_text=alt_text,
                metadata={
                    "src": src,
                    "original_width": img.get('width'),
                    "original_height": img.get('height')
                }
            )
            
            visual_elements.append(visual_element)
        
        return visual_elements
    
    def _build_spatial_map(self, text_regions: List[TextRegion], 
                          visual_elements: List[VisualElement]) -> SpatialMap:
        """Build spatial relationships map for chapter elements.
        
        Args:
            text_regions: List of text regions
            visual_elements: List of visual elements
            
        Returns:
            SpatialMap with element relationships
        """
        spatial_map = SpatialMap()
        
        # Set reading order based on document flow (top to bottom)
        all_elements = text_regions + visual_elements
        sorted_elements = sorted(
            all_elements,
            key=lambda elem: (elem.bounding_box.y, elem.bounding_box.x)
        )
        
        spatial_map.reading_order = [elem.id for elem in sorted_elements]
        
        # Build relationships based on proximity
        for i, element in enumerate(all_elements):
            nearby_elements = []
            
            for j, other_element in enumerate(all_elements):
                if i == j:
                    continue
                
                # Check if elements are nearby
                distance = self._calculate_distance(
                    element.bounding_box,
                    other_element.bounding_box
                )
                
                if distance < 200:  # Threshold for "nearby" in EPUB
                    nearby_elements.append(other_element.id)
            
            if nearby_elements:
                spatial_map.add_relationship(element.id, nearby_elements)
        
        return spatial_map
    
    def _calculate_distance(self, bbox1: BoundingBox, bbox2: BoundingBox) -> float:
        """Calculate distance between two bounding boxes.
        
        Args:
            bbox1: First bounding box
            bbox2: Second bounding box
            
        Returns:
            Distance between box centers
        """
        center1_x = bbox1.x + bbox1.width / 2
        center1_y = bbox1.y + bbox1.height / 2
        center2_x = bbox2.x + bbox2.width / 2
        center2_y = bbox2.y + bbox2.height / 2
        
        return ((center1_x - center2_x) ** 2 + (center1_y - center2_y) ** 2) ** 0.5
    
    def _set_book_metadata(self, book: epub.EpubBook, 
                          metadata: DocumentMetadata) -> None:
        """Set EPUB book metadata.
        
        Args:
            book: EpubBook object
            metadata: DocumentMetadata to set
        """
        if metadata.title:
            book.set_title(metadata.title)
        
        if metadata.author:
            book.add_author(metadata.author)
        
        if metadata.subject:
            book.add_metadata('DC', 'subject', metadata.subject)
        
        # Set language (default to English)
        book.set_language('en')
        
        # Set unique identifier
        book.set_identifier('id123456')
    
    def _reconstruct_chapter(self, page_structure: PageStructure, 
                           chapter_num: int) -> epub.EpubHtml:
        """Reconstruct a chapter from page structure.
        
        Args:
            page_structure: Page structure to reconstruct
            chapter_num: Chapter number
            
        Returns:
            EpubHtml chapter
        """
        # Create chapter
        chapter = epub.EpubHtml(
            title=f'Chapter {chapter_num}',
            file_name=f'chap_{chapter_num:02d}.xhtml',
            lang='en'
        )
        
        # Build HTML content
        html_content = self._build_html_content(page_structure)
        chapter.content = html_content
        
        return chapter
    
    def _build_html_content(self, page_structure: PageStructure) -> str:
        """Build HTML content from page structure.
        
        Args:
            page_structure: Page structure to convert
            
        Returns:
            HTML content as string
        """
        html_parts = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<!DOCTYPE html>',
            '<html xmlns="http://www.w3.org/1999/xhtml">',
            '<head>',
            '<title>Chapter</title>',
            '</head>',
            '<body>'
        ]
        
        # Add text regions as HTML elements
        for text_region in page_structure.text_regions:
            html_element = self._text_region_to_html(text_region)
            html_parts.append(html_element)
        
        # Add visual elements
        for visual_element in page_structure.visual_elements:
            if visual_element.element_type == "image":
                img_html = self._visual_element_to_html(visual_element)
                html_parts.append(img_html)
        
        html_parts.extend(['</body>', '</html>'])
        
        return '\n'.join(html_parts)
    
    def _text_region_to_html(self, text_region: TextRegion) -> str:
        """Convert text region to HTML element.
        
        Args:
            text_region: TextRegion to convert
            
        Returns:
            HTML element as string
        """
        formatting = text_region.formatting
        
        # Choose appropriate HTML tag based on formatting
        if formatting.font_size > 18:
            tag = 'h2'
        elif formatting.font_size > 16:
            tag = 'h3'
        elif formatting.font_size > 14:
            tag = 'h4'
        else:
            tag = 'p'
        
        # Build style string
        styles = []
        
        if formatting.font_family != "serif":
            styles.append(f"font-family: {formatting.font_family}")
        
        if formatting.font_size != 12.0:
            styles.append(f"font-size: {formatting.font_size}pt")
        
        if formatting.is_bold:
            styles.append("font-weight: bold")
        
        if formatting.is_italic:
            styles.append("font-style: italic")
        
        if formatting.is_underlined:
            styles.append("text-decoration: underline")
        
        if formatting.color != "#000000":
            styles.append(f"color: {formatting.color}")
        
        if formatting.alignment != "left":
            styles.append(f"text-align: {formatting.alignment}")
        
        # Build HTML element
        style_attr = f' style="{"; ".join(styles)}"' if styles else ''
        
        # Escape HTML content
        escaped_content = html.escape(text_region.text_content)
        
        return f'<{tag}{style_attr}>{escaped_content}</{tag}>'
    
    def _visual_element_to_html(self, visual_element: VisualElement) -> str:
        """Convert visual element to HTML.
        
        Args:
            visual_element: VisualElement to convert
            
        Returns:
            HTML element as string
        """
        if visual_element.element_type == "image":
            src = visual_element.metadata.get('src', 'image.jpg')
            alt = visual_element.alt_text or 'Image'
            
            width_attr = ''
            height_attr = ''
            
            if visual_element.metadata.get('original_width'):
                width_attr = f' width="{visual_element.metadata["original_width"]}"'
            
            if visual_element.metadata.get('original_height'):
                height_attr = f' height="{visual_element.metadata["original_height"]}"'
            
            return f'<img src="{src}" alt="{alt}"{width_attr}{height_attr} />'
        
        return ''
    
    def _book_to_bytes(self, book: epub.EpubBook) -> bytes:
        """Convert EpubBook to bytes.
        
        Args:
            book: EpubBook object
            
        Returns:
            EPUB content as bytes
        """
        import io
        
        epub_bytes = io.BytesIO()
        epub.write_epub(epub_bytes, book)
        epub_bytes.seek(0)
        return epub_bytes.read()