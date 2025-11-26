"""
PDFPlumber-based extractor - lightweight text/table extraction (no OCR).

Intended for digitally searchable PDFs. Produces ProcessedDocument compatible
with other engines (tables as DataFrames, text_content, markdown).
"""

import time
from pathlib import Path
from typing import Callable, List, Optional
import pandas as pd
import pdfplumber

from .ocr import ProcessedDocument


class PdfPlumberDocumentProcessor:
    """
    PDFPlumber extractor with the same interface as other processors.
    """

    def __init__(
        self,
        languages: tuple = ("th", "en"),  # unused; for interface parity
        max_pages: Optional[int] = None
    ):
        self.languages = languages
        self.max_pages = max_pages
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'total_time': 0.0,
        }

    def process_single(
        self,
        path: str,
        progress_cb: Optional[Callable[[str, float], None]] = None
    ) -> ProcessedDocument:
        start = time.time()
        file_path = Path(path)

        if not file_path.exists():
            return ProcessedDocument(
                status="failed",
                errors=[f"File not found: {path}"],
                source_file=str(path)
            )

        try:
            if progress_cb:
                progress_cb(f"Opening PDF: {file_path.name}", 0.1)

            text_chunks: List[str] = []
            tables: List[pd.DataFrame] = []
            markdown_parts: List[str] = []

            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                pages_to_process = (
                    list(range(total_pages)) if self.max_pages is None
                    else list(range(min(self.max_pages, total_pages)))
                )
                for idx, page_num in enumerate(pages_to_process, start=1):
                    if progress_cb:
                        progress_cb(f"Processing page {idx}/{len(pages_to_process)}", idx / len(pages_to_process))

                    page = pdf.pages[page_num]
                    text = page.extract_text() or ""
                    if text:
                        text_chunks.append(text)

                    # Extract tables
                    page_tables = page.extract_tables() or []
                    for t in page_tables:
                        try:
                            df = pd.DataFrame(t)
                            if not df.empty:
                                tables.append(df)
                        except Exception:
                            continue

                    # Build markdown-ish block per page (text only)
                    if text:
                        markdown_parts.append(f"<!--page:{idx}/{len(pages_to_process)}-->\n\n{text}")

            processing_time = time.time() - start
            self.stats['total_processed'] += 1
            self.stats['successful'] += 1
            self.stats['total_time'] += processing_time

            return ProcessedDocument(
                status="success",
                tables=tables,
                text_content="\n\n".join(text_chunks),
                markdown="\n\n".join(markdown_parts),
                json_data={"engine": "pdfplumber", "pages": len(markdown_parts)},
                processing_time=processing_time,
                source_file=str(path)
            )

        except Exception as e:
            processing_time = time.time() - start
            self.stats['total_processed'] += 1
            self.stats['failed'] += 1
            self.stats['total_time'] += processing_time
            return ProcessedDocument(
                status="failed",
                errors=[str(e)],
                processing_time=processing_time,
                source_file=str(path)
            )
