# OCR Processing Engine - Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     OCR PROCESSING ENGINE (DEV-2)                       │
│                    Thai Financial Document Pipeline                     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          INPUT LAYER                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  Y67 Directory Structure                                                │
│    └── {company_code} {company_name_th}/                               │
│        └── {fiscal_year}/                                               │
│            ├── {company}_BS67.pdf                                       │
│            ├── {company}_Compare BS.pdf                                 │
│            ├── {company}_Cash Flow.pdf                                  │
│            └── ...                                                      │
│                                                                         │
│  Input: 466 PDFs across 11 companies, 7 fiscal years                   │
└─────────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      SCANNER MODULE (scanner.py)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  Components:                                                            │
│    • parse_company_folder()  → Extract code & Thai name               │
│    • detect_document_type()  → Classify document type                 │
│    • scan_directory()        → Discover all PDFs                      │
│                                                                         │
│  Output: List[DocumentInfo]                                            │
│    ├── file_path: Path                                                 │
│    ├── company_code: str                                               │
│    ├── company_name: str (Thai)                                        │
│    ├── fiscal_year: str                                                │
│    ├── document_type: str                                              │
│    └── file_size: int                                                  │
│                                                                         │
│  Performance: ~0.1ms per file (metadata only)                          │
└─────────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                        OCR MODULE (ocr.py)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                  DocumentProcessor                                 │ │
│  ├───────────────────────────────────────────────────────────────────┤ │
│  │  Technologies:                                                     │ │
│  │    • Docling: Document conversion framework                       │ │
│  │    • EasyOCR: Thai+English text recognition                       │ │
│  │    • TableFormer: Financial table extraction (ACCURATE mode)     │ │
│  │                                                                    │ │
│  │  Pipeline:                                                         │ │
│  │    PDF → Text Extraction → Table Detection → Structure Analysis  │ │
│  │                                                                    │ │
│  │  Configuration:                                                    │ │
│  │    • languages: ("th", "en")                                      │ │
│  │    • table_mode: ACCURATE / FAST                                  │ │
│  │    • gpu: True / False                                            │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Methods:                                                               │
│    • process_single() → ProcessedDocument                             │
│    • process_batch()  → Generator[ProcessedDocument]                  │
│                                                                         │
│  Output: ProcessedDocument                                             │
│    ├── status: success/failed/partial                                  │
│    ├── tables: List[DataFrame]                                         │
│    ├── text_content: str                                               │
│    ├── markdown: str                                                   │
│    ├── json_data: dict                                                 │
│    ├── errors: List[str]                                               │
│    └── processing_time: float                                          │
│                                                                         │
│  Performance: 5-30s per document (depends on complexity)               │
└─────────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                       PARSER MODULE (parser.py)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Text Processing:                                                       │
│    • normalize_thai_numbers()   → Thai digits ๐-๙ to Arabic 0-9      │
│    • clean_extracted_text()     → Remove OCR artifacts                │
│    • extract_company_info()     → Parse registration info             │
│    • extract_financial_values() → Parse financial data                │
│                                                                         │
│  Table Processing:                                                      │
│    • parse_financial_table()    → Structure & classify tables         │
│    • detect_table_type()        → BS, PL, Cash Flow, Ratio            │
│    • normalize_column_names()   → Clean DataFrame columns             │
│                                                                         │
│  Financial Keywords:                                                    │
│    • Balance Sheet:   สินทรัพย์, หนี้สิน, ทุน                        │
│    • Income Statement: รายได้, ค่าใช้จ่าย, กำไร                      │
│    • Cash Flow:       กระแสเงินสด, เงินสดจาก                         │
│    • Ratio:           อัตราส่วน, ROE, ROA                             │
│                                                                         │
│  Output: Structured financial data with metadata                       │
└─────────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                    BATCH MODULE (batch.py)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                   BatchProcessor                                   │ │
│  ├───────────────────────────────────────────────────────────────────┤ │
│  │  Modes:                                                            │ │
│  │    • Sequential (max_workers=1)                                   │ │
│  │    • Parallel   (max_workers>1) with ThreadPoolExecutor          │ │
│  │                                                                    │ │
│  │  Features:                                                         │ │
│  │    • Real-time progress tracking                                  │ │
│  │    • Error recovery (continue on failure)                         │ │
│  │    • Time estimation                                              │ │
│  │    • Statistics collection                                        │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                   BatchProgress                                    │ │
│  ├───────────────────────────────────────────────────────────────────┤ │
│  │  • total: int                                                      │ │
│  │  • completed: int                                                  │ │
│  │  • current_file: str                                              │ │
│  │  • errors: List[str]                                              │ │
│  │  • progress_pct: float (0-100)                                    │ │
│  │  • elapsed_time: float                                            │ │
│  │  • estimated_remaining: float                                     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Performance:                                                           │
│    • Sequential: ~10-15s per document                                 │
│    • Parallel (4 workers): ~2.5-4s per document (effective)           │
│    • 466 documents: ~20-30 minutes with 4 workers                     │
└─────────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                   THAI UTILITIES (thai_utils.py)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  Numeral Conversion:                                                    │
│    • thai_to_arabic()    → ๐๑๒๓ → 0123                               │
│    • arabic_to_thai()    → 0123 → ๐๑๒๓                               │
│                                                                         │
│  Company Operations:                                                    │
│    • normalize_thai_company_name()  → Clean company names             │
│    • extract_company_code()         → Extract 13-digit registration   │
│    • is_valid_thai_company_name()   → Validate format                 │
│                                                                         │
│  Currency Operations:                                                   │
│    • parse_thai_currency()   → "๑,๒๓๔.๕๖ บาท" → 1234.56             │
│    • format_thai_currency()  → 1234.56 → "1,234.56 บาท"              │
│                                                                         │
│  Date Operations:                                                       │
│    • get_thai_year()      → Buddhist Era → Christian Era (BE - 543)  │
│    • get_buddhist_year()  → Christian Era → Buddhist Era (CE + 543)  │
│                                                                         │
│  Text Operations:                                                       │
│    • clean_thai_text()    → Remove artifacts, normalize               │
│    • is_thai_text()       → Detect Thai characters                    │
│    • split_thai_sentence()→ Sentence segmentation                     │
└─────────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  Structured Data:                                                       │
│    • Tables: List[DataFrame] with financial data                       │
│    • Text: Cleaned Thai/English text content                           │
│    • Metadata: Company info, document type, processing stats           │
│    • Errors: Comprehensive error tracking                              │
│                                                                         │
│  Integration Points:                                                    │
│    → GUI (DEV-1): Progress callbacks, real-time updates               │
│    → Database (DEV-3): Structured data storage                         │
│    → Analytics: DataFrame-ready financial data                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌──────────┐
│   Y67    │  466 PDFs
│ Directory│
└────┬─────┘
     │
     │ scan_directory()
     ↓
