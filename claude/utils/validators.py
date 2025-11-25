"""
Data validation and sanitization utilities for Thai financial documents.
"""
import re
from typing import Optional
from datetime import datetime

from app.config import config
from models.schema import DataType


def validate_company_code(code: str) -> bool:
    """
    Validate Thai company code format.

    Company codes should be 8 digits as found in Y67 folder names.

    Args:
        code: Company code string

    Returns:
        True if valid, False otherwise
    """
    if not code:
        return False

    # Remove whitespace
    code = code.strip()

    # Must be exactly 8 digits
    if not re.match(r'^\d{8}$', code):
        return False

    return True


def validate_document_type(doc_type: str) -> bool:
    """
    Validate document type against known types.

    Args:
        doc_type: Document type string

    Returns:
        True if valid, False otherwise
    """
    if not doc_type:
        return False

    return doc_type.strip() in config.VALID_DOCUMENT_TYPES


def validate_fiscal_year(year_be: int, min_year: int = 2500, max_year: int = 2600) -> bool:
    """
    Validate fiscal year in Buddhist Era.

    Args:
        year_be: Year in Buddhist Era (e.g., 2567)
        min_year: Minimum valid year
        max_year: Maximum valid year

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(year_be, int):
        return False

    # Buddhist Era years should be in reasonable range
    # 2500 BE = 1957 CE, 2600 BE = 2057 CE
    return min_year <= year_be <= max_year


def sanitize_thai_text(text: str) -> str:
    """
    Sanitize Thai text by removing control characters and normalizing whitespace.

    Args:
        text: Input text string

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Remove control characters except newline and tab
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # Normalize whitespace (but preserve Thai spaces)
    text = re.sub(r'[ \t]+', ' ', text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def detect_data_type(value: str) -> DataType:
    """
    Detect the data type of a cell value.

    Args:
        value: Cell value string

    Returns:
        DataType enum value
    """
    if not value or not value.strip():
        return DataType.UNKNOWN

    value = value.strip()

    # Check for currency (Thai Baht or common currency symbols)
    if re.search(r'[\฿$€£¥₹]|บาท', value):
        return DataType.CURRENCY

    # Check for percentage
    if '%' in value or 'เปอร์เซ็นต์' in value:
        return DataType.PERCENTAGE

    # Check for date patterns
    # Thai date: วันที่ 31/12/2567
    # ISO date: 2024-12-31
    # Buddhist calendar dates
    date_patterns = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # DD/MM/YYYY or DD-MM-YYYY
        r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',    # YYYY-MM-DD or YYYY/MM/DD
        r'วันที่\s*\d{1,2}',                # Thai date prefix
        r'\d{1,2}\s*(?:ม\.ค.|ก\.พ.|มี\.ค.|เม\.ย.|พ\.ค.|มิ\.ย.|ก\.ค.|ส\.ค.|ก\.ย.|ต\.ค.|พ\.ย.|ธ\.ค.)',  # Thai month abbreviations
    ]

    for pattern in date_patterns:
        if re.search(pattern, value):
            return DataType.DATE

    # Check for numbers (including Thai numerals and formatted numbers)
    # Remove common formatting characters
    cleaned = re.sub(r'[,\s]', '', value)

    # Check if it's a number (including negative and decimals)
    if re.match(r'^-?\d+\.?\d*$', cleaned):
        return DataType.NUMBER

    # Check for numbers in parentheses (negative numbers in accounting format)
    if re.match(r'^\(\s*\d+\.?\d*\s*\)$', value):
        return DataType.NUMBER

    # Default to text
    return DataType.TEXT


def parse_company_folder_name(folder_name: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse company code and name from Y67 folder name format.

    Expected format: "10002819 บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด"

    Args:
        folder_name: Folder name string

    Returns:
        Tuple of (company_code, company_name_th) or (None, None) if invalid
    """
    # Pattern: 8 digits followed by space and Thai company name
    match = re.match(r'^(\d{8})\s+(.+)$', folder_name)

    if not match:
        return None, None

    code = match.group(1)
    name = match.group(2).strip()

    if not validate_company_code(code):
        return None, None

    return code, sanitize_thai_text(name)


def extract_year_from_filename(filename: str) -> Optional[int]:
    """
    Extract Buddhist Era year from filename.

    Args:
        filename: Document filename

    Returns:
        Year in Buddhist Era or None if not found
    """
    # Look for 4-digit year patterns (2500-2600 range for BE)
    matches = re.findall(r'\b(25\d{2}|26\d{2})\b', filename)

    for match in matches:
        year = int(match)
        if validate_fiscal_year(year):
            return year

    return None


def format_thai_currency(amount: float) -> str:
    """
    Format number as Thai currency string.

    Args:
        amount: Numeric amount

    Returns:
        Formatted currency string with commas and 2 decimal places
    """
    return f"{amount:,.2f} บาท"


def convert_be_to_ce(year_be: int) -> int:
    """
    Convert Buddhist Era year to Common Era year.

    Args:
        year_be: Year in Buddhist Era

    Returns:
        Year in Common Era
    """
    return year_be - 543


def convert_ce_to_be(year_ce: int) -> int:
    """
    Convert Common Era year to Buddhist Era year.

    Args:
        year_ce: Year in Common Era

    Returns:
        Year in Buddhist Era
    """
    return year_ce + 543


def normalize_document_type(doc_type: str) -> Optional[str]:
    """
    Normalize document type string to standard format.

    Args:
        doc_type: Document type string (may have variations)

    Returns:
        Normalized document type or None if invalid
    """
    if not doc_type:
        return None

    # Clean up
    doc_type = doc_type.strip()

    # Direct match
    if doc_type in config.VALID_DOCUMENT_TYPES:
        return doc_type

    # Case-insensitive matching and common variations
    doc_type_lower = doc_type.lower()

    type_mapping = {
        'balance sheet': 'BS',
        'งบดุล': 'BS',
        'comparative balance sheet': 'Compare BS',
        'comparative profit': 'Compare PL',
        'profit loss': 'Compare PL',
        'งบกำไรขาดทุน': 'Compare PL',
        'cash flow': 'Cash Flow',
        'กระแสเงินสด': 'Cash Flow',
        'general': 'Gen Info',
        'ข้อมูลทั่วไป': 'Gen Info',
        'financial ratio': 'Ratio',
        'อัตราส่วน': 'Ratio',
        'related party': 'Related',
        'บุคคลหรือกิจการที่เกี่ยวข้อง': 'Related',
        'shareholder': 'Shareholders',
        'ผู้ถือหุ้น': 'Shareholders',
    }

    for key, value in type_mapping.items():
        if key in doc_type_lower:
            return value

    return None


def is_valid_thai_text(text: str) -> bool:
    """
    Check if text contains Thai characters.

    Args:
        text: Text to check

    Returns:
        True if contains Thai characters, False otherwise
    """
    if not text:
        return False

    # Thai Unicode range: U+0E00 to U+0E7F
    thai_pattern = re.compile(r'[\u0E00-\u0E7F]')
    return bool(thai_pattern.search(text))


def calculate_confidence_score(scores: list[float]) -> float:
    """
    Calculate average confidence score from list of scores.

    Args:
        scores: List of confidence scores (0.0 to 1.0)

    Returns:
        Average confidence score
    """
    if not scores:
        return 0.0

    valid_scores = [s for s in scores if 0.0 <= s <= 1.0]

    if not valid_scores:
        return 0.0

    return sum(valid_scores) / len(valid_scores)
