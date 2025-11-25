"""
Process Documents Page

Real-time processing view with parallel processing support, progress tracking,
state persistence, and logs. Saves processed documents to database for
persistence across restarts.
"""

import streamlit as st
import time
from datetime import datetime
import atexit
import os

st.set_page_config(
    page_title="Process Documents",
    page_icon="⚙️",
    layout="wide"
)

# Import database and parallel processor
try:
    from app.database import DatabaseManager
    from app.config import config
    from processing.parallel import (
        ParallelProcessor, BatchStatus, get_log_messages,
        add_log_message, estimate_processing_time
    )
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    import_error = str(e)


@st.cache_resource
def get_db():
    """Get database manager instance."""
    if not MODULES_AVAILABLE:
        return None
    db = DatabaseManager()
    db.init_db()
    return db


def save_session_on_exit():
    """Save session state when app shuts down."""
    db = get_db()
    if db and 'processed_documents' in st.session_state:
        db.save_session_state(st.session_state.processed_documents)


# Register shutdown handler
atexit.register(save_session_on_exit)


# Initialize session state
if 'selected_files' not in st.session_state:
    st.session_state.selected_files = []
if 'selected_file_paths' not in st.session_state:
    st.session_state.selected_file_paths = {}
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = None
if 'processed_documents' not in st.session_state:
    # Try to load from database on startup
    db = get_db()
    if db:
        st.session_state.processed_documents = db.load_session_state()
    else:
        st.session_state.processed_documents = []
if 'processing_logs' not in st.session_state:
    st.session_state.processing_logs = []
if 'batch_status' not in st.session_state:
    st.session_state.batch_status = None
if 'parallel_workers' not in st.session_state:
    st.session_state.parallel_workers = 4


