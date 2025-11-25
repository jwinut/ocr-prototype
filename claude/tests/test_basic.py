"""
Basic Tests - No dependencies required
Tests core functionality without pandas or Docling
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import directly from modules (avoid __init__.py imports that require pandas)
import processing.scanner as scanner
import processing.parser as parser
import utils.thai_utils as thai_utils

# Shortcuts for commonly used functions
parse_company_folder = scanner.parse_company_folder
detect_document_type = scanner.detect_document_type
scan_directory = scanner.scan_directory
get_statistics = scanner.get_statistics

normalize_thai_numbers = parser.normalize_thai_numbers
clean_extracted_text = parser.clean_extracted_text
extract_company_info = parser.extract_company_info

thai_to_arabic = thai_utils.thai_to_arabic
arabic_to_thai = thai_utils.arabic_to_thai
is_thai_text = thai_utils.is_thai_text
normalize_thai_company_name = thai_utils.normalize_thai_company_name
extract_company_code = thai_utils.extract_company_code
format_thai_currency = thai_utils.format_thai_currency
parse_thai_currency = thai_utils.parse_thai_currency
get_thai_year = thai_utils.get_thai_year
get_buddhist_year = thai_utils.get_buddhist_year


def test_scanner():
    """Test document scanner functionality"""
    print("\n" + "=" * 60)
    print("Testing Scanner")
    print("=" * 60)

    # Test company folder parsing
    folder_name = "10002819 บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด"
    code, name = parse_company_folder(folder_name)
    print(f"\n✓ Company folder parsing:")
    print(f"  Input: {folder_name}")
    print(f"  Code: {code}")
    print(f"  Name: {name}")

    assert code == "10002819", f"Expected code '10002819', got '{code}'"
    assert "โฮชุง" in name, f"Expected Thai text in name, got '{name}'"

    # Test document type detection
    test_files = [
        ("บริษัท โฮชุง_BS67.pdf", "BS"),
        ("บริษัท โฮชุง_Compare PL.pdf", "Compare PL"),
        ("บริษัท โฮชุง_Cash Flow.pdf", "Cash Flow"),
        ("บริษัท โฮชุง_Gen Info.pdf", "Gen Info"),
        ("บริษัท โฮชุง_Ratio.pdf", "Ratio"),
        ("บริษัท โฮชุง_Unknown.pdf", "Unknown"),
    ]

    print("\n✓ Document type detection:")
    for filename, expected_type in test_files:
        doc_type = detect_document_type(filename)
        print(f"  {filename} → {doc_type}")
        assert doc_type == expected_type, f"Expected '{expected_type}', got '{doc_type}'"

    print("\n✓ Scanner tests passed!")


def test_thai_utils():
    """Test Thai text utilities"""
    print("\n" + "=" * 60)
    print("Testing Thai Utilities")
    print("=" * 60)

    # Test Thai to Arabic conversion
    print("\n✓ Number conversion:")
    test_cases = [
        ("ปี ๒๕๖๗", "ปี 2567"),
        ("มูลค่า ๑,๒๓๔,๕๖๗.๘๙ บาท", "มูลค่า 1,234,567.89 บาท"),
        ("๐๑๒๓๔๕๖๗๘๙", "0123456789"),
    ]

    for thai, expected in test_cases:
        result = thai_to_arabic(thai)
        print(f"  {thai} → {result}")
        assert result == expected, f"Expected '{expected}', got '{result}'"

    # Test Arabic to Thai conversion
    print("\n✓ Reverse conversion:")
    arabic_text = "ปี 2567"
    thai_text = arabic_to_thai(arabic_text)
    print(f"  {arabic_text} → {thai_text}")
    assert "๒๕๖๗" in thai_text, f"Expected Thai digits in '{thai_text}'"

    # Test Thai text detection
    print("\n✓ Thai text detection:")
    test_cases = [
        ("บริษัท จำกัด", True),
        ("Company Limited", False),
        ("บริษัท ABC จำกัด", True),
    ]

    for text, expected in test_cases:
        result = is_thai_text(text)
        print(f"  '{text}' contains Thai: {result}")
        assert result == expected, f"Expected {expected}, got {result}"

    # Test company name normalization
    print("\n✓ Company name normalization:")
    messy_name = "บริษัท   ABC  (ประเทศไทย)  จำกัด  "
    clean_name = normalize_thai_company_name(messy_name)
    print(f"  Input:  '{messy_name}'")
    print(f"  Output: '{clean_name}'")
    assert "  " not in clean_name, "Should not have double spaces"
    assert clean_name.startswith("บริษัท"), "Should start with บริษัท"

    # Test company code extraction
    print("\n✓ Company code extraction:")
    test_text = "เลขทะเบียน: 0105567000123"
    code = extract_company_code(test_text)
    print(f"  Text: {test_text}")
    print(f"  Code: {code}")
    assert code == "0105567000123", f"Expected '0105567000123', got '{code}'"

    # Test currency formatting
    print("\n✓ Currency formatting:")
    amount = 1234567.89
    formatted = format_thai_currency(amount)
    print(f"  {amount} → {formatted}")
    assert "1,234,567.89" in formatted, "Should include formatted number"
    assert "บาท" in formatted, "Should include บาท"

    # Test currency parsing
    print("\n✓ Currency parsing:")
    currency_text = "1,234,567.89 บาท"
    parsed = parse_thai_currency(currency_text)
    print(f"  '{currency_text}' → {parsed}")
    assert parsed == 1234567.89, f"Expected 1234567.89, got {parsed}"

    # Test year conversion
    print("\n✓ Year conversion:")
    buddhist = 2567
    christian = get_thai_year(buddhist)
    print(f"  Buddhist {buddhist} → Christian {christian}")
    assert christian == 2024, f"Expected 2024, got {christian}"

    back = get_buddhist_year(christian)
    print(f"  Christian {christian} → Buddhist {back}")
    assert back == buddhist, f"Expected {buddhist}, got {back}"

    print("\n✓ Thai utils tests passed!")


def test_parser():
    """Test parser functionality"""
    print("\n" + "=" * 60)
    print("Testing Parser")
    print("=" * 60)

    # Test Thai number normalization
    print("\n✓ Thai number normalization:")
    text = "มูลค่า ๑,๒๓๔.๕๖ บาท"
    normalized = normalize_thai_numbers(text)
    print(f"  Input:  {text}")
    print(f"  Output: {normalized}")
    assert "1,234.56" in normalized, "Should contain Arabic numerals"

    # Test text cleaning
    print("\n✓ Text cleaning:")
    messy = "มูลค่า  ๑,๒๓๔.๕๖   บาท\n\n\n\nรายการถัดไป"
    clean = clean_extracted_text(messy)
    print(f"  Input lines:  {messy.count(chr(10))+1}")
    print(f"  Output lines: {clean.count(chr(10))+1}")
    assert clean.count("\n\n\n") == 0, "Should not have triple newlines"
    assert "1,234.56" in clean, "Should normalize Thai numbers"

    # Test company info extraction
    print("\n✓ Company info extraction:")
    sample_text = """
    บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด
    เลขทะเบียน: 0105567000123
    โทร: 02-123-4567
    www.example.co.th
    ที่อยู่: 123 ถนนสุขุมวิท แขวงคลองเตย
    """

    info = extract_company_info(sample_text)
    print(f"  Registration: {info['registration_number']}")
    print(f"  Phone: {info['phone']}")
    print(f"  Website: {info['website']}")

    assert info['registration_number'] == "0105567000123", "Should extract reg number"
    assert info['phone'] == "02-123-4567", "Should extract phone"
    assert "example.co.th" in (info['website'] or ""), "Should extract website"

    print("\n✓ Parser tests passed!")


def test_directory_scan():
    """Test scanning actual Y67 directory"""
    print("\n" + "=" * 60)
    print("Testing Directory Scan")
    print("=" * 60)

    base_path = "/Users/nut/ocr-prototype/Y67"

    try:
        # Scan directory
        print(f"\n✓ Scanning: {base_path}")
        documents = scan_directory(base_path, target_year="Y67")

        print(f"✓ Found {len(documents)} documents")

        # Show sample
        if documents:
            print("\n✓ Sample documents:")
            for doc in documents[:5]:
                print(f"  - {doc.company_code}: {doc.file_name}")
                print(f"    Type: {doc.document_type}, Size: {doc.file_size:,} bytes")

        # Show statistics
        stats = get_statistics(documents)

        print(f"\n✓ Statistics:")
        print(f"  Total documents: {stats['total_documents']}")
        print(f"  Total size: {stats['total_size_mb']} MB")
        print(f"  Unique companies: {stats['unique_companies']}")
        print(f"  Document types:")
        for doc_type, count in sorted(stats['document_types'].items()):
            print(f"    {doc_type}: {count}")

        print("\n✓ Directory scan tests passed!")

    except FileNotFoundError as e:
        print(f"⚠ Warning: Directory not found - {e}")
        print("  This is expected if Y67 folder is not available")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Thai Financial Document OCR Processing Pipeline")
    print("Basic Tests (No Dependencies)")
    print("=" * 60)

    try:
        test_scanner()
        test_thai_utils()
        test_parser()
        test_directory_scan()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
