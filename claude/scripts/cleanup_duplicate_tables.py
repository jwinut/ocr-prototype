#!/usr/bin/env python3
"""
Remove duplicate extracted_tables entries per document/table_index.

Keeps the most recent row (highest ID) for each (document_id, table_index)
and deletes older duplicates. Intended to be safe to run repeatedly.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "prototype.db"


def find_duplicates(conn):
    """Return list of (document_id, table_index, ids_to_delete)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT document_id, table_index, GROUP_CONCAT(id) AS ids, COUNT(*) AS cnt
        FROM extracted_tables
        GROUP BY document_id, table_index
        HAVING cnt > 1
        """
    )
    duplicates = []
    for doc_id, table_idx, ids_csv, cnt in cur.fetchall():
        ids = [int(x) for x in ids_csv.split(",") if x]
        # keep the newest row (highest id), delete the rest
        ids_to_delete = sorted(ids)[:-1]
        if ids_to_delete:
            duplicates.append((doc_id, table_idx, ids_to_delete))
    return duplicates


def cleanup(conn, duplicates):
    cur = conn.cursor()
    total_deleted = 0
    for doc_id, table_idx, ids in duplicates:
        placeholders = ",".join("?" for _ in ids)
        cur.execute(
            f"DELETE FROM extracted_tables WHERE id IN ({placeholders})",
            ids,
        )
        total_deleted += cur.rowcount
        print(
            f"Document {doc_id}, table_index {table_idx}: deleted {cur.rowcount} duplicate row(s)"
        )
    conn.commit()
    return total_deleted


def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        duplicates = find_duplicates(conn)
        if not duplicates:
            print("No duplicate tables found.")
            return

        print(f"Found duplicates for {len(duplicates)} document/table_index pairs.")
        total_deleted = cleanup(conn, duplicates)
        print(f"Cleanup complete. Deleted {total_deleted} rows.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
