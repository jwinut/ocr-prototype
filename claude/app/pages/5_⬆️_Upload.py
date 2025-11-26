"""
Upload Documents Page

Upload new PDF documents with validation and organization.
"""

import streamlit as st
from datetime import datetime
import os
from pathlib import Path

st.set_page_config(
    page_title="Upload Documents",
    page_icon="⬆️",
    layout="wide"
)

try:
    from app.database import DatabaseManager
    from app.config import config
    from models.schema import DocumentStatus
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

def validate_file(file):
    """Validate uploaded file"""
    errors = []

    # Check file type
    if not file.name.lower().endswith('.pdf'):
        errors.append(f"❌ {file.name}: Not a PDF file")

    # Check file size (max 50MB)
    max_size = 50 * 1024 * 1024  # 50MB in bytes
    if file.size > max_size:
        errors.append(f"❌ {file.name}: File size exceeds 50MB ({file.size / 1024 / 1024:.1f}MB)")

    return errors

def format_file_size(size_bytes):
    """Format file size in human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 / 1024:.1f} MB"

def main():
    """Upload documents page"""

    st.title("⬆️ Upload Documents")
    st.markdown("Upload new Thai financial PDF documents")

    st.markdown("---")

    if not DB_AVAILABLE:
        st.error("Database modules not available. Upload disabled.")
        return

    db = DatabaseManager()
    db.init_db()

    # Load companies and years from DB
    companies = db.get_all_companies()
    company_map = {c.company_code: c for c in companies}
    company_options = [f"{c.company_code} - {c.name_th or c.name_en or 'Unknown'}" for c in companies]
    company_options.append("➕ New company")

    fiscal_years = []
    for c in companies:
        fiscal_years.extend([fy.year_be for fy in db.get_fiscal_years_by_company(c.id)])
    fiscal_years = sorted(set(fiscal_years), reverse=True)
    if not fiscal_years:
        current_be = datetime.now().year + 543
        fiscal_years = [current_be]

    document_types = list(config.VALID_DOCUMENT_TYPES) + ["Unknown"]

    # Upload section
    st.subheader("📤 Select Files")

    uploaded_files = st.file_uploader(
        "Choose PDF files to upload",
        type=['pdf'],
        accept_multiple_files=True,
        help="Select one or more PDF files. Maximum file size: 50MB per file."
    )

    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} file(s) selected")

        # Validate files
        all_errors = []
        valid_files = []

        for file in uploaded_files:
            errors = validate_file(file)
            if errors:
                all_errors.extend(errors)
            else:
                valid_files.append(file)

        # Show validation errors
        if all_errors:
            st.warning("⚠️ Some files have validation errors:")
            for error in all_errors:
                st.error(error)

        # Show valid files
        if valid_files:
            st.markdown("---")
            st.subheader(f"✅ Valid Files ({len(valid_files)})")

            # Preview files in a table
            for idx, file in enumerate(valid_files):
                with st.expander(f"📄 {file.name}", expanded=idx == 0):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Filename:** {file.name}")
                        st.write(f"**Size:** {format_file_size(file.size)}")
                        st.write(f"**Type:** PDF Document")
                    with col2:
                        # File preview would go here
                        st.info("File preview available after upload")

            st.markdown("---")

            # Organization section
            st.subheader("📁 Organization")
            st.markdown("Specify where to store these documents")

            col1, col2, col3 = st.columns(3)

            with col1:
                selected_company = st.selectbox(
                    "Company *",
                    options=company_options,
                    help="Select the company these documents belong to"
                )
                new_company_name = ""
                if selected_company == "➕ New company":
                    new_company_name = st.text_input("New company name (TH or EN)")
                    new_company_code = st.text_input("New company code")
            with col2:
                selected_year = st.selectbox(
                    "Fiscal Year (BE) *",
                    options=fiscal_years,
                    index=0,
                    help="Select the fiscal year (B.E.)"
                )

            with col3:
                selected_type = st.selectbox(
                    "Document Type *",
                    options=document_types,
                    help="Select the type of document"
                )

            # Additional options
            st.markdown("---")
            st.subheader("⚙️ Upload Options")

            col1, col2 = st.columns(2)

            with col1:
                process_after = st.checkbox(
                    "Process documents after upload",
                    value=True,
                    help="Automatically start processing after upload completes"
                )

            with col2:
                overwrite = st.checkbox(
                    "Overwrite existing files",
                    value=False,
                    help="Replace files if they already exist"
                )

            # Upload button
            st.markdown("---")

            col1, col2, col3 = st.columns([2, 1, 1])

            with col2:
                if st.button("Cancel", use_container_width=True):
                    st.rerun()

            with col3:
                if st.button("🚀 Upload Files", use_container_width=True, type="primary"):
                    # Simulate upload process
                    st.session_state.upload_progress = 0

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for idx, file in enumerate(valid_files):
                        status_text.info(f"Uploading {file.name}...")

                        # Resolve company/fiscal year
                        if selected_company == "➕ New company":
                            if not new_company_name or not new_company_code:
                                st.error("Please provide new company name and code.")
                                break
                            company = db.get_or_create_company(
                                company_code=new_company_code,
                                name_th=new_company_name
                            )
                        else:
                            company_code = selected_company.split(" - ")[0]
                            existing = company_map.get(company_code)
                            if not existing:
                                st.error(f"Company {company_code} not found in database.")
                                break
                            company = db.get_or_create_company(
                                company_code=existing.company_code,
                                name_th=existing.name_th,
                                name_en=existing.name_en
                            )

                        fiscal_year = db.get_or_create_fiscal_year(company_id=company.id, year_be=int(selected_year))

                        # Save file to uploads directory
                        uploads_root = config.PROJECT_ROOT / "uploads"
                        uploads_root.mkdir(parents=True, exist_ok=True)
                        company_dir = uploads_root / company.company_code / str(selected_year)
                        company_dir.mkdir(parents=True, exist_ok=True)
                        dest_path = company_dir / file.name

                        if dest_path.exists() and not overwrite:
                            st.warning(f"Skipping {file.name} (exists and overwrite is off)")
                            continue

                        with open(dest_path, "wb") as f:
                            f.write(file.getbuffer())

                        # Create or update Document entry (engine-specific handled during processing)
                        from models.schema import DocumentStatus
                        db.create_document(
                            fiscal_year_id=fiscal_year.id,
                            document_type=selected_type,
                            file_path=str(dest_path),
                            file_name=file.name,
                            status=DocumentStatus.PENDING,
                            file_size_bytes=file.size
                        )

                        # Update progress
                        st.session_state.upload_progress = (idx + 1) / len(valid_files)
                        progress_bar.progress(st.session_state.upload_progress)

                    status_text.empty()
                    progress_bar.empty()

                    # Success message
                    st.success(f"✅ Successfully uploaded {len(valid_files)} file(s)!")

                    # Show upload summary
                    st.info(f"""
                    **Upload Summary:**
                    - Company: {company_code}
                    - Year: {selected_year}
                    - Type: {selected_type}
                    - Files: {len(valid_files)}
                    - Total Size: {format_file_size(sum(f.size for f in valid_files))}
                    """)

                    # Process after upload option
                    if process_after:
                        st.info("🔄 Preparing to process uploaded documents...")
                        # Fetch recently added docs for this company/year/type
                        uploaded_docs = db.get_documents_by_fiscal_year(fiscal_year.id)
                        if 'selected_files' not in st.session_state:
                            st.session_state.selected_files = []
                        if 'selected_file_paths' not in st.session_state:
                            st.session_state.selected_file_paths = {}

                        for doc in uploaded_docs:
                            doc_key = f"doc_{doc.id}"
                            if doc_key not in st.session_state.selected_files:
                                st.session_state.selected_files.append(doc_key)
                            st.session_state.selected_file_paths[doc_key] = doc.file_path

                        st.switch_page("pages/2_⚙️_Process.py")
                    else:
                        st.rerun()

    else:
        st.info("👆 Please select PDF files to upload")

    st.markdown("---")

    # Upload history
    if DB_AVAILABLE:
        st.subheader("📋 Recent Uploads")
        uploads_root = config.PROJECT_ROOT / "uploads"
        if uploads_root.exists():
            files = list(uploads_root.rglob("*.pdf"))
            latest_files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:10]
            if latest_files:
                for f in latest_files:
                    rel = f.relative_to(config.PROJECT_ROOT)
                    with st.expander(f"📄 {f.name}"):
                        st.write(f"**Path:** {rel}")
                        st.write(f"**Size:** {format_file_size(f.stat().st_size)}")
                        st.write(f"**Modified:** {datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                st.info("No uploads yet.")

    st.markdown("---")

    # Navigation
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("← Back to Dashboard", use_container_width=True):
            st.switch_page("main.py")

    with col2:
        if st.button("Browse Documents", use_container_width=True):
            st.switch_page("pages/1_📁_Browse.py")

    with col3:
        pass  # Spacing

    # Footer
    st.markdown("---")
    st.caption("Supported format: PDF | Maximum size: 50MB per file")

if __name__ == "__main__":
    main()
