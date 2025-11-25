# OCR Database Storage Implementation

## Overview
Enhanced the OCR prototype to save full OCR results to normalized database tables (`Document`, `ExtractedTable`, `TableCell`) instead of only storing metadata in the cache.

## Problem Statement
Previously, the system only saved:
- Document metadata (tables_found, text_blocks) in `ProcessedDocumentCache`
- A JSON blob of basic info
- **Did NOT save** extracted table data, text content, or markdown to the normalized schema

This meant OCR had to re-run every time a user viewed results.

## Solution Implementation

### 1. Enhanced Parallel Processor (`/Users/nut/ocr-prototype/claude/processing/parallel.py`)

#### Modified `process_single_document` function:
- Added `save_full_results_fn` parameter for saving to normalized tables
- Keeps `save_fn` for backward compatibility with cache storage
- Now passes the full `ocr_result` (ProcessedDocument) to the save function

```python
def process_single_document(
    doc_id: str,
    file_path: str,
    check_processed_fn: Optional[Callable[[str], Tuple[bool, str]]] = None,
    save_fn: Optional[Callable] = None,
    save_full_results_fn: Optional[Callable] = None  # NEW
) -> ProcessingResult:
```

#### Key changes:
1. Renamed `result` variable to `ocr_result` to avoid confusion
2. Added call to `save_full_results_fn` after successful processing:
```python
if save_full_results_fn and status == "success":
    try:
        save_full_results_fn(
            file_path=file_path,
            file_name=filename,
            ocr_result=ocr_result,  # Full OCR result with tables
            doc_id=doc_id
        )
        add_log_message(f"💾 Saved full results to database: {filename}", "info")
    except Exception as e:
        add_log_message(f"⚠️ Database save failed: {filename} - {e}", "warning")
```

#### Updated class methods:
- `process_documents()` - Added `save_full_results_fn` parameter
- `_process_sequential()` - Passes new save function to worker
- `_process_parallel()` - Passes new save function to workers

### 2. New Database Method (`/Users/nut/ocr-prototype/claude/app/database.py`)

Added `save_full_ocr_results()` method to `DatabaseManager` class:

```python
def save_full_ocr_results(
    self,
    file_path: str,
    file_name: str,
    ocr_result,  # ProcessedDocument from OCR
    doc_id: str
) -> Optional[int]:
```

#### Implementation details:

1. **Creates/gets default company and fiscal year**:
   - Company code: "UNCATEGORIZED"
   - Company name: "ไม่ระบุบริษัท" (TH) / "Uncategorized" (EN)
   - Fiscal year: Current year in BE (Buddhist Era)

2. **Creates or updates Document record**:
   - Checks if document exists by file_path
   - Updates existing or creates new with:
     - `fiscal_year_id` - Links to default fiscal year
     - `document_type` - "Unknown" (can be inferred from filename)
     - `file_path`, `file_name`, `file_size_bytes`
     - `status` - DocumentStatus.COMPLETED
     - `processed_at` - Current timestamp

3. **Stores extracted tables**:
   - Iterates through `ocr_result.tables` (list of pandas DataFrames)
   - Extracts headers from `df.columns`
   - Extracts data rows from `df.values`
   - Converts all cells to strings
   - Calls existing `store_extracted_table()` method which:
     - Creates `ExtractedTable` record with headers_json, row_count, col_count
     - Creates `TableCell` records for each cell with row/col indices
     - Stores markdown representation if available

4. **Error handling**:
   - Transaction rollback on failure
   - Raises descriptive exception

### 3. Updated Process Page (`/Users/nut/ocr-prototype/claude/app/pages/2_⚙️_Process.py`)

Modified `run_parallel_processing()` function:

```python
# Define save function for cache database (legacy)
def save_fn(**kwargs):
    if db:
        db.save_processed_document(**kwargs)

# Define save function for full OCR results to normalized tables
def save_full_results_fn(**kwargs):
    if db:
        db.save_full_ocr_results(**kwargs)

# Run processing
results = processor.process_documents(
    documents=documents,
    check_processed_fn=check_already_processed if db else None,
    save_fn=save_fn,
    save_full_results_fn=save_full_results_fn,  # NEW
    progress_callback=progress_cb
)
```

## Data Flow

```
1. User selects documents → Process page
2. run_parallel_processing() creates processor with both save functions
3. For each document:
   - process_single_document() runs OCR
   - Returns ProcessedDocument with:
     * tables: List[pd.DataFrame]
     * text_content: str
     * markdown: str
     * status, errors, etc.

4. If successful:
   a. save_fn() - Saves to ProcessedDocumentCache (legacy)
   b. save_full_results_fn() - NEW FLOW:
      - Calls db.save_full_ocr_results()
      - Creates/updates Document record
      - For each DataFrame in tables:
        * Extracts headers and data
        * Calls store_extracted_table()
        * Creates ExtractedTable + TableCell records
```

## Database Schema Usage

### Tables populated:
1. **Company** - Default "UNCATEGORIZED" company
2. **FiscalYear** - Current year for uncategorized documents
3. **Document** - Document metadata and status
4. **ExtractedTable** - Table metadata (headers, dimensions, markdown)
5. **TableCell** - Individual cell data with row/col positions

### Data structure:
```
Company (UNCATEGORIZED)
  └─ FiscalYear (current year BE)
       └─ Document (file_path, file_name, status)
            └─ ExtractedTable (table_index, headers_json, markdown)
                 └─ TableCell[] (row_index, col_index, value)
```

## Benefits

1. **No Re-processing**: Results stored in database, no need to re-run OCR
2. **Structured Access**: Tables and cells can be queried individually
3. **Backward Compatible**: Keeps existing cache system working
4. **Flexible Storage**: Can assign documents to proper companies/years later
5. **Complete Data**: Stores headers, data, markdown representations

## Future Enhancements

1. **Document Type Inference**: Parse filename to determine document type (BS, PL, etc.)
2. **Table Type Detection**: Classify tables (financial statements, balance sheet, etc.)
3. **Confidence Scores**: Extract and store OCR confidence metrics
4. **Page Numbers**: Store which page each table came from
5. **Company Assignment**: Allow users to assign documents to proper companies
6. **Text Content Storage**: Add field to Document model for full text_content
7. **Markdown Storage**: Add field for complete markdown representation

## Testing Recommendations

1. Process a sample document and verify:
   - Document record created in `documents` table
   - ExtractedTable records created for each table
   - TableCell records populated with actual data

2. Check logs for "💾 Saved full results to database" messages

3. Query database:
```python
db = DatabaseManager()
doc = db.get_document_by_id(1)
tables = db.get_tables_by_document(doc.id)
for table in tables:
    cells = db.get_table_cells(table.id)
```

4. Verify Results page can load data from database instead of re-running OCR

## Files Modified

1. `/Users/nut/ocr-prototype/claude/processing/parallel.py`
   - Modified: `process_single_document()`, `process_documents()`, `_process_sequential()`, `_process_parallel()`

2. `/Users/nut/ocr-prototype/claude/app/database.py`
   - Added: `save_full_ocr_results()` method

3. `/Users/nut/ocr-prototype/claude/app/pages/2_⚙️_Process.py`
   - Modified: `run_parallel_processing()` function

## Migration Path

Existing cached documents will continue to work. New processing will populate both:
- `ProcessedDocumentCache` (legacy, for session state)
- `Document` + `ExtractedTable` + `TableCell` (new normalized storage)

No migration needed for existing data.
