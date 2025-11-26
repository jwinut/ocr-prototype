"""
Database Management Page

View and manage processed documents and database state.
"""

import streamlit as st
from datetime import datetime
import os

st.set_page_config(
    page_title="Database Management",
    page_icon="🗄️",
    layout="wide"
)

# Import database
try:
    from app.database import DatabaseManager
    from app.config import config
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


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes is None:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_timestamp(dt) -> str:
    """Format datetime for display."""
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def main():
    """Database management page."""

    st.title("🗄️ Database Management")
    st.markdown("Manage processed documents and database state")

    if not MODULES_AVAILABLE:
        st.error(f"Required modules not available: {import_error}")
        return

    db = get_db()
    if not db:
        st.error("Database not available")
        return

    st.markdown("---")

    # Database Statistics
    st.subheader("📊 Database Statistics")

    # Get all processed documents (replaces get_all_cached_documents)
    processed_docs = db.get_processed_documents()
    valid_count = 0
    invalid_count = 0
    total_size = 0

    # Group by engine for display
    engines = {}
    for doc in processed_docs:
        engine = doc.engine or "unknown"
        if engine not in engines:
            engines[engine] = 0
        engines[engine] += 1

        is_valid, _ = db.is_document_processed(doc.file_path, engine=doc.engine)
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
        if doc.file_size_bytes:
            total_size += doc.file_size_bytes

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Processed", len(processed_docs))
    with col2:
        st.metric("✅ Valid", valid_count)
    with col3:
        st.metric("⚠️ Invalid", invalid_count)
    with col4:
        st.metric("📦 Total Size", format_file_size(total_size))

    # Show engine breakdown
    if engines:
        st.caption(f"By engine: {', '.join([f'{k}: {v}' for k, v in engines.items()])}")

    st.markdown("---")

    # Quick Actions
    st.subheader("⚡ Quick Actions")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_resource.clear()
            st.rerun()

    with col2:
        if st.button("💾 Save Session", use_container_width=True):
            if 'processed_documents' in st.session_state:
                count = db.save_session_state(st.session_state.processed_documents)
                st.success(f"Saved {count} documents!")
            else:
                st.info("No session documents to save")

    with col3:
        if st.button("🧹 Clear Invalid", use_container_width=True, type="secondary"):
            removed = 0
            for doc in processed_docs:
                is_valid, _ = db.is_document_processed(doc.file_path, engine=doc.engine)
                if not is_valid:
                    db.delete_document(doc.id)
                    removed += 1
            if removed > 0:
                st.success(f"Removed {removed} invalid entries")
                st.rerun()
            else:
                st.info("No invalid entries to remove")

    with col4:
        # Dangerous action - requires confirmation
        if 'confirm_clear_all' not in st.session_state:
            st.session_state.confirm_clear_all = False

        if st.session_state.confirm_clear_all:
            st.warning("Are you sure? This will delete ALL documents from the database.")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Yes, Clear All", type="primary", use_container_width=True):
                    # Delete all processed documents using efficient bulk delete
                    count = db.clear_all_documents()
                    # Also clear session state
                    st.session_state.processed_documents = []
                    st.session_state.confirm_clear_all = False
                    st.success(f"Cleared {count} documents from database!")
                    st.rerun()
            with col_no:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.confirm_clear_all = False
                    st.rerun()
        else:
            if st.button("🗑️ Clear All", use_container_width=True, type="secondary"):
                st.session_state.confirm_clear_all = True
                st.rerun()

    st.markdown("---")

    # Processed Documents Table
    st.subheader("📋 Processed Documents")

    if not processed_docs:
        st.info("No processed documents. Process some documents to see them here.")
    else:
        # Filter options
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            filter_status = st.selectbox(
                "Filter by Status",
                ["All", "Valid Only", "Invalid Only"]
            )
        with col2:
            engine_options = ["All"] + list(engines.keys())
            filter_engine = st.selectbox(
                "Filter by Engine",
                engine_options
            )

        # Build table data
        table_data = []
        for doc in processed_docs:
            is_valid, reason = db.is_document_processed(doc.file_path, engine=doc.engine)

            # Apply filters
            if filter_status == "Valid Only" and not is_valid:
                continue
            if filter_status == "Invalid Only" and is_valid:
                continue
            if filter_engine != "All" and doc.engine != filter_engine:
                continue

            table_data.append({
                "id": doc.id,
                "file_path": doc.file_path,
                "filename": doc.file_name,
                "engine": doc.engine or "unknown",
                "status": "✅ Valid" if is_valid else f"⚠️ {reason}",
                "tables": doc.tables_found or 0,
                "text_blocks": doc.text_blocks or 0,
                "size": format_file_size(doc.file_size_bytes),
                "processed_at": format_timestamp(doc.processed_at),
                "is_valid": is_valid
            })

        if not table_data:
            st.info(f"No documents match the current filters")
        else:
            # Display as expandable list for better control
            st.caption(f"Showing {len(table_data)} documents")

            # Select all / none
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("Select All", use_container_width=True):
                    st.session_state.selected_for_delete = [d["id"] for d in table_data]
                    st.rerun()
            with col2:
                if st.button("Select None", use_container_width=True):
                    st.session_state.selected_for_delete = []
                    st.rerun()

            # Initialize selection state
            if 'selected_for_delete' not in st.session_state:
                st.session_state.selected_for_delete = []

            # Display documents
            for doc in table_data:
                with st.container():
                    col1, col2, col3, col4, col5, col6 = st.columns([0.5, 2.5, 1, 1, 1, 1])

                    with col1:
                        is_selected = st.checkbox(
                            "Select",
                            value=doc["id"] in st.session_state.selected_for_delete,
                            key=f"select_{doc['id']}",
                            label_visibility="collapsed"
                        )
                        if is_selected and doc["id"] not in st.session_state.selected_for_delete:
                            st.session_state.selected_for_delete.append(doc["id"])
                        elif not is_selected and doc["id"] in st.session_state.selected_for_delete:
                            st.session_state.selected_for_delete.remove(doc["id"])

                    with col2:
                        st.text(doc["filename"])
                        st.caption(doc["file_path"])

                    with col3:
                        engine_icon = "🔧" if doc["engine"] == "docling" else "🌊"
                        st.text(f"{engine_icon} {doc['engine']}")

                    with col4:
                        st.text(doc["status"])

                    with col5:
                        st.text(f"📊 {doc['tables']} tables")

                    with col6:
                        st.text(doc["processed_at"])

                    st.divider()

            # Bulk delete action
            if st.session_state.selected_for_delete:
                st.warning(f"{len(st.session_state.selected_for_delete)} documents selected")

                if st.button(f"🗑️ Delete Selected ({len(st.session_state.selected_for_delete)})", type="primary"):
                    deleted = 0
                    for doc_id in st.session_state.selected_for_delete:
                        if db.delete_document(doc_id):
                            deleted += 1

                    # Also remove from session state if present
                    if 'processed_documents' in st.session_state:
                        deleted_file_paths = [
                            doc["file_path"] for doc in table_data
                            if doc["id"] in st.session_state.selected_for_delete
                        ]
                        st.session_state.processed_documents = [
                            d for d in st.session_state.processed_documents
                            if d.get('file_path') not in deleted_file_paths
                        ]

                    st.session_state.selected_for_delete = []
                    st.success(f"Deleted {deleted} documents")
                    st.rerun()

    st.markdown("---")

    # Session State Info
    st.subheader("📝 Current Session State")

    col1, col2 = st.columns(2)

    with col1:
        session_docs = st.session_state.get('processed_documents', [])
        st.metric("Session Documents", len(session_docs))

        if session_docs:
            with st.expander("View Session Documents"):
                for doc in session_docs:
                    st.text(f"• {doc.get('filename', 'Unknown')}")

    with col2:
        selected_files = st.session_state.get('selected_files', [])
        st.metric("Selected for Processing", len(selected_files))

        if selected_files:
            with st.expander("View Selected Files"):
                for file_id in selected_files[:10]:  # Show first 10
                    st.text(f"• {file_id}")
                if len(selected_files) > 10:
                    st.caption(f"... and {len(selected_files) - 10} more")

    # Clear session state
    st.markdown("---")
    st.subheader("🔄 Session Management")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Clear Selection", use_container_width=True):
            st.session_state.selected_files = []
            st.session_state.selected_file_paths = {}
            st.success("Selection cleared")
            st.rerun()

    with col2:
        if st.button("Clear Processing State", use_container_width=True):
            st.session_state.processing_status = None
            st.session_state.batch_status = None
            st.session_state.processing_logs = []
            st.success("Processing state cleared")
            st.rerun()

    with col3:
        if st.button("Reset All Session", use_container_width=True, type="secondary"):
            # Clear all relevant session state
            keys_to_clear = [
                'selected_files', 'selected_file_paths', 'processing_status',
                'processed_documents', 'processing_logs', 'batch_status',
                'selected_for_delete', 'confirm_clear_all'
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.success("Session reset")
            st.rerun()

    st.markdown("---")

    # Navigation
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("← Back to Browse", use_container_width=True):
            st.switch_page("pages/1_📁_Browse.py")

    with col2:
        if st.button("⚙️ Process Documents", use_container_width=True):
            st.switch_page("pages/2_⚙️_Process.py")

    with col3:
        if st.button("📊 View Results", use_container_width=True):
            st.switch_page("pages/3_📊_Results.py")


if __name__ == "__main__":
    main()
