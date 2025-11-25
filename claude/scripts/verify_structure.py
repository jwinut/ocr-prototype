#!/usr/bin/env python3
"""
Verify the data layer file structure without running the code.
"""
import sys
from pathlib import Path

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_file(file_path: Path, description: str) -> bool:
    """Check if a file exists and report."""
    exists = file_path.exists()
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {file_path.relative_to(project_root)}")
    return exists


def check_content(file_path: Path, required_strings: list[str]) -> bool:
    """Check if file contains required content."""
    if not file_path.exists():
        return False

    content = file_path.read_text()
    all_found = all(s in content for s in required_strings)

    if all_found:
        print(f"  ✓ Contains required content: {', '.join(required_strings[:3])}...")
    else:
        missing = [s for s in required_strings if s not in content]
        print(f"  ✗ Missing: {', '.join(missing[:3])}...")

    return all_found


def main():
    """Verify file structure."""
    print("Thai Financial Document OCR - Data Layer Structure Verification")
    print("=" * 70)

    all_good = True

    # Configuration
    print("\n1. Configuration Files:")
    all_good &= check_file(
        project_root / "app/config.py",
        "Application configuration"
    )
    all_good &= check_content(
        project_root / "app/config.py",
        ["class Config", "Y67_BASE_PATH", "DATABASE_PATH", "VALID_DOCUMENT_TYPES"]
    )

    # Models
    print("\n2. Database Models:")
    all_good &= check_file(
        project_root / "models/__init__.py",
        "Models package init"
    )
    all_good &= check_file(
        project_root / "models/schema.py",
        "SQLAlchemy schema"
    )
    all_good &= check_content(
        project_root / "models/schema.py",
        ["class Company", "class FiscalYear", "class Document",
         "class ExtractedTable", "class TableCell"]
    )

    # Database Manager
    print("\n3. Database Manager:")
    all_good &= check_file(
        project_root / "app/database.py",
        "Database manager"
    )
    all_good &= check_content(
        project_root / "app/database.py",
        ["class DatabaseManager", "init_db", "get_or_create_company",
         "create_document", "export_to_csv", "export_to_json"]
    )

    # Validators
    print("\n4. Validation Utilities:")
    all_good &= check_file(
        project_root / "utils/__init__.py",
        "Utils package init"
    )
    all_good &= check_file(
        project_root / "utils/validators.py",
        "Validation functions"
    )
    all_good &= check_content(
        project_root / "utils/validators.py",
        ["validate_company_code", "validate_document_type",
         "validate_fiscal_year", "sanitize_thai_text", "detect_data_type"]
    )

    # Scripts
    print("\n5. Utility Scripts:")
    all_good &= check_file(
        project_root / "scripts/init_database.py",
        "Database initialization script"
    )

    # Summary
    print("\n" + "=" * 70)
    if all_good:
        print("✓ All data layer files created successfully!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Initialize database: python scripts/init_database.py")
        print("3. Integrate with processing and GUI layers")
    else:
        print("✗ Some files are missing or incomplete")
        return 1

    # Display file tree
    print("\nData Layer File Tree:")
    print("claude/")
    print("├── app/")
    print("│   ├── __init__.py (updated)")
    print("│   ├── config.py (new)")
    print("│   └── database.py (new)")
    print("├── models/")
    print("│   ├── __init__.py (new)")
    print("│   └── schema.py (new)")
    print("├── utils/")
    print("│   ├── __init__.py (new)")
    print("│   └── validators.py (new)")
    print("└── scripts/")
    print("    ├── init_database.py (new)")
    print("    └── verify_structure.py (this file)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
