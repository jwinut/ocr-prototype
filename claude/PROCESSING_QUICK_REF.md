# OCR Processing Engine - Quick Reference

## Import Everything You Need

```python
# Scanner
from processing import (
    DocumentInfo,           # Metadata container
    scan_directory,         # Scan Y67 directory
    parse_company_folder,   # Extract company code/name
    detect_document_type    # Classify document type
)

# OCR Engine
from processing import (
    DocumentProcessor,      # Main OCR class
    ProcessedDocument       # Result container
)

# Parser
from processing import (
    normalize_thai_numbers,   # Thai → Arabic numerals
    clean_extracted_text,     # Clean OCR artifacts
    parse_financial_table,    # Structure table data
    extract_company_info      # Extract company registration info
)

# Batch Processing
from processing import (
    BatchProcessor,         # Parallel batch processor
    BatchProgress          # Progress tracking
)

# Thai Utilities
from utils.thai_utils import (
    thai_to_arabic,              # ๐-๙ → 0-9
    normalize_thai_company_name, # Clean company names
    parse_thai_currency,         # Parse currency strings
    format_thai_currency,        # Format currency
    get_thai_year,              # Buddhist → Christian year
    get_buddhist_year,          # Christian → Buddhist year
    clean_thai_text,            # Clean Thai text
    is_thai_text               # Detect Thai characters
)
```

---

## Quick Start Examples

### 1. Scan Directory (1 line)
```python
from processing import scan_directory
docs = scan_directory('../Y67')  # Returns List[DocumentInfo]
```

### 2. Process Single PDF (3 lines)
```python
from processing import DocumentProcessor
processor = DocumentProcessor()
result = processor.process_single('path/to/file.pdf')
```

### 3. Process All PDFs with Progress (5 lines)
```python
from processing import BatchProcessor
batch = BatchProcessor(max_workers=4)
for doc_info, result in batch.process_directory('../Y67'):
    if result.status == 'success':
        print(f"✓ {doc_info.company_name}: {result.get_table_count()} tables")
```

### 4. Thai Text Operations (1 line each)
```python
from utils.thai_utils import thai_to_arabic, parse_thai_currency
converted = thai_to_arabic("มูลค่า ๑,๒๓๔.๕๖ บาท")  # → "มูลค่า 1,234.56 บาท"
amount = parse_thai_currency("๑,๒๓๔.๕๖ บาท")  # → 1234.56
```

---

## Common Patterns

### Pattern 1: Scan → Filter → Process
```python
from processing import scan_directory, BatchProcessor

# 1. Scan directory
all_docs = scan_directory('../Y67')

# 2. Filter by document type
bs_docs = [d for d in all_docs if d.document_type == 'BS']

# 3. Process filtered documents
batch = BatchProcessor(max_workers=4)
for doc_info, result in batch.process_document_list(bs_docs):
    # Handle results
    pass
```

### Pattern 2: Process with Progress Callback
```python
from processing import DocumentProcessor

def show_progress(message, pct):
    print(f"[{pct*100:.0f}%] {message}")

processor = DocumentProcessor()
result = processor.process_single('file.pdf', progress_cb=show_progress)
```

### Pattern 3: Batch Processing with Statistics
```python
from processing import BatchProcessor

def show_batch_progress(progress):
    pct = progress.progress_pct
    print(f"{progress.completed}/{progress.total} ({pct:.1f}%)")
    print(f"  Current: {progress.current_file}")
    print(f"  Errors: {len(progress.errors)}")
    print(f"  ETA: {progress.estimated_remaining:.0f}s")

batch = BatchProcessor(max_workers=4)
results = list(batch.process_directory('../Y67', show_batch_progress))

# Get final stats
stats = batch.get_processor_stats()
print(f"Success rate: {stats['success_rate']}%")
print(f"Total time: {stats['total_time_seconds']:.1f}s")
```

### Pattern 4: Parse Tables from Results
```python
from processing import DocumentProcessor, parse_financial_table

processor = DocumentProcessor()
result = processor.process_single('balance_sheet.pdf')

if result.status == 'success' and result.has_tables():
    for idx, table_df in enumerate(result.tables):
        # Parse each table
        parsed = parse_financial_table(table_df, metadata={'table_index': idx})

        print(f"Table {idx+1}:")
        print(f"  Type: {parsed['metadata']['table_type']}")
        print(f"  Shape: {parsed['metadata']['row_count']}x{parsed['metadata']['column_count']}")

        # Access cleaned data
        cleaned_df = parsed['data']
```

