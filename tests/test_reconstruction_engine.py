"""Tests for layout reconstruction engine."""

import pytest
from unittest.mock import Mock, patch

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement,
    BoundingBox, Dimensions, TextFormatting, DocumentMetadata
)
from src.models.layout import (
    AdjustedRegion, LayoutAdjustment, LayoutAdjustmentType,
    LayoutConflict, ConflictResolution
)
from src.layout.reconstruction_engine import (
    DefaultLayoutReconstructionEngine, PDFReconstructor,
    DOCXReconstructor, EPUBReconstructor
)


class TestDefaultLayoutReconstructionEngine:
    """Test cases for DefaultLayoutReconstructionEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = DefaultLayoutReconstructionEngine()
        
        # Create test document
        self.test_region = TextRegion(
            id="test_region",
            bounding_box=BoundingBox(10, 10, 200, 50),
            text_content="Original text",
            formatting=TextFormatting(font_size=12.0, font_family="Arial"),
            confidence=0.9
        )
        
        self.test_page = PageStructure(
            page_number=1,
            dimensions=Dimensions(width=400, height=600),
            text_regions=[self.test_region],
            visual_elements=[]
        )
        
        self.test_document = DocumentStructure(
            format="pdf",
            pages=[self.test_page],
            metadata=DocumentMetadata(title="Test Document")
        )
    
    def test_fit_translated_text_basic(self):
        """Test basic text fitting functionality."""
        translated_text = "Translated text content"
        
        result = self.engine.fit_translated_text(self.test_region, translated_text)
        
        assert isinstance(result, AdjustedRegion)
        assert result.original_region == self.test_region
        assert result.adjusted_text == translated_text
        assert 0.0 <= result.fit_quality <= 1.0
    
    def test_fit_translated_text_long_content(self):
        """Test text fitting with long content requiring adjustments."""
        long_text = "This is a very long translated text that will definitely require adjustments " * 3
        
        result = self.engine.fit_translated_text(self.test_region, long_text)
        
        assert isinstance(result, AdjustedRegion)
        assert result.fit_quality < 1.0  # Should require adjustments
        assert len(result.adjustments) > 0  # Should have adjustments
    
    def test_adjust_layout_no_adjustments(self):
        """Test layout adjustment with no adjustments needed."""
        result = self.engine.adjust_layout(self.test_page, [])
        
        assert isinstance(result, PageStructure)
        assert result.page_number == self.test_page.page_number
        assert len(result.text_regions) == len(self.test_page.text_regions)
        assert len(result.visual_elements) == len(self.test_page.visual_elements)
    
    def test_adjust_layout_with_font_adjustment(self):
        """Test layout adjustment with font size changes."""
        adjustment = LayoutAdjustment(
            adjustment_type=LayoutAdjustmentType.FONT_SIZE_CHANGE,
            element_id=self.test_region.id,
            original_value=12.0,
            new_value=10.0,
            confidence=0.9,
            reason="Font size reduced for fitting"
        )
        
        result = self.engine.adjust_layout(self.test_page, [adjustment])
        
        assert isinstance(result, PageStructure)
        # Find the adjusted region
        adjusted_region = next(r for r in result.text_regions if r.id == self.test_region.id)
        assert adjusted_region.formatting.font_size == 10.0
    
    def test_adjust_layout_with_position_adjustment(self):
        """Test layout adjustment with position changes."""
        adjustment = LayoutAdjustment(
            adjustment_type=LayoutAdjustmentType.POSITION_SHIFT,
            element_id=self.test_region.id,
            original_value=(10, 10),
            new_value=(20, 30),
            confidence=0.8,
            reason="Position adjusted to resolve conflict"
        )
        
        result = self.engine.adjust_layout(self.test_page, [adjustment])
        
        adjusted_region = next(r for r in result.text_regions if r.id == self.test_region.id)
        assert adjusted_region.bounding_box.x == 20
        assert adjusted_region.bounding_box.y == 30
    
    def test_adjust_layout_with_boundary_adjustment(self):
        """Test layout adjustment with boundary expansion."""
        adjustment = LayoutAdjustment(
            adjustment_type=LayoutAdjustmentType.BOUNDARY_EXPANSION,
            element_id=self.test_region.id,
            original_value=(200, 50),
            new_value=(250, 60),
            confidence=0.7,
            reason="Boundary expanded for text fitting"
        )
        
        result = self.engine.adjust_layout(self.test_page, [adjustment])
        
        adjusted_region = next(r for r in result.text_regions if r.id == self.test_region.id)
        assert adjusted_region.bounding_box.width == 250
        assert adjusted_region.bounding_box.height == 60
    
    def test_reconstruct_document_pdf(self):
        """Test document reconstruction for PDF format."""
        translated_regions = {
            "1": {
                self.test_region.id: "Translated PDF text"
            }
        }
        
        result = self.engine.reconstruct_document(self.test_document, translated_regions)
        
        assert isinstance(result, bytes)
        content = result.decode('utf-8')
        assert "%PDF-1.4" in content
        assert "Translated PDF text" in content
    
    def test_reconstruct_document_docx(self):
        """Test document reconstruction for DOCX format."""
        docx_document = DocumentStructure(
            format="docx",
            pages=[self.test_page],
            metadata=self.test_document.metadata
        )
        
        translated_regions = {
            "1": {
                self.test_region.id: "Translated DOCX text"
            }
        }
        
        result = self.engine.reconstruct_document(docx_document, translated_regions)
        
        assert isinstance(result, bytes)
        content = result.decode('utf-8')
        assert "w:document" in content
        assert "Translated DOCX text" in content
    
    def test_reconstruct_document_epub(self):
        """Test document reconstruction for EPUB format."""
        epub_document = DocumentStructure(
            format="epub",
            pages=[self.test_page],
            metadata=self.test_document.metadata
        )
        
        translated_regions = {
            "1": {
                self.test_region.id: "Translated EPUB text"
            }
        }
        
        result = self.engine.reconstruct_document(epub_document, translated_regions)
        
        assert isinstance(result, bytes)
        content = result.decode('utf-8')
        assert "<!DOCTYPE html>" in content
        assert "Translated EPUB text" in content
    
    def test_reconstruct_document_unsupported_format(self):
        """Test document reconstruction with unsupported format."""
        unsupported_document = DocumentStructure(
            format="txt",
            pages=[self.test_page],
            metadata=self.test_document.metadata
        )
        
        translated_regions = {"1": {self.test_region.id: "Text"}}
        
        with pytest.raises(ValueError, match="Unsupported format: txt"):
            self.engine.reconstruct_document(unsupported_document, translated_regions)
    
    def test_apply_adjustments_to_region_multiple(self):
        """Test applying multiple adjustments to a region."""
        adjustments = [
            LayoutAdjustment(
                adjustment_type=LayoutAdjustmentType.FONT_SIZE_CHANGE,
                element_id=self.test_region.id,
                original_value=12.0,
                new_value=10.0
            ),
            LayoutAdjustment(
                adjustment_type=LayoutAdjustmentType.POSITION_SHIFT,
                element_id=self.test_region.id,
                original_value=(10, 10),
                new_value=(15, 20)
            )
        ]
        
        result = self.engine._apply_adjustments_to_region(self.test_region, adjustments)
        
        assert result.formatting.font_size == 10.0
        assert result.bounding_box.x == 15
        assert result.bounding_box.y == 20
    
    def test_apply_conflict_resolutions(self):
        """Test applying conflict resolutions to adjusted regions."""
        adjusted_region = AdjustedRegion(
            original_region=self.test_region,
            adjusted_text="Adjusted text",
            new_bounding_box=BoundingBox(10, 10, 200, 50),
            adjustments=[],
            fit_quality=0.8
        )
        
        resolution = ConflictResolution(
            conflict_id="test_conflict",
            resolution_type="reposition",
            actions=[
                LayoutAdjustment(
                    adjustment_type=LayoutAdjustmentType.POSITION_SHIFT,
                    element_id=self.test_region.id,
                    original_value=(10, 10),
                    new_value=(10, 70)
                )
            ],
            success_probability=0.9
        )
        
        result = self.engine._apply_conflict_resolutions([adjusted_region], [resolution])
        
        assert len(result) == 1
        assert result[0].new_bounding_box.y == 70
        assert len(result[0].adjustments) == 1


class TestPDFReconstructor:
    """Test cases for PDFReconstructor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.reconstructor = PDFReconstructor()
        
        self.test_region = TextRegion(
            id="pdf_region",
            bounding_box=BoundingBox(10, 10, 200, 50),
            text_content="PDF text",
            formatting=TextFormatting(font_size=12.0, font_family="Arial")
        )
        
        self.adjusted_region = AdjustedRegion(
            original_region=self.test_region,
            adjusted_text="Translated PDF text",
            new_bounding_box=BoundingBox(10, 10, 220, 55),
            adjustments=[],
            fit_quality=0.9
        )
    
    def test_create_pdf_text_object(self):
        """Test PDF text object creation."""
        result = self.reconstructor._create_pdf_text_object(self.adjusted_region)
        
        assert isinstance(result, list)
        assert "BT" in result  # Begin text
        assert "ET" in result  # End text
        assert "Translated PDF text" in " ".join(result)
    
    def test_create_pdf_visual_object_image(self):
        """Test PDF visual object creation for images."""
        image_element = VisualElement(
            id="img1",
            element_type="image",
            bounding_box=BoundingBox(50, 50, 100, 80)
        )
        
        result = self.reconstructor._create_pdf_visual_object(image_element)
        
        assert isinstance(result, list)
        assert any("Do" in line for line in result)  # Image drawing command
    
    def test_create_pdf_visual_object_line(self):
        """Test PDF visual object creation for lines."""
        line_element = VisualElement(
            id="line1",
            element_type="line",
            bounding_box=BoundingBox(10, 10, 100, 2)
        )
        
        result = self.reconstructor._create_pdf_visual_object(line_element)
        
        assert isinstance(result, list)
        assert any("m" in line for line in result)  # Move command
        assert any("l" in line for line in result)  # Line command
    
    def test_optimize_pdf_font(self):
        """Test PDF font optimization."""
        formatting = TextFormatting(
            font_family="Arial",
            font_size=12.0,
            is_bold=True
        )
        
        result = self.reconstructor._optimize_pdf_font(formatting)
        
        assert result.font_family == "Helvetica"  # Should be mapped
        assert result.font_size == 12.0
        assert result.is_bold is True


