"""Example usage of PDF parser."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parsers import get_parser_factory
from models.document import DocumentStructure


def demonstrate_pdf_parsing():
    """Demonstrate PDF parsing functionality."""
    print("PDF Parser Example")
    print("=" * 50)
    
    # Get the global parser factory
    factory = get_parser_factory()
    
    # Show supported formats
    print(f"Supported formats: {factory.get_supported_formats()}")
    
    # Check if PDF is supported
    if factory.is_format_supported("pdf"):
        print("✓ PDF format is supported")
    else:
        print("✗ PDF format is not supported")
        return
    
    # Create a PDF parser
    pdf_parser = factory.create_parser("pdf")
    print(f"Created parser: {pdf_parser.__class__.__name__}")
    print(f"Parser supports: {pdf_parser.get_supported_formats()}")
    
    # Example of what would happen with a real PDF file
    print("\nExample workflow:")
    print("1. Upload PDF file")
    print("2. Validate file format and size")
    print("3. Parse PDF structure:")
    print("   - Extract text regions with formatting")
    print("   - Extract images and visual elements")
    print("   - Build spatial relationships")
    print("   - Create document structure")
    print("4. Process for translation")
    print("5. Reconstruct translated PDF")
    
    # Show what a parsed structure would look like
    print("\nExample parsed structure:")
    example_structure = DocumentStructure(format="pdf")
    print(f"Format: {example_structure.format}")
    print(f"Pages: {len(example_structure.pages)}")
    print(f"Metadata: {example_structure.metadata.title}")
    
    print("\nPDF Parser Features:")
    features = [
        "✓ Extract text with precise positioning",
        "✓ Preserve font formatting (size, style, color)",
        "✓ Extract images and visual elements",
        "✓ Handle encrypted PDFs (with error handling)",
        "✓ Build spatial relationships between elements",
        "✓ Reconstruct PDFs with translated content",
        "✓ Maintain layout and visual fidelity"
    ]
    
    for feature in features:
        print(f"  {feature}")


def show_pdf_capabilities():
    """Show PDF parser capabilities."""
    print("\nPDF Parser Capabilities")
    print("=" * 30)
    
    capabilities = {
        "Text Extraction": [
            "Character-level positioning",
            "Font family and size detection",
            "Bold, italic, underline detection",
            "Color information",
            "Reading order determination"
        ],
        "Visual Elements": [
            "Image extraction with positioning",
            "Drawing and shape detection",
            "Table structure recognition",
            "Chart and diagram handling"
        ],
        "Layout Analysis": [
            "Spatial relationship mapping",
            "Column detection",
            "Header and footer identification",
            "Text flow analysis"
        ],
        "Reconstruction": [
            "Precise text placement",
            "Image reintegration",
            "Format preservation",
            "Layout adjustment for translations"
        ]
    }
    
    for category, items in capabilities.items():
        print(f"\n{category}:")
        for item in items:
            print(f"  • {item}")


if __name__ == "__main__":
    demonstrate_pdf_parsing()
    show_pdf_capabilities()
    
    print("\n" + "=" * 50)
    print("To use with a real PDF file:")
    print("1. Ensure PyMuPDF is installed: pip install PyMuPDF")
    print("2. Use factory.parse_document('path/to/file.pdf')")
    print("3. Process the returned DocumentStructure")
    print("4. Use factory.reconstruct_document(structure) to create new PDF")