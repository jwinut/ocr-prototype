"""
OCR Processing Engine - Docling wrapper with Thai language support
Uses Docling with EasyOCR for Thai financial document processing
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Generator
import pandas as pd

# Docling imports
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        EasyOcrOptions,
        TableFormerMode,
    )
    from docling.datamodel.base_models import InputFormat
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    print("Warning: Docling not installed. Install with: pip install docling")


@dataclass
class ProcessedDocument:
    """Results from OCR processing a single document"""
    status: str  # success, failed, partial
    tables: List[pd.DataFrame] = field(default_factory=list)
    text_content: str = ""
    markdown: str = ""
    json_data: dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    source_file: str = ""

    def __repr__(self) -> str:
        return (
            f"ProcessedDocument(status={self.status}, "
            f"tables={len(self.tables)}, "
            f"time={self.processing_time:.2f}s)"
        )

    def has_tables(self) -> bool:
        """Check if document has extracted tables"""
        return len(self.tables) > 0

    def get_table_count(self) -> int:
        """Get number of extracted tables"""
        return len(self.tables)


class DocumentProcessor:
    """
    Docling-based OCR processor with Thai language support.

    Uses EasyOCR for Thai/English text recognition and
    TableFormer for accurate financial table extraction.
    """

    def __init__(
        self,
        languages: tuple = ("th", "en"),
        table_mode: str = "ACCURATE",
        gpu: bool = False
    ):
        """
        Initialize Docling processor with EasyOCR for Thai.

        Args:
            languages: Tuple of language codes for OCR (default: Thai + English)
            table_mode: TableFormer mode - FAST or ACCURATE (default: ACCURATE)
            gpu: Enable GPU acceleration if available (default: False)
        """
        if not DOCLING_AVAILABLE:
            raise ImportError(
                "Docling not installed. Install with: pip install docling"
            )

        self.languages = languages
        self.table_mode = table_mode
        self.gpu = gpu

        # Configure OCR options for Thai
        self.ocr_options = EasyOcrOptions(
            lang=list(languages),
            use_gpu=gpu
        )

        # Configure pipeline for financial documents
        self.pipeline_options = PdfPipelineOptions(
            do_ocr=True,
            ocr_options=self.ocr_options,
            do_table_structure=True,
            table_structure_options={
                "mode": TableFormerMode.ACCURATE if table_mode == "ACCURATE"
                else TableFormerMode.FAST
            }
        )

        # Initialize converter
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=self.pipeline_options
                )
            }
        )

        # Processing statistics
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'partial': 0,
            'total_time': 0.0,
        }

    def process_single(
        self,
        path: str,
        progress_cb: Optional[Callable[[str, float], None]] = None
    ) -> ProcessedDocument:
        """
        Process single PDF with optional progress callback.

        Args:
            path: Path to PDF file
            progress_cb: Optional callback(message, progress_pct)

        Returns:
            ProcessedDocument with extraction results

        Example:
            >>> processor = DocumentProcessor()
            >>> result = processor.process_single('document.pdf')
            >>> print(f"Tables: {result.get_table_count()}")
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
                progress_cb(f"Starting OCR: {file_path.name}", 0.0)

            # Convert document
            if progress_cb:
                progress_cb("Extracting text and tables...", 0.3)

            result = self.converter.convert(str(file_path))

            if progress_cb:
                progress_cb("Processing extraction results...", 0.6)

            # Extract content
            doc = result.document

            # Get text content
            text_content = doc.export_to_text() if hasattr(doc, 'export_to_text') else ""

            # Get markdown
            markdown = doc.export_to_markdown() if hasattr(doc, 'export_to_markdown') else ""

            # Get JSON representation
            json_data = doc.export_to_dict() if hasattr(doc, 'export_to_dict') else {}

            # Extract tables
            tables = []
            if hasattr(doc, 'tables') and doc.tables:
                for table in doc.tables:
                    try:
                        # Convert table to pandas DataFrame
                        # Pass doc argument as required by newer Docling versions
                        df = table.export_to_dataframe(doc=doc) if hasattr(table, 'export_to_dataframe') else pd.DataFrame()
                        if not df.empty:
                            tables.append(df)
                    except Exception as e:
                        # Log table extraction error but continue
                        print(f"Warning: Failed to extract table: {str(e)}")

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
                markdown=markdown,
                json_data=json_data,
                processing_time=processing_time,
                source_file=str(path)
            )

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Processing failed: {str(e)}"

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

        Example:
            >>> processor = DocumentProcessor()
            >>> for result in processor.process_batch(pdf_paths):
            ...     if result.status == 'success':
            ...         print(f"Tables: {result.get_table_count()}")
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
            )
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


def extract_tables_only(
    path: str,
    languages: tuple = ("th", "en")
) -> List[pd.DataFrame]:
    """
    Convenience function to extract only tables from PDF.

    Args:
        path: PDF file path
        languages: OCR languages

    Returns:
        List of DataFrames for extracted tables
    """
    processor = DocumentProcessor(languages=languages)
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
    Convenience function to extract only text from PDF.

    Args:
        path: PDF file path
        languages: OCR languages

    Returns:
        Extracted text content
    """
    processor = DocumentProcessor(languages=languages)
    result = processor.process_single(path)

    if result.status == "success":
        return result.text_content
    else:
        return ""
