# Database Layer Quick Start Guide

Quick reference for DEV-2 (BETA) and DEV-3 (GAMMA) developers.

---

## Setup (One-time)

```bash
# Install dependencies
pip install sqlalchemy>=2.0.0 alembic>=1.13.0

# Initialize database
python3 -c "from app.database import DatabaseManager; DatabaseManager().init_db()"
```

---

## Common Operations

### 1. Initialize Database Manager

```python
from app.database import DatabaseManager
from models.schema import DocumentStatus

db = DatabaseManager()
```

### 2. Register Company & Fiscal Year

```python
# Parse Y67 folder name: "10002819 บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด"
company_code = "10002819"
company_name = "บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด"

company = db.get_or_create_company(company_code, company_name)
fiscal_year = db.get_or_create_fiscal_year(company.id, 2567)  # Y67 = 2567 BE
```

### 3. Create Document Record

```python
from pathlib import Path

pdf_path = Path("/Users/nut/ocr-prototype/Y67/10002819 .../BS_Y67.pdf")

document = db.create_document(
    fiscal_year_id=fiscal_year.id,
    document_type="BS",  # BS, Compare PL, Cash Flow, etc.
    file_path=str(pdf_path),
    file_name=pdf_path.name,
    page_count=5,  # Optional
    file_size_bytes=pdf_path.stat().st_size  # Optional
)
```

### 4. Update Processing Status

```python
# Before processing
db.update_document_status(document.id, DocumentStatus.PROCESSING)

# After success
db.update_document_status(document.id, DocumentStatus.COMPLETED)

# After failure
db.update_document_status(
    document.id,
    DocumentStatus.FAILED,
    error_message="OCR engine timeout"
)
```

### 5. Store Extracted Tables

```python
# For each table extracted from PDF
headers = ["รายการ", "จำนวนเงิน (บาท)", "หมายเหตุ"]
data = [
    ["สินทรัพย์รวม", "1,234,567.89", ""],
    ["หนี้สินรวม", "234,567.89", ""],
    ["ส่วนของผู้ถือหุ้น", "1,000,000.00", ""]
]
markdown = "| รายการ | จำนวนเงิน (บาท) | หมายเหตุ |\n|---|---|---|\n..."

table = db.store_extracted_table(
    document_id=document.id,
    table_index=0,  # First table = 0, second = 1, etc.
    headers=headers,
    data=data,
    markdown=markdown,
    table_type="balance_sheet",  # Optional
    confidence_score=0.95  # Optional
)
```

### 6. Query Operations

```python
# Get pending documents for processing
pending = db.get_documents_by_status(DocumentStatus.PENDING, limit=10)

# Get all documents for a fiscal year
docs = db.get_documents_by_fiscal_year(fiscal_year.id)

# Search documents
results = db.search_documents("โฮชุง", document_type="BS")

# Get dashboard stats
summary = db.get_company_summary()
print(f"Total companies: {summary['total_companies']}")
print(f"Completed: {summary['status_counts']['completed']}")
```

### 7. Export Data

```python
# Export to CSV
csv_path = db.export_to_csv(document.id)
print(f"Exported to: {csv_path}")

# Export to JSON
json_data = db.export_to_json(document.id)
# Returns dict with document metadata + all tables
```

---

## Complete Workflow Example (DEV-2)

```python
from pathlib import Path
from app.database import DatabaseManager
from models.schema import DocumentStatus
from utils.validators import parse_company_folder_name

# Initialize
db = DatabaseManager()
db.init_db()

# Process Y67 directory
y67_path = Path("/Users/nut/ocr-prototype/Y67")

for company_folder in y67_path.iterdir():
    if not company_folder.is_dir():
        continue

    # Parse folder name
    code, name = parse_company_folder_name(company_folder.name)
    if not code:
        continue

    # Register company
    company = db.get_or_create_company(code, name)

    # Process each PDF
    for pdf_file in company_folder.glob("*.pdf"):
        # Extract year from filename (e.g., BS_Y67.pdf)
        year_be = 2567  # Extract from filename

        # Get/create fiscal year
        fiscal_year = db.get_or_create_fiscal_year(company.id, year_be)

        # Create document
        doc = db.create_document(
            fiscal_year_id=fiscal_year.id,
            document_type="BS",  # Detect from filename
            file_path=str(pdf_file),
            file_name=pdf_file.name
        )

        # Process with OCR
        try:
            db.update_document_status(doc.id, DocumentStatus.PROCESSING)

            # Your OCR code here
            extracted_tables = process_pdf_with_ocr(pdf_file)

            # Store results
            for idx, (headers, data, markdown) in enumerate(extracted_tables):
                db.store_extracted_table(
                    document_id=doc.id,
                    table_index=idx,
                    headers=headers,
                    data=data,
                    markdown=markdown
                )

            db.update_document_status(doc.id, DocumentStatus.COMPLETED)

        except Exception as e:
            db.update_document_status(
                doc.id,
                DocumentStatus.FAILED,
                error_message=str(e)
            )
```

---

## Complete Workflow Example (DEV-3)

