"""
Typhoon OCR Processing Engine - Cloud-based Thai OCR

Uses Typhoon OCR API (v1.5) for Thai financial document processing.
Provides same interface as ocr.py for easy swapping.

Rate limits: 2 req/s, 20 req/min
"""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Generator, List, Optional
import pandas as pd
from importlib import import_module

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Typhoon OCR imports
try:
    from typhoon_ocr import ocr_document
    TYPHOON_AVAILABLE = True
except ImportError:
    TYPHOON_AVAILABLE = False
    print("Warning: typhoon-ocr not installed. Install with: pip install typhoon-ocr")

# Import shared dataclass
from .ocr import ProcessedDocument


def _html_table_to_dataframe(html_table: str) -> Optional[pd.DataFrame]:
    """
    Convert HTML table to pandas DataFrame.

    Args:
        html_table: HTML table string

    Returns:
        DataFrame or None if parsing fails
    """
    try:
        # Use pandas read_html to parse; wrap literal string in StringIO to avoid deprecation
        from io import StringIO
        dfs = pd.read_html(StringIO(html_table))
        if dfs:
            return dfs[0]
    except Exception:
        pass
    return None


def _extract_tables_from_markdown(markdown: str) -> List[pd.DataFrame]:
    """
    Extract HTML tables from markdown and convert to DataFrames.

    Args:
        markdown: Markdown text containing HTML tables

    Returns:
        List of DataFrames
    """
    import re

    tables = []
    # Find all HTML tables
    table_pattern = re.compile(r'<table>.*?</table>', re.DOTALL | re.IGNORECASE)

    for match in table_pattern.finditer(markdown):
        html_table = match.group(0)
        df = _html_table_to_dataframe(html_table)
        if df is not None and not df.empty:
            tables.append(df)

    return tables


