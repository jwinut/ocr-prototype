#!/usr/bin/env python3
"""
Fix Missing Document IDs in Thai Phrases

This script fixes the missing document_id values in thai_phrases table
by properly joining through the extracted_tables relationship.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config


def fix_missing_document_ids():
    """Fix missing document_id values in thai_phrases table"""

    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    try:
        print("🔧 Fixing missing document_id values in thai_phrases...")

        # First, let's see the current state
        cursor.execute('''
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN document_id IS NULL THEN 1 END) as missing_doc_id,
                COUNT(CASE WHEN document_id IS NOT NULL THEN 1 END) as has_doc_id
            FROM thai_phrases
        ''')

        before_stats = cursor.fetchone()
        print(f"Before fix:")
        print(f"   Total phrases: {before_stats[0]:,}")
        print(f"   Missing document_id: {before_stats[1]:,}")
        print(f"   Has document_id: {before_stats[2]:,}")

        # Update phrases from table_cells where document_id is missing
        # Join through extracted_tables -> documents
        cursor.execute('''
            UPDATE thai_phrases tp
            SET document_id = (
                SELECT d.id
                FROM extracted_tables et
                JOIN documents d ON et.document_id = d.id
                WHERE et.id = tp.source_id
                AND tp.source_table = 'table_cells'
                AND tp.document_id IS NULL
                LIMIT 1
            )
            WHERE tp.source_table = 'table_cells'
            AND tp.document_id IS NULL
        ''')

        updated_rows = cursor.rowcount
        conn.commit()

        print(f"Updated {updated_rows:,} phrase records with missing document_id")

        # Check the result
        cursor.execute('''
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN document_id IS NULL THEN 1 END) as missing_doc_id,
                COUNT(CASE WHEN document_id IS NOT NULL THEN 1 END) as has_doc_id
            FROM thai_phrases
        ''')

        after_stats = cursor.fetchone()
        print(f"After fix:")
        print(f"   Total phrases: {after_stats[0]:,}")
        print(f"   Missing document_id: {after_stats[1]:,}")
        print(f"   Has document_id: {after_stats[2]:,}")

        # Verify a few sample records
        print()
        print("Sample records after fix:")
        cursor.execute('''
            SELECT tp.id, tp.phrase, tp.document_id, d.file_name
            FROM thai_phrases tp
            LEFT JOIN documents d ON tp.document_id = d.id
            WHERE tp.document_id IS NOT NULL
            LIMIT 5
        ''')

        samples = cursor.fetchall()
        for sample in samples:
            print(f"   ID {sample[0]}: {sample[1][:40]}... | Doc: {sample[2]} | File: {sample[3]}")

        return True

    except Exception as e:
        print(f"❌ Error fixing document IDs: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def update_phrase_context():
    """Update phrase context with better information"""

    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    try:
        print()
        print("📝 Updating phrase context information...")

        # Update context for table_cells source to include document info
        cursor.execute('''
            UPDATE thai_phrases tp
            SET context = (
                'Table ' || et.id || ', Row ' || tc.row_index || ', Col ' || tc.col_index ||
                ': ' || SUBSTR(tc.value, 1, 50) || ' | Doc: ' || COALESCE(d.file_name, 'Unknown')
            )
            FROM table_cells tc
            JOIN extracted_tables et ON tc.extracted_table_id = et.id
            LEFT JOIN documents d ON et.document_id = d.id
            WHERE tp.source_id = tc.id
            AND tp.source_table = 'table_cells'
        ''')

        context_updated = cursor.rowcount
        conn.commit()

        print(f"Updated context for {context_updated:,} phrase records")

        return True

    except Exception as e:
        print(f"❌ Error updating phrase context: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def verify_phrase_fixes():
    """Verify that the phrase fixes are working correctly"""

    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    try:
        print()
        print("✅ Verifying phrase fixes...")

        # Test the Dictionary Management page query
        test_query = '''
            SELECT tp.id, tp.phrase, tp.word_count, tp.confidence_score,
                   tp.status, tp.needs_correction, tp.correction_suggestion,
                   tp.created_at, tp.context, d.file_name, c.name_th as company_name
            FROM thai_phrases tp
            LEFT JOIN documents d ON tp.document_id = d.id
            LEFT JOIN fiscal_years fy ON d.fiscal_year_id = fy.id
            LEFT JOIN companies c ON fy.company_id = c.id
            WHERE 1=1
            ORDER BY tp.created_at DESC
            LIMIT 10
        '''

        cursor.execute(test_query)
        results = cursor.fetchall()

        print(f"Dictionary Management query test: ✅ SUCCESS")
        print(f"Returned {len(results)} sample records")

        print()
        print("Sample data with company info:")
        companies_found = 0
        for row in results:
            company_name = row[10] or 'None'
            if company_name != 'None':
                companies_found += 1

            print(f"   Phrase {row[0]}: {row[1][:35]}... | Company: {company_name}")

        print(f"\\nPhrases with company info: {companies_found} out of {len(results)}")

        return True

    except Exception as e:
        print(f"❌ Error verifying fixes: {e}")
        return False
    finally:
        conn.close()


def main():
    """Main execution function"""
    print("🔧 Fixing Thai Phrase Document IDs")
    print("=" * 50)

    success = True

    # Fix missing document IDs
    if not fix_missing_document_ids():
        success = False

    # Update phrase context
    if not update_phrase_context():
        success = False

    # Verify fixes
    if not verify_phrase_fixes():
        success = False

    if success:
        print("\\n🎉 Phrase fixes completed successfully!")
        print("\\nThe Dictionary Management page should now work correctly.")
        print("\\nNext steps:")
        print("1. Restart the Streamlit application")
        print("2. Navigate to the Dictionary Management page")
        print("3. Verify phrases load correctly with company information")
    else:
        print("\\n❌ Some fixes failed. Please check the error messages above.")


if __name__ == "__main__":
    main()