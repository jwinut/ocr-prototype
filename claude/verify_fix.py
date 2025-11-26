import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from app.database import DatabaseManager
from processing.ocr import DocumentProcessor
from models.schema import Document, ExtractedTable

def verify_fix():
    print("=== Starting Verification ===")
    
    # 1. Setup
    db = DatabaseManager()
    file_path = "/Users/nut/ocr-prototype/Y67/10000588 บริษัท สโตเรจซิสเต็ม อินดัสตรี จำกัด/Y67/บริษัท สโตเรจซิสเต็ม อินดัสตรี จำกัด_BS67.pdf"
    file_name = os.path.basename(file_path)
    
    # 2. Process Document (Simulate what parallel.py does)
    print(f"Processing {file_name}...")
    processor = DocumentProcessor()
    # Note: DocumentProcessor is the underlying class, it doesn't take engine.
    # We should test process_single_document from parallel.py instead to verify the wrapper.
    
    from processing.parallel import process_single_document
    
    # Define save callback
    def save_callback(**kwargs):
        print("Callback triggered! Saving to database...")
        return db.save_full_ocr_results(**kwargs)

    ocr_result = process_single_document(
        doc_id="test_doc",
        file_path=file_path,
        engine="docling",
        save_full_results_fn=save_callback
    )
    
    if ocr_result.status != "success":
        print("❌ OCR Processing Failed")
        return

    print(f"OCR Success. Text Len: {len(ocr_result.text_content)}, Markdown Len: {len(ocr_result.markdown_content)}")

    # 3. Save to Database (Handled by callback now)
    # print("Saving to database...")
    # try:
    #     doc_id = db.save_full_ocr_results(...)
    
    # We need the doc_id to verify. In the real app we don't get it back easily from the wrapper.
    # But we can query by file path.

    # 4. Verify Database Content
    print("Verifying database content...")
    with db.get_session() as session:
        # doc = session.query(Document).filter(Document.id == doc_id).first()
        doc = db.get_document_by_file_path(file_path, engine="docling")
        
        if not doc:
            print("❌ Document not found in DB")
            return
            
        print(f"DB Text Content Length: {len(doc.text_content) if doc.text_content else 0}")
        print(f"DB Markdown Content Length: {len(doc.markdown_content) if doc.markdown_content else 0}")
        
        if doc.text_content and len(doc.text_content) > 0:
            print("✅ Text Content Persisted")
        else:
            print("❌ Text Content Missing in DB")
            
        if doc.markdown_content and len(doc.markdown_content) > 0:
            print("✅ Markdown Content Persisted")
        else:
            print("❌ Markdown Content Missing in DB")

        # Verify Tables (should NOT have markdown)
        tables = session.query(ExtractedTable).filter(ExtractedTable.document_id == doc.id).all()
        print(f"Tables Found: {len(tables)}")
        for table in tables:
            md_len = len(table.markdown_content) if table.markdown_content else 0
            print(f"  Table {table.table_index} Markdown Length: {md_len}")
            if md_len > 1000: # Arbitrary large number, full doc md is ~4000
                print("  ❌ WARNING: Table markdown seems too large (might still be full doc markdown)")
            elif md_len == 0:
                 print("  ✅ Table markdown is empty (as expected for now)")

if __name__ == "__main__":
    verify_fix()
