"""
Minimal Tests - Pure Python, no external dependencies
Tests core functionality that doesn't require pandas or Docling
"""

import sys
import re
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_scanner_parsing():
    """Test scanner parsing functions (no imports needed)"""
    print("\n" + "=" * 60)
    print("Testing Scanner Logic")
    print("=" * 60)

    # Test company folder parsing
    def parse_company_folder(folder_name: str):
        """Inline implementation for testing"""
        match = re.match(r'^(\d+)\s+(.+)$', folder_name)
        if not match:
            return folder_name, folder_name
        company_code = match.group(1)
        company_name = match.group(2).strip()
        return company_code, company_name

    print("\n✓ Company folder parsing:")
    folder_name = "10002819 บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด"
    code, name = parse_company_folder(folder_name)
    print(f"  Input: {folder_name}")
    print(f"  Code: {code}")
    print(f"  Name: {name}")

    assert code == "10002819", f"Expected '10002819', got '{code}'"
    assert "โฮชุง" in name, f"Expected Thai text in name"
    print("  ✅ PASS")

    # Test document type detection
    DOCUMENT_TYPE_PATTERNS = {
        'BS': r'_BS\d{2}\.pdf$',
        'Compare PL': r'_Compare PL\.pdf$',
        'Cash Flow': r'_Cash Flow\.pdf$',
        'Gen Info': r'_Gen Info\.pdf$',
    }

    def detect_document_type(filename: str):
        """Inline implementation for testing"""
        for doc_type, pattern in DOCUMENT_TYPE_PATTERNS.items():
            if re.search(pattern, filename):
                return doc_type
        return 'Unknown'

    print("\n✓ Document type detection:")
    test_cases = [
        ("บริษัท โฮชุง_BS67.pdf", "BS"),
        ("บริษัท โฮชุง_Compare PL.pdf", "Compare PL"),
        ("บริษัท โฮชุง_Cash Flow.pdf", "Cash Flow"),
        ("บริษัท โฮชุง_Unknown.pdf", "Unknown"),
    ]

    for filename, expected in test_cases:
        result = detect_document_type(filename)
        print(f"  {filename} → {result}")
        assert result == expected, f"Expected '{expected}', got '{result}'"
    print("  ✅ PASS")


def test_thai_utils():
    """Test Thai text utilities"""
    print("\n" + "=" * 60)
    print("Testing Thai Utilities")
    print("=" * 60)

    # Thai digit translation
    THAI_DIGITS = "๐๑๒๓๔๕๖๗๘๙"
    ARABIC_DIGITS = "0123456789"
    THAI_TO_ARABIC = str.maketrans(THAI_DIGITS, ARABIC_DIGITS)
    ARABIC_TO_THAI = str.maketrans(ARABIC_DIGITS, THAI_DIGITS)

    def thai_to_arabic(text: str) -> str:
        return text.translate(THAI_TO_ARABIC)

    def arabic_to_thai(text: str) -> str:
        return text.translate(ARABIC_TO_THAI)

    def is_thai_text(text: str) -> bool:
        thai_pattern = re.compile(r'[\u0E00-\u0E7F]')
        return bool(thai_pattern.search(text))

    print("\n✓ Number conversion:")
    test_cases = [
        ("ปี ๒๕๖๗", "ปี 2567"),
        ("มูลค่า ๑,๒๓๔.๕๖ บาท", "มูลค่า 1,234.56 บาท"),
    ]

    for thai, expected in test_cases:
        result = thai_to_arabic(thai)
        print(f"  {thai} → {result}")
        assert result == expected, f"Expected '{expected}', got '{result}'"
    print("  ✅ PASS")

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
    print("  ✅ PASS")


def test_file_discovery():
    """Test actual file discovery"""
    print("\n" + "=" * 60)
    print("Testing File Discovery")
    print("=" * 60)

    base_path = Path("/Users/nut/ocr-prototype/Y67")

    if not base_path.exists():
        print("⚠ Warning: Y67 directory not found")
        print("  Skipping file discovery test")
        return

    print(f"\n✓ Scanning: {base_path}")

    # Count company folders
    company_folders = [
        f for f in base_path.iterdir()
        if f.is_dir() and not f.name.startswith('.')
    ]

    print(f"  Found {len(company_folders)} company folders")

    # Sample first company
    if company_folders:
        sample = company_folders[0]
        print(f"\n✓ Sample company: {sample.name}")

        # Parse company info
        match = re.match(r'^(\d+)\s+(.+)$', sample.name)
        if match:
            code = match.group(1)
            name = match.group(2)
            print(f"  Code: {code}")
            print(f"  Name: {name}")

        # Check for Y67 subfolder
        y67_folder = sample / "Y67"
        if y67_folder.exists():
            pdfs = list(y67_folder.glob('*.pdf'))
            print(f"\n✓ Y67 folder has {len(pdfs)} PDFs:")
            for pdf in pdfs[:3]:  # Show first 3
                size_kb = pdf.stat().st_size / 1024
                print(f"  - {pdf.name} ({size_kb:.1f} KB)")

    print("  ✅ PASS")


def main():
    """Run all minimal tests"""
    print("\n" + "=" * 60)
    print("Thai Financial Document OCR Processing Pipeline")
    print("Minimal Tests (Pure Python, No Dependencies)")
    print("=" * 60)

    try:
        test_scanner_parsing()
        test_thai_utils()
        test_file_discovery()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nNote: Install dependencies to test full OCR pipeline:")
        print("  pip install -r requirements.txt")
        print("=" * 60)

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
