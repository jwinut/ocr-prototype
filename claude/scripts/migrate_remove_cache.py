#!/usr/bin/env python3
"""
Database migration to remove ProcessedDocumentCache and consolidate into documents table.

This migration:
1. Adds markdown_content, text_content, tables_found, text_blocks columns to documents table
2. Migrates data from processed_document_cache to documents table
3. Drops the processed_document_cache table
"""

import sqlite3
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import config


def migrate():
    """Run the migration."""
    db_path = config.DATABASE_PATH

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("Run init_database.py first to create the database.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check current schema
        cursor.execute("PRAGMA table_info(documents)")
        columns = {col[1] for col in cursor.fetchall()}
        print(f"Current documents columns: {columns}")

        # Step 1: Add new columns to documents table if they don't exist
        new_columns = [
            ("markdown_content", "TEXT"),
            ("text_content", "TEXT"),
            ("tables_found", "INTEGER DEFAULT 0"),
            ("text_blocks", "INTEGER DEFAULT 0"),
        ]

        for col_name, col_type in new_columns:
            if col_name not in columns:
                print(f"Adding column '{col_name}' to documents table...")
                cursor.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")
                print(f"  Added '{col_name}'")
            else:
                print(f"Column '{col_name}' already exists in documents table")

        # Step 2: Check if processed_document_cache exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='processed_document_cache'
        """)
        cache_exists = cursor.fetchone() is not None

        if cache_exists:
            # Count cache entries
            cursor.execute("SELECT COUNT(*) FROM processed_document_cache")
            cache_count = cursor.fetchone()[0]
            print(f"\nFound {cache_count} entries in processed_document_cache")

            # Step 3: Migrate data from cache to documents
            if cache_count > 0:
                print("Migrating data from cache to documents table...")

                # Get all cache entries
                cursor.execute("""
                    SELECT file_path, engine, markdown_content, text_content,
                           tables_found, text_blocks, file_hash
                    FROM processed_document_cache
                    WHERE status = 'success'
                """)
                cache_entries = cursor.fetchall()

                migrated = 0
                for entry in cache_entries:
                    file_path, engine, markdown, text, tables, blocks, file_hash = entry

                    # Update corresponding document record
                    cursor.execute("""
                        UPDATE documents
                        SET markdown_content = ?,
                            text_content = ?,
                            tables_found = ?,
                            text_blocks = ?,
                            file_hash = COALESCE(file_hash, ?)
                        WHERE file_path = ? AND engine = ?
                    """, (markdown, text, tables, blocks, file_hash, file_path, engine))

                    if cursor.rowcount > 0:
                        migrated += 1

                print(f"  Migrated {migrated} entries to documents table")

            # Step 4: Drop the cache table
            print("\nDropping processed_document_cache table...")
            cursor.execute("DROP TABLE IF EXISTS processed_document_cache")
            print("  Dropped processed_document_cache table")
        else:
            print("\nprocessed_document_cache table does not exist (already migrated)")

        conn.commit()
        print("\nMigration completed successfully!")
        print("\nNew architecture:")
        print("  - documents table now stores markdown_content, text_content")
        print("  - No separate cache table needed")
        print("  - Engine-specific queries use (file_path, engine) unique constraint")
        return True

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
