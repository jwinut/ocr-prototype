"""
Results Viewer Page

Display processed document results with multiple view formats and export options.
Loads persisted results from database on refresh to maintain state.
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime
from typing import Optional

st.set_page_config(
    page_title="View Results",
    page_icon="📊",
    layout="wide"
)

# Import database
try:
    from app.database import DatabaseManager
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# Import Thai post-processing
try:
    from processing.thai_postprocess import postprocess_thai_ocr, postprocess_markdown
    POSTPROCESS_AVAILABLE = True
except ImportError:
    POSTPROCESS_AVAILABLE = False


@st.cache_resource
def get_db():
    """Get database manager instance."""
    if not DB_AVAILABLE:
        return None
    db = DatabaseManager()
    db.init_db()
    return db


def auto_save_state():
    """Auto-save processed documents to database."""
    if 'processed_documents' in st.session_state and st.session_state.processed_documents:
        db = get_db()
        if db:
            db.save_session_state(st.session_state.processed_documents)


# Initialize session state - load from database if empty
if 'processed_documents' not in st.session_state:
    # Try to load from database on startup/refresh
    db = get_db()
    if db:
        st.session_state.processed_documents = db.load_session_state()
    else:
        st.session_state.processed_documents = []
if 'selected_result' not in st.session_state:
    st.session_state.selected_result = None


def load_from_database(file_path: str) -> Optional[dict]:
    """
    Load OCR results from database if available.

    Args:
        file_path: Path to the processed document

    Returns:
        Dict with tables, text_content, markdown if found, None otherwise
    """
    db = get_db()
    if not db:
        return None

    try:
        # Find document by file_path
        document = db.get_document_by_file_path(file_path)
        if not document:
            return None

        # Load extracted tables
        tables = db.get_tables_by_document(document.id)
        if not tables:
            return None

        # Reconstruct tables in expected format
        result_tables = []
        text_content_parts = []
        markdown_parts = []

        for table in tables:
            # Parse headers
            headers = json.loads(table.headers_json) if table.headers_json else []

            # Get cells and organize into rows
            cells = db.get_table_cells(table.id)
            rows = []
            current_row = []
            current_row_idx = 0

            for cell in cells:
                if cell.row_index != current_row_idx:
                    if current_row:
                        rows.append(current_row)
                    current_row = []
                    current_row_idx = cell.row_index
                current_row.append(cell.value or '')

            if current_row:
                rows.append(current_row)

            # Build table dict
            table_dict = {
                'headers': headers,
                'rows': rows,
                'type': table.table_type or 'extracted',
                'name': f'Table {table.table_index + 1}'
            }
            result_tables.append(table_dict)

            # Collect markdown if available
            if table.markdown_content:
                markdown_parts.append(table.markdown_content)

            # Build text content from table cells
            if headers:
                text_content_parts.append(' '.join(headers))
            for row in rows:
                text_content_parts.append(' '.join(row))

        return {
            "status": "success",
            "tables": result_tables,
            "text_content": '\n'.join(text_content_parts),
            "markdown": '\n\n'.join(markdown_parts) if markdown_parts else '',
            "metadata": {
                "document_id": document.id,
                "document_type": document.document_type,
                "loaded_from_database": True
            },
            "postprocess_info": {
                "applied": False,
                "corrections_made": 0,
                "negatives_converted": 0
            }
        }
    except Exception as e:
        # Log error but return None to fall back to OCR processing
        return None


def load_ocr_result(file_path: str, apply_postprocess: bool = True) -> dict:
    """
    Load OCR result from database or re-process if needed.

    Args:
        file_path: Path to the processed document
        apply_postprocess: Whether to apply Thai post-processing

    Returns:
        Dict with tables, text_content, and metadata
    """
    # Try to load from database first
    db_result = load_from_database(file_path)
    if db_result:
        return db_result

    # Fall back to OCR processing if not in database
    try:
        from processing.ocr import DocumentProcessor
        processor = DocumentProcessor(languages=("th", "en"))
        result = processor.process_single(file_path)

        if result.status == "success":
            text_content = result.text_content
            markdown = result.markdown
            corrections_made = 0
            negatives_converted = 0

            # Apply Thai post-processing if available and enabled
            if apply_postprocess and POSTPROCESS_AVAILABLE:
                if text_content:
                    pp_result = postprocess_thai_ocr(text_content)
                    text_content = pp_result.corrected
                    corrections_made += pp_result.corrections_made
                    negatives_converted += pp_result.negative_numbers_converted

                if markdown:
                    markdown = postprocess_markdown(markdown)

            return {
                "status": "success",
                "tables": result.tables,
                "text_content": text_content,
                "markdown": markdown,
                "metadata": result.json_data,  # ProcessedDocument uses json_data, not metadata
                "postprocess_info": {
                    "applied": apply_postprocess and POSTPROCESS_AVAILABLE,
                    "corrections_made": corrections_made,
                    "negatives_converted": negatives_converted
                }
            }
        else:
            return {
                "status": "failed",
                "errors": result.errors,
                "tables": [],
                "text_content": "",
                "markdown": "",
                "metadata": {},
                "postprocess_info": {"applied": False}
            }
    except Exception as e:
        return {
            "status": "error",
            "errors": [str(e)],
            "tables": [],
            "text_content": "",
            "markdown": "",
            "metadata": {},
            "postprocess_info": {"applied": False}
        }


def format_tables_for_display(tables: list) -> list:
    """
    Convert OCR table results to displayable format.

    Args:
        tables: List of table dicts from OCR result

    Returns:
        List of dicts with 'name', 'data' (DataFrame), 'type'
    """
    display_tables = []
    for idx, table in enumerate(tables):
        if isinstance(table, dict):
            # Table has headers and data
            headers = table.get('headers', [])
            rows = table.get('rows', [])
            table_type = table.get('type', 'unknown')

            if headers and rows:
                # Handle column count mismatch between headers and data
                max_cols = max(len(headers), max(len(row) for row in rows) if rows else 0)

                # Extend headers if rows have more columns
                if len(headers) < max_cols:
                    headers = list(headers) + [f'Column {i+1}' for i in range(len(headers), max_cols)]

                # Normalize row lengths to match header count
                normalized_rows = []
                for row in rows:
                    if len(row) < max_cols:
                        # Pad short rows
                        normalized_rows.append(list(row) + [''] * (max_cols - len(row)))
                    elif len(row) > max_cols:
                        # Truncate long rows (shouldn't happen after extending headers)
                        normalized_rows.append(list(row)[:max_cols])
                    else:
                        normalized_rows.append(list(row))

                df = pd.DataFrame(normalized_rows, columns=headers)
            elif rows:
                df = pd.DataFrame(rows)
            else:
                continue

            display_tables.append({
                'name': table.get('name', f'Table {idx + 1}'),
                'data': df,
                'type': table_type
            })
        elif hasattr(table, 'to_dataframe'):
            # Docling table object
            df = table.to_dataframe()
            display_tables.append({
                'name': f'Table {idx + 1}',
                'data': df,
                'type': 'extracted'
            })

    return display_tables


def generate_json_output(doc: dict, ocr_result: dict) -> dict:
    """
    Generate JSON output from document and OCR result.

    Args:
        doc: Document info dict
        ocr_result: OCR processing result

    Returns:
        Formatted JSON dict
    """
    tables_info = []
    for idx, table in enumerate(ocr_result.get('tables', [])):
        if isinstance(table, dict):
            tables_info.append({
                "table_id": idx + 1,
                "name": table.get('name', f'Table {idx + 1}'),
                "type": table.get('type', 'unknown'),
                "rows": len(table.get('rows', [])),
                "columns": len(table.get('headers', []))
            })

    return {
        "document_info": {
            "id": doc.get('id', 'unknown'),
            "filename": doc.get('filename', 'unknown'),
            "file_path": doc.get('file_path', ''),
            "processed_at": doc.get('timestamp', 'unknown'),
            "status": doc.get('status', 'unknown')
        },
        "extraction_summary": {
            "tables_found": doc.get('tables_found', len(ocr_result.get('tables', []))),
            "text_blocks": doc.get('text_blocks', 0),
            "status": ocr_result.get('status', 'unknown')
        },
        "metadata": ocr_result.get('metadata', {}),
        "tables": tables_info
    }

def main():
    """Results viewer page"""

    st.title("📊 View Results")
    st.markdown("Browse and export processed document results")

    st.markdown("---")

    # Check if there are processed documents
    if not st.session_state.processed_documents:
        st.warning("No processed documents available.")
        st.info("Process some documents first to see results here.")
        if st.button("← Go to Process Page"):
            st.switch_page("pages/2_⚙️_Process.py")
        return

    # Document selector
    st.subheader("📄 Select Document")

    # Create document options
    doc_options = {f"{doc['filename']} ({doc['timestamp']})": doc
                   for doc in st.session_state.processed_documents}

    selected_doc_key = st.selectbox(
        "Choose a document to view",
        options=list(doc_options.keys()),
        index=0
    )

    selected_doc = doc_options[selected_doc_key]
    st.session_state.selected_result = selected_doc

    # Document info summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Status", "✅ Success" if selected_doc.get('status') == 'success' else "❌ Failed")
    with col2:
        st.metric("Tables Found", selected_doc.get('tables_found', 0))
    with col3:
        st.metric("Text Blocks", selected_doc.get('text_blocks', 0))
    with col4:
        st.metric("Processed", selected_doc.get('timestamp', 'N/A').split()[1] if ' ' in selected_doc.get('timestamp', '') else 'N/A')

    st.markdown("---")

    # Load OCR result for the selected document
    file_path = selected_doc.get('file_path') or selected_doc.get('path')

    if not file_path:
        st.error("Document file path not available.")
        return

    # Load and cache OCR result
    with st.spinner("Loading document data..."):
        ocr_result = load_ocr_result(file_path)

    if ocr_result.get('status') == 'error':
        st.error(f"Failed to load document: {ocr_result.get('errors', ['Unknown error'])}")
        return

    # Format data for display
    tables = format_tables_for_display(ocr_result.get('tables', []))
    text_content = ocr_result.get('text_content', '')
    markdown_content = ocr_result.get('markdown', '')
    json_output = generate_json_output(selected_doc, ocr_result)

    # Show database load info if available
    metadata = ocr_result.get('metadata', {})
    if metadata.get('loaded_from_database'):
        st.info("📂 Results loaded from database (no re-processing needed)")

    # Show post-processing info if available
    pp_info = ocr_result.get('postprocess_info', {})
    if pp_info.get('applied'):
        corrections = pp_info.get('corrections_made', 0)
        negatives = pp_info.get('negatives_converted', 0)
        if corrections > 0 or negatives > 0:
            st.success(f"🔧 Thai post-processing applied: {corrections} text corrections, {negatives} negative number conversions")

    # Results tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Tables", "📝 Text", "📋 Markdown", "🔧 JSON"])

    with tab1:
        st.subheader("Extracted Tables")

        if not tables:
            st.info("No tables found in this document.")
        else:
            for idx, table in enumerate(tables):
                with st.expander(f"Table {idx + 1}: {table['name']}", expanded=idx == 0):
                    st.markdown(f"**Type:** {table['type']}")
                    st.dataframe(table['data'], use_container_width=True)

                    # Export button for individual table
                    col1, col2 = st.columns([3, 1])
                    with col2:
                        csv = table['data'].to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 Export CSV",
                            data=csv,
                            file_name=f"{table['name']}_{selected_doc['id']}.csv",
                            mime="text/csv",
                            key=f"export_table_{idx}",
                            use_container_width=True
                        )

    with tab2:
        st.subheader("Extracted Text Content")

        if not text_content:
            st.info("No text content extracted from this document.")
        else:
            # Text display with scrolling
            st.text_area(
                "Full Text",
                value=text_content,
                height=400,
                label_visibility="collapsed"
            )

            # Export text
            col1, col2, col3 = st.columns([2, 1, 1])
            with col3:
                st.download_button(
                    label="📥 Export Text",
                    data=text_content.encode('utf-8-sig'),
                    file_name=f"{selected_doc['id']}_text.txt",
                    mime="text/plain",
                    use_container_width=True
                )

    with tab3:
        st.subheader("Markdown Preview")

        if not markdown_content:
            st.info("No markdown content available for this document.")
        else:
            # Show markdown preview
            st.markdown(markdown_content)

            st.markdown("---")

            # Raw markdown
            with st.expander("View Raw Markdown"):
                st.code(markdown_content, language="markdown")

            # Export markdown
            col1, col2, col3 = st.columns([2, 1, 1])
            with col3:
                st.download_button(
                    label="📥 Export Markdown",
                    data=markdown_content.encode('utf-8-sig'),
                    file_name=f"{selected_doc['id']}_markdown.md",
                    mime="text/markdown",
                    use_container_width=True
                )

    with tab4:
        st.subheader("JSON Output")

        # Display formatted JSON
        st.json(json_output)

        # Export JSON
        col1, col2, col3 = st.columns([2, 1, 1])
        with col3:
            json_str = json.dumps(json_output, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 Export JSON",
                data=json_str.encode('utf-8-sig'),
                file_name=f"{selected_doc['id']}_data.json",
                mime="application/json",
                use_container_width=True
            )

    st.markdown("---")

    # Batch export section
    st.subheader("📦 Batch Export")

    col1, col2, col3 = st.columns(3)

    with col1:
        if tables:
            # Combine all tables into one CSV
            all_tables_csv = ""
            for table in tables:
                all_tables_csv += f"\n# {table['name']}\n"
                all_tables_csv += table['data'].to_csv(index=False)
                all_tables_csv += "\n"

            st.download_button(
                label="📥 Export All Tables (CSV)",
                data=all_tables_csv.encode('utf-8-sig'),
                file_name=f"{selected_doc['id']}_all_tables.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button("Export All Tables (CSV)", use_container_width=True, disabled=True)

    with col2:
        if text_content:
            st.download_button(
                label="📥 Export All Text",
                data=text_content.encode('utf-8-sig'),
                file_name=f"{selected_doc['id']}_full_text.txt",
                mime="text/plain",
                use_container_width=True
            )
        else:
            st.button("Export All Text", use_container_width=True, disabled=True)

    with col3:
        json_str = json.dumps(json_output, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 Export Complete JSON",
            data=json_str.encode('utf-8-sig'),
            file_name=f"{selected_doc['id']}_complete.json",
            mime="application/json",
            use_container_width=True
        )

    st.markdown("---")

    # Navigation buttons
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("← Back to Dashboard", use_container_width=True):
            auto_save_state()  # Auto-save before navigating
            st.switch_page("app/main.py")

    with col2:
        if st.button("Process More Documents", use_container_width=True):
            auto_save_state()  # Auto-save before navigating
            st.switch_page("pages/1_📁_Browse.py")

    with col3:
        if st.button("🗄️ Manage Database", use_container_width=True):
            auto_save_state()  # Auto-save before navigating
            st.switch_page("pages/4_🗄️_Database.py")

    with col4:
        if st.button("💾 Save Now", use_container_width=True):
            auto_save_state()
            st.success("State saved!")

if __name__ == "__main__":
    main()
