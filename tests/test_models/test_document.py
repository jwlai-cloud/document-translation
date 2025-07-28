"""Tests for document data models."""

import pytest
from datetime import datetime

from src.models.document import (
    Dimensions, BoundingBox, TextFormatting, DocumentMetadata,
    TextRegion, VisualElement, SpatialMap, PageStructure, DocumentStructure
)


class TestDimensions:
    """Test cases for Dimensions model."""
    
    def test_dimensions_creation(self):
        """Test creating dimensions."""
        dims = Dimensions(width=100.0, height=200.0)
        assert dims.width == 100.0
        assert dims.height == 200.0
        assert dims.unit == "pt"
    
    def test_dimensions_with_custom_unit(self):
        """Test dimensions with custom unit."""
        dims = Dimensions(width=100.0, height=200.0, unit="px")
        assert dims.unit == "px"


class TestBoundingBox:
    """Test cases for BoundingBox model."""
    
    def test_bounding_box_creation(self):
        """Test creating bounding box."""
        bbox = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
        assert bbox.x == 10.0
        assert bbox.y == 20.0
        assert bbox.width == 100.0
        assert bbox.height == 50.0
    
    def test_bounding_box_area(self):
        """Test area calculation."""
        bbox = BoundingBox(x=0.0, y=0.0, width=10.0, height=5.0)
        assert bbox.area() == 50.0
    
    def test_bounding_box_overlaps(self):
        """Test overlap detection."""
        bbox1 = BoundingBox(x=0.0, y=0.0, width=10.0, height=10.0)
        bbox2 = BoundingBox(x=5.0, y=5.0, width=10.0, height=10.0)
        bbox3 = BoundingBox(x=20.0, y=20.0, width=10.0, height=10.0)
        
        assert bbox1.overlaps_with(bbox2)
        assert bbox2.overlaps_with(bbox1)
        assert not bbox1.overlaps_with(bbox3)
        assert not bbox3.overlaps_with(bbox1)


class TestTextFormatting:
    """Test cases for TextFormatting model."""
    
    def test_text_formatting_defaults(self):
        """Test default text formatting."""
        formatting = TextFormatting()
        assert formatting.font_family == "Arial"
        assert formatting.font_size == 12.0
        assert not formatting.is_bold
        assert not formatting.is_italic
        assert not formatting.is_underlined
        assert formatting.color == "#000000"
        assert formatting.alignment == "left"
    
    def test_text_formatting_custom(self):
        """Test custom text formatting."""
        formatting = TextFormatting(
            font_family="Times New Roman",
            font_size=14.0,
            is_bold=True,
            color="#FF0000"
        )
        assert formatting.font_family == "Times New Roman"
        assert formatting.font_size == 14.0
        assert formatting.is_bold
        assert formatting.color == "#FF0000"


class TestDocumentMetadata:
    """Test cases for DocumentMetadata model."""
    
    def test_document_metadata_defaults(self):
        """Test default metadata creation."""
        metadata = DocumentMetadata()
        assert metadata.title is None
        assert metadata.author is None
        assert metadata.page_count == 0
        assert metadata.file_size == 0
        assert isinstance(metadata.creation_date, datetime)
        assert isinstance(metadata.modification_date, datetime)
    
    def test_document_metadata_custom(self):
        """Test custom metadata."""
        creation_date = datetime(2023, 1, 1)
        metadata = DocumentMetadata(
            title="Test Document",
            author="Test Author",
            page_count=5,
            creation_date=creation_date
        )
        assert metadata.title == "Test Document"
        assert metadata.author == "Test Author"
        assert metadata.page_count == 5
        assert metadata.creation_date == creation_date


