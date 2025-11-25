"""
Browse Documents Page

File browser with filtering capabilities for selecting documents to process.
Shows processing status and detects modified documents.
"""

import streamlit as st
import os
from datetime import datetime
from pathlib import Path

st.set_page_config(
    page_title="Browse Documents",
    page_icon="📁",
    layout="wide"
)

# Import database and scanner
try:
    from app.database import DatabaseManager
    from app.config import config
    from processing.scanner import scan_directory, DocumentInfo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# Initialize session state
if 'selected_files' not in st.session_state:
    st.session_state.selected_files = []
if 'filter_company' not in st.session_state:
    st.session_state.filter_company = "All"
if 'filter_year' not in st.session_state:
    st.session_state.filter_year = "All"
if 'filter_types' not in st.session_state:
    st.session_state.filter_types = []
if 'filter_status' not in st.session_state:
    st.session_state.filter_status = "All"


@st.cache_resource
def get_db():
    """Get database manager instance."""
    if not DB_AVAILABLE:
        return None
    db = DatabaseManager()
    db.init_db()
    return db


@st.cache_data(ttl=60)
def get_processed_status():
    """Get processed document status from database."""
    db = get_db()
    if db is None:
        return {}
    try:
        return db.get_processed_file_paths()
    except Exception:
        return {}


@st.cache_data(ttl=300)
def scan_documents():
    """Scan Y67 folder for documents."""
    if not DB_AVAILABLE:
        return []

    try:
        y67_path = config.Y67_BASE_PATH
        if not y67_path.exists():
            return []

        docs = scan_directory(str(y67_path))
        return docs
    except Exception:
        return []


def get_document_list():
    """Get document list with processing status."""
    scanned_docs = scan_documents()
    processed_status = get_processed_status()

    documents = []
    for doc in scanned_docs:
        file_path = str(doc.file_path)

        # Check processing status
        if file_path in processed_status:
            status_info = processed_status[file_path]
            if status_info['is_valid']:
                status = 'processed'
            elif status_info['validity_reason'] == 'file_changed':
                status = 'modified'  # File changed since processing
            else:
                status = 'pending'
        else:
            status = 'pending'

        documents.append({
            "id": f"{doc.company_code}_{doc.fiscal_year}_{doc.document_type}",
            "filename": doc.file_path.name,
            "company_code": doc.company_code,
            "company_name": doc.company_code,  # Could map to actual name
            "year": doc.fiscal_year,
            "type": doc.document_type,
            "size": f"{doc.file_size / 1024 / 1024:.1f} MB" if doc.file_size else "N/A",
            "status": status,
            "path": file_path,
            "file_path": file_path
        })

    return documents


def apply_filters(documents):
    """Apply current filters to document list"""
    filtered = documents

    # Company filter
    if st.session_state.filter_company != "All":
        filtered = [d for d in filtered if d['company_code'] == st.session_state.filter_company]

    # Year filter
    if st.session_state.filter_year != "All":
        filtered = [d for d in filtered if str(d['year']) == st.session_state.filter_year]

    # Type filter
    if st.session_state.filter_types:
        filtered = [d for d in filtered if d['type'] in st.session_state.filter_types]

    # Status filter
    if st.session_state.filter_status != "All":
        filtered = [d for d in filtered if d['status'] == st.session_state.filter_status]

    return filtered


