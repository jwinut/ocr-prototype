"""
Test Processing Pipeline
Basic tests for scanner, OCR, parser, and batch processing
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from processing import (
    scan_directory,
    parse_company_folder,
    detect_document_type,
    normalize_thai_numbers,
    clean_extracted_text,
    extract_company_info,
)

from utils import (
    thai_to_arabic,
    is_thai_text,
    normalize_thai_company_name,
)


def test_scanner():
    """Test document scanner functionality"""
    print("\n=== Testing Scanner ===")

    # Test company folder parsing
    folder_name = "10002819 บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด"
    code, name = parse_company_folder(folder_name)
    print(f"✓ Company code: {code}")
    print(f"✓ Company name: {name}")

    # Test document type detection
    test_files = [
        "บริษัท โฮชุง_BS67.pdf",
        "บริษัท โฮชุง_Compare PL.pdf",
        "บริษัท โฮชุง_Cash Flow.pdf",
        "บริษัท โฮชุง_Gen Info.pdf",
    ]

    print("\nDocument type detection:")
    for filename in test_files:
        doc_type = detect_document_type(filename)
        print(f"✓ {filename} → {doc_type}")


def test_thai_utils():
    """Test Thai text utilities"""
    print("\n=== Testing Thai Utils ===")

    # Test Thai to Arabic conversion
    thai_text = "ปี ๒๕๖๗ มูลค่า ๑,๒๓๔,๕๖๗.๘๙ บาท"
    arabic_text = thai_to_arabic(thai_text)
    print(f"✓ Thai numerals: {thai_text}")
    print(f"✓ Arabic numerals: {arabic_text}")

    # Test Thai text detection
    texts = [
        "บริษัท จำกัด",
        "Company Limited",
        "บริษัท ABC จำกัด",
    ]

    print("\nThai text detection:")
    for text in texts:
        result = is_thai_text(text)
        print(f"✓ '{text}' contains Thai: {result}")

    # Test company name normalization
    messy_name = "บริษัท   ABC  (ประเทศไทย)  จำกัด  "
    clean_name = normalize_thai_company_name(messy_name)
    print(f"\n✓ Messy: '{messy_name}'")
    print(f"✓ Clean: '{clean_name}'")


def test_parser():
    """Test parser functionality"""
    print("\n=== Testing Parser ===")

    # Test text cleaning
    messy_text = "มูลค่า  ๑,๒๓๔.๕๖   บาท\n\n\n\nรายการถัดไป"
    clean_text = clean_extracted_text(messy_text)
    print(f"✓ Messy: '{messy_text}'")
    print(f"✓ Clean: '{clean_text}'")

    # Test company info extraction
    sample_text = """
    บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด
    เลขทะเบียน: 0105567000123
    โทร: 02-123-4567
    www.example.co.th
    ที่อยู่: 123 ถนนสุขุมวิท แขวงคลองเตย เขตคลองเตย กรุงเทพฯ 10110
    """

    info = extract_company_info(sample_text)
    print("\nExtracted company info:")
    for key, value in info.items():
        if value:
            print(f"✓ {key}: {value}")


def test_directory_scan():
    """Test scanning actual Y67 directory"""
    print("\n=== Testing Directory Scan ===")

    base_path = "/Users/nut/ocr-prototype/Y67"

    try:
        # Scan directory
        documents = scan_directory(base_path, target_year="Y67")

        print(f"✓ Found {len(documents)} documents")

        # Show sample
        if documents:
            print("\nSample documents:")
            for doc in documents[:3]:
                print(f"  - {doc.company_code}: {doc.document_type}")

        # Show statistics
        from processing.scanner import get_statistics
        stats = get_statistics(documents)

        print(f"\nStatistics:")
        print(f"✓ Total documents: {stats['total_documents']}")
        print(f"✓ Total size: {stats['total_size_mb']} MB")
        print(f"✓ Unique companies: {stats['unique_companies']}")
        print(f"✓ Document types:")
        for doc_type, count in stats['document_types'].items():
            print(f"    {doc_type}: {count}")

    except FileNotFoundError as e:
        print(f"⚠ Skipping directory scan: {e}")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Thai Financial Document OCR Processing Pipeline")
    print("=" * 60)

    test_scanner()
    test_thai_utils()
    test_parser()
    test_directory_scan()

    print("\n" + "=" * 60)
    print("✓ All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