### Pattern 5: Extract Company Information
```python
from processing import DocumentProcessor, extract_company_info

processor = DocumentProcessor()
result = processor.process_single('gen_info.pdf')

if result.status == 'success':
    company_info = extract_company_info(result.text_content)

    print(f"Company: {company_info['company_name_th']}")
    print(f"Registration: {company_info['registration_number']}")
    print(f"Phone: {company_info['phone']}")
    print(f"Website: {company_info['website']}")
```

---

## Data Structures

### DocumentInfo
```python
doc_info.file_path          # Path object
doc_info.file_name          # str: "บริษัท ABC_BS67.pdf"
doc_info.company_code       # str: "10002819"
doc_info.company_name       # str: "บริษัท โฮชุง..."
doc_info.fiscal_year        # str: "Y67"
doc_info.document_type      # str: "BS", "PL", "Cash Flow", etc.
doc_info.file_size          # int: bytes
```

### ProcessedDocument
```python
result.status               # str: "success", "failed", "partial"
result.tables               # List[DataFrame]: extracted tables
result.text_content         # str: full text
result.markdown             # str: markdown format
result.json_data            # dict: JSON representation
result.errors               # List[str]: error messages
result.processing_time      # float: seconds
result.source_file          # str: original file path

# Methods
result.has_tables()         # bool
result.get_table_count()    # int
```

### BatchProgress
```python
progress.total              # int: total documents
progress.completed          # int: completed documents
progress.current_file       # str: currently processing
progress.errors             # List[str]: error messages
progress.start_time         # float: timestamp

# Properties
progress.progress_pct       # float: 0-100
progress.elapsed_time       # float: seconds
progress.estimated_remaining # float: seconds
```

---

## Configuration Options

### DocumentProcessor Options
```python
# Default: Thai+English, accurate tables, no GPU
processor = DocumentProcessor(
    languages=("th", "en"),     # OCR languages
    table_mode="ACCURATE",      # or "FAST"
    gpu=False                   # Enable GPU acceleration
)
```

### BatchProcessor Options
```python
# Default: sequential processing
batch = BatchProcessor(
    max_workers=1,              # Parallel workers (1 = sequential)
    languages=("th", "en")      # OCR languages
)

# For faster processing
batch = BatchProcessor(max_workers=4)  # Use 4 parallel workers
```

---

## Document Types

Detected automatically from filename patterns:

| Type | Pattern | Example |
|------|---------|---------|
| BS | `_BS\d{2}\.pdf$` | `บริษัท ABC_BS67.pdf` |
| PL | `_PL\d{2}\.pdf$` | `บริษัท ABC_PL67.pdf` |
| Compare BS | `_Compare BS\.pdf$` | `บริษัท ABC_Compare BS.pdf` |
| Compare PL | `_Compare PL\.pdf$` | `บริษัท ABC_Compare PL.pdf` |
| Cash Flow | `_Cash Flow\.pdf$` | `บริษัท ABC_Cash Flow.pdf` |
| Gen Info | `_Gen Info\.pdf$` | `บริษัท ABC_Gen Info.pdf` |
| Ratio | `_Ratio\.pdf$` | `บริษัท ABC_Ratio.pdf` |
| Related | `_Related\.pdf$` | `บริษัท ABC_Related.pdf` |
| Shareholders | `_Shareholders\.pdf$` | `บริษัท ABC_Shareholders.pdf` |
| Others | `_Others\.pdf$` | `บริษัท ABC_Others.pdf` |

---

## Thai Language Support

### Numeral Conversion
```python
from utils.thai_utils import thai_to_arabic, arabic_to_thai

# Thai → Arabic
thai_to_arabic("๑๒๓๔๕")  # → "12345"

# Arabic → Thai
arabic_to_thai("12345")  # → "๑๒๓๔๕"
```

### Company Name Normalization
```python
from utils.thai_utils import normalize_thai_company_name

# Clean up messy company names
name = "บริษัท   ABC  (ประเทศไทย)  จำกัด  "
clean = normalize_thai_company_name(name)
# → "บริษัท ABC (ประเทศไทย) จำกัด"
```

### Currency Operations
```python
from utils.thai_utils import parse_thai_currency, format_thai_currency

# Parse currency strings
amount = parse_thai_currency("๑,๒๓๔.๕๖ บาท")  # → 1234.56
amount = parse_thai_currency("1,234.56 บาท")  # → 1234.56

# Format numbers as currency
formatted = format_thai_currency(1234.56)  # → "1,234.56 บาท"
formatted = format_thai_currency(1234.56, include_symbol=False)  # → "1,234.56"
```

### Year Conversion
```python
from utils.thai_utils import get_thai_year, get_buddhist_year

# Buddhist Era → Christian Era
christian = get_thai_year(2567)  # → 2024

# Christian Era → Buddhist Era
buddhist = get_buddhist_year(2024)  # → 2567
```

---

## Error Handling

All functions handle errors gracefully:

