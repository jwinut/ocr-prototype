"""
Upload Documents Page

Upload new PDF documents with validation and organization.
"""

import streamlit as st
from datetime import datetime
import os

st.set_page_config(
    page_title="Upload Documents",
    page_icon="⬆️",
    layout="wide"
)

# Initialize session state
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []
if 'upload_progress' not in st.session_state:
    st.session_state.upload_progress = 0
if 'process_after_upload' not in st.session_state:
    st.session_state.process_after_upload = False

# Mock company data
MOCK_COMPANIES = [
    {"code": "10002819", "name": "บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด"},
    {"code": "10002821", "name": "บริษัท ยาคูลท์ (ประเทศไทย) จำกัด"},
    {"code": "10002823", "name": "บริษัท ไทย-โอตะ จำกัด"},
    {"code": "10002828", "name": "บริษัท ไทยซุยซัง จำกัด"},
    {"code": "10002835", "name": "บริษัท คาร์ออดิโอโทเทิล (ไทยแลนด์) จำกัด"},
    {"code": "10002836", "name": "บริษัท ไทยซูโกกุ จำกัด"},
    {"code": "10002843", "name": "บริษัท ไทยมาเชก จำกัด"},
    {"code": "10002846", "name": "บริษัท ไทยไดกิน (ประเทศไทย) จำกัด"},
    {"code": "10002847", "name": "บริษัท ซี เอส ไลน์ (ประเทศไทย) จำกัด"},
    {"code": "10002848", "name": "บริษัท ไทยชินเทค จำกัด"},
    {"code": "10002849", "name": "บริษัท ไทยไซยา (ประเทศไทย) จำกัด"},
]

FISCAL_YEARS = [str(year) for year in range(2020, 2025)]
DOCUMENT_TYPES = ["งบการเงิน", "รายงานประจำปี", "รายงานคณะกรรมการ", "อื่นๆ"]

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
                company_options = [f"{c['code']} - {c['name']}" for c in MOCK_COMPANIES]
                selected_company = st.selectbox(
                    "Company *",
                    options=company_options,
                    help="Select the company these documents belong to"
                )
                company_code = selected_company.split(" - ")[0]

            with col2:
                selected_year = st.selectbox(
                    "Fiscal Year *",
                    options=FISCAL_YEARS,
                    index=len(FISCAL_YEARS) - 1,  # Default to latest year
                    help="Select the fiscal year"
                )

            with col3:
                selected_type = st.selectbox(
                    "Document Type *",
                    options=DOCUMENT_TYPES,
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

                        # Simulate upload
                        import time
                        time.sleep(0.5)

                        # Update progress
                        st.session_state.upload_progress = (idx + 1) / len(valid_files)
                        progress_bar.progress(st.session_state.upload_progress)

                        # Store file info
                        file_info = {
                            'filename': file.name,
                            'size': file.size,
                            'company_code': company_code,
                            'year': selected_year,
                            'type': selected_type,
                            'uploaded_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'path': f"/Y67/{company_code}/{selected_year}/{file.name}"
                        }
                        st.session_state.uploaded_files.append(file_info)

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
                        time.sleep(1)

                        # Add uploaded files to selected_files for processing
                        if 'selected_files' not in st.session_state:
                            st.session_state.selected_files = []

                        for file_info in st.session_state.uploaded_files[-len(valid_files):]:
                            doc_id = f"{file_info['company_code']}_{file_info['year']}_{file_info['type']}"
                            if doc_id not in st.session_state.selected_files:
                                st.session_state.selected_files.append(doc_id)

                        st.switch_page("pages/2_⚙️_Process.py")
                    else:
                        time.sleep(2)
                        st.rerun()

    else:
        st.info("👆 Please select PDF files to upload")

    st.markdown("---")

    # Upload history
    if st.session_state.uploaded_files:
        st.subheader("📋 Recent Uploads")

        # Show last 10 uploads
        recent_uploads = st.session_state.uploaded_files[-10:]

        for upload in reversed(recent_uploads):
            with st.expander(f"📄 {upload['filename']} - {upload['uploaded_at']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Company:** {upload['company_code']}")
                    st.write(f"**Year:** {upload['year']}")
                    st.write(f"**Type:** {upload['type']}")
                with col2:
                    st.write(f"**Size:** {format_file_size(upload['size'])}")
                    st.write(f"**Path:** {upload['path']}")
                    st.write(f"**Uploaded:** {upload['uploaded_at']}")

        if len(st.session_state.uploaded_files) > 10:
            st.caption(f"Showing 10 most recent of {len(st.session_state.uploaded_files)} total uploads")

    st.markdown("---")

    # Navigation
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("← Back to Dashboard", use_container_width=True):
            st.switch_page("app/main.py")

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
