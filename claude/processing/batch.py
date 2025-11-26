"""
Batch Processor - Parallel processing with progress tracking
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Generator, List, Optional

from .ocr import DocumentProcessor, ProcessedDocument

# Engine factory function
def get_processor(engine: str = "docling", languages: tuple = ("th", "en"), **kwargs):
    """
    Factory function to get the appropriate OCR processor.

    Args:
        engine: OCR engine to use ("docling" or "typhoon")
        languages: Language codes for OCR
        **kwargs: Additional engine-specific parameters

    Returns:
        DocumentProcessor or TyphoonDocumentProcessor instance
    """
    if engine == "typhoon":
        from .ocr_typhoon import TyphoonDocumentProcessor
        return TyphoonDocumentProcessor(
            languages=languages,
            rate_limit_delay=kwargs.get('rate_limit_delay', 3.0),
            convert_tables_to_df=kwargs.get('convert_tables_to_df', True),
        )
    else:
        # Default to Docling
        return DocumentProcessor(
            languages=languages,
            table_mode=kwargs.get('table_mode', 'ACCURATE'),
            gpu=kwargs.get('gpu', False),
        )
from .scanner import DocumentInfo, scan_directory


@dataclass
class BatchProgress:
    """Progress tracking for batch operations"""
    total: int
    completed: int = 0
    current_file: str = ""
    errors: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    def __post_init__(self):
        """Initialize start time"""
        if not hasattr(self, 'start_time'):
            self.start_time = time.time()

    @property
    def progress_pct(self) -> float:
        """Calculate progress percentage"""
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100

    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time in seconds"""
        return time.time() - self.start_time

    @property
    def estimated_remaining(self) -> float:
        """Estimate remaining time in seconds"""
        if self.completed == 0:
            return 0.0

        avg_time = self.elapsed_time / self.completed
        remaining = self.total - self.completed
        return avg_time * remaining

    def __repr__(self) -> str:
        return (
            f"BatchProgress({self.completed}/{self.total}, "
            f"{self.progress_pct:.1f}%, "
            f"errors={len(self.errors)})"
        )


