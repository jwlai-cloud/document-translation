"""Pytest configuration and fixtures."""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_text():
    """Sample text for testing."""
    return "This is a sample text for testing translation functionality."


@pytest.fixture
def sample_languages():
    """Sample language pairs for testing."""
    return [
        ('en', 'fr'),
        ('en', 'zh'),
        ('fr', 'en'),
        ('zh', 'en'),
    ]