def main():
    """Browse documents page"""

    st.title("📁 Browse Documents")
    st.markdown("Filter and select documents for processing")

    st.markdown("---")

    # Get documents
    all_documents = get_document_list()

    if not all_documents:
        st.warning("No documents found in Y67 folder.")
        st.info("Make sure the Y67 folder exists with PDF documents.")
        if st.button("← Back to Dashboard"):
            st.switch_page("app/main.py")
        return

    # Extract unique values for filters
    companies = sorted(set(d['company_code'] for d in all_documents))
    years = sorted(set(str(d['year']) for d in all_documents), reverse=True)
    doc_types = sorted(set(d['type'] for d in all_documents))

    # Processing status summary
    processed_count = len([d for d in all_documents if d['status'] == 'processed'])
    modified_count = len([d for d in all_documents if d['status'] == 'modified'])
    pending_count = len([d for d in all_documents if d['status'] == 'pending'])

    # Status summary cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Documents", len(all_documents))
    with col2:
        st.metric("✅ Processed", processed_count)
    with col3:
        st.metric("🔄 Modified", modified_count, help="Files changed since last processing")
    with col4:
        st.metric("⏳ Pending", pending_count)

    st.markdown("---")

    # Filters section
    st.subheader("🔍 Filters")

    col1, col2, col3, col4, col5 = st.columns([2, 1, 1.5, 1, 1])

    with col1:
        company_options = ["All"] + companies
        selected_company = st.selectbox(
            "Company",
            options=company_options,
            index=0,
            key="company_selector"
        )
        st.session_state.filter_company = selected_company if selected_company != "All" else "All"

    with col2:
        year_options = ["All"] + years
        st.session_state.filter_year = st.selectbox(
            "Fiscal Year",
            options=year_options,
            key="year_selector"
        )

    with col3:
        st.session_state.filter_types = st.multiselect(
            "Document Type",
            options=doc_types,
            key="type_selector"
        )

    with col4:
        status_options = ["All", "pending", "processed", "modified"]
        st.session_state.filter_status = st.selectbox(
            "Status",
            options=status_options,
            format_func=lambda x: {"All": "All", "pending": "⏳ Pending", "processed": "✅ Processed", "modified": "🔄 Modified"}.get(x, x),
            key="status_selector"
        )

    with col5:
        st.markdown("&nbsp;")  # Spacing
        if st.button("Clear Filters", use_container_width=True):
            st.session_state.filter_company = "All"
            st.session_state.filter_year = "All"
            st.session_state.filter_types = []
            st.session_state.filter_status = "All"
            st.rerun()

    st.markdown("---")

    # Apply filters
    filtered_docs = apply_filters(all_documents)

    # Document list section
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.subheader(f"📄 Documents ({len(filtered_docs)})")
    with col2:
        if st.button(f"Select Pending ({len([d for d in filtered_docs if d['status'] != 'processed'])})", use_container_width=True):
            st.session_state.selected_files = [doc['id'] for doc in filtered_docs if doc['status'] != 'processed']
            st.rerun()
    with col3:
        if st.button(f"Select All ({len(filtered_docs)})", use_container_width=True):
            st.session_state.selected_files = [doc['id'] for doc in filtered_docs]
            st.rerun()

    # Selection summary
    if st.session_state.selected_files:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.info(f"✅ {len(st.session_state.selected_files)} documents selected")
        with col2:
            if st.button("Clear Selection", use_container_width=True):
                st.session_state.selected_files = []
                st.rerun()
        with col3:
            if st.button("Process Selected", use_container_width=True, type="primary"):
                # Store file paths for processing
                st.session_state.selected_file_paths = {
                    doc['id']: doc['file_path']
                    for doc in filtered_docs
                    if doc['id'] in st.session_state.selected_files
                }
                st.switch_page("pages/2_⚙️_Process.py")

    st.markdown("---")

    # Document table
    if not filtered_docs:
        st.warning("No documents match the current filters.")
    else:
        # Create table header
        col1, col2, col3, col4, col5, col6 = st.columns([0.5, 2, 1, 1.5, 1, 1])
        with col1:
            st.markdown("**Select**")
        with col2:
            st.markdown("**Company**")
        with col3:
            st.markdown("**Year**")
        with col4:
            st.markdown("**Type**")
        with col5:
            st.markdown("**Status**")
        with col6:
            st.markdown("**Actions**")

        st.markdown("---")

        # Display documents
        for idx, doc in enumerate(filtered_docs[:50]):  # Limit display for performance
            col1, col2, col3, col4, col5, col6 = st.columns([0.5, 2, 1, 1.5, 1, 1])

            with col1:
                is_selected = doc['id'] in st.session_state.selected_files
                if st.checkbox("", value=is_selected, key=f"check_{doc['id']}", label_visibility="collapsed"):
                    if doc['id'] not in st.session_state.selected_files:
                        st.session_state.selected_files.append(doc['id'])
                else:
                    if doc['id'] in st.session_state.selected_files:
                        st.session_state.selected_files.remove(doc['id'])

            with col2:
                company_display = doc['company_code']
                st.text(company_display[:25] + "..." if len(company_display) > 25 else company_display)

            with col3:
                st.text(str(doc['year']))

            with col4:
                st.text(doc['type'])

            with col5:
                if doc['status'] == 'pending':
                    st.markdown("⏳ Pending")
                elif doc['status'] == 'processed':
                    st.markdown("✅ Done")
                elif doc['status'] == 'modified':
                    st.markdown("🔄 Modified")
                else:
                    st.markdown("❌ Error")

            with col6:
                if st.button("Details", key=f"detail_{doc['id']}", use_container_width=True):
                    st.session_state.viewing_doc = doc['id']

            # Show details if expanded
            if hasattr(st.session_state, 'viewing_doc') and st.session_state.viewing_doc == doc['id']:
                with st.expander("Document Details", expanded=True):
                    detail_col1, detail_col2 = st.columns(2)
                    with detail_col1:
                        st.write(f"**Filename:** {doc['filename']}")
                        st.write(f"**Company Code:** {doc['company_code']}")
                        st.write(f"**Size:** {doc['size']}")
                    with detail_col2:
                        st.write(f"**Year:** {doc['year']}")
                        st.write(f"**Type:** {doc['type']}")
                        st.write(f"**Status:** {doc['status']}")
                        st.write(f"**Path:** {doc['path']}")

                    if st.button("Close Details", key=f"close_{doc['id']}"):
                        del st.session_state.viewing_doc
                        st.rerun()

        if len(filtered_docs) > 50:
            st.info(f"Showing 50 of {len(filtered_docs)} documents. Use filters to narrow results.")

    # Footer with action buttons
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("← Back to Dashboard", use_container_width=True):
            st.switch_page("app/main.py")

    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with col3:
        disabled = len(st.session_state.selected_files) == 0
        if st.button("Process Selected →", use_container_width=True, type="primary", disabled=disabled):
            # Store file paths for processing
            st.session_state.selected_file_paths = {
                doc['id']: doc['file_path']
                for doc in filtered_docs
                if doc['id'] in st.session_state.selected_files
            }
            st.switch_page("pages/2_⚙️_Process.py")

if __name__ == "__main__":
    main()
