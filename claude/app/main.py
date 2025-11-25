"""
Main Dashboard for Thai Financial Document OCR Application

Entry point for the Streamlit application showing overview statistics
and quick actions.

INTEGRATED: Uses actual DatabaseManager and Scanner instead of mock data.
"""

import streamlit as st
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config
from app.database import DatabaseManager
from processing.scanner import scan_directory, DocumentInfo

# Page configuration
st.set_page_config(
    page_title="Thai OCR Prototype",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database manager (cached)
@st.cache_resource
def get_db():
    """Get or create DatabaseManager instance."""
    db = DatabaseManager()
    db.init_db()  # Creates tables if not exist
    return db

# Get real document data from Y67 folder (cached)
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_document_stats():
    """Scan Y67 folder and get document statistics."""
    try:
        y67_path = config.Y67_BASE_PATH
        if y67_path.exists():
            docs = scan_directory(str(y67_path))
            # Group by company
            companies = {}
            for doc in docs:
                key = (doc.company_code, doc.company_name)
                if key not in companies:
                    companies[key] = {"code": doc.company_code, "name": doc.company_name, "count": 0}
                companies[key]["count"] += 1
            return list(companies.values()), docs
        else:
            return [], []
    except Exception as e:
        st.warning(f"Could not scan Y67 folder: {e}")
        return [], []

# Initialize session state - load from database if empty
if 'selected_files' not in st.session_state:
    st.session_state.selected_files = []
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = None
if 'processed_documents' not in st.session_state:
    # Load processed documents from database on startup/refresh
    db = get_db()
    if db:
        st.session_state.processed_documents = db.load_session_state()
    else:
        st.session_state.processed_documents = []
if 'all_documents' not in st.session_state:
    st.session_state.all_documents = []

# Get actual data
db = get_db()
COMPANIES, ALL_DOCS = get_document_stats()

# Store documents in session state for other pages
if ALL_DOCS:
    st.session_state.all_documents = ALL_DOCS

def main():
    """Main dashboard page"""

    # Header
    st.title("📄 Thai Financial Document OCR")
    st.markdown("Process Thai financial PDFs with AI-powered OCR")

    # Add some spacing
    st.markdown("---")

    # Dashboard metrics
    st.subheader("📊 System Overview")
    col1, col2, col3, col4 = st.columns(4)

    total_docs = sum(company["count"] for company in COMPANIES) if COMPANIES else 0
    processed_docs = len(st.session_state.processed_documents)

    with col1:
        st.metric(
            label="Total Companies",
            value=len(COMPANIES),
            delta=None
        )

    with col2:
        st.metric(
            label="Total Documents",
            value=total_docs,
            delta=None
        )

    with col3:
        st.metric(
            label="Processed",
            value=processed_docs,
            delta=f"+{processed_docs}" if processed_docs > 0 else None
        )

    with col4:
        processing_rate = (processed_docs / total_docs * 100) if total_docs > 0 else 0
        st.metric(
            label="Progress",
            value=f"{processing_rate:.1f}%",
            delta=None
        )

    st.markdown("---")

    # Quick actions section
    st.subheader("⚡ Quick Actions")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("📁 Browse Documents", use_container_width=True):
            st.switch_page("pages/1_📁_Browse.py")
        st.caption("View and select documents")

    with col2:
        disabled = len(st.session_state.selected_files) == 0
        if st.button("⚙️ Start Processing", use_container_width=True, disabled=disabled):
            st.switch_page("pages/2_⚙️_Process.py")
        st.caption(f"{len(st.session_state.selected_files)} files")

    with col3:
        disabled = len(st.session_state.processed_documents) == 0
        if st.button("📊 View Results", use_container_width=True, disabled=disabled):
            st.switch_page("pages/3_📊_Results.py")
        st.caption(f"{len(st.session_state.processed_documents)} results")

    with col4:
        if st.button("🗄️ Manage Database", use_container_width=True):
            st.switch_page("pages/4_🗄️_Database.py")
        st.caption("Database management")

    with col5:
        if st.button("📖 Dictionary", use_container_width=True):
            st.switch_page("pages/6_📖_Dictionary.py")
        st.caption("Thai OCR dictionary")

    st.markdown("---")

    # Company list
    st.subheader("🏢 Companies")

    if not COMPANIES:
        st.warning("⚠️ No companies found. Make sure Y67 folder exists at: " + str(config.Y67_BASE_PATH))

    # Create a table-like view
    for company in COMPANIES:
        with st.expander(f"{company['name']} ({company['code']})"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**Company Code:** {company['code']}")
                st.write(f"**Total Documents:** {company['count']}")
            with col2:
                if st.button("Browse", key=f"browse_{company['code']}", use_container_width=True):
                    # Store selected company and navigate
                    st.session_state.filter_company = company['code']
                    st.switch_page("pages/1_📁_Browse.py")

    st.markdown("---")

    # Recent activity section
    st.subheader("📋 Recent Activity")

    if st.session_state.processed_documents:
        for doc in st.session_state.processed_documents[-5:]:  # Show last 5
            st.info(f"✅ Processed: {doc.get('filename', 'Unknown')} at {doc.get('timestamp', 'N/A')}")
    else:
        st.info("No recent activity. Start by browsing and selecting documents to process.")

    # Footer
    st.markdown("---")
    st.caption(f"Thai Financial Document OCR Prototype v0.1.0 | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