class TyphoonDocumentProcessor:
    """
    Typhoon OCR-based processor with same interface as DocumentProcessor.

    Uses Typhoon OCR API for Thai/English text recognition.
    Optimized for Thai financial documents.
    """

    def __init__(
        self,
        languages: tuple = ("th", "en"),  # Kept for interface compatibility
        api_key: Optional[str] = None,
        rate_limit_delay: float = 3.0,  # Seconds between requests
        convert_tables_to_df: bool = True,
    ):
        """
        Initialize Typhoon OCR processor.

        Args:
            languages: Language codes (for interface compatibility, Typhoon auto-detects)
            api_key: Typhoon API key (defaults to TYPHOON_OCR_API_KEY env var)
            rate_limit_delay: Delay between API calls (default: 3s for safety)
            convert_tables_to_df: Convert HTML tables to DataFrames
        """
        if not TYPHOON_AVAILABLE:
            raise ImportError(
                "typhoon-ocr not installed. Install with: pip install typhoon-ocr"
            )

        # Check API key
        self.api_key = api_key or os.getenv('TYPHOON_OCR_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Typhoon API key not found. Set TYPHOON_OCR_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Set API key in environment for typhoon_ocr package
        os.environ['TYPHOON_OCR_API_KEY'] = self.api_key

        self.languages = languages
        self.rate_limit_delay = rate_limit_delay
        self.convert_tables_to_df = convert_tables_to_df
        self._last_request_time = 0

        # Processing statistics
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'partial': 0,
            'total_time': 0.0,
        }

    def _wait_for_rate_limit(self):
        """Wait if needed to respect rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def process_single(
        self,
        path: str,
        progress_cb: Optional[Callable[[str, float], None]] = None
    ) -> ProcessedDocument:
        """
        Process single PDF with Typhoon OCR.

        Args:
            path: Path to PDF file
            progress_cb: Optional callback(message, progress_pct)

        Returns:
            ProcessedDocument with extraction results
        """
        start_time = time.time()
        file_path = Path(path)

        if not file_path.exists():
            return ProcessedDocument(
                status="failed",
                errors=[f"File not found: {path}"],
                source_file=str(path)
            )

        try:
            if progress_cb:
                progress_cb(f"Starting Typhoon OCR: {file_path.name}", 0.0)

            # Determine page count (best-effort; fallback to 1). Try pypdf first, then PyPDF2.
            num_pages = 1
            for lib_name, cls_name in (("pypdf", "PdfReader"), ("PyPDF2", "PdfReader")):
                try:
                    lib = import_module(lib_name)
                    reader_cls = getattr(lib, cls_name)
                    with open(file_path, "rb") as f:
                        reader = reader_cls(f)
                        num_pages = max(1, len(reader.pages))
                    break
                except Exception:
                    continue

            markdown_pages: List[str] = []
            tables: List[pd.DataFrame] = []

            for page_idx in range(num_pages):
                if progress_cb:
                    progress_cb(f"Calling Typhoon OCR API (page {page_idx + 1}/{num_pages})...", (page_idx) / max(1, num_pages))

                # Wait for rate limit between calls
                self._wait_for_rate_limit()

                page_markdown = ocr_document(
                    pdf_or_image_path=str(file_path),
                    page_num=page_idx + 1
                )

                if page_markdown:
                    markdown_pages.append(page_markdown)

                    # Extract tables if enabled
                    if self.convert_tables_to_df:
                        tables.extend(_extract_tables_from_markdown(page_markdown))

            if progress_cb:
                progress_cb("Processing results...", 0.9)

            # Combine pages with explicit markers for downstream pagination
            markdown = ""
            if markdown_pages:
                parts = []
                total = len(markdown_pages)
                for idx, content in enumerate(markdown_pages, start=1):
                    parts.append(f"<!--page:{idx}/{total}-->\\n{content}")
                markdown = "\\n\\n".join(parts)

            # Create text content (strip HTML tags for plain text)
            import re
            text_content = re.sub(r'<[^>]+>', '', markdown) if markdown else ""

            processing_time = time.time() - start_time

            if progress_cb:
                progress_cb("Complete", 1.0)

            # Update stats
            self.stats['total_processed'] += 1
            self.stats['successful'] += 1
            self.stats['total_time'] += processing_time

            return ProcessedDocument(
                status="success",
                tables=tables,
                text_content=text_content,
                markdown=markdown or "",
                json_data={"engine": "typhoon-ocr", "version": "1.5", "pages": num_pages},
                processing_time=processing_time,
                source_file=str(path)
            )

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Typhoon OCR failed: {str(e)}"

            if progress_cb:
                progress_cb(f"Error: {error_msg}", 0.0)

            self.stats['total_processed'] += 1
            self.stats['failed'] += 1
            self.stats['total_time'] += processing_time

            return ProcessedDocument(
                status="failed",
                errors=[error_msg],
                processing_time=processing_time,
                source_file=str(path)
            )

    def process_batch(
        self,
        paths: List[str],
        progress_cb: Optional[Callable[[int, int, str], None]] = None
    ) -> Generator[ProcessedDocument, None, None]:
        """
        Generator yielding ProcessedDocument for each file.

        Args:
            paths: List of PDF file paths
            progress_cb: Optional callback(current, total, filename)

        Yields:
            ProcessedDocument for each processed file
        """
        total = len(paths)

        for idx, path in enumerate(paths, 1):
            filename = Path(path).name

            if progress_cb:
                progress_cb(idx, total, filename)

            result = self.process_single(path)
            yield result

    def get_processing_status(self) -> dict:
        """
        Return current processing statistics.

        Returns:
            Dict with processing stats
        """
        total = self.stats['total_processed']
        avg_time = (
            self.stats['total_time'] / total
            if total > 0 else 0.0
        )

        return {
            'total_processed': total,
            'successful': self.stats['successful'],
            'failed': self.stats['failed'],
            'partial': self.stats['partial'],
            'total_time_seconds': round(self.stats['total_time'], 2),
            'average_time_seconds': round(avg_time, 2),
            'success_rate': (
                round((self.stats['successful'] / total) * 100, 1)
                if total > 0 else 0.0
            ),
            'engine': 'typhoon-ocr',
            'rate_limit_delay': self.rate_limit_delay,
        }

    def reset_statistics(self):
        """Reset processing statistics"""
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'partial': 0,
            'total_time': 0.0,
        }


# Convenience functions matching ocr.py interface

def extract_tables_only(
    path: str,
    languages: tuple = ("th", "en")
) -> List[pd.DataFrame]:
    """
    Convenience function to extract only tables from PDF using Typhoon OCR.

    Args:
        path: PDF file path
        languages: OCR languages (for interface compatibility)

    Returns:
        List of DataFrames for extracted tables
    """
    processor = TyphoonDocumentProcessor(languages=languages)
    result = processor.process_single(path)

    if result.status == "success":
        return result.tables
    else:
        return []


def extract_text_only(
    path: str,
    languages: tuple = ("th", "en")
) -> str:
    """
    Convenience function to extract only text from PDF using Typhoon OCR.

    Args:
        path: PDF file path
        languages: OCR languages (for interface compatibility)

    Returns:
        Extracted text content
    """
    processor = TyphoonDocumentProcessor(languages=languages)
    result = processor.process_single(path)

    if result.status == "success":
        return result.text_content
    else:
        return ""


def extract_markdown(
    path: str,
    languages: tuple = ("th", "en")
) -> str:
    """
    Extract document as markdown using Typhoon OCR.

    Args:
        path: PDF file path
        languages: OCR languages (for interface compatibility)

    Returns:
        Markdown content with HTML tables
    """
    processor = TyphoonDocumentProcessor(languages=languages)
    result = processor.process_single(path)

    if result.status == "success":
        return result.markdown
    else:
        return ""
