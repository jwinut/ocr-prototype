# OCR Extraction Plan

## Folder structure observations
- Each company is nested under `Y67/<company code> <company name>/Y67` and contains multiple financial PDFs (e.g., `…_BS67.pdf`, `…_Cash Flow.pdf`, `…_Compare PL.pdf`).
- Files appear to be scan-based; quick inspection only finds metadata and no embedded text, so OCR is required.
- Some companies include historical subfolders (e.g., `Y59`–`Y67`). Preserve these paths when emitting OCR results so company/year metadata stays intact.

## Requirements recap
- Documents contain Thai + English text, tables, and numeric data.
- Solution must be self-hostable (bare metal or Docker) with zero per-use cost.
- Desired output: searchable PDFs plus structured text/table exports for downstream analysis.

## Recommended toolchain
1. **Pre-processing**
   - Render PDFs to 300 dpi images using Poppler (`pdftoppm -r 300 -png`) or ImageMagick.
   - Apply deskew/denoise (`convert -deskew 40% -strip -sharpen 0x1`) to improve recognition.

2. **OCR layer**
   - Start with **OCRmyPDF + Tesseract** using Thai + English models (`ocrmypdf --language tha+eng --deskew --clean`).
   - If accuracy is insufficient, switch to **PaddleOCR** (PP-OCRv4) or **EasyOCR**. Both support Docker, GPU acceleration, and output bounding boxes/confidences.

3. **Post-processing & data extraction**
   - When a text layer exists, use `pdfplumber` or `tabula` to extract tables; alternatively run PaddleOCR’s PP-Structure (table module) to produce JSON/Excel.
   - Normalize Thai numerals/spaces via `pythainlp` helpers.
   - Save outputs per source file, e.g., `output/<company>/<year>/<file>.(pdf|txt|json)`.

4. **Quality control**
   - Log OCR confidence scores and flag low-confidence pages for manual review.
   - Compare generated searchable PDFs with originals spot-checking alignment.

## Next actions
1. Install Poppler + OCRmyPDF (or pull `ocrmypdf/ocrmypdf` Docker image) and process two sample PDFs (`บริษัท สโตเรจซิสเต็ม อินดัสตรี จำกัด_BS67.pdf`, `…_Cash Flow.pdf`).
2. Benchmark PaddleOCR on the same pages to judge accuracy/speed; decide on CPU vs. GPU hosting.
3. Prototype table extraction with PP-Structure or pdfplumber on the OCR’d balance sheet.
4. Script batch processing over all `Y67` folders, capturing output paths, confidences, and logs for future auditing.

## Workflow plan (status)
1. **Environment setup – ✅ implemented**
   - Deliverables: `requirements.txt`, reusable Typer CLI (`manage_workflow.py`), and modular workflow package (`workflow/`).
   - Still required before execution: install Poppler, ImageMagick, OCRmyPDF, and `pip install -r requirements.txt`.
2. **Sample evaluation – ⏳ pending run**
   - Use `python manage_workflow.py full-run --sample-limit 3` after dependencies are installed to produce baseline outputs and JSON logs.
3. **PaddleOCR comparison – ⏳ pending run**
   - CLI supports `python manage_workflow.py paddle-ocr --sample-limit 3`; compare with `ocrmypdf` logs manually.
4. **Select pipeline – ⏳ pending analysis**
   - Apply manual review of generated outputs/confidences to approve the default PaddleOCR + OCRmyPDF combo.
5. **Table extraction prototype – ✅ scripted / pending validation**
   - `workflow/tables.py` builds csv tables via pdfplumber; supply OCR’d PDFs (`output/.../ocr/*.pdf`) to confirm accuracy.
6. **Batch processing script – ✅ implemented**
   - `OCRWorkflow.run_batch()` walks the entire `Y67` tree; `python manage_workflow.py full-run` orchestrates preprocessing → OCR → tables.
7. **Validation & handoff – ⏳ pending QA**
   - Need to record confidence metrics and create deployment docs once sample runs are reviewed.

## Implementation artifacts
- `manage_workflow.py`: Typer-powered CLI to init configs, preprocess PDFs, run PaddleOCR, call OCRmyPDF, extract tables, or execute the whole batch.
- `workflow/config.py`: dataclass configuration with JSON serialization + PDF discovery helpers.
- `workflow/preprocess.py`: renders 300 dpi PNG pages via pdf2image/Poppler.
- `workflow/ocr.py`: wraps PaddleOCR inference and OCRmyPDF subprocess execution, writing structured JSON.
- `workflow/tables.py`: extracts tables from OCR’d PDFs using pdfplumber and emits CSVs per page.
- `workflow/pipeline.py`: orchestrates preprocessing, OCR, and table export for individual PDFs or batches.
- `requirements.txt`: pins Python dependencies required by the pipeline.

## Usage quick-start
1. `pip install -r requirements.txt` and ensure Poppler + OCRmyPDF binaries exist in `$PATH`.
2. `python manage_workflow.py init-config workflow.config.json --source-root Y67 --output-root output` (adjust paths as needed).
3. Dry run on a handful of files: `python manage_workflow.py full-run --config-path workflow.config.json --sample-limit 5`.
4. Inspect outputs under `output/<company>/<year>/<file>/` (JSON, searchable PDFs, table CSVs). Use these artifacts to complete validation steps 2–4 in the workflow plan.