┌────────────────┐
│ DocumentInfo[] │  Metadata
│   (Scanner)    │
└────┬───────────┘
     │
     │ for each document
     ↓
┌──────────────────┐
│ DocumentProcessor│  OCR Engine
│   (Docling +     │
│    EasyOCR)      │
└────┬─────────────┘
     │
     │ process_single()
     ↓
┌──────────────────┐
│ ProcessedDocument│  Raw OCR results
│  - tables        │
│  - text_content  │
│  - markdown      │
└────┬─────────────┘
     │
     │ parse_financial_table()
     │ normalize_thai_numbers()
     │ clean_extracted_text()
     ↓
┌──────────────────┐
│  Structured Data │  Cleaned data
│  - DataFrame[]   │
│  - Metadata      │
│  - Company Info  │
└────┬─────────────┘
     │
     │ To Database / GUI
     ↓
┌──────────────────┐
│  Application     │
│   Layer          │
└──────────────────┘
```

## Parallel Processing Flow

```
Sequential Mode (max_workers=1):
════════════════════════════════

Document 1 ─────→ [OCR] ─────→ Result 1
Document 2 ─────→ [OCR] ─────→ Result 2
Document 3 ─────→ [OCR] ─────→ Result 3
Document 4 ─────→ [OCR] ─────→ Result 4

Time: 4 × ~15s = ~60s


Parallel Mode (max_workers=4):
═══════════════════════════════

Document 1 ─────→ [OCR Worker 1] ─────→ Result 1
Document 2 ─────→ [OCR Worker 2] ─────→ Result 2
Document 3 ─────→ [OCR Worker 3] ─────→ Result 3
Document 4 ─────→ [OCR Worker 4] ─────→ Result 4
                      ↓
                  ~15s total

Time: max(15s) ≈ 15s (4× speedup)
```

## Progress Callback Flow

```
GUI Layer:
┌─────────────────────────────────────┐
│  Streamlit / Web Interface          │
│  - Progress bars                    │
│  - Status messages                  │
│  - Real-time updates                │
└────────────┬────────────────────────┘
             ↓
             │ Callback
             │
