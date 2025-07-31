# Project Structure & Architecture

## Directory Organization

```
document_translator/
├── src/                     # Main source code
│   ├── parsers/            # Document format parsers (PDF, DOCX, EPUB)
│   ├── layout/             # Layout analysis and reconstruction
│   ├── translation/        # Translation services and language detection
│   ├── services/           # Core services (upload, preview, quality, orchestrator)
│   ├── models/             # Data models and structures
│   ├── performance/        # Performance optimization and monitoring
│   ├── quality/            # Quality assessment services
│   ├── errors/             # Error handling and recovery
│   ├── web/                # Web interface (Gradio)
│   └── config.py           # Configuration settings
├── tests/                  # Comprehensive test suite
├── examples/               # Usage examples for each component
├── .kiro/specs/            # Feature specifications and design docs
├── app.py                  # Main application entry point
└── requirements.txt        # Project dependencies
```

## Architecture Patterns

### Abstract Base Classes
- All major components follow ABC pattern with concrete implementations
- Base classes in `src/parsers/base.py`, `src/services/base.py`, etc.
- Factory pattern for parser creation (`DocumentParserFactory`)

### Data Models
- Dataclass-based models in `src/models/`
- Core models: `DocumentStructure`, `PageStructure`, `TextRegion`, `VisualElement`
- Validation built into model `__post_init__` methods
- UUID-based element identification

### Service Layer
- Service-oriented architecture with clear separation of concerns
- Services: Upload, Preview, Download, Quality Assessment, Orchestrator
- Abstract base classes define contracts for all services

### Error Handling
- Custom exception hierarchy in `src/errors/`
- Structured error handling with recovery mechanisms
- Comprehensive logging with `structlog`

## Code Conventions

### File Naming
- Snake_case for Python files and directories
- Descriptive names indicating purpose (e.g., `pdf_parser.py`, `translation_service.py`)
- Test files prefixed with `test_`

### Class Structure
- Abstract base classes for extensibility
- Factory patterns for object creation
- Dataclasses for data models with validation
- Logging integrated into all major classes

### Import Organization
- Standard library imports first
- Third-party imports second
- Local imports last
- Absolute imports preferred (`from src.models.document import DocumentStructure`)

### Testing Structure
- Tests mirror source structure in `tests/` directory
- Integration tests for end-to-end workflows
- Performance tests marked with `@pytest.mark.performance`
- Async tests supported with `pytest-asyncio`

## Key Design Principles
- **Modularity**: Clear separation between parsing, translation, and reconstruction
- **Extensibility**: Easy to add new document formats via parser registration
- **Validation**: Input validation at multiple layers (file, model, service)
- **Error Recovery**: Graceful handling of failures with detailed error reporting
- **Performance**: Memory optimization and concurrent processing support
- **Specification-Driven**: Detailed specs in `.kiro/specs/` guide development