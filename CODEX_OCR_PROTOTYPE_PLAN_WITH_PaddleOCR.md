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