class BatchProcessor:
    """
    Batch document processor with progress tracking.

    Handles parallel processing with error recovery and progress callbacks.
    Supports multiple OCR engines (Docling, Typhoon).
    """

    def __init__(
        self,
        max_workers: int = 1,
        languages: tuple = ("th", "en"),
        engine: str = "docling",
        **engine_kwargs
    ):
        """
        Initialize batch processor.

        Args:
            max_workers: Number of parallel workers (default: 1 for sequential)
            languages: OCR languages for DocumentProcessor
            engine: OCR engine to use ("docling" or "typhoon")
            **engine_kwargs: Additional engine-specific parameters
        """
        self.max_workers = max_workers
        self.languages = languages
        self.engine = engine
        self.processor = get_processor(engine=engine, languages=languages, **engine_kwargs)
        self.current_progress: Optional[BatchProgress] = None

    def process_directory(
        self,
        path: str,
        progress_cb: Optional[Callable[[BatchProgress], None]] = None,
        target_year: str = "Y67"
    ) -> Generator[tuple[DocumentInfo, ProcessedDocument], None, None]:
        """
        Process all PDFs in directory with progress updates.

        Args:
            path: Root directory path
            progress_cb: Optional callback receiving BatchProgress
            target_year: Fiscal year to process (default: Y67)

        Yields:
            Tuple of (DocumentInfo, ProcessedDocument) for each file

        Example:
            >>> processor = BatchProcessor(max_workers=4)
            >>> def progress_callback(progress):
            ...     print(f"Progress: {progress.progress_pct:.1f}%")
            >>> for doc_info, result in processor.process_directory('/path/to/Y67', progress_callback):
            ...     if result.status == 'success':
            ...         print(f"Processed: {doc_info.company_name}")
        """
        # Scan directory for documents
        documents = scan_directory(path, target_year=target_year)

        if not documents:
            print(f"No documents found in {path}")
            return

        # Initialize progress
        self.current_progress = BatchProgress(total=len(documents))

        # Process documents
        if self.max_workers == 1:
            # Sequential processing
            yield from self._process_sequential(documents, progress_cb)
        else:
            # Parallel processing
            yield from self._process_parallel(documents, progress_cb)

    def _process_sequential(
        self,
        documents: List[DocumentInfo],
        progress_cb: Optional[Callable[[BatchProgress], None]] = None
    ) -> Generator[tuple[DocumentInfo, ProcessedDocument], None, None]:
        """
        Process documents sequentially.

        Args:
            documents: List of DocumentInfo to process
            progress_cb: Progress callback

        Yields:
            Tuple of (DocumentInfo, ProcessedDocument)
        """
        for doc_info in documents:
            # Update progress
            self.current_progress.current_file = doc_info.file_name

            if progress_cb:
                progress_cb(self.current_progress)

            # Process document
            try:
                result = self.processor.process_single(str(doc_info.file_path))

                # Track errors
                if result.status == 'failed':
                    error_msg = f"{doc_info.file_name}: {', '.join(result.errors)}"
                    self.current_progress.errors.append(error_msg)

                yield (doc_info, result)

            except Exception as e:
                # Handle unexpected errors
                error_msg = f"{doc_info.file_name}: {str(e)}"
                self.current_progress.errors.append(error_msg)

                # Yield failed result
                yield (doc_info, ProcessedDocument(
                    status='failed',
                    errors=[str(e)],
                    source_file=str(doc_info.file_path)
                ))

            finally:
                # Update progress
                self.current_progress.completed += 1

                if progress_cb:
                    progress_cb(self.current_progress)

    def _process_parallel(
        self,
        documents: List[DocumentInfo],
        progress_cb: Optional[Callable[[BatchProgress], None]] = None
    ) -> Generator[tuple[DocumentInfo, ProcessedDocument], None, None]:
        """
        Process documents in parallel.

        Args:
            documents: List of DocumentInfo to process
            progress_cb: Progress callback

        Yields:
            Tuple of (DocumentInfo, ProcessedDocument)
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_doc = {
                executor.submit(
                    self.processor.process_single,
                    str(doc_info.file_path)
                ): doc_info
                for doc_info in documents
            }

            # Process completed tasks
            for future in as_completed(future_to_doc):
                doc_info = future_to_doc[future]

                # Update progress
                self.current_progress.current_file = doc_info.file_name

                try:
                    result = future.result()

                    # Track errors
                    if result.status == 'failed':
                        error_msg = f"{doc_info.file_name}: {', '.join(result.errors)}"
                        self.current_progress.errors.append(error_msg)

                    yield (doc_info, result)

                except Exception as e:
                    # Handle unexpected errors
                    error_msg = f"{doc_info.file_name}: {str(e)}"
                    self.current_progress.errors.append(error_msg)

                    # Yield failed result
                    yield (doc_info, ProcessedDocument(
                        status='failed',
                        errors=[str(e)],
                        source_file=str(doc_info.file_path)
                    ))

                finally:
                    # Update progress
                    self.current_progress.completed += 1

                    if progress_cb:
                        progress_cb(self.current_progress)

    def process_document_list(
        self,
        documents: List[DocumentInfo],
        progress_cb: Optional[Callable[[BatchProgress], None]] = None
    ) -> Generator[tuple[DocumentInfo, ProcessedDocument], None, None]:
        """
        Process a specific list of documents.

        Args:
            documents: List of DocumentInfo to process
            progress_cb: Progress callback

        Yields:
            Tuple of (DocumentInfo, ProcessedDocument)
        """
        # Initialize progress
        self.current_progress = BatchProgress(total=len(documents))

        # Process documents
        if self.max_workers == 1:
            yield from self._process_sequential(documents, progress_cb)
        else:
            yield from self._process_parallel(documents, progress_cb)

    def get_status(self) -> Optional[BatchProgress]:
        """
        Get current batch processing status.

        Returns:
            Current BatchProgress or None if no batch is running
        """
        return self.current_progress

    def get_processor_stats(self) -> dict:
        """
        Get underlying processor statistics.

        Returns:
            Dict with processor stats
        """
        return self.processor.get_processing_status()


def process_sample(
    base_path: str,
    sample_size: int = 10,
    progress_cb: Optional[Callable[[BatchProgress], None]] = None
) -> List[tuple[DocumentInfo, ProcessedDocument]]:
    """
    Convenience function to process a sample of documents.

    Args:
        base_path: Root directory path
        sample_size: Number of documents to sample
        progress_cb: Progress callback

    Returns:
        List of (DocumentInfo, ProcessedDocument) tuples
    """
    # Scan and sample
    all_docs = scan_directory(base_path)
    sample_docs = all_docs[:sample_size]

    # Process sample
    processor = BatchProcessor(max_workers=1)
    results = []

    for doc_info, result in processor.process_document_list(sample_docs, progress_cb):
        results.append((doc_info, result))

    return results


def estimate_processing_time(
    base_path: str,
    sample_size: int = 5,
    max_workers: int = 1
) -> dict:
    """
    Estimate total processing time based on sample.

    Args:
        base_path: Root directory path
        sample_size: Number of documents to sample for estimation
        max_workers: Number of parallel workers

    Returns:
        Dict with time estimates
    """
    # Scan documents
    all_docs = scan_directory(base_path)
    total_docs = len(all_docs)

    if total_docs == 0:
        return {
            'total_documents': 0,
            'estimated_time_seconds': 0,
            'estimated_time_minutes': 0,
        }

    # Process sample
    sample_docs = all_docs[:min(sample_size, total_docs)]
    processor = BatchProcessor(max_workers=1)

    start_time = time.time()
    sample_count = 0

    for doc_info, result in processor.process_document_list(sample_docs):
        sample_count += 1

    elapsed_time = time.time() - start_time

    # Calculate estimates
    avg_time_per_doc = elapsed_time / sample_count if sample_count > 0 else 0

    # Adjust for parallel workers
    if max_workers > 1:
        avg_time_per_doc = avg_time_per_doc / max_workers

    total_estimated_time = avg_time_per_doc * total_docs

    return {
        'total_documents': total_docs,
        'sample_size': sample_count,
        'avg_time_per_doc': round(avg_time_per_doc, 2),
        'estimated_time_seconds': round(total_estimated_time, 2),
        'estimated_time_minutes': round(total_estimated_time / 60, 2),
        'estimated_time_hours': round(total_estimated_time / 3600, 2),
        'parallel_workers': max_workers,
    }
