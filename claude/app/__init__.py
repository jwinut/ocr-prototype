"""
Thai Financial Document OCR Application Package

This package contains the Streamlit GUI application for processing
Thai financial documents with OCR capabilities.
"""

__version__ = "0.1.0"
__author__ = "DEV-3 (GAMMA)"

# Lazy imports to avoid errors when dependencies not installed
try:
    from app.database import DatabaseManager
    __all__ = ["DatabaseManager"]
except ImportError:
    __all__ = []
