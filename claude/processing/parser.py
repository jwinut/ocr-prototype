"""
Data Parser - Thai text normalization and financial data extraction
"""

import re
from typing import Dict, List, Optional
import pandas as pd


# Thai digit mappings
THAI_DIGITS = "๐๑๒๓๔๕๖๗๘๙"
ARABIC_DIGITS = "0123456789"

# Thai digit translation table
THAI_TO_ARABIC = str.maketrans(THAI_DIGITS, ARABIC_DIGITS)

# Financial keywords for table detection
FINANCIAL_KEYWORDS = {
    'balance_sheet': ['สินทรัพย์', 'หนี้สิน', 'ทุน', 'สินทรัพย์รวม'],
    'income_statement': ['รายได้', 'ค่าใช้จ่าย', 'กำไร', 'ขาดทุน'],
    'cash_flow': ['กระแสเงินสด', 'เงินสดจาก', 'เงินสดรับ', 'เงินสดจ่าย'],
    'ratio': ['อัตราส่วน', 'เปอร์เซ็นต์', 'ROE', 'ROA'],
}


def normalize_thai_numbers(text: str) -> str:
    """
    Convert Thai numerals (๐-๙) to Arabic (0-9).

    Args:
        text: Text containing Thai numerals

    Returns:
        Text with Arabic numerals

    Examples:
        >>> normalize_thai_numbers("มูลค่า ๑,๒๓๔,๕๖๗.๘๙ บาท")
        'มูลค่า 1,234,567.89 บาท'
        >>> normalize_thai_numbers("ปี ๒๕๖๗")
        'ปี 2567'
    """
    return text.translate(THAI_TO_ARABIC)


def clean_extracted_text(text: str) -> str:
    """
    Clean OCR artifacts and normalize whitespace.

    Args:
        text: Raw OCR text

    Returns:
        Cleaned text

    Cleaning operations:
    - Normalize Thai numbers
    - Remove multiple spaces
    - Remove trailing/leading whitespace
    - Normalize line breaks
    - Remove special OCR artifacts
    """
    if not text:
        return ""

    # Convert Thai numerals to Arabic
    text = normalize_thai_numbers(text)

    # Remove common OCR artifacts
    text = text.replace('\x00', '')  # Null bytes
    text = text.replace('\ufeff', '')  # BOM

    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double

    # Remove trailing/leading whitespace per line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


def parse_financial_table(
    df: pd.DataFrame,
    metadata: Optional[Dict] = None
) -> Dict:
    """
    Parse financial table to structured dict with metadata.

    Args:
        df: Pandas DataFrame from OCR extraction
        metadata: Optional metadata dict

    Returns:
        Dict with parsed table data and metadata

    Structure:
        {
            'data': cleaned DataFrame,
            'metadata': {
                'row_count': int,
                'column_count': int,
                'table_type': str,  # detected type
                'has_numbers': bool,
                'has_thai': bool,
            }
        }
    """
    if df is None or df.empty:
        return {
            'data': pd.DataFrame(),
            'metadata': {
                'row_count': 0,
                'column_count': 0,
                'table_type': 'empty',
                'has_numbers': False,
                'has_thai': False,
            }
        }

    # Clean DataFrame
    cleaned_df = df.copy()

    # Normalize Thai numbers in all cells
    for col in cleaned_df.columns:
        if cleaned_df[col].dtype == 'object':
            cleaned_df[col] = cleaned_df[col].apply(
                lambda x: normalize_thai_numbers(str(x)) if pd.notna(x) else x
            )

    # Detect table type
    table_type = detect_table_type(cleaned_df)

    # Check for numbers and Thai text
    has_numbers = contains_numbers(cleaned_df)
    has_thai = contains_thai(cleaned_df)

    result = {
        'data': cleaned_df,
        'metadata': {
            'row_count': len(cleaned_df),
            'column_count': len(cleaned_df.columns),
            'table_type': table_type,
            'has_numbers': has_numbers,
            'has_thai': has_thai,
        }
    }

    # Add custom metadata if provided
    if metadata:
        result['metadata'].update(metadata)

    return result


def detect_table_type(df: pd.DataFrame) -> str:
    """
    Detect financial table type from content.

    Args:
        df: DataFrame to analyze

    Returns:
        Table type: 'balance_sheet', 'income_statement', 'cash_flow',
                   'ratio', or 'unknown'
    """
    if df.empty:
        return 'unknown'

    # Convert DataFrame to lowercase text for keyword matching
    text = ' '.join([
        str(cell).lower()
        for row in df.values
        for cell in row
        if pd.notna(cell)
    ])

    # Check keywords
    for table_type, keywords in FINANCIAL_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return table_type

    return 'unknown'


