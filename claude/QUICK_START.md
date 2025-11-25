# Quick Start Guide - Data Layer

## Installation

```bash
cd /Users/nut/ocr-prototype/claude

# Install dependencies
pip install -r requirements.txt

# Initialize database
python scripts/init_database.py

# Verify structure
python scripts/verify_structure.py
```

## Basic Usage

### Import and Setup

```python
from app.database import DatabaseManager
from app.config import config
from models.schema import DocumentStatus, DataType

# Initialize
db = DatabaseManager()
db.init_db()
```

### Create Company and Document

```python
# Create company
company = db.get_or_create_company(
    company_code="10002819",
    name_th="บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด"
)

# Create fiscal year
fiscal_year = db.get_or_create_fiscal_year(
    company_id=company.id,
    year_be=2567  # 2024 CE
)

# Create document
document = db.create_document(
    fiscal_year_id=fiscal_year.id,
    document_type="BS",
    file_path="/path/to/file.pdf",
    file_name="balance_sheet.pdf"
)
```

### Store OCR Results

```python
# Update status
db.update_document_status(document.id, DocumentStatus.PROCESSING)

# Store table
table = db.store_extracted_table(
    document_id=document.id,
    table_index=0,
    headers=["รายการ", "จำนวนเงิน"],
    data=[
        ["สินทรัพย์รวม", "1,500,000"],
        ["หนี้สินรวม", "800,000"]
    ],
    confidence_score=0.95
)

# Mark complete
db.update_document_status(document.id, DocumentStatus.COMPLETED)
```

### Query and Export

```python
# Search documents
results = db.search_documents("โฮชุง")

# Get summary
summary = db.get_company_summary()

# Export to CSV
csv_path = db.export_to_csv(document.id)

# Export to JSON
json_data = db.export_to_json(document.id)
```

## File Locations

```
/Users/nut/ocr-prototype/claude/
├── app/config.py           # Configuration
├── app/database.py         # DatabaseManager
├── models/schema.py        # ORM models
├── utils/validators.py     # Validation functions
├── scripts/init_database.py # Database setup
└── data/
    ├── prototype.db        # SQLite database
    └── exports/            # Exported files
```

## Key Classes

- **DatabaseManager** (`app.database.py`)
  - `init_db()`, `get_or_create_company()`, `create_document()`
  - `store_extracted_table()`, `export_to_csv()`, `export_to_json()`

- **Models** (`models.schema.py`)
  - `Company`, `FiscalYear`, `Document`, `ExtractedTable`, `TableCell`

- **Config** (`app.config.py`)
  - `config.Y67_BASE_PATH`, `config.DATABASE_PATH`

- **Validators** (`utils.validators.py`)
  - `validate_company_code()`, `sanitize_thai_text()`, `detect_data_type()`

## Documentation

See `/Users/nut/ocr-prototype/claude/docs/DATA_LAYER_IMPLEMENTATION.md` for complete documentation.
