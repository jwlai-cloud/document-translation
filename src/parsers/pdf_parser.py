"""PDF document parser using PyMuPDF."""

import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
from datetime import datetime

from .base import DocumentParser, ParsingError, ReconstructionError
from src.models.document import (
    DocumentStructure,
    PageStructure,
    TextRegion,
    VisualElement,
    BoundingBox,
    Dimensions,
    TextFormatting,
    DocumentMetadata,
    SpatialMap,
)


class PDFParser(DocumentParser):
    """PDF document parser using PyMuPDF for advanced PDF processing."""

    def __init__(self):
        """Initialize the PDF parser."""
        super().__init__()
        self.supported_formats = ["pdf"]

    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats.

        Returns:
            List containing 'pdf'
        """
        return self.supported_formats

    def parse(self, file_path: str) -> DocumentStructure:
        """Parse a PDF document and extract its structure.

        Args:
            file_path: Path to the PDF file

        Returns:
            DocumentStructure containing parsed content and layout

        Raises:
            ParsingError: If PDF parsing fails
        """
        try:
            self.logger.info(f"Starting PDF parsing: {file_path}")

            # Open the PDF document
            doc = fitz.open(file_path)

            if doc.is_encrypted:
                raise ParsingError(
                    "PDF is encrypted and cannot be processed",
                    file_path,
                    "PDF_ENCRYPTED",
                )

            # Extract document metadata
            metadata = self._extract_pdf_metadata(doc, file_path)

            # Create document structure
            document = DocumentStructure(format="pdf", metadata=metadata)

            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_structure = self._parse_page(page, page_num + 1)
                document.add_page(page_structure)

            doc.close()

            self.logger.info(
                f"Successfully parsed PDF: {file_path} "
                f"({len(document.pages)} pages, "
                f"{sum(len(p.text_regions) for p in document.pages)} text regions)"
            )

            return document

        except fitz.FileDataError as e:
            raise ParsingError(
                f"Invalid or corrupted PDF file: {str(e)}", file_path, "PDF_CORRUPTED"
            )
        except fitz.FileNotFoundError as e:
            raise ParsingError(
                f"PDF file not found: {str(e)}", file_path, "PDF_NOT_FOUND"
            )
        except Exception as e:
            if isinstance(e, ParsingError):
                raise
            raise ParsingError(
                f"Unexpected error parsing PDF: {str(e)}", file_path, "PDF_PARSE_ERROR"
            )

    def reconstruct(self, structure: DocumentStructure) -> bytes:
        """Reconstruct a PDF document from its structure.

        Args:
            structure: DocumentStructure to reconstruct

        Returns:
            Binary content of the reconstructed PDF

        Raises:
            ReconstructionError: If PDF reconstruction fails
        """
        try:
            self.logger.info(
                f"Starting PDF reconstruction ({len(structure.pages)} pages)"
            )

            # Create new PDF document
            doc = fitz.open()

            # Reconstruct each page
            for page_structure in structure.pages:
                self._reconstruct_page(doc, page_structure)

            # Get PDF content as bytes
            pdf_bytes = doc.tobytes()
            doc.close()

            self.logger.info(f"Successfully reconstructed PDF ({len(pdf_bytes)} bytes)")

            return pdf_bytes

        except Exception as e:
            raise ReconstructionError(
                f"Failed to reconstruct PDF: {str(e)}",
                "pdf",
                "PDF_RECONSTRUCTION_ERROR",
            )

    def _extract_pdf_metadata(
        self, doc: fitz.Document, file_path: str
    ) -> DocumentMetadata:
        """Extract metadata from PDF document.

        Args:
            doc: PyMuPDF document object
            file_path: Path to the PDF file

        Returns:
            DocumentMetadata with extracted information
        """
        metadata_dict = doc.metadata
        file_stat = Path(file_path).stat()

        # Parse creation and modification dates
        creation_date = None
        modification_date = None

        if metadata_dict.get("creationDate"):
            try:
                # PyMuPDF date format: D:YYYYMMDDHHmmSSOHH'mm'
                date_str = metadata_dict["creationDate"]
                if date_str.startswith("D:"):
                    date_str = date_str[2:16]  # Extract YYYYMMDDHHMMSS
                    creation_date = datetime.strptime(date_str, "%Y%m%d%H%M%S")
            except (ValueError, TypeError):
                self.logger.warning(
                    f"Could not parse creation date: {metadata_dict.get('creationDate')}"
                )

        if metadata_dict.get("modDate"):
            try:
                date_str = metadata_dict["modDate"]
                if date_str.startswith("D:"):
                    date_str = date_str[2:16]
                    modification_date = datetime.strptime(date_str, "%Y%m%d%H%M%S")
            except (ValueError, TypeError):
                self.logger.warning(
                    f"Could not parse modification date: {metadata_dict.get('modDate')}"
                )

        return DocumentMetadata(
            title=metadata_dict.get("title") or Path(file_path).stem,
            author=metadata_dict.get("author"),
            subject=metadata_dict.get("subject"),
            creator=metadata_dict.get("creator"),
            producer=metadata_dict.get("producer"),
            creation_date=creation_date,
            modification_date=modification_date,
            page_count=len(doc),
            file_size=file_stat.st_size,
        )

    def _parse_page(self, page: fitz.Page, page_number: int) -> PageStructure:
        """Parse a single PDF page.

        Args:
            page: PyMuPDF page object
            page_number: Page number (1-based)

        Returns:
            PageStructure with extracted content and layout
        """
        # Get page dimensions
        rect = page.rect
        dimensions = Dimensions(width=rect.width, height=rect.height, unit="pt")

        # Create page structure
        page_structure = PageStructure(page_number=page_number, dimensions=dimensions)

        # Extract text regions
        text_regions = self._extract_text_regions(page)
        page_structure.text_regions.extend(text_regions)

        # Extract visual elements
        visual_elements = self._extract_visual_elements(page)
        page_structure.visual_elements.extend(visual_elements)

        # Build spatial map
        spatial_map = self._build_spatial_map(text_regions, visual_elements)
        page_structure.spatial_map = spatial_map

        return page_structure

    def _extract_text_regions(self, page: fitz.Page) -> List[TextRegion]:
        """Extract text regions from a PDF page.

        Args:
            page: PyMuPDF page object

        Returns:
            List of TextRegion objects
        """
        text_regions = []

        # Get text blocks with formatting information
        blocks = page.get_text("dict")

        for block_idx, block in enumerate(blocks.get("blocks", [])):
            if "lines" not in block:
                continue  # Skip non-text blocks

            # Process each line in the block
            for line_idx, line in enumerate(block["lines"]):
                line_text = ""
                line_bbox = None
                line_formatting = None

                # Process each span (text with consistent formatting) in the line
                for span_idx, span in enumerate(line.get("spans", [])):
                    span_text = span.get("text", "").strip()
                    if not span_text:
                        continue

                    # Get span bounding box
                    span_bbox = BoundingBox(
                        x=span["bbox"][0],
                        y=span["bbox"][1],
                        width=span["bbox"][2] - span["bbox"][0],
                        height=span["bbox"][3] - span["bbox"][1],
                    )

                    # Extract formatting information
                    formatting = self._extract_text_formatting(span)

                    # Create text region for this span
                    region_id = f"page_{page.number + 1}_block_{block_idx}_line_{line_idx}_span_{span_idx}"

                    text_region = TextRegion(
                        id=region_id,
                        bounding_box=span_bbox,
                        text_content=span_text,
                        formatting=formatting,
                        language="en",  # Will be detected later
                        confidence=1.0,
                        reading_order=len(text_regions),
                    )

                    text_regions.append(text_region)

        return text_regions

    def _extract_text_formatting(self, span: Dict[str, Any]) -> TextFormatting:
        """Extract text formatting from a PyMuPDF span.

        Args:
            span: PyMuPDF span dictionary

        Returns:
            TextFormatting object
        """
        flags = span.get("flags", 0)

        return TextFormatting(
            font_family=span.get("font", "Arial"),
            font_size=span.get("size", 12.0),
            is_bold=bool(flags & 2**4),  # Bold flag
            is_italic=bool(flags & 2**1),  # Italic flag
            color=self._convert_color(span.get("color", 0)),
            alignment="left",  # Default alignment
        )

    def _convert_color(self, color_int: int) -> str:
        """Convert PyMuPDF color integer to hex string.

        Args:
            color_int: Color as integer

        Returns:
            Color as hex string (e.g., "#FF0000")
        """
        if color_int == 0:
            return "#000000"  # Black

        # Convert integer to RGB hex
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF

        return f"#{r:02X}{g:02X}{b:02X}"

    def _extract_visual_elements(self, page: fitz.Page) -> List[VisualElement]:
        """Extract visual elements from a PDF page.

        Args:
            page: PyMuPDF page object

        Returns:
            List of VisualElement objects
        """
        visual_elements = []

        # Extract images
        image_list = page.get_images()
        for img_idx, img in enumerate(image_list):
            try:
                # Get image information
                xref = img[0]
                pix = fitz.Pixmap(page.parent, xref)

                if pix.n - pix.alpha < 4:  # GRAY or RGB
                    img_data = pix.tobytes("png")

                    # Get image rectangle (approximate)
                    img_rects = page.get_image_rects(xref)
                    if img_rects:
                        rect = img_rects[0]
                        bbox = BoundingBox(
                            x=rect.x0, y=rect.y0, width=rect.width, height=rect.height
                        )
                    else:
                        # Fallback bounding box
                        bbox = BoundingBox(x=0, y=0, width=pix.width, height=pix.height)

                    element_id = f"page_{page.number + 1}_image_{img_idx}"

                    visual_element = VisualElement(
                        id=element_id,
                        element_type="image",
                        bounding_box=bbox,
                        content=img_data,
                        metadata={
                            "width": pix.width,
                            "height": pix.height,
                            "colorspace": pix.colorspace.name
                            if pix.colorspace
                            else "unknown",
                            "xref": xref,
                        },
                    )

                    visual_elements.append(visual_element)

                pix = None  # Clean up

            except Exception as e:
                self.logger.warning(f"Failed to extract image {img_idx}: {str(e)}")

        # Extract drawings/shapes
        drawings = page.get_drawings()
        for draw_idx, drawing in enumerate(drawings):
            try:
                # Get drawing bounding box
                rect = drawing.get("rect")
                if rect:
                    bbox = BoundingBox(
                        x=rect.x0, y=rect.y0, width=rect.width, height=rect.height
                    )

                    element_id = f"page_{page.number + 1}_drawing_{draw_idx}"

                    visual_element = VisualElement(
                        id=element_id,
                        element_type="shape",
                        bounding_box=bbox,
                        content=None,
                        metadata={
                            "type": drawing.get("type", "unknown"),
                            "items": len(drawing.get("items", [])),
                        },
                    )

                    visual_elements.append(visual_element)

            except Exception as e:
                self.logger.warning(f"Failed to extract drawing {draw_idx}: {str(e)}")

        return visual_elements

    def _build_spatial_map(
        self, text_regions: List[TextRegion], visual_elements: List[VisualElement]
    ) -> SpatialMap:
        """Build spatial relationships map for page elements.

        Args:
            text_regions: List of text regions
            visual_elements: List of visual elements

        Returns:
            SpatialMap with element relationships
        """
        spatial_map = SpatialMap()

        # Set reading order based on vertical position (top to bottom)
        all_elements = text_regions + visual_elements
        sorted_elements = sorted(
            all_elements, key=lambda elem: (elem.bounding_box.y, elem.bounding_box.x)
        )

        spatial_map.reading_order = [elem.id for elem in sorted_elements]

        # Build relationships based on proximity
        for i, element in enumerate(all_elements):
            nearby_elements = []

            for j, other_element in enumerate(all_elements):
                if i == j:
                    continue

                # Check if elements are nearby (within reasonable distance)
                distance = self._calculate_distance(
                    element.bounding_box, other_element.bounding_box
                )

                if distance < 100:  # Threshold for "nearby"
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

    def _reconstruct_page(
        self, doc: fitz.Document, page_structure: PageStructure
    ) -> None:
        """Reconstruct a single page in the PDF document.

        Args:
            doc: PyMuPDF document object
            page_structure: Page structure to reconstruct
        """
        # Create new page with original dimensions
        page = doc.new_page(
            width=page_structure.dimensions.width,
            height=page_structure.dimensions.height,
        )

        # Add text regions
        for text_region in page_structure.text_regions:
            self._add_text_to_page(page, text_region)

        # Add visual elements
        for visual_element in page_structure.visual_elements:
            self._add_visual_element_to_page(page, visual_element)

    def _add_text_to_page(self, page: fitz.Page, text_region: TextRegion) -> None:
        """Add a text region to a PDF page.

        Args:
            page: PyMuPDF page object
            text_region: Text region to add
        """
        try:
            # Create text rectangle
            rect = fitz.Rect(
                text_region.bounding_box.x,
                text_region.bounding_box.y,
                text_region.bounding_box.x + text_region.bounding_box.width,
                text_region.bounding_box.y + text_region.bounding_box.height,
            )

            # Convert formatting
            font_size = text_region.formatting.font_size
            color = self._hex_to_rgb(text_region.formatting.color)

            # Insert text
            page.insert_text(
                (rect.x0, rect.y0 + font_size),  # Position (baseline)
                text_region.text_content,
                fontsize=font_size,
                color=color,
                fontname="helv" if not text_region.formatting.is_bold else "helv-bold",
            )

        except Exception as e:
            self.logger.warning(f"Failed to add text region {text_region.id}: {str(e)}")

    def _add_visual_element_to_page(
        self, page: fitz.Page, visual_element: VisualElement
    ) -> None:
        """Add a visual element to a PDF page.

        Args:
            page: PyMuPDF page object
            visual_element: Visual element to add
        """
        try:
            if visual_element.element_type == "image" and visual_element.content:
                # Create image rectangle
                rect = fitz.Rect(
                    visual_element.bounding_box.x,
                    visual_element.bounding_box.y,
                    visual_element.bounding_box.x + visual_element.bounding_box.width,
                    visual_element.bounding_box.y + visual_element.bounding_box.height,
                )

                # Insert image
                page.insert_image(rect, stream=visual_element.content)

        except Exception as e:
            self.logger.warning(
                f"Failed to add visual element {visual_element.id}: {str(e)}"
            )

    def _hex_to_rgb(self, hex_color: str) -> Tuple[float, float, float]:
        """Convert hex color to RGB tuple.

        Args:
            hex_color: Color in hex format (e.g., "#FF0000")

        Returns:
            RGB tuple with values between 0 and 1
        """
        try:
            hex_color = hex_color.lstrip("#")
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
            return (r, g, b)
        except (ValueError, IndexError):
            return (0.0, 0.0, 0.0)  # Default to black
