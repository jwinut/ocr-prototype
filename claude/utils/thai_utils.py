"""
Thai Text Utilities - Thai language processing helpers
"""

import re
from typing import Optional


# Thai Unicode ranges
THAI_CONSONANTS = "กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"
THAI_VOWELS = "ะาิีึืุูเแโใไ"
THAI_TONES = "่้๊๋"
THAI_DIGITS = "๐๑๒๓๔๕๖๗๘๙"
THAI_SPECIAL = "ๆฯ"

# Arabic digits
ARABIC_DIGITS = "0123456789"

# Translation tables
THAI_TO_ARABIC = str.maketrans(THAI_DIGITS, ARABIC_DIGITS)
ARABIC_TO_THAI = str.maketrans(ARABIC_DIGITS, THAI_DIGITS)


def thai_to_arabic(text: str) -> str:
    """
    Convert Thai numerals (๐-๙) to Arabic numerals (0-9).

    Args:
        text: Text containing Thai numerals

    Returns:
        Text with Arabic numerals

    Examples:
        >>> thai_to_arabic("ปี ๒๕๖๗")
        'ปี 2567'
        >>> thai_to_arabic("มูลค่า ๑,๒๓๔.๕๖ บาท")
        'มูลค่า 1,234.56 บาท'
    """
    return text.translate(THAI_TO_ARABIC)


def arabic_to_thai(text: str) -> str:
    """
    Convert Arabic numerals (0-9) to Thai numerals (๐-๙).

    Args:
        text: Text containing Arabic numerals

    Returns:
        Text with Thai numerals

    Examples:
        >>> arabic_to_thai("ปี 2567")
        'ปี ๒๕๖๗'
        >>> arabic_to_thai("มูลค่า 1,234.56 บาท")
        'มูลค่า ๑,๒๓๔.๕๖ บาท'
    """
    return text.translate(ARABIC_TO_THAI)


def is_thai_text(text: str) -> bool:
    """
    Check if text contains Thai characters.

    Args:
        text: Text to check

    Returns:
        True if Thai characters found, False otherwise

    Examples:
        >>> is_thai_text("บริษัท จำกัด")
        True
        >>> is_thai_text("Company Limited")
        False
        >>> is_thai_text("บริษัท ABC Company จำกัด")
        True
    """
    thai_pattern = re.compile(r'[\u0E00-\u0E7F]')
    return bool(thai_pattern.search(text))


def contains_thai_digits(text: str) -> bool:
    """
    Check if text contains Thai digits.

    Args:
        text: Text to check

    Returns:
        True if Thai digits found
    """
    return any(digit in text for digit in THAI_DIGITS)


def normalize_thai_company_name(name: str) -> str:
    """
    Normalize Thai company name format.

    Normalization:
    - Convert Thai numerals to Arabic
    - Normalize whitespace
    - Standardize company type suffix
    - Remove extra punctuation

    Args:
        name: Thai company name

    Returns:
        Normalized company name

    Examples:
        >>> normalize_thai_company_name("บริษัท   ABC  (ประเทศไทย)  จำกัด  ")
        'บริษัท ABC (ประเทศไทย) จำกัด'
        >>> normalize_thai_company_name("บริษัท XYZ จำกัด (มหาชน)")
        'บริษัท XYZ จำกัด (มหาชน)'
    """
    # Convert Thai numerals
    name = thai_to_arabic(name)

    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name)

    # Remove trailing/leading whitespace
    name = name.strip()

    # Standardize company type suffixes
    company_types = [
        'บริษัท',
        'จำกัด',
        'มหาชน',
        'ห้างหุ้นส่วนจำกัด',
        'ห้างหุ้นส่วนสามัญ',
    ]

    # Ensure proper spacing around company types
    for comp_type in company_types:
        # Add space after "บริษัท" if missing
        if comp_type == 'บริษัท':
            name = re.sub(rf'{comp_type}(\S)', rf'{comp_type} \1', name)

        # Add space before "จำกัด" if missing
        if comp_type in ['จำกัด', 'มหาชน']:
            name = re.sub(rf'(\S){comp_type}', rf'\1 {comp_type}', name)

    return name