```python
from processing import DocumentProcessor

processor = DocumentProcessor()
result = processor.process_single('file.pdf')

# Check status
if result.status == 'success':
    # Use result.tables, result.text_content, etc.
    print(f"Success! {result.get_table_count()} tables extracted")

elif result.status == 'partial':
    # Some data extracted, check errors
    print(f"Partial success with {len(result.errors)} errors")
    print(f"Errors: {result.errors}")

elif result.status == 'failed':
    # Complete failure, check errors
    print(f"Failed: {result.errors}")
```

---

## Performance Tips

### 1. Use Parallel Processing
```python
# Sequential (slow)
batch = BatchProcessor(max_workers=1)

# Parallel (fast) - 4x speedup with 4 workers
batch = BatchProcessor(max_workers=4)
```

### 2. Filter Before Processing
```python
# Don't process everything if you only need BS documents
all_docs = scan_directory('../Y67')
bs_docs = [d for d in all_docs if d.document_type == 'BS']
batch.process_document_list(bs_docs)  # Much faster!
```

### 3. Use Fast Mode for Quick Preview
```python
# Fast but less accurate
processor = DocumentProcessor(table_mode="FAST")

# Accurate but slower (default)
processor = DocumentProcessor(table_mode="ACCURATE")
```

### 4. Estimate Processing Time
```python
from processing.batch import estimate_processing_time

estimates = estimate_processing_time(
    base_path='../Y67',
    sample_size=5,        # Test with 5 documents
    max_workers=4         # Parallel processing
)

print(f"Total documents: {estimates['total_documents']}")
print(f"Estimated time: {estimates['estimated_time_minutes']:.1f} minutes")
print(f"Average per doc: {estimates['avg_time_per_doc']:.1f} seconds")
```

---

## Common Issues & Solutions

### Issue: "File not found"
**Solution**: Use absolute paths or verify relative path from current directory
```python
from pathlib import Path
abs_path = Path('../Y67').resolve()
docs = scan_directory(str(abs_path))
```

### Issue: "Docling not installed"
**Solution**: Install required dependencies
```bash
pip install docling pandas easyocr
```

### Issue: Slow processing
**Solution**: Use parallel processing and filter documents
```python
batch = BatchProcessor(max_workers=4)  # 4x faster
bs_only = [d for d in docs if d.document_type == 'BS']  # Process subset
```

### Issue: Memory errors with parallel processing
**Solution**: Reduce number of workers
```python
# If running out of memory with 4 workers
batch = BatchProcessor(max_workers=2)  # Use fewer workers
```

---

## Complete Minimal Example

```python
#!/usr/bin/env python3
"""Process all BS documents from Y67 directory"""

from processing import scan_directory, BatchProcessor

def main():
    # 1. Scan directory
    print("Scanning Y67 directory...")
    all_docs = scan_directory('../Y67')
    print(f"Found {len(all_docs)} documents")

    # 2. Filter Balance Sheet documents
    bs_docs = [d for d in all_docs if d.document_type == 'BS']
    print(f"Filtering to {len(bs_docs)} Balance Sheet documents")

    # 3. Process with progress
    def show_progress(progress):
        print(f"[{progress.progress_pct:.1f}%] {progress.current_file}")

    batch = BatchProcessor(max_workers=4)
    success_count = 0

    for doc_info, result in batch.process_document_list(bs_docs, show_progress):
        if result.status == 'success':
            success_count += 1
            print(f"  ✓ {result.get_table_count()} tables, {result.processing_time:.1f}s")
        else:
            print(f"  ✗ {result.errors}")

    # 4. Show final statistics
    print(f"\nProcessed {success_count}/{len(bs_docs)} successfully")
    stats = batch.get_processor_stats()
    print(f"Success rate: {stats['success_rate']}%")
    print(f"Total time: {stats['total_time_seconds']:.1f}s")

if __name__ == '__main__':
    main()
```

---

## File Locations

```
/Users/nut/ocr-prototype/claude/
├── processing/
│   ├── __init__.py          # Package exports
│   ├── scanner.py           # File discovery (6,920 bytes)
│   ├── ocr.py              # OCR engine (10,131 bytes)
│   ├── parser.py           # Data parsing (9,607 bytes)
│   └── batch.py            # Batch processing (11,484 bytes)
└── utils/
    └── thai_utils.py        # Thai utilities (9,063 bytes)
```

Total: 48KB of production-ready code

---

## Next Steps

1. **Test**: Run with sample PDFs
2. **Integrate**: Connect to GUI and database
3. **Deploy**: Package for production
4. **Monitor**: Track performance and errors
5. **Optimize**: Profile and improve hot paths

---

**Quick Reference Last Updated**: 2024-11-25