```python
import streamlit as st
from app.database import DatabaseManager
from models.schema import DocumentStatus

# Initialize
db = DatabaseManager()

# Sidebar - Company selector
companies = db.get_all_companies()
selected_company = st.sidebar.selectbox(
    "Select Company",
    companies,
    format_func=lambda c: f"{c.company_code} - {c.name_th}"
)

# Main page - Dashboard
if selected_company:
    st.title(f"📊 {selected_company.name_th}")

    # Get fiscal years
    fiscal_years = db.get_fiscal_years_by_company(selected_company.id)

    for fy in fiscal_years:
        with st.expander(f"Year {fy.year_be - 2500} (CE: {fy.year_ce})"):
            docs = db.get_documents_by_fiscal_year(fy.id)

            for doc in docs:
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.write(f"📄 {doc.document_type} - {doc.file_name}")

                with col2:
                    status_icon = {
                        DocumentStatus.PENDING: "⏳",
                        DocumentStatus.PROCESSING: "🔄",
                        DocumentStatus.COMPLETED: "✅",
                        DocumentStatus.FAILED: "❌"
                    }
                    st.write(f"{status_icon[doc.status]} {doc.status.value}")

                with col3:
                    if doc.status == DocumentStatus.COMPLETED:
                        if st.button("Export", key=f"export_{doc.id}"):
                            csv_path = db.export_to_csv(doc.id)
                            st.success(f"Exported to {csv_path}")

                # Show extracted tables
                if doc.status == DocumentStatus.COMPLETED:
                    tables = db.get_tables_by_document(doc.id)
                    st.info(f"📊 {len(tables)} tables extracted")

# Search functionality
st.sidebar.header("🔍 Search")
query = st.sidebar.text_input("Search documents")
if query:
    results = db.search_documents(query)
    st.write(f"Found {len(results)} documents")
    for doc in results:
        st.write(f"- {doc.file_name}")
```

---

## Document Status Flow

```
PENDING → PROCESSING → COMPLETED
                    ↘
                     FAILED
```

Always update status at each stage!

---

## Valid Document Types

From `app.config.Config.VALID_DOCUMENT_TYPES`:
- `"BS"` - Balance Sheet
- `"Compare BS"` - Comparative Balance Sheet
- `"Compare PL"` - Comparative Profit & Loss
- `"Cash Flow"` - Cash Flow Statement
- `"Gen Info"` - General Information
- `"Ratio"` - Financial Ratios
- `"Related"` - Related Party Transactions
- `"Shareholders"` - Shareholders Information

---

## Helper Functions

### From `utils.validators`

```python
from utils.validators import (
    validate_company_code,
    parse_company_folder_name,
    extract_year_from_filename,
    detect_data_type,
    sanitize_thai_text
)

# Validate company code
is_valid = validate_company_code("10002819")  # True

# Parse Y67 folder name
code, name = parse_company_folder_name("10002819 บริษัท โฮชุง...")
# Returns: ("10002819", "บริษัท โฮชุง...")

# Extract year from filename
year_be = extract_year_from_filename("BS_Y67.pdf")
# Returns: 2567

# Detect data type
dtype = detect_data_type("1,234.56 บาท")
# Returns: DataType.CURRENCY

# Clean Thai text
clean = sanitize_thai_text("  บริษัท  \n  ทดสอบ  ")
# Returns: "บริษัท ทดสอบ"
```

---

## Error Handling

```python
try:
    db.update_document_status(doc_id, DocumentStatus.PROCESSING)
    # Your processing code
    db.update_document_status(doc_id, DocumentStatus.COMPLETED)

except FileNotFoundError as e:
    db.update_document_status(
        doc_id,
        DocumentStatus.FAILED,
        error_message=f"File not found: {e}"
    )

except TimeoutError as e:
    db.update_document_status(
        doc_id,
        DocumentStatus.FAILED,
        error_message=f"Processing timeout: {e}"
    )

except Exception as e:
    db.update_document_status(
        doc_id,
        DocumentStatus.FAILED,
        error_message=f"Unexpected error: {e}"
    )
```

---

## Database Paths

```python
from app.config import config

# Database file location
print(config.DATABASE_PATH)
# /Users/nut/ocr-prototype/claude/data/prototype.db

# Y67 source documents
print(config.Y67_BASE_PATH)
# /Users/nut/ocr-prototype/Y67

# Export directory
print(config.EXPORTS_PATH)
# /Users/nut/ocr-prototype/claude/data/exports
```

---

## Troubleshooting

### Database not found?
```python
from app.database import DatabaseManager
db = DatabaseManager()
db.init_db()  # Creates all tables
```

### Foreign key violation?
Make sure company and fiscal_year exist before creating documents:
```python
company = db.get_or_create_company(code, name)
fiscal_year = db.get_or_create_fiscal_year(company.id, year_be)
# Now safe to create documents
```

### Thai text not displaying?
Ensure UTF-8 encoding:
```python
import sys
print(sys.getdefaultencoding())  # Should be 'utf-8'
```

---

## Need Help?

See full documentation:
- `/Users/nut/ocr-prototype/claude/BACKEND_IMPLEMENTATION_SUMMARY.md`
- Schema: `/Users/nut/ocr-prototype/claude/models/schema.py`
- Database ops: `/Users/nut/ocr-prototype/claude/app/database.py`
- Config: `/Users/nut/ocr-prototype/claude/app/config.py`