class TestDOCXReconstructor:
    """Test cases for DOCXReconstructor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.reconstructor = DOCXReconstructor()
        
        self.test_region = TextRegion(
            id="docx_region",
            bounding_box=BoundingBox(10, 10, 200, 50),
            text_content="DOCX text",
            formatting=TextFormatting(
                font_size=12.0,
                font_family="Times New Roman",
                is_bold=True,
                alignment="center"
            )
        )
        
        self.adjusted_region = AdjustedRegion(
            original_region=self.test_region,
            adjusted_text="Translated DOCX text",
            new_bounding_box=BoundingBox(10, 10, 220, 55),
            adjustments=[],
            fit_quality=0.9
        )
    
    def test_create_docx_paragraph(self):
        """Test DOCX paragraph creation."""
        result = self.reconstructor._create_docx_paragraph(self.adjusted_region)
        
        assert isinstance(result, list)
        assert any("<w:p>" in line for line in result)
        assert any("</w:p>" in line for line in result)
        assert any("Translated DOCX text" in line for line in result)
        assert any("center" in line for line in result)  # Alignment
        assert any("<w:b/>" in line for line in result)  # Bold formatting
    
    def test_optimize_docx_formatting(self):
        """Test DOCX formatting optimization."""
        formatting = TextFormatting(
            font_family="Arial",
            font_size=12.0,
            is_italic=True
        )
        
        result = self.reconstructor._optimize_docx_formatting(formatting)
        
        assert result.font_size < 12.0  # Should be reduced
        assert result.font_family == "Arial"  # Should be preserved
        assert result.is_italic is True  # Should be preserved


class TestEPUBReconstructor:
    """Test cases for EPUBReconstructor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.reconstructor = EPUBReconstructor()
        
        self.test_region = TextRegion(
            id="epub_region",
            bounding_box=BoundingBox(10, 10, 200, 50),
            text_content="EPUB text",
            formatting=TextFormatting(
                font_size=14.0,
                font_family="serif",
                is_underlined=True,
                color="#333333"
            )
        )
        
        self.adjusted_region = AdjustedRegion(
            original_region=self.test_region,
            adjusted_text="Translated EPUB text",
            new_bounding_box=BoundingBox(10, 10, 220, 55),
            adjustments=[],
            fit_quality=0.9
        )
    
    def test_create_epub_styles(self):
        """Test EPUB CSS styles creation."""
        result = self.reconstructor._create_epub_styles()
        
        assert isinstance(result, str)
        assert "font-family" in result
        assert "line-height" in result
        assert ".bold" in result
        assert ".italic" in result
    
    def test_create_epub_paragraph(self):
        """Test EPUB paragraph creation."""
        result = self.reconstructor._create_epub_paragraph(self.adjusted_region)
        
        assert isinstance(result, str)
        assert "<p" in result
        assert "</p>" in result
        assert "Translated EPUB text" in result
        assert "underlined" in result  # CSS class for underline
        assert "font-size: 14.0pt" in result  # Inline style
        assert "color: #333333" in result  # Color style
    
    def test_create_epub_paragraph_with_alignment(self):
        """Test EPUB paragraph creation with text alignment."""
        # Create region with right alignment
        right_aligned_region = AdjustedRegion(
            original_region=TextRegion(
                id="right_region",
                bounding_box=BoundingBox(10, 10, 200, 50),
                text_content="Right aligned text",
                formatting=TextFormatting(alignment="right")
            ),
            adjusted_text="Right aligned translated text",
            new_bounding_box=BoundingBox(10, 10, 220, 55),
            adjustments=[],
            fit_quality=1.0
        )
        
        result = self.reconstructor._create_epub_paragraph(right_aligned_region)
        
        assert "right" in result  # Should include right alignment class


