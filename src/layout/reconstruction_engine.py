"""Layout reconstruction engine implementation."""

import io
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement,
    BoundingBox, TextFormatting, DocumentMetadata
)
from src.models.layout import (
    AdjustedRegion, LayoutAdjustment, LayoutConflict, ConflictResolution,
    LayoutAdjustmentType
)
from src.layout.base import LayoutReconstructionEngine
from src.layout.text_fitting import TextFittingEngine, LayoutAdjustmentEngine


class FormatSpecificReconstructor(ABC):
    """Abstract base class for format-specific document reconstruction."""
    
    @abstractmethod
    def reconstruct_document(self, document: DocumentStructure, 
                           adjusted_regions: Dict[str, List[AdjustedRegion]]) -> bytes:
        """Reconstruct document with adjusted regions.
        
        Args:
            document: Original document structure
            adjusted_regions: Dict mapping page numbers to adjusted regions
            
        Returns:
            Reconstructed document as bytes
        """
        pass
    
    @abstractmethod
    def optimize_fonts_and_spacing(self, document: DocumentStructure) -> DocumentStructure:
        """Optimize fonts and spacing for better text fitting.
        
        Args:
            document: Document to optimize
            
        Returns:
            Optimized document structure
        """
        pass


class PDFReconstructor(FormatSpecificReconstructor):
    """PDF-specific document reconstruction."""
    
    def reconstruct_document(self, document: DocumentStructure,
                           adjusted_regions: Dict[str, List[AdjustedRegion]]) -> bytes:
        """Reconstruct PDF document with translated content."""
        # This is a simplified implementation
        # In a real system, this would use PyMuPDF or similar library
        
        pdf_content = []
        pdf_content.append("%PDF-1.4")
        pdf_content.append("% Reconstructed PDF with translations")
        
        for page in document.pages:
            page_key = str(page.page_number)
            page_adjusted_regions = adjusted_regions.get(page_key, [])
            
            # Create page content
            page_content = self._create_pdf_page_content(page, page_adjusted_regions)
            pdf_content.extend(page_content)
        
        # Add PDF trailer
        pdf_content.append("%%EOF")
        
        return "\n".join(pdf_content).encode('utf-8')
    
    def optimize_fonts_and_spacing(self, document: DocumentStructure) -> DocumentStructure:
        """Optimize PDF fonts and spacing."""
        optimized_document = DocumentStructure(
            format=document.format,
            pages=[],
            metadata=document.metadata
        )
        
        for page in document.pages:
            optimized_page = self._optimize_pdf_page(page)
            optimized_document.pages.append(optimized_page)
        
        return optimized_document
    
    def _create_pdf_page_content(self, page: PageStructure, 
                               adjusted_regions: List[AdjustedRegion]) -> List[str]:
        """Create PDF content for a single page."""
        content = []
        content.append(f"% Page {page.page_number}")
        
        # Create text objects for each adjusted region
        for region in adjusted_regions:
            text_obj = self._create_pdf_text_object(region)
            content.extend(text_obj)
        
        # Add visual elements
        for visual_element in page.visual_elements:
            visual_obj = self._create_pdf_visual_object(visual_element)
            content.extend(visual_obj)
        
        return content
    
    def _create_pdf_text_object(self, region: AdjustedRegion) -> List[str]:
        """Create PDF text object for an adjusted region."""
        box = region.new_bounding_box
        text = region.adjusted_text
        
        # Get font size from adjustments or original
        font_size = region.original_region.formatting.font_size
        for adj in region.adjustments:
            if adj.adjustment_type == LayoutAdjustmentType.FONT_SIZE_CHANGE:
                font_size = adj.new_value
                break
        
        return [
            "BT",  # Begin text
            f"/{region.original_region.formatting.font_family} {font_size} Tf",
            f"{box.x} {box.y} Td",  # Text position
            f"({text}) Tj",  # Show text
            "ET"  # End text
        ]
    
    def _create_pdf_visual_object(self, element: VisualElement) -> List[str]:
        """Create PDF object for a visual element."""
        box = element.bounding_box
        
        if element.element_type == "image":
            return [
                f"q",  # Save graphics state
                f"{box.width} 0 0 {box.height} {box.x} {box.y} cm",
                f"/Im{element.id} Do",  # Draw image
                f"Q"  # Restore graphics state
            ]
        elif element.element_type == "line":
            return [
                f"{box.x} {box.y} m",  # Move to start
                f"{box.x + box.width} {box.y + box.height} l",  # Line to end
                "S"  # Stroke
            ]
        
        return [f"% Visual element {element.id} ({element.element_type})"]
    
    def _optimize_pdf_page(self, page: PageStructure) -> PageStructure:
        """Optimize a PDF page for better text fitting."""
        optimized_regions = []
        
        for region in page.text_regions:
            # Optimize font selection
            optimized_formatting = self._optimize_pdf_font(region.formatting)
            
            optimized_region = TextRegion(
                id=region.id,
                bounding_box=region.bounding_box,
                text_content=region.text_content,
                formatting=optimized_formatting,
                language=region.language,
                confidence=region.confidence,
                reading_order=region.reading_order
            )
            optimized_regions.append(optimized_region)
        
        return PageStructure(
            page_number=page.page_number,
            dimensions=page.dimensions,
            text_regions=optimized_regions,
            visual_elements=page.visual_elements,
            spatial_map=page.spatial_map
        )
    
    def _optimize_pdf_font(self, formatting: TextFormatting) -> TextFormatting:
        """Optimize font settings for PDF."""
        # Choose more compact fonts for better fitting
        font_mapping = {
            "Arial": "Helvetica",
            "Times New Roman": "Times-Roman",
            "Courier New": "Courier"
        }
        
        optimized_font = font_mapping.get(formatting.font_family, formatting.font_family)
        
        return TextFormatting(
            font_family=optimized_font,
            font_size=formatting.font_size,
            is_bold=formatting.is_bold,
            is_italic=formatting.is_italic,
            is_underlined=formatting.is_underlined,
            color=formatting.color,
            background_color=formatting.background_color,
            alignment=formatting.alignment
        )


