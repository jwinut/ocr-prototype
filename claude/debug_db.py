import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.database import DatabaseManager
from models.schema import Document, ExtractedTable

def check_latest_document():
    db = DatabaseManager()
    
    with db.get_session() as session:
        # Get latest document
        doc = session.query(Document).order_by(Document.created_at.desc()).first()
        
        if not doc:
            print("No documents found in database.")
            return

        print(f"=== Latest Document ===")
        print(f"ID: {doc.id}")
        print(f"File: {doc.file_name}")
        print(f"Path: {doc.file_path}")
        print(f"Engine: {doc.engine}")
        print(f"Status: {doc.status}")
        
        print(f"\n--- Content Stats ---")
        text_len = len(doc.text_content) if doc.text_content else 0
        md_len = len(doc.markdown_content) if doc.markdown_content else 0
        print(f"Text Content Length: {text_len}")
        print(f"Markdown Content Length: {md_len}")
        
        if text_len > 0:
            print(f"Text Preview: {doc.text_content[:100]}...")
        else:
            print("Text Content is EMPTY or NULL")
            
        if md_len > 0:
            print(f"Markdown Preview: {doc.markdown_content[:100]}...")
        else:
            print("Markdown Content is EMPTY or NULL")

        print(f"\n--- Tables ---")
        tables = session.query(ExtractedTable).filter(ExtractedTable.document_id == doc.id).all()
        print(f"Tables Found: {len(tables)}")
        
        for table in tables:
            print(f"  Table {table.table_index}:")
            md_len = len(table.markdown_content) if table.markdown_content else 0
            print(f"    Markdown Length: {md_len}")

if __name__ == "__main__":
    check_latest_document()
