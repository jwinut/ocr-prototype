#!/usr/bin/env python3
"""
Database migration to add engine column to documents table.

This migration:
1. Adds 'engine' column to documents table with default 'docling'
2. Creates unique constraint on (file_path, engine)
3. Clears existing extracted tables data (will be re-processed)
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
        # Check if engine column already exists
        cursor.execute("PRAGMA table_info(documents)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'engine' in columns:
            print("Column 'engine' already exists in documents table.")
        else:
            print("Adding 'engine' column to documents table...")
            cursor.execute("""
                ALTER TABLE documents
                ADD COLUMN engine VARCHAR(20) NOT NULL DEFAULT 'docling'
            """)
            print("  Added 'engine' column with default 'docling'")

        # Create index on engine column if it doesn't exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='ix_documents_engine'
        """)
        if not cursor.fetchone():
            print("Creating index on engine column...")
            cursor.execute("CREATE INDEX ix_documents_engine ON documents(engine)")
            print("  Created index ix_documents_engine")

        # Note: SQLite doesn't support adding constraints to existing tables
        # The unique constraint will be enforced by the application layer
        # For new databases, the constraint is defined in the schema

        # Clear existing extracted data since it's not engine-specific
        print("\nClearing existing extracted tables and cells (will be re-processed)...")

        cursor.execute("SELECT COUNT(*) FROM table_cells")
        cell_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM extracted_tables")
        table_count = cursor.fetchone()[0]

        cursor.execute("DELETE FROM table_cells")
        cursor.execute("DELETE FROM extracted_tables")

        print(f"  Deleted {cell_count} cells and {table_count} tables")

        # Also clear processed_document_cache to force re-processing
        cursor.execute("SELECT COUNT(*) FROM processed_document_cache")
        cache_count = cursor.fetchone()[0]

        cursor.execute("DELETE FROM processed_document_cache")
        print(f"  Deleted {cache_count} cache entries")

        # Reset documents to pending status
        # Use UPPERCASE to match SQLAlchemy Enum member names
        cursor.execute("""
            UPDATE documents
            SET status = 'PENDING', processed_at = NULL
        """)
        print("  Reset all documents to 'pending' status")

        conn.commit()
        print("\nMigration completed successfully!")
        print("Please re-process documents to populate engine-specific data.")
        return True

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