class TestIntegration:
    """Integration tests for reconstruction engine."""
    
    def test_full_reconstruction_workflow(self):
        """Test complete reconstruction workflow."""
        # Create test document with multiple regions
        region1 = TextRegion(
            id="region1",
            bounding_box=BoundingBox(10, 10, 200, 30),
            text_content="First paragraph",
            formatting=TextFormatting(font_size=12.0),
            reading_order=0
        )
        
        region2 = TextRegion(
            id="region2",
            bounding_box=BoundingBox(10, 50, 200, 30),
            text_content="Second paragraph",
            formatting=TextFormatting(font_size=12.0),
            reading_order=1
        )
        
        page = PageStructure(
            page_number=1,
            dimensions=Dimensions(width=400, height=600),
            text_regions=[region1, region2],
            visual_elements=[]
        )
        
        document = DocumentStructure(
            format="pdf",
            pages=[page],
            metadata=DocumentMetadata(title="Test Document")
        )
        
        # Prepare translations
        translated_regions = {
            "1": {
                "region1": "Premier paragraphe traduit",
                "region2": "Deuxième paragraphe traduit"
            }
        }
        
        # Reconstruct document
        engine = DefaultLayoutReconstructionEngine()
        result = engine.reconstruct_document(document, translated_regions)
        
        assert isinstance(result, bytes)
        content = result.decode('utf-8')
        assert "Premier paragraphe traduit" in content
        assert "Deuxième paragraphe traduit" in content


if __name__ == "__main__":
    pytest.main([__file__])