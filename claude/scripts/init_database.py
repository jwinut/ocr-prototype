#!/usr/bin/env python3
"""
Database initialization script for Thai Financial Document OCR Prototype.

Run this script to create the database schema and verify the setup.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import DatabaseManager
from app.config import config
from models.schema import DocumentStatus


def main():
    """Initialize database and display summary."""
    print("Thai Financial Document OCR - Database Initialization")
    print("=" * 60)

    # Validate paths
    try:
        config.validate_paths()
        print(f"✓ Y67 directory found: {config.Y67_BASE_PATH}")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        return 1

    # Initialize database
    print(f"\nInitializing database: {config.DATABASE_PATH}")
    db = DatabaseManager()

    try:
        db.init_db()
        print("✓ Database tables created successfully")
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        return 1

    # Display summary
    print("\nDatabase Schema:")
    print("  - companies (id, company_code, name_th, name_en, created_at)")
    print("  - fiscal_years (id, company_id, year_be, year_ce, created_at)")
    print("  - documents (id, fiscal_year_id, document_type, file_path, ...)")
    print("  - extracted_tables (id, document_id, table_index, headers_json, ...)")
    print("  - table_cells (id, extracted_table_id, row_index, col_index, value, ...)")

    # Test basic operations
    print("\nTesting database operations...")

    try:
        # Create test company
        company = db.get_or_create_company(
            company_code="10002819",
            name_th="บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด",
            name_en="Hocheng Industrial (Thailand) Co., Ltd."
        )
        print(f"✓ Test company created: {company.company_code}")

        # Create test fiscal year
        fiscal_year = db.get_or_create_fiscal_year(
            company_id=company.id,
            year_be=2567
        )
        print(f"✓ Test fiscal year created: {fiscal_year.year_be} (CE: {fiscal_year.year_ce})")

        # Get summary
        summary = db.get_company_summary()
        print(f"\nCurrent Database Status:")
        print(f"  - Total companies: {summary['total_companies']}")
        print(f"  - Total documents: {summary['total_documents']}")
        print(f"  - Total tables: {summary['total_tables']}")
        print(f"\n  Document Status:")
        for status, count in summary['status_counts'].items():
            print(f"    - {status}: {count}")

    except Exception as e:
        print(f"✗ Error during testing: {e}")
        return 1

    print("\n" + "=" * 60)
    print("Database initialization completed successfully!")
    print(f"Database file: {config.DATABASE_PATH}")
    print(f"Exports directory: {config.EXPORTS_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