class DOCXReconstructor(FormatSpecificReconstructor):
    """DOCX-specific document reconstruction."""
    
    def reconstruct_document(self, document: DocumentStructure,
                           adjusted_regions: Dict[str, List[AdjustedRegion]]) -> bytes:
        """Reconstruct DOCX document with translated content."""
        # This is a simplified implementation
        # In a real system, this would use python-docx library
        
        docx_content = []
        docx_content.append('<?xml version="1.0" encoding="UTF-8"?>')
        docx_content.append('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">')
        docx_content.append('<w:body>')
        
        for page in document.pages:
            page_key = str(page.page_number)
            page_adjusted_regions = adjusted_regions.get(page_key, [])
            
            # Create page content
            page_content = self._create_docx_page_content(page, page_adjusted_regions)
            docx_content.extend(page_content)
        
        docx_content.append('</w:body>')
        docx_content.append('</w:document>')
        
        return "\n".join(docx_content).encode('utf-8')
    
    def optimize_fonts_and_spacing(self, document: DocumentStructure) -> DocumentStructure:
        """Optimize DOCX fonts and spacing."""
        optimized_document = DocumentStructure(
            format=document.format,
            pages=[],
            metadata=document.metadata
        )
        
        for page in document.pages:
            optimized_page = self._optimize_docx_page(page)
            optimized_document.pages.append(optimized_page)
        
        return optimized_document
    
    def _create_docx_page_content(self, page: PageStructure,
                                adjusted_regions: List[AdjustedRegion]) -> List[str]:
        """Create DOCX content for a single page."""
        content = []
        
        # Sort regions by reading order
        sorted_regions = sorted(adjusted_regions, 
                              key=lambda r: r.original_region.reading_order)
        
        for region in sorted_regions:
            paragraph = self._create_docx_paragraph(region)
            content.extend(paragraph)
        
        return content
    
    def _create_docx_paragraph(self, region: AdjustedRegion) -> List[str]:
        """Create DOCX paragraph for an adjusted region."""
        # Get font size from adjustments or original
        font_size = region.original_region.formatting.font_size
        for adj in region.adjustments:
            if adj.adjustment_type == LayoutAdjustmentType.FONT_SIZE_CHANGE:
                font_size = adj.new_value
                break
        
        formatting = region.original_region.formatting
        
        paragraph = [
            '<w:p>',
            '<w:pPr>',
            f'<w:jc w:val="{formatting.alignment}"/>',
            '</w:pPr>',
            '<w:r>',
            '<w:rPr>',
            f'<w:rFonts w:ascii="{formatting.font_family}"/>',
            f'<w:sz w:val="{int(font_size * 2)}"/>',  # DOCX uses half-points
        ]
        
        if formatting.is_bold:
            paragraph.append('<w:b/>')
        if formatting.is_italic:
            paragraph.append('<w:i/>')
        if formatting.is_underlined:
            paragraph.append('<w:u w:val="single"/>')
        
        paragraph.extend([
            '</w:rPr>',
            f'<w:t>{region.adjusted_text}</w:t>',
            '</w:r>',
            '</w:p>'
        ])
        
        return paragraph
    
    def _optimize_docx_page(self, page: PageStructure) -> PageStructure:
        """Optimize a DOCX page for better text fitting."""
        optimized_regions = []
        
        for region in page.text_regions:
            # Optimize spacing and fonts
            optimized_formatting = self._optimize_docx_formatting(region.formatting)
            
            optimized_region = TextRegion(
                id=region.id,
                bounding_box=region.bounding_box,
                text_content=region.text_content,
                formatting=optimized_formatting,
                language=region.language,
                confidence=region.confidence,
                reading_order=region.reading_order
            )
            optimized_regions.append(optimized_region)
        
        return PageStructure(
            page_number=page.page_number,
            dimensions=page.dimensions,
            text_regions=optimized_regions,
            visual_elements=page.visual_elements,
            spatial_map=page.spatial_map
        )
    
    def _optimize_docx_formatting(self, formatting: TextFormatting) -> TextFormatting:
        """Optimize formatting for DOCX."""
        # Slightly reduce font size for better fitting
        optimized_size = max(8.0, formatting.font_size * 0.95)
        
        return TextFormatting(
            font_family=formatting.font_family,
            font_size=optimized_size,
            is_bold=formatting.is_bold,
            is_italic=formatting.is_italic,
            is_underlined=formatting.is_underlined,
            color=formatting.color,
            background_color=formatting.background_color,
            alignment=formatting.alignment
        )


