#!/usr/bin/env python3
"""
Simple fix for missing document IDs in Thai phrases
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config

def fix_document_ids():
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    try:
        print('🔧 Fixing missing document IDs...')

        # Get phrase-document mappings
        cursor.execute('''
            SELECT tp.id as phrase_id, d.id as doc_id
            FROM thai_phrases tp
            JOIN table_cells tc ON tp.source_id = tc.id
            JOIN extracted_tables et ON tc.extracted_table_id = et.id
            JOIN documents d ON et.document_id = d.id
            WHERE tp.source_table = 'table_cells'
            AND tp.document_id IS NULL
            LIMIT 1000
        ''')

        mappings = cursor.fetchall()
        print(f'Found {len(mappings)} phrase-document mappings')

        # Update each phrase
        for phrase_id, doc_id in mappings:
            cursor.execute('UPDATE thai_phrases SET document_id = ? WHERE id = ?', (doc_id, phrase_id))

        conn.commit()
        print(f'Updated {len(mappings)} phrase records')

        # Verify results
        cursor.execute('''
            SELECT COUNT(*), COUNT(CASE WHEN document_id IS NULL THEN 1 END), COUNT(CASE WHEN document_id IS NOT NULL THEN 1 END)
            FROM thai_phrases
        ''')

        total, missing, has_doc = cursor.fetchone()
        print(f'Status: Total={total}, Missing={missing}, Has Doc={has_doc}')

        return True

    except Exception as e:
        print(f'Error: {e}')
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    fix_document_ids()