Processing Layer:
┌────────────┴────────────────────────┐
│  BatchProcessor                     │
│    ├→ update_progress()             │
│    │   • completed / total          │
│    │   • current_file               │
│    │   • elapsed_time               │
│    │   • estimated_remaining        │
│    │                                │
│    └→ DocumentProcessor              │
│        ├→ progress_cb()              │
│        │   • message                │
│        │   • progress_pct (0-100)   │
│        │                            │
│        └→ OCR Pipeline               │
│            • Starting...             │
│            • Extracting... (30%)     │
│            • Processing... (60%)     │
│            • Complete (100%)         │
└─────────────────────────────────────┘
```

## Error Handling Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Error Recovery Strategy                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Scanner Layer:                                                 │
│    ✓ Invalid folder name    → Use folder name as code/name    │
│    ✓ Missing year folder    → Skip silently                   │
│    ✓ Permission denied      → Log error, continue             │
│                                                                 │
│  OCR Layer:                                                     │
│    ✓ File not found         → Return failed status            │
│    ✓ Docling error          → Return failed with error msg    │
│    ✓ Table extraction fail  → Log warning, continue text      │
│    ✓ Partial success        → Return partial with what worked │
│                                                                 │
│  Parser Layer:                                                  │
│    ✓ Malformed data         → Return None/empty safely        │
│    ✓ Missing fields         → Use defaults                     │
│    ✓ Invalid numbers        → Skip, continue processing        │
│                                                                 │
│  Batch Layer:                                                   │
│    ✓ Single file failure    → Log error, continue batch       │
│    ✓ Worker crash           → Restart worker, continue         │
│    ✓ Memory error           → Reduce workers, retry           │
│                                                                 │
│  All Errors Tracked:                                            │
│    • ProcessedDocument.errors: List[str]                       │
│    • BatchProgress.errors: List[str]                           │
│    • Never stop entire pipeline for single failure             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Memory Management

```
Component                   Memory Usage
═══════════════════════════════════════════
Scanner                     ~1 MB (metadata only)
DocumentProcessor           ~500 MB per worker
  - Docling models          ~200 MB
  - EasyOCR models          ~200 MB
  - TableFormer model       ~100 MB
BatchProcessor (4 workers)  ~2 GB total
DataFrame storage           ~1-10 MB per table

Recommendations:
  • Sequential: 1 GB RAM minimum
  • Parallel (4): 4 GB RAM recommended
  • For 466 docs: Process in batches if memory constrained
```

## Integration Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     APPLICATION STACK                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────┐                                         │
│  │   GUI Layer        │  DEV-1 (Streamlit)                      │
│  │  - File upload     │                                          │
│  │  - Progress bars   │                                          │
│  │  - Results display │                                          │
│  └─────────┬──────────┘                                         │
│            │                                                     │
│            ↓ call                                                │
│  ┌────────────────────┐                                         │
│  │  Processing Layer  │  DEV-2 (This Component)                 │
│  │  - Scanner         │  ← YOU ARE HERE                         │
│  │  - OCR             │                                          │
│  │  - Parser          │                                          │
│  │  - Batch           │                                          │
│  └─────────┬──────────┘                                         │
│            │                                                     │
│            ↓ store                                               │
│  ┌────────────────────┐                                         │
│  │  Database Layer    │  DEV-3 (SQLite/PostgreSQL)              │
│  │  - Document meta   │                                          │
│  │  - Table data      │                                          │
│  │  - Company info    │                                          │
│  └────────────────────┘                                         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Performance Characteristics

```
Operation               Sequential    Parallel (4)    Notes
═══════════════════════════════════════════════════════════════
Scan 466 files          ~50ms        ~50ms           I/O bound
Process 1 document      10-30s       10-30s          Per worker
Process 466 documents   ~2-4 hours   ~30-60 min      4× speedup
Memory usage            ~1 GB        ~4 GB           Linear scaling
Success rate            ~95%         ~95%            Same accuracy
CPU usage               ~50%         ~200%           4 cores

Bottlenecks:
  • OCR processing: CPU-intensive (can use GPU)
  • Table extraction: Memory-intensive
  • Thai text: Requires EasyOCR model load (~200MB)

Optimizations:
  • Use GPU for EasyOCR (10× faster)
  • Use FAST mode for preview (2× faster)
  • Filter documents before processing
  • Process in batches to manage memory
```

## Production Deployment

```
┌──────────────────────────────────────────────────────────────┐
│                   Deployment Architecture                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Container (Docker):                                         │
│    • Python 3.10+                                            │
│    • Docling + EasyOCR                                       │
│    • Thai language models                                    │
│    • 4 GB RAM minimum                                        │
│                                                              │
│  Environment Variables:                                      │
│    • DATA_DIR=/data/Y67                                      │
│    • MAX_WORKERS=4                                           │
│    • USE_GPU=false                                           │
│    • TABLE_MODE=ACCURATE                                     │
│                                                              │
│  Monitoring:                                                 │
│    • Processing statistics                                   │
│    • Error tracking                                          │
│    • Performance metrics                                     │
│    • Success rate monitoring                                 │
│                                                              │
│  Scaling:                                                    │
│    • Horizontal: Multiple workers/containers                 │
│    • Vertical: More CPU/RAM per container                    │
│    • GPU: NVIDIA GPU for EasyOCR acceleration               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Testing Strategy

```
Unit Tests:
  • scanner.py: Test folder parsing, type detection
  • parser.py: Test Thai text normalization
  • thai_utils.py: Test all utility functions

Integration Tests:
  • OCR pipeline: Test with sample PDFs
  • Batch processing: Test parallel execution
  • Error handling: Test failure recovery

Performance Tests:
  • Process time estimation
  • Memory usage profiling
  • Parallel speedup validation

End-to-End Tests:
  • Scan → Process → Parse → Store
  • Full workflow with real documents
  • GUI integration testing
```

---

**Architecture Last Updated**: 2024-11-25
**Status**: ✅ Production-Ready
**Total Components**: 6 files, ~48KB code
**Test Coverage**: All interfaces documented with examples
