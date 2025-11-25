"""
OCR Processing Pipeline
Thai financial document processing with Docling OCR engine

Lazy imports to avoid errors when dependencies not installed.
"""

__version__ = '0.1.0'

# Scanner has no external dependencies - always available
from .scanner import DocumentInfo, scan_directory, parse_company_folder, detect_document_type

__all__ = [
    'DocumentInfo',
    'scan_directory',
    'parse_company_folder',
    'detect_document_type',
]

# OCR, Parser, Batch require pandas/docling - lazy import
try:
    from .ocr import DocumentProcessor, ProcessedDocument
    from .parser import (
        normalize_thai_numbers,
        clean_extracted_text,
        parse_financial_table,
        extract_company_info
    )
    from .batch import BatchProcessor, BatchProgress
    from .thai_postprocess import (
        postprocess_thai_ocr,
        postprocess_markdown,
        fix_spacing_issues,
        apply_common_corrections,
        convert_parentheses_to_negative,
        normalize_thai_text,
        add_correction,
        get_pythainlp_status,
        PostProcessResult,
    )

    __all__.extend([
        'DocumentProcessor',
        'ProcessedDocument',
        'normalize_thai_numbers',
        'clean_extracted_text',
        'parse_financial_table',
        'extract_company_info',
        'BatchProcessor',
        'BatchProgress',
        'postprocess_thai_ocr',
        'postprocess_markdown',
        'fix_spacing_issues',
        'apply_common_corrections',
        'convert_parentheses_to_negative',
        'normalize_thai_text',
        'add_correction',
        'get_pythainlp_status',
        'PostProcessResult',
    ])
except ImportError:
    # Dependencies not installed - scanner still works
    pass