def add_log(message: str, level: str = "info"):
    """Add a log entry to session state."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "level": level,
        "message": message
    }
    st.session_state.processing_logs.append(log_entry)


def sync_logs_from_processor():
    """Sync logs from parallel processor queue to session state."""
    messages = get_log_messages()
    for msg in messages:
        st.session_state.processing_logs.append(msg)


def check_already_processed(file_path: str) -> tuple:
    """
    Check if document is already processed and still valid.

    Returns:
        (is_processed, reason) tuple
    """
    db = get_db()
    if db is None:
        return False, 'no_db'

    return db.is_document_processed(file_path)


def run_parallel_processing(documents: list, workers: int):
    """
    Run parallel processing on documents.

    Args:
        documents: List of dicts with 'id' and 'file_path'
        workers: Number of parallel workers
    """
    db = get_db()

    # Create processor
    processor = ParallelProcessor(max_workers=workers)

    # Store processor in session for cancellation
    st.session_state.processor = processor

    # Define save function for cache database (legacy)
    def save_fn(**kwargs):
        if db:
            db.save_processed_document(**kwargs)

    # Define save function for full OCR results to normalized tables
    def save_full_results_fn(**kwargs):
        if db:
            db.save_full_ocr_results(**kwargs)

    # Define progress callback
    def progress_cb(status: BatchStatus):
        st.session_state.batch_status = status

    # Run processing
    results = processor.process_documents(
        documents=documents,
        check_processed_fn=check_already_processed if db else None,
        save_fn=save_fn,
        save_full_results_fn=save_full_results_fn,
        progress_callback=progress_cb
    )

    # Add successful results to session state
    for result_dict in processor.get_successful_results():
        # Check if already in session state
        existing_ids = [d.get('id') for d in st.session_state.processed_documents]
        if result_dict['id'] not in existing_ids:
            st.session_state.processed_documents.append(result_dict)

    return processor.get_status()


def main():
    """Process documents page"""

    st.title("⚙️ Process Documents")
    st.markdown("Parallel document processing with real-time progress tracking")

    if not MODULES_AVAILABLE:
        st.error(f"Required modules not available: {import_error}")
        return

    st.markdown("---")

    # Check if files are selected
    if not st.session_state.selected_files:
        st.warning("No documents selected for processing.")
        st.info("Please go to the Browse page to select documents.")

        # Show previously processed documents
        if st.session_state.processed_documents:
            st.markdown("---")
            st.subheader("📋 Previously Processed Documents")
            st.info(f"{len(st.session_state.processed_documents)} documents from previous sessions")

            if st.button("View Results →", type="primary"):
                st.switch_page("pages/3_📊_Results.py")

        if st.button("← Back to Browse"):
            st.switch_page("pages/1_📁_Browse.py")
        return

    # Selected files summary
    st.subheader("📋 Selected Documents")

    # Check how many are already processed
    already_processed = 0
    needs_reprocess = 0
    pending = 0

    for doc_id in st.session_state.selected_files:
        file_path = st.session_state.selected_file_paths.get(doc_id)
        if file_path:
            is_processed, reason = check_already_processed(file_path)
            if is_processed:
                already_processed += 1
            elif reason == 'file_changed':
                needs_reprocess += 1
            else:
                pending += 1
        else:
            pending += 1

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Selected", len(st.session_state.selected_files))
    with col2:
        st.metric("✅ Already Done", already_processed)
    with col3:
        st.metric("🔄 Modified", needs_reprocess)
    with col4:
        st.metric("⏳ Pending", pending)

    if already_processed > 0:
        st.info(f"ℹ️ {already_processed} documents are already processed and will be skipped.")

    st.markdown("---")

    # Processing Configuration
    st.subheader("⚡ Processing Configuration")

    col1, col2 = st.columns(2)

    with col1:
        workers = st.slider(
            "Parallel Workers",
            min_value=1,
            max_value=8,
            value=st.session_state.parallel_workers,
            help="Number of documents to process simultaneously. Higher = faster but uses more resources."
        )
        st.session_state.parallel_workers = workers

    with col2:
        # Show time estimate
        docs_to_process = pending + needs_reprocess
        if docs_to_process > 0:
            estimate = estimate_processing_time(
                num_documents=docs_to_process,
                max_workers=workers,
                avg_seconds_per_doc=15.0  # Real OCR processing time
            )
            st.metric(
                "Est. Time",
                f"{estimate['parallel_minutes']:.1f} min",
                delta=f"{estimate['speedup_factor']:.1f}x faster" if workers > 1 else None
            )

    st.markdown("---")

    # Control section
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        if st.session_state.processing_status == "running":
            st.info("⚙️ Processing in progress...")
        elif st.session_state.processing_status == "completed":
            st.success("✅ Processing completed!")
        elif st.session_state.processing_status == "cancelled":
            st.warning("⚠️ Processing cancelled by user")
        else:
            st.info("Ready to start processing")

    with col2:
        if st.session_state.processing_status != "running":
            if st.button("▶️ Start Processing", use_container_width=True, type="primary"):
                st.session_state.processing_status = "running"
                st.session_state.processing_logs = []
                st.session_state.batch_status = None
                add_log("=== Processing started ===", level="info")
                add_log(f"Workers: {workers}", level="info")
                if already_processed > 0:
                    add_log(f"ℹ️ {already_processed} documents will be skipped (already processed)", level="info")
                st.rerun()

    with col3:
        if st.session_state.processing_status == "running":
            if st.button("⏹️ Cancel", use_container_width=True):
                if 'processor' in st.session_state:
                    st.session_state.processor.cancel()
                st.session_state.processing_status = "cancelled"
                add_log("=== Processing cancelled by user ===", level="warning")
                # Save state on cancel
                db = get_db()
                if db:
                    db.save_session_state(st.session_state.processed_documents)
                st.rerun()

    with col4:
        if st.session_state.processing_status in ["completed", "cancelled"]:
            if st.button("💾 Save State", use_container_width=True):
                db = get_db()
                if db:
                    count = db.save_session_state(st.session_state.processed_documents)
                    st.success(f"Saved {count} documents!")
                else:
                    st.error("Database not available")

    st.markdown("---")

    # Processing execution
    if st.session_state.processing_status == "running":
        st.subheader("📊 Progress")

        # Prepare documents for processing
        documents = [
            {"id": doc_id, "file_path": st.session_state.selected_file_paths.get(doc_id)}
            for doc_id in st.session_state.selected_files
        ]

        # Run processing
        with st.spinner(f"Processing {len(documents)} documents with {workers} workers..."):
            final_status = run_parallel_processing(
                documents=documents,
                workers=workers
            )

        # Sync logs from processor
        sync_logs_from_processor()

        # Update status
        st.session_state.processing_status = "completed"
        st.session_state.batch_status = final_status

        # Auto-save on completion
        db = get_db()
        if db:
            count = db.save_session_state(st.session_state.processed_documents)
            add_log(f"💾 Auto-saved {count} documents to database", level="info")

        st.rerun()

    # Show batch status if available
    if st.session_state.batch_status:
        status = st.session_state.batch_status

        st.subheader("📊 Progress")

        # Progress bar
        progress = status.completed / status.total if status.total > 0 else 0
        st.progress(progress)

        # Statistics
        st.markdown("---")
        st.subheader("📈 Processing Statistics")

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total", status.total)
        with col2:
            st.metric("✅ Successful", status.successful)
        with col3:
            st.metric("❌ Failed", status.failed)
        with col4:
            st.metric("⏭️ Skipped", status.skipped)
        with col5:
            elapsed = status.elapsed_seconds
            st.metric("⏱️ Time", f"{elapsed:.1f}s")

    st.markdown("---")

    # Processing logs
    st.subheader("📝 Processing Logs")

    # Sync any remaining logs
    sync_logs_from_processor()

    with st.expander("View Logs", expanded=True):
        log_container = st.container()

        with log_container:
            if not st.session_state.processing_logs:
                st.info("No logs yet. Start processing to see logs.")
            else:
                # Display logs in reverse order (newest first)
                for log in reversed(st.session_state.processing_logs[-100:]):
                    timestamp = log['timestamp']
                    level = log['level']
                    message = log['message']

                    if level == "success":
                        st.success(f"[{timestamp}] {message}")
                    elif level == "warning":
                        st.warning(f"[{timestamp}] {message}")
                    elif level == "error":
                        st.error(f"[{timestamp}] {message}")
                    else:
                        st.text(f"[{timestamp}] {message}")

                if len(st.session_state.processing_logs) > 100:
                    st.caption(f"Showing last 100 of {len(st.session_state.processing_logs)} log entries")

    st.markdown("---")

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("← Back to Browse", use_container_width=True):
            st.switch_page("pages/1_📁_Browse.py")

    with col2:
        if st.session_state.processing_status in ["completed", "cancelled"]:
            if st.button("🔄 Process More", use_container_width=True):
                st.session_state.selected_files = []
                st.session_state.selected_file_paths = {}
                st.session_state.processing_status = None
                st.session_state.batch_status = None
                st.switch_page("pages/1_📁_Browse.py")

    with col3:
        if st.session_state.processed_documents:
            if st.button("View Results →", use_container_width=True, type="primary"):
                st.switch_page("pages/3_📊_Results.py")


if __name__ == "__main__":
    main()