def contains_numbers(df: pd.DataFrame) -> bool:
    """Check if DataFrame contains numeric data"""
    for col in df.columns:
        if df[col].dtype in ['int64', 'float64']:
            return True

        # Check for numeric strings
        if df[col].dtype == 'object':
            sample = df[col].dropna().head(5)
            for val in sample:
                if re.search(r'\d', str(val)):
                    return True

    return False


def contains_thai(df: pd.DataFrame) -> bool:
    """Check if DataFrame contains Thai text"""
    thai_pattern = re.compile(r'[\u0E00-\u0E7F]')

    for col in df.columns:
        if df[col].dtype == 'object':
            sample = df[col].dropna().head(5)
            for val in sample:
                if thai_pattern.search(str(val)):
                    return True

    return False


def extract_company_info(text: str) -> Dict:
    """
    Extract company registration info from Gen Info documents.

    Args:
        text: Full text from Gen Info PDF

    Returns:
        Dict with extracted company information

    Extracted fields:
        - company_name_th: Thai company name
        - company_name_en: English company name
        - registration_number: Company registration number
        - address: Registered address
        - phone: Contact phone
        - website: Company website
    """
    info = {
        'company_name_th': None,
        'company_name_en': None,
        'registration_number': None,
        'address': None,
        'phone': None,
        'website': None,
    }

    if not text:
        return info

    # Clean text
    text = clean_extracted_text(text)

    # Extract company name patterns
    # Thai: "บริษัท ... จำกัด"
    th_name_match = re.search(
        r'บริษัท\s+([^\n]+?)\s+จำกัด',
        text
    )
    if th_name_match:
        info['company_name_th'] = f"บริษัท {th_name_match.group(1).strip()} จำกัด"

    # Registration number: typically 13 digits
    reg_match = re.search(r'เลขทะเบียน[:\s]*(\d{13})', text)
    if reg_match:
        info['registration_number'] = reg_match.group(1)

    # Phone: Thai format
    phone_patterns = [
        r'โทร[:\s]*(\d{1,3}-\d{3,4}-\d{4})',
        r'Tel[:\s]*(\d{1,3}-\d{3,4}-\d{4})',
        r'(?:โทรศัพท์|telephone)[:\s]*(\d{2,3}-\d{3,4}-\d{4})',
    ]
    for pattern in phone_patterns:
        phone_match = re.search(pattern, text, re.IGNORECASE)
        if phone_match:
            info['phone'] = phone_match.group(1)
            break

    # Website
    website_match = re.search(
        r'(?:www\.|https?://)([\w\.-]+\.\w+)',
        text,
        re.IGNORECASE
    )
    if website_match:
        info['website'] = website_match.group(1)

    # Address: typically after "ที่อยู่" or "address"
    address_match = re.search(
        r'(?:ที่อยู่|address)[:\s]*([^\n]+(?:\n[^\n]+){0,3})',
        text,
        re.IGNORECASE
    )
    if address_match:
        info['address'] = ' '.join(address_match.group(1).split())

    return info


def extract_financial_values(text: str) -> List[Dict]:
    """
    Extract financial values from text.

    Args:
        text: Text containing financial data

    Returns:
        List of dicts with {label, value, unit}
    """
    values = []

    # Patterns for financial values
    # Example: "สินทรัพย์รวม 1,234,567.89 บาท"
    pattern = r'([^\n\d]+?)\s+([\d,]+(?:\.\d+)?)\s*(บาท|Baht|THB)?'

    matches = re.finditer(pattern, text)

    for match in matches:
        label = match.group(1).strip()
        value_str = match.group(2).replace(',', '')
        unit = match.group(3) or 'THB'

        try:
            value = float(value_str)
            values.append({
                'label': label,
                'value': value,
                'unit': unit
            })
        except ValueError:
            continue

    return values


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names in DataFrame.

    Args:
        df: DataFrame with potentially messy column names

    Returns:
        DataFrame with normalized column names
    """
    normalized = df.copy()

    # Rename columns
    new_columns = []
    for col in normalized.columns:
        # Convert to string and clean
        col_str = str(col).strip()
        col_str = normalize_thai_numbers(col_str)
        col_str = re.sub(r'\s+', '_', col_str)
        new_columns.append(col_str)

    normalized.columns = new_columns
    return normalized
