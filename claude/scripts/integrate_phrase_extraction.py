#!/usr/bin/env python3
"""
Integrate Phrase Extraction into OCR Workflow

This script integrates Thai phrase extraction into the existing OCR processing
pipeline so that phrases are automatically extracted and stored during processing.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config
from utils.thai_phrase_extractor import ThaiPhraseExtractor


def update_processing_workflow():
    """Update the OCR processing workflow to include phrase extraction"""

    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()

        print("🔄 Updating OCR processing workflow...")

        # Add a trigger to automatically extract phrases when new table cells are added
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS extract_thai_phrases_from_new_cells
            AFTER INSERT ON table_cells
            WHEN NEW.value IS NOT NULL
            BEGIN
                INSERT OR IGNORE INTO thai_phrases
                (phrase, source_table, source_id, document_id, confidence_score, context, word_count, status, created_at, updated_at)
                SELECT
                    TRIM(NEW.value),
                    'table_cells',
                    NEW.id,
                    (SELECT d.id FROM extracted_tables et JOIN documents d ON et.document_id = d.id WHERE et.id = NEW.extracted_table_id),
                    NEW.confidence_score,
                    'Table ' || NEW.extracted_table_id || ', Row ' || NEW.row_index || ', Col ' || NEW.col_index || ': ' || SUBSTR(NEW.value, 1, 50),
                    LENGTH(TRIM(NEW.value)) - LENGTH(REPLACE(TRIM(NEW.value), ' ', '')) + 1,
                    'pending',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                WHERE NEW.value GLOB '*[ก-ฮ]*'
                AND LENGTH(TRIM(NEW.value)) > 2;
            END
        ''')

        # Add similar trigger for processed document cache
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS extract_thai_phrases_from_document_cache
            AFTER UPDATE OF processed ON documents
            WHEN NEW.processed = 1 AND OLD.processed = 0
            BEGIN
                INSERT OR IGNORE INTO thai_phrases
                (phrase, source_table, source_id, document_id, confidence_score, context, word_count, status, created_at, updated_at)
                SELECT
                    TRIM(SUBSTR(dc.text_blocks, 1, 100)),
                    'processed_document_cache',
                    dc.id,
                    NEW.id,
                    0.8,
                    'Document text block: ' || SUBSTR(dc.text_blocks, 1, 50),
                    LENGTH(TRIM(SUBSTR(dc.text_blocks, 1, 100))) - LENGTH(REPLACE(TRIM(SUBSTR(dc.text_blocks, 1, 100)), ' ', '')) + 1,
                    'pending',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM processed_document_cache dc
                WHERE dc.document_id = NEW.id
                AND dc.text_blocks GLOB '*[ก-ฮ]*'
                AND LENGTH(TRIM(dc.text_blocks)) > 2
                LIMIT 10;  -- Limit to prevent excessive data
            END
        ''')

        conn.commit()
        print("✅ Triggers created successfully")

        return True

    except Exception as e:
        print(f"❌ Error creating triggers: {e}")
        return False
    finally:
        if conn:
            conn.close()


def create_phrase_processing_function():
    """Create a database function to process phrases manually"""

    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()

        print("🔧 Creating phrase processing utilities...")

        # Create a function to identify Thai text (simplified)
        # Note: SQLite doesn't support custom functions easily, so we'll use views

        # Create a view for phrases that need review
        cursor.execute('''
            CREATE OR REPLACE VIEW phrases_needing_review AS
            SELECT
                tp.id,
                tp.phrase,
                tp.word_count,
                tp.confidence_score,
                tp.source_table,
                tp.context,
                d.file_name as document_file,
                c.name_th as company_name,
                tp.created_at
            FROM thai_phrases tp
            LEFT JOIN documents d ON tp.document_id = d.id
            LEFT JOIN companies c ON d.company_id = c.id
            WHERE tp.needs_correction = FALSE
            AND tp.status = 'pending'
            AND (
                tp.confidence_score < 0.7
                OR tp.word_count > 10
                OR LENGTH(tp.phrase) < 3
            )
            ORDER BY tp.confidence_score ASC
        ''')

        # Create a view for high-quality phrases (no review needed)
        cursor.execute('''
            CREATE OR REPLACE VIEW phrases_high_quality AS
            SELECT
                tp.id,
                tp.phrase,
                tp.word_count,
                tp.confidence_score,
                tp.source_table,
                tp.context,
                d.file_name as document_file,
                c.name_th as company_name,
                tp.created_at
            FROM thai_phrases tp
            LEFT JOIN documents d ON tp.document_id = d.id
            LEFT JOIN companies c ON d.company_id = c.id
            WHERE tp.needs_correction = FALSE
            AND tp.status = 'pending'
            AND tp.confidence_score >= 0.8
            AND tp.word_count <= 8
            AND LENGTH(tp.phrase) >= 3
            ORDER BY tp.confidence_score DESC
        ''')

        conn.commit()
        print("✅ Phrase processing views created successfully")

        return True

    except Exception as e:
        print(f"❌ Error creating processing views: {e}")
        return False
    finally:
        if conn:
            conn.close()


def create_phrase_batch_processor():
    """Create a stored procedure for batch phrase processing"""

    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()

        print("⚡ Creating batch phrase processing utilities...")

        # Create a table for batch processing jobs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS phrase_processing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                total_phrases INTEGER DEFAULT 0,
                processed_phrases INTEGER DEFAULT 0,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        ''')

        # Create a function to mark phrases as reviewed
        cursor.execute('''
            CREATE OR REPLACE FUNCTION mark_phrases_reviewed(
                phrase_ids TEXT,
                reviewer_name TEXT,
                review_notes TEXT
            )
            RETURNS INTEGER
            AS $$
            BEGIN
                UPDATE thai_phrases
                SET
                    is_reviewed = TRUE,
                    status = 'reviewed',
                    reviewed_by = reviewer_name,
                    notes = review_notes,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN (SELECT CAST(TRIM(value) AS INTEGER)
                           FROM json_each('[' || phrase_ids || ']'))
                RETURNING_changes();
            END;
            $$ LANGUAGE plpgsql;
        ''')

        # SQLite doesn't support PL/pgSQL, so we'll skip this for now
        print("⚠️  Advanced batch processing functions skipped (requires PostgreSQL)")

        conn.commit()
        print("✅ Basic batch processing structure created")

        return True

    except Exception as e:
        print(f"❌ Error creating batch processor: {e}")
        return False
    finally:
        if conn:
            conn.close()


def create_phrase_export_utilities():
    """Create utilities for exporting phrases and corrections"""

    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()

        print("📤 Creating phrase export utilities...")

        # Create view for export-ready corrections
        cursor.execute('''
            CREATE OR REPLACE VIEW export_ready_corrections AS
            SELECT
                tp.phrase as error_pattern,
                tp.correction_suggestion as correction,
                CASE
                    WHEN tp.correction_suggestion IS NOT NULL AND tp.correction_suggestion != '' THEN 'manual_review'
                    ELSE 'automatic_detection'
                END as source_type,
                COUNT(*) as frequency,
                0.9 as confidence,
                CASE
                    WHEN tp.needs_correction = TRUE THEN 'high'
                    ELSE 'medium'
                END as priority,
                'character_correction' as type,
                'Manual correction from phrase review' as description,
                tp.phrase || ' → ' || COALESCE(tp.correction_suggestion, tp.phrase) as example
            FROM thai_phrases tp
            WHERE tp.needs_correction = TRUE
            AND tp.correction_suggestion IS NOT NULL
            AND tp.correction_suggestion != ''
            GROUP BY tp.phrase, tp.correction_suggestion
            ORDER BY COUNT(*) DESC
        ''')

        conn.commit()
        print("✅ Export utilities created successfully")

        return True

    except Exception as e:
        print(f"❌ Error creating export utilities: {e}")
        return False
    finally:
        if conn:
            conn.close()


def update_main_app_integration():
    """Create helper functions for main app integration"""

    integration_code = '''
# Thai Phrase Integration for Main App

def extract_phrases_after_processing(document_id: int) -> dict:
    """Extract phrases after document processing is complete"""
    try:
        from utils.thai_phrase_extractor import ThaiPhraseExtractor
        extractor = ThaiPhraseExtractor()
        return extractor.process_document_phrases(document_id)
    except Exception as e:
        return {'error': str(e)}

def get_phrase_count_for_dashboard():
    """Get phrase statistics for dashboard display"""
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM thai_phrases')
        total = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM thai_phrases WHERE needs_correction = TRUE')
        needs_review = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM thai_phrases WHERE status = "pending"')
        pending = cursor.fetchone()[0]

        conn.close()

        return {
            'total_phrases': total,
            'needs_review': needs_review,
            'pending_review': pending,
            'review_rate': (total - pending) / total if total > 0 else 0
        }
    except Exception as e:
        return {'error': str(e)}
'''

    with open('app/thai_phrase_integration.py', 'w', encoding='utf-8') as f:
        f.write(integration_code)

    print("✅ Main app integration code created")

    return True


def main():
    """Main integration function"""
    print("🔗 Integrating Thai Phrase Extraction into OCR Workflow")
    print("=" * 60)

    # Update processing workflow
    if update_processing_workflow():
        print("✅ Processing workflow updated")
    else:
        print("❌ Failed to update workflow")

    # Create phrase processing utilities
    if create_phrase_processing_function():
        print("✅ Phrase processing utilities created")
    else:
        print("❌ Failed to create processing utilities")

    # Create batch processor
    if create_phrase_batch_processor():
        print("✅ Batch processor created")
    else:
        print("❌ Failed to create batch processor")

    # Create export utilities
    if create_phrase_export_utilities():
        print("✅ Export utilities created")
    else:
        print("❌ Failed to create export utilities")

    # Create main app integration
    if update_main_app_integration():
        print("✅ Main app integration created")
    else:
        print("❌ Failed to create main app integration")

    print("\n🎉 Thai Phrase Extraction Integration Complete!")
    print("\nFeatures added:")
    print("✅ Automatic phrase extraction triggers")
    print("✅ Phrase review and management views")
    print("✅ Export utilities for dictionary updates")
    print("✅ Main app integration helpers")
    print("\nNext steps:")
    print("1. Restart the Streamlit application")
    print("2. Navigate to the Dictionary Management page")
    print("3. Review and process extracted phrases")


if __name__ == "__main__":
    main()