def extract_company_code(text: str) -> Optional[str]:
    """
    Extract company registration code from text.

    Common patterns:
    - 13-digit registration number
    - Stock symbol (if listed company)

    Args:
        text: Text containing company code

    Returns:
        Extracted company code or None

    Examples:
        >>> extract_company_code("เลขทะเบียน: 0105567000123")
        '0105567000123'
        >>> extract_company_code("Registration: 0105567000123")
        '0105567000123'
    """
    # Thai format
    thai_pattern = r'(?:เลขทะเบียน|ทะเบียนเลขที่)[:\s]*(\d{13})'
    match = re.search(thai_pattern, text)
    if match:
        return match.group(1)

    # English format
    eng_pattern = r'(?:Registration No|Reg\. No|Registration)[:\s.]*(\d{13})'
    match = re.search(eng_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Standalone 13-digit number
    standalone = re.search(r'\b(\d{13})\b', text)
    if standalone:
        return standalone.group(1)

    return None


def clean_thai_text(text: str) -> str:
    """
    Clean Thai text by removing unwanted characters and normalizing.

    Args:
        text: Thai text to clean

    Returns:
        Cleaned text
    """
    # Remove zero-width characters
    text = text.replace('\u200b', '')  # Zero-width space
    text = text.replace('\ufeff', '')  # BOM

    # Normalize Thai tone marks (should follow consonant/vowel)
    # This is a simplified version
    text = re.sub(r'\s+([่้๊๋])', r'\1', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def split_thai_sentence(text: str) -> list[str]:
    """
    Split Thai text into sentences.

    Thai doesn't use spaces between words, but uses spaces
    for sentence boundaries along with punctuation.

    Args:
        text: Thai text

    Returns:
        List of sentences
    """
    # Split on Thai and English punctuation
    sentences = re.split(r'[.!?।\n]+', text)

    # Clean and filter empty
    sentences = [s.strip() for s in sentences if s.strip()]

    return sentences


def is_valid_thai_company_name(name: str) -> bool:
    """
    Validate if string is a proper Thai company name.

    Checks:
    - Contains Thai characters
    - Contains "บริษัท" or company type keywords
    - Reasonable length

    Args:
        name: Potential company name

    Returns:
        True if valid company name format
    """
    if not name or len(name) < 10:
        return False

    # Must contain Thai text
    if not is_thai_text(name):
        return False

    # Should contain company type keywords
    company_keywords = ['บริษัท', 'ห้างหุ้นส่วน', 'จำกัด', 'มหาชน']
    if not any(keyword in name for keyword in company_keywords):
        return False

    return True


def format_thai_currency(amount: float, include_symbol: bool = True) -> str:
    """
    Format number as Thai currency.

    Args:
        amount: Amount to format
        include_symbol: Include "บาท" suffix

    Returns:
        Formatted currency string

    Examples:
        >>> format_thai_currency(1234567.89)
        '1,234,567.89 บาท'
        >>> format_thai_currency(1234567.89, include_symbol=False)
        '1,234,567.89'
    """
    formatted = f"{amount:,.2f}"

    if include_symbol:
        formatted += " บาท"

    return formatted


def parse_thai_currency(text: str) -> Optional[float]:
    """
    Parse Thai currency string to float.

    Args:
        text: Text containing currency amount

    Returns:
        Parsed amount or None

    Examples:
        >>> parse_thai_currency("1,234,567.89 บาท")
        1234567.89
        >>> parse_thai_currency("๑,๒๓๔.๕๖ บาท")
        1234.56
    """
    # Convert Thai numerals first
    text = thai_to_arabic(text)

    # Extract number
    match = re.search(r'([\d,]+(?:\.\d+)?)', text)

    if match:
        # Remove commas and convert
        number_str = match.group(1).replace(',', '')
        try:
            return float(number_str)
        except ValueError:
            return None

    return None


def get_thai_year(buddhist_year: int) -> int:
    """
    Convert Buddhist Era year to Christian Era.

    Args:
        buddhist_year: Year in Buddhist Era (e.g., 2567)

    Returns:
        Year in Christian Era (e.g., 2024)

    Examples:
        >>> get_thai_year(2567)
        2024
        >>> get_thai_year(2500)
        1957
    """
    return buddhist_year - 543


def get_buddhist_year(christian_year: int) -> int:
    """
    Convert Christian Era year to Buddhist Era.

    Args:
        christian_year: Year in Christian Era (e.g., 2024)

    Returns:
        Year in Buddhist Era (e.g., 2567)

    Examples:
        >>> get_buddhist_year(2024)
        2567
        >>> get_buddhist_year(1957)
        2500
    """
    return christian_year + 543
