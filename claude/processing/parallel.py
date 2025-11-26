"""
Parallel Processing Integration for Streamlit UI

Thread-safe wrapper around BatchProcessor for use with Streamlit's
session state and progress tracking.
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from queue import Queue
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple
import threading

# Thread-safe logging queue for UI updates
_log_queue: Queue = Queue()
_results_lock = Lock()

# Thread-local processor storage for thread safety
_thread_local = threading.local()


def get_thread_processor(engine: str = "docling", languages: tuple = ("th", "en")):
    """
    Get thread-local OCR processor instance (each thread gets its own).
    
    Args:
        engine: OCR engine to use ("docling" or "typhoon")
        languages: Tuple of languages to support
    """
    # Initialize processor storage if not exists
    if not hasattr(_thread_local, 'processors'):
        _thread_local.processors = {}

    # Check if we already have a processor for this engine
    if engine in _thread_local.processors:
        return _thread_local.processors[engine]

    # Create new processor for requested engine
    if engine == "typhoon":
        from processing.ocr_typhoon import TyphoonDocumentProcessor
        _thread_local.processors[engine] = TyphoonDocumentProcessor(languages=languages)
    else:
        from processing.ocr import DocumentProcessor
        _thread_local.processors[engine] = DocumentProcessor(languages=languages)

    return _thread_local.processors[engine]


@dataclass
class ProcessingResult:
    """Result from processing a single document."""
    doc_id: str
    file_path: str
    filename: str
    status: str  # 'success', 'failed', 'skipped'
    tables_found: int = 0
    text_blocks: int = 0
    error_message: str = ""
    processing_time: float = 0.0
    text_content: str = ""
    markdown_content: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class BatchStatus:
    """Status of batch processing operation."""
    total: int
    completed: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    current_files: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    is_running: bool = True
    is_cancelled: bool = False

    @property
    def progress(self) -> float:
        """Progress percentage 0.0 to 1.0."""
        if self.total == 0:
            return 1.0
        return self.completed / self.total

    @property
    def elapsed_seconds(self) -> float:
        """Elapsed time in seconds."""
        return time.time() - self.start_time

    @property
    def estimated_remaining(self) -> float:
        """Estimated remaining time in seconds."""
        if self.completed == 0:
            return 0.0
        rate = self.elapsed_seconds / self.completed
        remaining = self.total - self.completed
        return rate * remaining


def get_log_messages() -> List[Dict[str, Any]]:
    """Get all pending log messages from the queue."""
    messages = []
    while not _log_queue.empty():
        try:
            messages.append(_log_queue.get_nowait())
        except Exception:
            break
    return messages


def add_log_message(message: str, level: str = "info"):
    """Add a log message to the queue (thread-safe)."""
    _log_queue.put({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message
    })


def process_single_document(
    doc_id: str,
    file_path: str,
    engine: str = "docling",
    check_processed_fn: Optional[Callable[[str], Tuple[bool, str]]] = None,
    save_full_results_fn: Optional[Callable] = None
) -> ProcessingResult:
    """
    Process a single document using OCR (thread-safe).

    Args:
        doc_id: Document identifier
        file_path: Path to the PDF file
        engine: OCR engine to use
        check_processed_fn: Function to check if already processed
        save_full_results_fn: Function to save full OCR results to database

    Returns:
        ProcessingResult with status and extracted data
    """
    start_time = time.time()
    filename = os.path.basename(file_path) if file_path else doc_id

    # Check if already processed
    if check_processed_fn and file_path:
        is_processed, reason = check_processed_fn(file_path)
        if is_processed:
            add_log_message(f"⏭️ Skipping (already processed): {filename}", "info")
            return ProcessingResult(
                doc_id=doc_id,
                file_path=file_path,
                filename=filename,
                status="skipped"
            )
        if reason == 'file_changed':
            add_log_message(f"🔄 File modified, reprocessing: {filename}", "warning")

    add_log_message(f"📄 Processing: {filename} (Engine: {engine})", "info")

    try:
        # Use thread-local OCR processor (each thread has its own)
        processor = get_thread_processor(engine=engine, languages=("th", "en"))
        ocr_result = processor.process_single(file_path)

        if ocr_result.status == "success":
            tables_found = len(ocr_result.tables)
            text_blocks = len(ocr_result.text_content.split('\\n\\n')) if ocr_result.text_content else 0
            status = "success"
            add_log_message(f"✅ Completed: {filename} ({tables_found} tables)", "success")
        else:
            tables_found = 0
            text_blocks = 0
            status = "failed"
            add_log_message(f"❌ Failed: {filename} - {ocr_result.errors}", "error")

        processing_time = time.time() - start_time

        # Create result
        result = ProcessingResult(
            doc_id=doc_id,
            file_path=file_path,
            filename=filename,
            status=status,
            tables_found=tables_found,
            text_blocks=text_blocks,
            processing_time=processing_time,
            text_content=ocr_result.text_content if ocr_result.status == "success" else "",
            markdown_content=ocr_result.markdown if ocr_result.status == "success" else ""
        )

        # Save full OCR results to database (single source of truth)
        if save_full_results_fn and status == "success":
            try:
                save_full_results_fn(
                    file_path=file_path,
                    file_name=filename,
                    ocr_result=ocr_result,
                    doc_id=doc_id,
                    engine=engine
                )
                add_log_message(f"💾 Saved full results to database ({engine}): {filename}", "info")
            except Exception as e:
                add_log_message(f"⚠️ Database save failed: {filename} - {e}", "warning")

        return result

    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = str(e)
        add_log_message(f"❌ Error processing {filename}: {error_msg}", "error")

        return ProcessingResult(
            doc_id=doc_id,
            file_path=file_path,
            filename=filename,
            status="failed",
            error_message=error_msg,
            processing_time=processing_time
        )


class ParallelProcessor:
    """
    Parallel document processor with progress tracking.

    Thread-safe and designed for integration with Streamlit UI.
    Uses Docling OCR for document processing.
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize parallel processor.

        Args:
            max_workers: Number of parallel workers (1 = sequential)
        """
        self.max_workers = max(1, min(max_workers, 8))  # Clamp 1-8
        self.status: Optional[BatchStatus] = None
        self.results: List[ProcessingResult] = []
        self._cancel_flag = False
        self._lock = Lock()

    def cancel(self):
        """Request cancellation of processing."""
        self._cancel_flag = True
        if self.status:
            self.status.is_cancelled = True
            self.status.is_running = False

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancel_flag

    def process_documents(
        self,
        documents: List[Dict[str, str]],
        engine: str = "docling",
        check_processed_fn: Optional[Callable] = None,
        save_full_results_fn: Optional[Callable] = None,
        progress_callback: Optional[Callable[[BatchStatus], None]] = None  # Force reload
    ) -> List[ProcessingResult]:
        """
        Process documents in parallel.

        Args:
            documents: List of dicts with 'id' and 'file_path' keys
            engine: OCR engine to use ("docling" or "typhoon")
            check_processed_fn: Optional function to check if doc already processed
            save_full_results_fn: Optional function to save full OCR results to database
            progress_callback: Optional callback for progress updates

        Returns:
            List of ProcessingResult objects
        """
        self._cancel_flag = False
        self.results = []
        self.status = BatchStatus(total=len(documents))

        add_log_message(f"=== Starting batch processing ({len(documents)} documents, {self.max_workers} workers, engine: {engine}) ===", "info")

        try:
            if self.max_workers == 1:
                # Sequential processing
                self._process_sequential(documents, engine, check_processed_fn, save_full_results_fn, progress_callback)
            else:
                # Parallel processing
                self._process_parallel(documents, engine, check_processed_fn, save_full_results_fn, progress_callback)
        except KeyboardInterrupt:
            # Graceful shutdown on Ctrl+C
            add_log_message("⏹️ Interrupt received. Cancelling outstanding tasks and flushing results...", "warning")
            self.cancel()
        finally:
            if self.status:
                self.status.is_running = False
            add_log_message(
                f"=== Batch complete: {self.status.successful if self.status else 0} success, {self.status.failed if self.status else 0} failed, {self.status.skipped if self.status else 0} skipped ===",
                "success"
            )
            if self._cancel_flag:
                add_log_message("✅ Graceful shutdown complete (all worker threads joined).", "info")

        return self.results

    def _process_sequential(
        self,
        documents: List[Dict[str, str]],
        engine: str,
        check_processed_fn: Optional[Callable],
        save_full_results_fn: Optional[Callable],
        progress_callback: Optional[Callable]
    ):
        """Process documents sequentially."""
        for doc in documents:
            if self._cancel_flag:
                add_log_message("⚠️ Processing cancelled", "warning")
                break

            doc_id = doc.get('id', '')
            file_path = doc.get('file_path', '')

            self.status.current_files = [os.path.basename(file_path)]

            result = process_single_document(
                doc_id=doc_id,
                file_path=file_path,
                engine=engine,
                check_processed_fn=check_processed_fn,
                save_full_results_fn=save_full_results_fn
            )

            self._update_status(result)
            self.results.append(result)

            if progress_callback:
                progress_callback(self.status)

    def _process_parallel(
        self,
        documents: List[Dict[str, str]],
        engine: str,
        check_processed_fn: Optional[Callable],
        save_full_results_fn: Optional[Callable],
        progress_callback: Optional[Callable]
    ):
        """Process documents in parallel using ThreadPoolExecutor."""
        future_to_doc = {}
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                for doc in documents:
                    if self._cancel_flag:
                        break

                    future = executor.submit(
                        process_single_document,
                        doc_id=doc.get('id', ''),
                        file_path=doc.get('file_path', ''),
                        engine=engine,
                        check_processed_fn=check_processed_fn,
                        save_full_results_fn=save_full_results_fn
                    )
                    future_to_doc[future] = doc

                # Collect results as they complete
                for future in as_completed(future_to_doc):
                    if self._cancel_flag:
                        # Cancel remaining futures
                        for f in future_to_doc:
                            f.cancel()
                        add_log_message("⚠️ Processing cancelled", "warning")
                        break

                    try:
                        result = future.result()
                        self._update_status(result)
                        self.results.append(result)
                    except Exception as e:
                        # Handle unexpected errors
                        doc = future_to_doc[future]
                        error_result = ProcessingResult(
                            doc_id=doc.get('id', ''),
                            file_path=doc.get('file_path', ''),
                            filename=os.path.basename(doc.get('file_path', '')),
                            status="failed",
                            error_message=str(e)
                        )
                        self._update_status(error_result)
                        self.results.append(error_result)
                        add_log_message(f"❌ Unexpected error: {e}", "error")

                    if progress_callback:
                        progress_callback(self.status)
        except KeyboardInterrupt:
            # Ensure all futures are cancelled and executor shuts down cleanly
            self._cancel_flag = True
            for f in future_to_doc:
                f.cancel()
            add_log_message("⏹️ Interrupt received during parallel processing; cancelling remaining tasks.", "warning")
        finally:
            # Executor context manager ensures threads are joined here
            if self._cancel_flag:
                add_log_message("🛑 Parallel executor shutdown completed after cancellation.", "info")

    def _update_status(self, result: ProcessingResult):
        """Update batch status with result (thread-safe)."""
        with self._lock:
            self.status.completed += 1
            if result.status == "success":
                self.status.successful += 1
            elif result.status == "failed":
                self.status.failed += 1
            elif result.status == "skipped":
                self.status.skipped += 1

    def get_status(self) -> Optional[BatchStatus]:
        """Get current processing status."""
        return self.status

    def get_results(self) -> List[ProcessingResult]:
        """Get all processing results."""
        return self.results

    def get_successful_results(self) -> List[Dict[str, Any]]:
        """Get successful results as dicts for session state."""
        return [
            {
                "id": r.doc_id,
                "filename": r.filename,
                "file_path": r.file_path,
                "path": r.file_path,
                "timestamp": r.timestamp,
                "status": r.status,
                "tables_found": r.tables_found,
                "text_blocks": r.text_blocks,
                "text_content": r.text_content,
                "markdown_content": r.markdown_content
            }
            for r in self.results
            if r.status == "success"
        ]


def estimate_processing_time(
    num_documents: int,
    max_workers: int = 4,
    avg_seconds_per_doc: float = 2.0
) -> Dict[str, float]:
    """
    Estimate total processing time.

    Args:
        num_documents: Number of documents to process
        max_workers: Number of parallel workers
        avg_seconds_per_doc: Average processing time per document

    Returns:
        Dict with time estimates
    """
    # Sequential time
    sequential_time = num_documents * avg_seconds_per_doc

    # Parallel time (with overhead factor)
    overhead_factor = 1.1  # 10% overhead for thread management
    parallel_time = (sequential_time / max_workers) * overhead_factor

    speedup = sequential_time / parallel_time if parallel_time > 0 else 1.0

    return {
        "documents": num_documents,
        "workers": max_workers,
        "sequential_seconds": round(sequential_time, 1),
        "parallel_seconds": round(parallel_time, 1),
        "speedup_factor": round(speedup, 2),
        "sequential_minutes": round(sequential_time / 60, 1),
        "parallel_minutes": round(parallel_time / 60, 1)
    }