class EPUBReconstructor(FormatSpecificReconstructor):
    """EPUB-specific document reconstruction."""
    
    def reconstruct_document(self, document: DocumentStructure,
                           adjusted_regions: Dict[str, List[AdjustedRegion]]) -> bytes:
        """Reconstruct EPUB document with translated content."""
        # This is a simplified implementation
        # In a real system, this would use ebooklib
        
        html_content = []
        html_content.append('<!DOCTYPE html>')
        html_content.append('<html xmlns="http://www.w3.org/1999/xhtml">')
        html_content.append('<head>')
        html_content.append('<title>Translated Document</title>')
        html_content.append('<style>')
        html_content.append(self._create_epub_styles())
        html_content.append('</style>')
        html_content.append('</head>')
        html_content.append('<body>')
        
        for page in document.pages:
            page_key = str(page.page_number)
            page_adjusted_regions = adjusted_regions.get(page_key, [])
            
            # Create chapter content
            chapter_content = self._create_epub_chapter_content(page, page_adjusted_regions)
            html_content.extend(chapter_content)
        
        html_content.append('</body>')
        html_content.append('</html>')
        
        return "\n".join(html_content).encode('utf-8')
    
    def optimize_fonts_and_spacing(self, document: DocumentStructure) -> DocumentStructure:
        """Optimize EPUB fonts and spacing."""
        optimized_document = DocumentStructure(
            format=document.format,
            pages=[],
            metadata=document.metadata
        )
        
        for page in document.pages:
            optimized_page = self._optimize_epub_page(page)
            optimized_document.pages.append(optimized_page)
        
        return optimized_document
    
    def _create_epub_styles(self) -> str:
        """Create CSS styles for EPUB."""
        return """
        body { font-family: serif; line-height: 1.4; }
        .text-region { margin-bottom: 1em; }
        .bold { font-weight: bold; }
        .italic { font-style: italic; }
        .underlined { text-decoration: underline; }
        .center { text-align: center; }
        .right { text-align: right; }
        .justify { text-align: justify; }
        """
    
    def _create_epub_chapter_content(self, page: PageStructure,
                                   adjusted_regions: List[AdjustedRegion]) -> List[str]:
        """Create EPUB chapter content for a page."""
        content = []
        content.append(f'<div class="chapter" id="page-{page.page_number}">')
        
        # Sort regions by reading order
        sorted_regions = sorted(adjusted_regions,
                              key=lambda r: r.original_region.reading_order)
        
        for region in sorted_regions:
            paragraph = self._create_epub_paragraph(region)
            content.append(paragraph)
        
        content.append('</div>')
        return content
    
    def _create_epub_paragraph(self, region: AdjustedRegion) -> str:
        """Create EPUB paragraph for an adjusted region."""
        # Get font size from adjustments or original
        font_size = region.original_region.formatting.font_size
        for adj in region.adjustments:
            if adj.adjustment_type == LayoutAdjustmentType.FONT_SIZE_CHANGE:
                font_size = adj.new_value
                break
        
        formatting = region.original_region.formatting
        
        # Build CSS classes
        css_classes = ["text-region"]
        if formatting.is_bold:
            css_classes.append("bold")
        if formatting.is_italic:
            css_classes.append("italic")
        if formatting.is_underlined:
            css_classes.append("underlined")
        if formatting.alignment != "left":
            css_classes.append(formatting.alignment)
        
        # Build inline styles
        styles = [f"font-size: {font_size}pt"]
        if formatting.font_family:
            styles.append(f"font-family: {formatting.font_family}")
        if formatting.color != "#000000":
            styles.append(f"color: {formatting.color}")
        
        style_attr = f'style="{"; ".join(styles)}"'
        class_attr = f'class="{" ".join(css_classes)}"'
        
        return f'<p {class_attr} {style_attr}>{region.adjusted_text}</p>'
    
    def _optimize_epub_page(self, page: PageStructure) -> PageStructure:
        """Optimize an EPUB page for better text fitting."""
        optimized_regions = []
        
        for region in page.text_regions:
            # EPUB is more flexible with text flow
            optimized_region = TextRegion(
                id=region.id,
                bounding_box=region.bounding_box,
                text_content=region.text_content,
                formatting=region.formatting,  # Keep original formatting
                language=region.language,
                confidence=region.confidence,
                reading_order=region.reading_order
            )
            optimized_regions.append(optimized_region)
        
        return PageStructure(
            page_number=page.page_number,
            dimensions=page.dimensions,
            text_regions=optimized_regions,
            visual_elements=page.visual_elements,
            spatial_map=page.spatial_map
        )


