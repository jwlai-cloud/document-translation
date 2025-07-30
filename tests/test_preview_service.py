"""Tests for preview service."""

import pytest
from unittest.mock import Mock, patch

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement,
    BoundingBox, Dimensions, TextFormatting, DocumentMetadata
)
from src.models.layout import AdjustedRegion, LayoutAdjustment, LayoutAdjustmentType
from src.services.preview_service import (
    PreviewService, PreviewConfig, PreviewFormat, HighlightType,
    PreviewRegion, PreviewPage, PreviewDocument, HTMLPreviewRenderer
)


class TestPreviewService:
    """Test cases for PreviewService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = PreviewService()
        
        # Create test document
        text_regions = [
            TextRegion(
                id="region1",
                bounding_box=BoundingBox(10, 10, 200, 30),
                text_content="First paragraph",
                confidence=0.9
            ),
            TextRegion(
                id="region2",
                bounding_box=BoundingBox(10, 50, 200, 30),
                text_content="Second paragraph",
                confidence=0.85
            )
        ]
        
        page = PageStructure(
            page_number=1,
            dimensions=Dimensions(width=400, height=600),
            text_regions=text_regions,
            visual_elements=[]
        )
        
        self.test_document = DocumentStructure(
            format="pdf",
            pages=[page],
            metadata=DocumentMetadata(title="Test Document")
        )
    
    def test_create_preview_basic(self):
        """Test basic preview creation."""
        preview_doc = self.service.create_preview(self.test_document)
        
        assert isinstance(preview_doc, PreviewDocument)
        assert preview_doc.title == "Test Document"
        assert len(preview_doc.pages) == 1
        assert preview_doc.total_regions == 2
        assert preview_doc.translated_regions == 0
    
    def test_render_preview_html(self):
        """Test HTML preview rendering."""
        preview_doc = self.service.create_preview(self.test_document)
        html = self.service.render_preview(preview_doc)
        
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "Test Document" in html
        assert "First paragraph" in html
    
    def test_update_highlighting(self):
        """Test highlighting update."""
        preview_doc = self.service.create_preview(self.test_document)
        
        updated_doc = self.service.update_highlighting(
            preview_doc,
            HighlightType.CHANGED
        )
        
        # Check that all regions have updated highlight type
        for page in updated_doc.pages:
            for region in page.original_regions:
                assert region.highlight_type == HighlightType.CHANGED
    
    def test_set_zoom_level(self):
        """Test zoom level setting."""
        preview_doc = self.service.create_preview(self.test_document)
        
        updated_doc = self.service.set_zoom_level(preview_doc, 2.0)
        
        assert updated_doc.pages[0].zoom_level == 2.0
    
    def test_get_region_info(self):
        """Test getting region information."""
        preview_doc = self.service.create_preview(self.test_document)
        
        region_info = self.service.get_region_info(preview_doc, "region1")
        
        assert region_info is not None
        assert region_info['region_id'] == "region1"
        assert region_info['page_number'] == 1
        assert region_info['type'] == 'original'
        assert region_info['text'] == "First paragraph"


if __name__ == "__main__":
    pytest.main([__file__])