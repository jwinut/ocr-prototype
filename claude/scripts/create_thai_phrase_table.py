#!/usr/bin/env python3
"""
Create Thai Phrase Storage Table

This script creates a new table to store Thai phrases extracted from OCR results.
These phrases can be reviewed and incorrect ones can be added to the custom dictionary.
"""

import sqlite3
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config


def create_thai_phrase_table(db_path: str = None):
    """Create the thai_phrases table for storing OCR-extracted Thai phrases"""

    if db_path is None:
        db_path = config.DATABASE_PATH

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create thai_phrases table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS thai_phrases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phrase TEXT NOT NULL,
                source_table TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                document_id INTEGER,
                confidence_score REAL,
                context TEXT,
                word_count INTEGER,
                is_reviewed BOOLEAN DEFAULT FALSE,
                needs_correction BOOLEAN DEFAULT FALSE,
                correction_suggestion TEXT,
                status TEXT DEFAULT 'pending',  -- pending, reviewed, corrected
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_by TEXT,
                notes TEXT,
                FOREIGN KEY (document_id) REFERENCES documents (id)
            )
        ''')

        # Create indexes for performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_thai_phrases_phrase ON thai_phrases(phrase)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_thai_phrases_status ON thai_phrases(status)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_thai_phrases_document ON thai_phrases(document_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_thai_phrases_needs_correction ON thai_phrases(needs_correction)
        ''')

        # Create table for phrase correction history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS phrase_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phrase_id INTEGER NOT NULL,
                original_phrase TEXT NOT NULL,
                corrected_phrase TEXT NOT NULL,
                correction_type TEXT,  -- character_fix, spacing, tone_mark, etc.
                confidence REAL,
                added_by TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                notes TEXT,
                FOREIGN KEY (phrase_id) REFERENCES thai_phrases (id)
            )
        ''')

        conn.commit()
        print("✅ Thai phrases table created successfully")

        # Test the table structure
        cursor.execute('PRAGMA table_info(thai_phrases)')
        columns = cursor.fetchall()
        print(f"📊 thai_phrases table has {len(columns)} columns:")
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")

        return True

    except Exception as e:
        print(f"❌ Error creating Thai phrases table: {e}")
        return False
    finally:
        if conn:
            conn.close()


def populate_thai_phrases_from_existing_data():
    """Populate thai_phrases table with existing Thai text from OCR results"""

    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()

        # Check if we already have data
        cursor.execute('SELECT COUNT(*) FROM thai_phrases')
        existing_count = cursor.fetchone()[0]

        if existing_count > 0:
            print(f"📝 Thai phrases table already has {existing_count} entries")
            return

        print("🔄 Extracting Thai phrases from existing OCR data...")

        # Extract Thai phrases from table_cells
        cursor.execute('''
            SELECT value, extracted_table_id, confidence_score, row_index, col_index
            FROM table_cells
            WHERE value IS NOT NULL
            AND LENGTH(TRIM(value)) > 0
            ORDER BY extracted_table_id, row_index, col_index
        ''')

        cell_results = cursor.fetchall()
        phrases_added = 0

        for value, table_id, confidence, row, col in cell_results:
            # Check if text contains Thai characters
            if any(ord(char) >= 3584 for char in str(value)):
                # Get document ID for this table
                cursor.execute('''
                    SELECT document_id FROM extracted_tables
                    WHERE id = ?
                ''', (table_id,))
                doc_result = cursor.fetchone()
                document_id = doc_result[0] if doc_result else None

                # Split into potential phrases (basic splitting by spaces and punctuation)
                thai_phrases = []
                import re

                # Basic Thai phrase extraction
                candidate_phrases = re.split(r'[,\.;:()\[\]{}]+', str(value))

                for phrase in candidate_phrases:
                    phrase = phrase.strip()
                    if len(phrase) > 2 and any(ord(char) >= 3584 for char in phrase):
                        thai_phrases.append(phrase)

                # Insert unique phrases
                for phrase in thai_phrases:
                    word_count = len(phrase.split())

                    cursor.execute('''
                        INSERT OR IGNORE INTO thai_phrases
                        (phrase, source_table, source_id, document_id, confidence_score,
                         context, word_count, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                    ''', (
                        phrase,
                        'table_cells',
                        table_id,
                        document_id,
                        confidence,
                        f"Row {row}, Col {col}: {str(value)[:50]}...",
                        word_count
                    ))

                    if cursor.rowcount > 0:
                        phrases_added += 1

        conn.commit()
        print(f"✅ Added {phrases_added} Thai phrases to the database")

        # Show summary
        cursor.execute('SELECT COUNT(*) FROM thai_phrases')
        total_phrases = cursor.fetchone()[0]

        cursor.execute('''
            SELECT COUNT(*) FROM thai_phrases
            WHERE needs_correction = TRUE
        ''')
        needs_review = cursor.fetchone()[0]

        print(f"📊 Summary:")
        print(f"   Total Thai phrases: {total_phrases}")
        print(f"   Need review: {needs_review}")
        print(f"   Pending review: {total_phrases - needs_review}")

        return True

    except Exception as e:
        print(f"❌ Error populating Thai phrases: {e}")
        return False
    finally:
        if conn:
            conn.close()


def create_dictionary_management_view():
    """Create a view for dictionary management"""

    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()

        # Create view that joins phrases with corrections
        cursor.execute('''
            CREATE OR REPLACE VIEW dictionary_management AS
            SELECT
                tp.id as phrase_id,
                tp.phrase,
                tp.word_count,
                tp.confidence_score,
                tp.source_table,
                tp.status,
                tp.needs_correction,
                tp.correction_suggestion,
                tp.created_at,
                d.file_name as document_file,
                c.name_th as company_name,
                CASE
                    WHEN tc.id IS NOT NULL THEN 'corrected'
                    ELSE tp.status
                END as current_status
            FROM thai_phrases tp
            LEFT JOIN extracted_tables et ON tp.source_id = et.id
            LEFT JOIN documents d ON tp.document_id = d.id
            LEFT JOIN companies c ON d.company_id = c.id
            LEFT JOIN phrase_corrections tc ON tp.id = tc.phrase_id AND tc.is_active = 1
            ORDER BY tp.created_at DESC
        ''')

        conn.commit()
        print("✅ Dictionary management view created successfully")

        return True

    except Exception as e:
        print(f"❌ Error creating dictionary management view: {e}")
        return False
    finally:
        if conn:
            conn.close()


def main():
    """Main execution function"""
    print("🏗️ Creating Thai Phrase Storage System")
    print("=" * 50)

    # Create tables
    if create_thai_phrase_table():
        print("✅ Tables created successfully")
    else:
        print("❌ Failed to create tables")
        return

    # Create management view
    if create_dictionary_management_view():
        print("✅ Management view created successfully")

    # Populate with existing data
    if populate_thai_phrases_from_existing_data():
        print("✅ Data population completed")

    print("\n🎉 Thai Phrase Storage System is ready!")
    print("\nNext steps:")
    print("1. Use the Dictionary Management page to review phrases")
    print("2. Mark incorrect phrases and suggest corrections")
    print("3. Export corrections to thai_ocr_corrections table")


if __name__ == "__main__":
    main()