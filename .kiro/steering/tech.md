# Technology Stack

## Core Technologies
- **Python 3.10+**: Primary development language
- **Gradio 4.0+**: Web interface framework
- **FastAPI**: Web framework for API endpoints

## Document Processing Libraries
- **PyMuPDF 1.23+**: Advanced PDF processing and manipulation
- **python-docx 0.8+**: Microsoft Word document handling
- **ebooklib 0.18+**: EPUB format processing

## Translation & Language Processing
- **langdetect 1.0+**: Automatic language detection
- **googletrans 4.0+**: Translation services
- **Transformers & PyTorch**: ML models for translation (when needed)

## Supporting Libraries
- **Pillow 10.0+**: Image processing
- **pandas 2.0+**: Data processing
- **numpy 1.24+**: Numerical computations
- **pydantic 2.0+**: Data validation and settings
- **structlog 23.1+**: Structured logging
- **psutil 5.9+**: System monitoring

## Development & Testing
- **pytest 7.4+**: Testing framework with async support
- **pytest-asyncio**: Async test support
- **python-dotenv**: Environment variable management

## Common Commands

### Local Development
```bash
# Setup and run locally
./run_local.sh

# Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test categories
pytest -m integration
pytest -m performance
pytest -m slow
```

### Environment Setup
```bash
# Set Python path
export PYTHONPATH=$(pwd)

# Default port
export PORT=7860
```

## Configuration
- Environment variables managed via `.env` files
- Configuration classes in `src/config.py`
- Default settings for file size limits, supported formats, and processing options
- Language support configured in `SUPPORTED_LANGUAGES` constant