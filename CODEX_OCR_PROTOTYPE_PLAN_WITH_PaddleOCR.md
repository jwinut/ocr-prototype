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
1. **Environment setup – ⚠️ blocked on external binaries**
   - Deliverables committed: `requirements.txt`, argparse-based CLI (`manage_workflow.py`), modular workflow package (`workflow/`).
   - Command `python3 manage_workflow.py check-deps` verified only `tesseract` exists; Poppler (`pdftoppm`/`pdftocairo`), ImageMagick (`convert`), and `ocrmypdf` binaries are missing. Python libs (`paddleocr`, `pdf2image`, `Pillow`, `pdfplumber`) also absent because network install is disallowed here.
   - Action required outside this environment: install Poppler + OCRmyPDF + ImageMagick and run `pip install -r requirements.txt`.
2. **Sample evaluation – ⏳ pending run (blocked by dependencies)**
   - Once deps exist, execute `python3 manage_workflow.py full-run --sample-limit 3 --config-path workflow.config.json` to generate baseline outputs and JSON logs.
3. **PaddleOCR comparison – ⏳ pending run**
   - Run `python3 manage_workflow.py paddle-ocr --sample-limit 3` and compare with `ocrmypdf` outputs for accuracy/perf.
4. **Select pipeline – ⏳ pending analysis**
   - Requires reviewing artifacts from steps 2–3; document final parameter choices afterward.
5. **Table extraction prototype – ✅ scripted / awaiting empirical validation**
   - `workflow/tables.py` exports CSV tables via pdfplumber using OCR’d PDFs; confirm quality after step 2 outputs exist.
6. **Batch processing script – ✅ implemented**
   - `OCRWorkflow.run_batch()` processes full tree; `python3 manage_workflow.py full-run` handles end-to-end flow once dependencies resolve.
7. **Validation & handoff – ⏳ pending QA**
   - Need to review confidence metrics and prep deployment guide after actual OCR runs complete.

## Implementation artifacts
- `manage_workflow.py`: Argparse CLI to init configs, check dependencies, preprocess PDFs, run PaddleOCR, call OCRmyPDF, extract tables, or execute the whole batch.
- `workflow/config.py`: dataclass configuration with JSON serialization + PDF discovery helpers.
- `workflow/preprocess.py`: renders 300 dpi PNG pages via pdf2image/Poppler.
- `workflow/ocr.py`: wraps PaddleOCR inference and OCRmyPDF subprocess execution, writing structured JSON.
- `workflow/tables.py`: extracts tables from OCR’d PDFs using pdfplumber and emits CSVs per page.
- `workflow/pipeline.py`: orchestrates preprocessing, OCR, and table export for individual PDFs or batches.
- `requirements.txt`: pins Python dependencies required by the pipeline.

## Usage quick-start
1. Install Poppler, ImageMagick, OCRmyPDF, and run `pip install -r requirements.txt` (network install required outside this sandbox).
2. Write configuration: `python3 manage_workflow.py init-config workflow.config.json --source-root Y67 --output-root output`.
3. Inspect environment readiness anytime via `python3 manage_workflow.py check-deps`.
4. Dry run on a handful of files: `python3 manage_workflow.py full-run --config-path workflow.config.json --sample-limit 5`.
5. Inspect outputs under `output/<company>/<year>/<file>/` (JSON, searchable PDFs, table CSVs). Use these artifacts to complete validation steps 2–4 in the workflow plan.
