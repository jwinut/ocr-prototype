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
if 'processing_thread' not in st.session_state:
    st.session_state.processing_thread = None
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
    st.session_state.parallel_workers = 1
if 'selected_engines' not in st.session_state:
    st.session_state.selected_engines = ["docling"]
# Ensure logs list exists before any background thread uses it
if 'processing_logs' not in st.session_state:
    st.session_state.processing_logs = []
if 'processed_documents' not in st.session_state:
    # Try to load from DB for consistency
    db = get_db()
    st.session_state.processed_documents = db.load_session_state() if db else []


def add_log(message: str, level: str = "info"):
    """Add a log entry; safe for background threads (falls back to shared queue)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "level": level,
        "message": message
    }
    try:
        st.session_state.processing_logs.append(log_entry)
    except Exception:
        try:
            from processing.parallel import add_log_message as _add_log_message
            _add_log_message(message, level)
        except Exception:
            pass


def sync_logs_from_processor():
    """Sync logs from parallel processor queue to session state."""
    messages = get_log_messages()
    for msg in messages:
        st.session_state.processing_logs.append(msg)


def check_already_processed(file_path: str, engine: str = "docling") -> tuple:
    """
    Check if document is already processed and still valid for a specific engine.

    Args:
        file_path: Path to the document
        engine: OCR engine to check (docling or typhoon)

    Returns:
        (is_processed, reason) tuple
    """
    db = get_db()
    if db is None:
        return False, 'no_db'

    return db.is_document_processed(file_path, engine=engine)


def run_parallel_processing(documents: list, workers: int, engines_override: list | None = None):
    """
    Run parallel processing on documents for one or more engines.

    Args:
        documents: List of dicts with 'id' and 'file_path'
        workers: Number of parallel workers
    """
    db = get_db()

    selected_engines = engines_override or st.session_state.get('selected_engines', ['docling'])

    if not selected_engines:
        add_log("No engines selected; skipping processing.", level="warning")
        return None

    last_status = None

    for current_engine in selected_engines:
        add_log(f"=== Starting engine: {current_engine.upper()} ===", level="info")

        # Force single worker for Typhoon to respect rate limits and Streamlit context
        effective_workers = 1 if current_engine == "typhoon" else workers

        # Create processor per engine run
        processor = ParallelProcessor(max_workers=effective_workers)
        st.session_state.processor = processor  # for cancellation support

        # Define check function with engine captured in closure
        def check_processed_with_engine(file_path: str, engine=current_engine) -> tuple:
            """Check if document is processed for the captured engine."""
            return check_already_processed(file_path, engine=engine)

        # Define save function for full OCR results to database
        def save_full_results_fn(**kwargs):
            if db:
                try:
                    db.save_full_ocr_results(**kwargs)
                except Exception as e:
                    import traceback
                    print(f"ERROR in save_full_results_fn: {e}")
                    print(traceback.format_exc())
                    raise  # Re-raise so parallel.py can log it too

        # Define progress callback
        def progress_cb(status: BatchStatus):
            st.session_state.batch_status = status

        # Run processing
        results = processor.process_documents(
            documents=documents,
            engine=current_engine,
            check_processed_fn=check_processed_with_engine if db else None,
            save_full_results_fn=save_full_results_fn,
            progress_callback=progress_cb  # Force reload
        )

        # Add successful results to session state
        for result_dict in processor.get_successful_results():
            existing_ids = [d.get('id') for d in st.session_state.processed_documents]
            if result_dict['id'] not in existing_ids:
                st.session_state.processed_documents.append(result_dict)

        last_status = processor.get_status()

    return last_status


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

    # Check how many are already processed across selected engines
    already_processed = 0
    needs_reprocess = 0
    pending = 0
    selected_engines = st.session_state.get('selected_engines', ['docling'])

    if not selected_engines:
        pending = len(st.session_state.selected_files)
        st.warning("Select at least one engine to process.")
    else:
        for doc_id in st.session_state.selected_files:
            file_path = st.session_state.selected_file_paths.get(doc_id)
            if not file_path:
                pending += 1
                continue

            per_engine_status = []
            for eng in selected_engines:
                is_processed, reason = check_already_processed(file_path, engine=eng)
                per_engine_status.append((is_processed, reason))

            if per_engine_status and all(flag for flag, _ in per_engine_status):
                already_processed += 1
            elif any(reason == 'file_changed' for _, reason in per_engine_status):
                needs_reprocess += 1
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

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**OCR Engines**")
        docling_checked = st.checkbox("🔧 Docling (Local)", value="docling" in st.session_state.selected_engines)
        typhoon_checked = st.checkbox("🌊 Typhoon (Cloud API)", value="typhoon" in st.session_state.selected_engines)

        new_engines = []
        if docling_checked:
            new_engines.append("docling")
        if typhoon_checked:
            new_engines.append("typhoon")

        if not new_engines:
            st.warning("Select at least one engine.")
        if new_engines != st.session_state.selected_engines:
            st.session_state.selected_engines = new_engines
            st.rerun()

    with col2:
        worker_options = [1, 2, 3]
        current_workers = st.session_state.parallel_workers
        if current_workers not in worker_options:
            current_workers = 1
        typhoon_only = st.session_state.get('selected_engines', ['docling']) == ['typhoon']
        if typhoon_only:
            st.info("Typhoon uses 1 worker due to rate limits.")
            workers = 1
            st.session_state.parallel_workers = 1
        else:
            workers = st.selectbox(
                "Parallel Workers",
                options=worker_options,
                index=worker_options.index(current_workers),
                help="Number of documents to process simultaneously. Default: 1 (sequential)."
            )
            st.session_state.parallel_workers = workers

    with col3:
        # Show time estimate (per-engine total)
        docs_to_process = pending + needs_reprocess
        engines_to_run = st.session_state.get('selected_engines', ['docling'])
        total_tasks = docs_to_process * max(1, len(engines_to_run))
        if docs_to_process > 0 and engines_to_run:
            # Rough per-engine averages
            per_engine_time = []
            for eng in engines_to_run:
                per_engine_time.append(15.0 if eng == "docling" else 8.0)
            avg_time = sum(per_engine_time) / len(per_engine_time)
            estimate = estimate_processing_time(
                num_documents=total_tasks,
                max_workers=workers if 'typhoon' not in engines_to_run else 1,
                avg_seconds_per_doc=avg_time
            )
            st.metric(
                "Est. Time",
                f"{estimate['parallel_minutes']:.1f} min",
                delta=f"{estimate['speedup_factor']:.1f}x faster" if workers > 1 and 'typhoon' not in engines_to_run else None
            )
            if 'typhoon' in engines_to_run:
                st.caption("Typhoon runs sequentially (rate-limited).")

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
        engines_selected = st.session_state.get('selected_engines', [])
        if st.session_state.processing_status != "running":
            if st.button(
                "▶️ Start Processing",
                use_container_width=True,
                type="primary",
                disabled=not engines_selected
            ):
                st.session_state.processing_status = "running"
                st.session_state.processing_logs = []
                st.session_state.batch_status = None
                st.session_state.processing_thread = None
                engines = st.session_state.get('selected_engines', ['docling'])
                add_log("=== Processing started ===", level="info")
                add_log(f"Engines: {', '.join([e.upper() for e in engines])}", level="info")
                add_log(f"Workers: {workers if 'typhoon' not in engines else 1} (Typhoon forces 1 worker)", level="info")
                if already_processed > 0:
                    add_log(f"ℹ️ {already_processed} documents will be skipped (already processed for selected engines)", level="info")
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

    # Prepare documents list once
    documents = [
        {"id": doc_id, "file_path": st.session_state.selected_file_paths.get(doc_id)}
        for doc_id in st.session_state.selected_files
    ]

    # Show live/last-known progress while a run is active
    is_running = (
        st.session_state.processing_status == "running"
        or (st.session_state.batch_status and st.session_state.batch_status.is_running)
        or (st.session_state.processing_thread is not None)
    )
    if is_running:
        st.subheader("📊 Progress")
        sync_logs_from_processor()

        # Ensure we always have a status object while running (survives reruns)
        if st.session_state.batch_status is None and documents:
            st.session_state.batch_status = BatchStatus(total=len(documents))
            st.session_state.batch_status.is_running = True

        status = st.session_state.batch_status
        if status:
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

            if status.is_running:
                st.caption("Processing... refresh to update progress")
        else:
            st.info("Initializing...")

    # Kick off processing (in main thread for Typhoon-only, thread otherwise)
    if st.session_state.processing_status == "running" and st.session_state.processing_thread is None:
        engines_snapshot = st.session_state.get('selected_engines', ['docling'])

        # Initialize a visible batch status so UI isn't stuck at "Initializing"
        if documents:
            st.session_state.batch_status = BatchStatus(total=len(documents))
            st.session_state.batch_status.is_running = True

        def do_work():
            final_status = run_parallel_processing(documents=documents, workers=workers, engines_override=engines_snapshot)
            st.session_state.batch_status = final_status
            st.session_state.processing_status = "completed"
            # Auto-save on completion
            db = get_db()
            if db:
                try:
                    count = db.save_session_state(st.session_state.processed_documents)
                    add_log(f"💾 Auto-saved {count} documents to database", level="info")
                except Exception:
                    pass

        import threading
        from streamlit.runtime.scriptrunner import add_script_run_ctx
        t = threading.Thread(target=do_work, daemon=True)
        add_script_run_ctx(t)
        st.session_state.processing_thread = t
        t.start()

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