class TestTextRegion:
    """Test cases for TextRegion model."""
    
    def test_text_region_creation(self):
        """Test creating text region."""
        bbox = BoundingBox(x=0.0, y=0.0, width=100.0, height=20.0)
        region = TextRegion(
            bounding_box=bbox,
            text_content="Hello, world!",
            language="en"
        )
        assert region.text_content == "Hello, world!"
        assert region.language == "en"
        assert region.confidence == 1.0
        assert region.reading_order == 0
        assert len(region.id) > 0  # UUID should be generated
    
    def test_text_region_validation(self):
        """Test text region validation."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            TextRegion(confidence=1.5)
        
        with pytest.raises(ValueError, match="Reading order must be non-negative"):
            TextRegion(reading_order=-1)


class TestVisualElement:
    """Test cases for VisualElement model."""
    
    def test_visual_element_creation(self):
        """Test creating visual element."""
        bbox = BoundingBox(x=0.0, y=0.0, width=100.0, height=100.0)
        element = VisualElement(
            element_type="image",
            bounding_box=bbox,
            content=b"fake image data"
        )
        assert element.element_type == "image"
        assert element.content == b"fake image data"
        assert len(element.id) > 0  # UUID should be generated
    
    def test_visual_element_validation(self):
        """Test visual element validation."""
        with pytest.raises(ValueError, match="Element type must be one of"):
            VisualElement(element_type="invalid_type")


class TestSpatialMap:
    """Test cases for SpatialMap model."""
    
    def test_spatial_map_creation(self):
        """Test creating spatial map."""
        spatial_map = SpatialMap()
        assert len(spatial_map.element_relationships) == 0
        assert len(spatial_map.reading_order) == 0
        assert len(spatial_map.column_groups) == 0
    
    def test_add_relationship(self):
        """Test adding spatial relationship."""
        spatial_map = SpatialMap()
        spatial_map.add_relationship("elem1", ["elem2", "elem3"])
        
        assert "elem1" in spatial_map.element_relationships
        assert spatial_map.element_relationships["elem1"] == ["elem2", "elem3"]
    
    def test_get_neighbors(self):
        """Test getting neighbors."""
        spatial_map = SpatialMap()
        spatial_map.add_relationship("elem1", ["elem2", "elem3"])
        
        neighbors = spatial_map.get_neighbors("elem1")
        assert neighbors == ["elem2", "elem3"]
        
        # Non-existent element should return empty list
        assert spatial_map.get_neighbors("nonexistent") == []


class TestPageStructure:
    """Test cases for PageStructure model."""
    
    def test_page_structure_creation(self):
        """Test creating page structure."""
        dims = Dimensions(width=612.0, height=792.0)  # Letter size
        page = PageStructure(page_number=1, dimensions=dims)
        
        assert page.page_number == 1
        assert page.dimensions.width == 612.0
        assert page.dimensions.height == 792.0
        assert len(page.text_regions) == 0
        assert len(page.visual_elements) == 0
    
    def test_page_structure_validation(self):
        """Test page structure validation."""
        dims = Dimensions(width=612.0, height=792.0)
        
        with pytest.raises(ValueError, match="Page number must be positive"):
            PageStructure(page_number=0, dimensions=dims)
    
    def test_get_all_elements(self):
        """Test getting all elements from page."""
        dims = Dimensions(width=612.0, height=792.0)
        page = PageStructure(page_number=1, dimensions=dims)
        
        # Add text region and visual element
        text_region = TextRegion(text_content="Test text")
        visual_element = VisualElement(element_type="image")
        
        page.text_regions.append(text_region)
        page.visual_elements.append(visual_element)
        
        all_elements = page.get_all_elements()
        assert len(all_elements) == 2
        assert text_region in all_elements
        assert visual_element in all_elements
    
    def test_get_text_content(self):
        """Test getting text content from page."""
        dims = Dimensions(width=612.0, height=792.0)
        page = PageStructure(page_number=1, dimensions=dims)
        
        # Add text regions
        page.text_regions.append(TextRegion(text_content="Hello"))
        page.text_regions.append(TextRegion(text_content="world"))
        
        text_content = page.get_text_content()
        assert text_content == "Hello world"


class TestDocumentStructure:
    """Test cases for DocumentStructure model."""
    
    def test_document_structure_creation(self):
        """Test creating document structure."""
        doc = DocumentStructure(format="pdf")
        
        assert doc.format == "pdf"
        assert len(doc.pages) == 0
        assert doc.metadata.page_count == 0
        assert isinstance(doc.processing_timestamp, datetime)
    
    def test_document_structure_validation(self):
        """Test document structure validation."""
        with pytest.raises(ValueError, match="Format must be one of"):
            DocumentStructure(format="invalid")
    
    def test_add_page(self):
        """Test adding page to document."""
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612.0, height=792.0)
        page = PageStructure(page_number=1, dimensions=dims)
        
        doc.add_page(page)
        
        assert len(doc.pages) == 1
        assert doc.metadata.page_count == 1
        assert doc.pages[0] == page
    
    def test_get_page(self):
        """Test getting page by number."""
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612.0, height=792.0)
        page1 = PageStructure(page_number=1, dimensions=dims)
        page2 = PageStructure(page_number=2, dimensions=dims)
        
        doc.add_page(page1)
        doc.add_page(page2)
        
        retrieved_page = doc.get_page(1)
        assert retrieved_page == page1
        
        # Non-existent page should return None
        assert doc.get_page(99) is None
    
    def test_get_total_text_content(self):
        """Test getting total text content from document."""
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612.0, height=792.0)
        
        # Create pages with text
        page1 = PageStructure(page_number=1, dimensions=dims)
        page1.text_regions.append(TextRegion(text_content="Page 1 text"))
        
        page2 = PageStructure(page_number=2, dimensions=dims)
        page2.text_regions.append(TextRegion(text_content="Page 2 text"))
        
        doc.add_page(page1)
        doc.add_page(page2)
        
        total_text = doc.get_total_text_content()
        assert total_text == "Page 1 text Page 2 text"