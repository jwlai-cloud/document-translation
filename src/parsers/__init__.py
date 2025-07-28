"""Document parsers for different formats."""

from .base import (
    DocumentParser,
    DocumentParserFactory,
    ParsingError,
    ReconstructionError,
    get_parser_factory,
    register_parser,
)
from .pdf_parser import PDFParser

# Register parsers in the global factory
register_parser("pdf", PDFParser)

__all__ = [
    'DocumentParser',
    'DocumentParserFactory',
    'ParsingError',
    'ReconstructionError',
    'get_parser_factory',
    'register_parser',
    'PDFParser',
]