class DefaultLayoutReconstructionEngine(LayoutReconstructionEngine):
    """Default implementation of layout reconstruction engine."""
    
    def __init__(self):
        """Initialize the reconstruction engine."""
        self.text_fitting_engine = TextFittingEngine()
        self.layout_adjustment_engine = LayoutAdjustmentEngine()
        
        # Format-specific reconstructors
        self.reconstructors = {
            "pdf": PDFReconstructor(),
            "docx": DOCXReconstructor(),
            "epub": EPUBReconstructor()
        }
    
    def fit_translated_text(self, region: TextRegion, translated: str) -> AdjustedRegion:
        """Fit translated text into a text region."""
        return self.text_fitting_engine.fit_text_to_region(region, translated)
    
    def adjust_layout(self, page: PageStructure, 
                     adjustments: List[LayoutAdjustment]) -> PageStructure:
        """Adjust page layout based on text changes."""
        # Apply adjustments to create new page structure
        adjusted_regions = []
        adjusted_visual_elements = page.visual_elements.copy()
        
        # Group adjustments by element ID
        adjustments_by_element = {}
        for adj in adjustments:
            if adj.element_id not in adjustments_by_element:
                adjustments_by_element[adj.element_id] = []
            adjustments_by_element[adj.element_id].append(adj)
        
        # Apply adjustments to text regions
        for region in page.text_regions:
            if region.id in adjustments_by_element:
                adjusted_region = self._apply_adjustments_to_region(
                    region, adjustments_by_element[region.id]
                )
                adjusted_regions.append(adjusted_region)
            else:
                # No adjustments needed
                adjusted_regions.append(region)
        
        return PageStructure(
            page_number=page.page_number,
            dimensions=page.dimensions,
            text_regions=adjusted_regions,
            visual_elements=adjusted_visual_elements,
            spatial_map=page.spatial_map
        )
    
    def resolve_conflicts(self, conflicts: List[LayoutConflict]) -> List[ConflictResolution]:
        """Resolve layout conflicts between elements."""
        # This would typically require the adjusted regions as well
        # For now, return empty list as conflicts need context
        return []
    
    def reconstruct_document(self, document: DocumentStructure,
                           translated_regions: Dict[str, Dict[str, str]]) -> bytes:
        """Reconstruct entire document with translated content.
        
        Args:
            document: Original document structure
            translated_regions: Dict mapping page_id -> {region_id: translated_text}
            
        Returns:
            Reconstructed document as bytes
        """
        # Get format-specific reconstructor
        reconstructor = self.reconstructors.get(document.format.lower())
        if not reconstructor:
            raise ValueError(f"Unsupported format: {document.format}")
        
        # Optimize document for better fitting
        optimized_document = reconstructor.optimize_fonts_and_spacing(document)
        
        # Fit translated text to regions
        adjusted_regions_by_page = {}
        
        for page in optimized_document.pages:
            page_key = str(page.page_number)
            page_translations = translated_regions.get(page_key, {})
            
            adjusted_regions = []
            for region in page.text_regions:
                if region.id in page_translations:
                    translated_text = page_translations[region.id]
                    adjusted_region = self.fit_translated_text(region, translated_text)
                    adjusted_regions.append(adjusted_region)
                else:
                    # No translation, keep original
                    adjusted_region = AdjustedRegion(
                        original_region=region,
                        adjusted_text=region.text_content,
                        new_bounding_box=region.bounding_box,
                        adjustments=[],
                        fit_quality=1.0
                    )
                    adjusted_regions.append(adjusted_region)
            
            # Detect and resolve conflicts
            conflicts = self.layout_adjustment_engine.detect_layout_conflicts(adjusted_regions)
            if conflicts:
                resolutions = self.layout_adjustment_engine.resolve_conflicts(
                    conflicts, adjusted_regions
                )
                # Apply resolutions (simplified)
                adjusted_regions = self._apply_conflict_resolutions(
                    adjusted_regions, resolutions
                )
            
            adjusted_regions_by_page[page_key] = adjusted_regions
        
        # Reconstruct document
        return reconstructor.reconstruct_document(optimized_document, adjusted_regions_by_page)
    
    def _apply_adjustments_to_region(self, region: TextRegion,
                                   adjustments: List[LayoutAdjustment]) -> TextRegion:
        """Apply layout adjustments to a text region."""
        new_formatting = TextFormatting(
            font_family=region.formatting.font_family,
            font_size=region.formatting.font_size,
            is_bold=region.formatting.is_bold,
            is_italic=region.formatting.is_italic,
            is_underlined=region.formatting.is_underlined,
            color=region.formatting.color,
            background_color=region.formatting.background_color,
            alignment=region.formatting.alignment
        )
        
        new_bounding_box = BoundingBox(
            x=region.bounding_box.x,
            y=region.bounding_box.y,
            width=region.bounding_box.width,
            height=region.bounding_box.height
        )
        
        # Apply each adjustment
        for adj in adjustments:
            if adj.adjustment_type == LayoutAdjustmentType.FONT_SIZE_CHANGE:
                new_formatting.font_size = adj.new_value
            elif adj.adjustment_type == LayoutAdjustmentType.POSITION_SHIFT:
                new_bounding_box.x, new_bounding_box.y = adj.new_value
            elif adj.adjustment_type == LayoutAdjustmentType.BOUNDARY_EXPANSION:
                new_bounding_box.width, new_bounding_box.height = adj.new_value
        
        return TextRegion(
            id=region.id,
            bounding_box=new_bounding_box,
            text_content=region.text_content,
            formatting=new_formatting,
            language=region.language,
            confidence=region.confidence,
            reading_order=region.reading_order
        )
    
    def _apply_conflict_resolutions(self, adjusted_regions: List[AdjustedRegion],
                                  resolutions: List[ConflictResolution]) -> List[AdjustedRegion]:
        """Apply conflict resolutions to adjusted regions."""
        # Create a mapping for quick lookup
        regions_by_id = {r.original_region.id: r for r in adjusted_regions}
        
        # Apply each resolution
        for resolution in resolutions:
            for action in resolution.actions:
                if action.element_id in regions_by_id:
                    region = regions_by_id[action.element_id]
                    
                    # Apply the action
                    if action.adjustment_type == LayoutAdjustmentType.POSITION_SHIFT:
                        region.new_bounding_box.x, region.new_bounding_box.y = action.new_value
                    elif action.adjustment_type == LayoutAdjustmentType.BOUNDARY_EXPANSION:
                        region.new_bounding_box.width, region.new_bounding_box.height = action.new_value
                    
                    # Add the adjustment to the region's adjustment list
                    region.adjustments.append(action)
        
        return list(regions_by_id.values())