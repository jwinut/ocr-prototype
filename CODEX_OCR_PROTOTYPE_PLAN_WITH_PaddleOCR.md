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

## Workflow plan
1. **Environment setup**
   - Install Poppler/ImageMagick and OCRmyPDF locally or pull their Docker images.
   - Fetch PaddleOCR repo/image for CLI + PP-Structure modules; verify GPU drivers if available.
2. **Sample evaluation**
   - Pick 2–3 representative PDFs per company type (Balance Sheet, Cash Flow, Compare PL).
   - Run OCRmyPDF baseline; archive outputs + logs for accuracy review.
3. **PaddleOCR comparison**
   - Convert the same sample pages to PNG, execute PaddleOCR CLI with `--lang thai --rec_model_dir ppocr/v4`.
   - Collect recognition JSON with bounding boxes/confidences; document runtime/resources.
4. **Select pipeline**
   - Compare accuracy metrics (manual spot check + confidence). Decide primary OCR engine and fallbacks.
   - Lock in preprocessing settings (resolution, denoise) and any GPU requirements.
5. **Table extraction prototype**
   - Use PP-Structure (table) or pdfplumber on OCR’d pages; map outputs to desired schema (e.g., assets/liabilities columns).
   - Define normalization scripts for Thai numerals and currency formatting.
6. **Batch processing script**
   - Build a Python/Bash pipeline walking `Y67/**/Y*/*.pdf`, applying preprocessing → OCR → table extraction.
   - Emit per-file artifacts: searchable PDF, plain text, table JSON/CSV, and a log entry with confidence stats.
7. **Validation & handoff**
   - Spot-check random samples across companies/years; log issues requiring manual review.
   - Package documentation (commands, configs, docker-compose) for reproducible deployment; plan next iteration (automation, UI).
