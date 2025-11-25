"""
Utility functions for Thai Financial Document OCR Prototype.
"""
from utils.validators import (
    validate_company_code,
    validate_document_type,
    validate_fiscal_year,
    sanitize_thai_text,
    detect_data_type,
)

from .thai_utils import (
    thai_to_arabic,
    arabic_to_thai,
    is_thai_text,
    contains_thai_digits,
    normalize_thai_company_name,
    extract_company_code,
    clean_thai_text,
    split_thai_sentence,
    is_valid_thai_company_name,
    format_thai_currency,
    parse_thai_currency,
    get_thai_year,
    get_buddhist_year,
    THAI_DIGITS,
    ARABIC_DIGITS,
)

__all__ = [
    # Validators
    "validate_company_code",
    "validate_document_type",
    "validate_fiscal_year",
    "sanitize_thai_text",
    "detect_data_type",

    # Thai text conversion
    'thai_to_arabic',
    'arabic_to_thai',

    # Thai text validation
    'is_thai_text',
    'contains_thai_digits',
    'is_valid_thai_company_name',

    # Thai text processing
    'normalize_thai_company_name',
    'extract_company_code',
    'clean_thai_text',
    'split_thai_sentence',

    # Currency handling
    'format_thai_currency',
    'parse_thai_currency',

    # Year conversion
    'get_thai_year',
    'get_buddhist_year',

    # Constants
    'THAI_DIGITS',
    'ARABIC_DIGITS',
]
