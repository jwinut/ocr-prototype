"""
Results Viewer Page

Display processed document results with multiple view formats and export options.
Loads persisted results from database on refresh to maintain state.
"""

import streamlit as st
import pandas as pd
import json
import re
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
if 'view_engine' not in st.session_state:
    st.session_state.view_engine = None  # None means auto-detect available


def get_available_engines(file_path: str) -> list:
    """
    Get list of engines that have processed this document.

    Args:
        file_path: Path to the document

    Returns:
        List of engine names that have cached results
    """
    db = get_db()
    if not db:
        return []
    return db.get_available_engines_for_document(file_path)


def load_cached_result(file_path: str, engine: str) -> Optional[dict]:
    """
    Load OCR result from database for specific engine.

    Args:
        file_path: Path to the document
        engine: OCR engine name (docling/typhoon)

    Returns:
        Dict with markdown_content, text_content, tables, etc if found
    """
    db = get_db()
    if not db:
        return None

    # Get document record directly from documents table (single source of truth)
    document = db.get_document_by_file_path(file_path, engine=engine)
    if not document:
        return None

    # If document exists but has no content AND no tables, return None
    # Some documents may have tables extracted but no markdown/text content
    # (e.g., PDF with only tables and images)
    has_content = bool(document.markdown_content or document.text_content)
    has_tables = document.tables_found and document.tables_found > 0

    if not has_content and not has_tables:
        return None

    # Load tables from the normalized database tables for this specific engine
    result_tables = []
    if document:
        tables = db.get_tables_by_document(document.id)
        seen_table_indexes = set()
        for table in tables:
            # Skip duplicates for the same table index (can happen if a prior run left stale rows)
            if table.table_index in seen_table_indexes:
                continue
            seen_table_indexes.add(table.table_index)

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

    return {
        "status": "success",
        "engine": document.engine,
        "tables": result_tables,
        "text_content": document.text_content or "",
        "markdown": document.markdown_content or "",
        "metadata": {
            "engine": document.engine,
            "tables_found": document.tables_found,
            "text_blocks": document.text_blocks,
            "processed_at": document.processed_at.isoformat() if document.processed_at else None,
            "loaded_from_database": True
        },
        "postprocess_info": {
            "applied": False,
            "corrections_made": 0,
            "negatives_converted": 0
        }
    }


def load_from_database_with_engine(file_path: str, engine: str = None) -> Optional[dict]:
    """
    Load OCR results from database for specific engine.

    This is the primary data loading function - Results page should NEVER trigger OCR.

    Args:
        file_path: Path to the processed document
        engine: OCR engine name (docling/typhoon), or None for any

    Returns:
        Dict with tables, text_content, markdown if found, None otherwise
    """
    db = get_db()
    if not db:
        return None

    try:
        # Find document by file_path and engine
        document = db.get_document_by_file_path(file_path, engine=engine)
        if not document:
            return None

        # Load extracted tables
        tables = db.get_tables_by_document(document.id)
        if not tables:
            # Document exists but no tables - still return with empty tables
            return {
                "status": "success",
                "engine": document.engine,
                "tables": [],
                "text_content": "",
                "markdown": "",
                "metadata": {
                    "document_id": document.id,
                    "document_type": document.document_type,
                    "engine": document.engine,
                    "loaded_from_database": True
                },
                "postprocess_info": {
                    "applied": False,
                    "corrections_made": 0,
                    "negatives_converted": 0
                }
            }

        # Reconstruct tables in expected format
        result_tables = []
        text_content_parts = []
        markdown_parts = []
        seen_table_indexes = set()

        for table in tables:
            # Guard against duplicate table rows stored for the same document
            if table.table_index in seen_table_indexes:
                continue
            seen_table_indexes.add(table.table_index)

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
            "engine": document.engine,
            "tables": result_tables,
            "text_content": '\n'.join(text_content_parts),
            "markdown": '\n\n'.join(markdown_parts) if markdown_parts else '',
            "metadata": {
                "document_id": document.id,
                "document_type": document.document_type,
                "engine": document.engine,
                "loaded_from_database": True
            },
            "postprocess_info": {
                "applied": False,
                "corrections_made": 0,
                "negatives_converted": 0
            }
        }
    except Exception as e:
        return None


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


def split_markdown_into_pages(markdown_content: str) -> list:
    """
    Split combined markdown/HTML into pages using known markers.

    Supports:
    - Typhoon combined pages: <!--page:x/y-->
    - Docling exports containing <page_number> tags
    """
    if not markdown_content:
        return []

    # Typhoon combined pages marker
    if "<!--page:" in markdown_content:
        parts = re.split(r'<!--page:\d+/\d+-->\s*', markdown_content)
        return [p for p in parts if p.strip()]

    # Docling page markers
    if "<page_number>" in markdown_content.lower():
        parts = re.split(r'<page_number>.*?</page_number>', markdown_content, flags=re.IGNORECASE | re.DOTALL)
        return [p for p in parts if p.strip()]

    return [markdown_content]


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
    doc_options = {
        f"{doc.get('filename', 'Unknown')} ({doc.get('timestamp', doc.get('engine', 'N/A'))})": doc
        for doc in st.session_state.processed_documents
    }

    selected_doc_key = st.selectbox(
        "Choose a document to view",
        options=list(doc_options.keys()),
        index=0
    )

    selected_doc = doc_options[selected_doc_key]
    st.session_state.selected_result = selected_doc

    # Get file path for engine detection
    file_path = selected_doc.get('file_path') or selected_doc.get('path')

    # Engine version selector
    if file_path:
        available_engines = get_available_engines(file_path)
        if len(available_engines) > 1:
            st.subheader("🔄 OCR Engine Version")
            engine_labels = {
                "docling": "🔧 Docling (Local)",
                "typhoon": "🌊 Typhoon (Cloud API)"
            }
            col_eng1, col_eng2 = st.columns([2, 3])
            with col_eng1:
                selected_engine = st.selectbox(
                    "View results from",
                    options=available_engines,
                    index=available_engines.index(st.session_state.view_engine) if st.session_state.view_engine in available_engines else 0,
                    format_func=lambda x: engine_labels.get(x, x),
                    key="engine_version_select"
                )
                st.session_state.view_engine = selected_engine
            with col_eng2:
                st.info(f"📊 This document has been processed by **{len(available_engines)}** OCR engines: {', '.join(available_engines)}")
            st.markdown("---")
        elif len(available_engines) == 1:
            st.session_state.view_engine = available_engines[0]
            engine_labels = {"docling": "🔧 Docling", "typhoon": "🌊 Typhoon"}
            st.caption(f"Engine: {engine_labels.get(available_engines[0], available_engines[0])}")
        else:
            # No cached results - will fall back to re-processing
            st.session_state.view_engine = None

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
    # file_path is already set above for engine detection

    if not file_path:
        st.error("Document file path not available.")
        return

    # Load data from database - NEVER trigger OCR from Results page
    with st.spinner("Loading document data..."):
        selected_engine = st.session_state.view_engine
        ocr_result = None

        # Try to load from cache with selected engine first
        if selected_engine:
            ocr_result = load_cached_result(file_path, selected_engine)

        # Fall back to database (still no OCR)
        if not ocr_result:
            ocr_result = load_from_database_with_engine(file_path, selected_engine)

        # If still no result, try database without engine filter
        if not ocr_result:
            ocr_result = load_from_database_with_engine(file_path)

    # Handle case where document has not been processed
    if not ocr_result:
        st.error("⚠️ This document has not been processed yet.")
        st.info("Please go to the Process page to run OCR on this document first.")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("← Go to Process Page", type="primary", use_container_width=True):
                st.switch_page("pages/2_⚙️_Process.py")
        with col2:
            if st.button("← Back to Browse", use_container_width=True):
                st.switch_page("pages/1_📁_Browse.py")
        return

    if ocr_result.get('status') == 'error':
        st.error(f"Failed to load document: {ocr_result.get('errors', ['Unknown error'])}")
        return

    # Format data for display
    tables = format_tables_for_display(ocr_result.get('tables', []))
    text_content = ocr_result.get('text_content', '')
    markdown_content = ocr_result.get('markdown', '')
    page_segments = split_markdown_into_pages(markdown_content)
    page_count = len(page_segments) if page_segments else 0
    json_output = generate_json_output(selected_doc, ocr_result)

    # Show source info
    metadata = ocr_result.get('metadata', {})
    engine_used = metadata.get('engine') or ocr_result.get('engine')
    if metadata.get('loaded_from_cache'):
        engine_labels = {"docling": "🔧 Docling", "typhoon": "🌊 Typhoon"}
        engine_label = engine_labels.get(engine_used, engine_used)
        st.info(f"📂 Results loaded from cache ({engine_label})")
    elif metadata.get('loaded_from_database'):
        st.info("📂 Results loaded from database (no re-processing needed)")

    # Show post-processing info if available
    pp_info = ocr_result.get('postprocess_info', {})
    if pp_info.get('applied'):
        corrections = pp_info.get('corrections_made', 0)
        negatives = pp_info.get('negatives_converted', 0)
        if corrections > 0 or negatives > 0:
            st.success(f"🔧 Thai post-processing applied: {corrections} text corrections, {negatives} negative number conversions")

    # Results tabs - swap Markdown for HTML when viewing Typhoon output
    is_typhoon = (engine_used == "typhoon")
    tab_labels = [
        "📊 Tables",
        "📝 Text",
        "🖥️ HTML" if is_typhoon else "📋 Markdown",
        "🔧 JSON"
    ]
    tab1, tab2, tab3, tab4 = st.tabs(tab_labels)

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
        if is_typhoon:
                st.subheader("HTML Preview")

                if not markdown_content:
                    st.info("No HTML content available for this document.")
                else:
                    if page_count > 1:
                        col_prev, col_label, col_next = st.columns([1, 2, 1])
                        page_state_key = f"{selected_doc['id']}_typhoon_page"
                        page_idx = st.session_state.get(page_state_key, 1)
                        page_idx = max(1, min(page_idx, page_count))
                        with col_prev:
                            if st.button("◀", key=f"prev_typhoon_{selected_doc['id']}", use_container_width=True) and page_idx > 1:
                                page_idx -= 1
                        with col_label:
                            st.markdown(f"<div style='text-align:center; font-weight:600;'>Page {page_idx} of {page_count}</div>", unsafe_allow_html=True)
                            page_input = st.text_input(
                                "Page",
                                value=str(page_idx),
                                key=f"{selected_doc['id']}_typhoon_page_input",
                                label_visibility="collapsed"
                            )
                            try:
                                page_idx = int(page_input)
                            except ValueError:
                                pass
                        with col_next:
                            if st.button("▶", key=f"next_typhoon_{selected_doc['id']}", use_container_width=True) and page_idx < page_count:
                                page_idx += 1
                        page_idx = int(max(1, min(page_idx, page_count)))
                        st.session_state[page_state_key] = page_idx
                    else:
                        page_idx = 1

                    current_page_html = page_segments[page_idx - 1] if page_segments else markdown_content

                # Lightweight styling wrapper to make Typhoon HTML tables legible
                styled_html = f"""
                <html>
                  <head>
                    <style>
                      body {{
                        font-family: "Segoe UI", Arial, sans-serif;
                        padding: 16px;
                        background: #f9fafb;
                        color: #111827;
                      }}
                      table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin: 12px 0;
                      }}
                      th, td {{
                        border: 1px solid #d0d7de;
                        padding: 6px 8px;
                        font-size: 13px;
                      }}
                      th {{
                        background: #eef2f7;
                        font-weight: 600;
                      }}
                      h1, h2, h3, h4 {{
                        margin-top: 1rem;
                      }}
                      p {{
                        margin: 0.25rem 0 0.75rem;
                      }}
                    </style>
                  </head>
                  <body>
                    {current_page_html}
                  </body>
                </html>
                """
                # Render Typhoon's HTML output directly
                st.components.v1.html(styled_html, height=600, scrolling=True)

                st.markdown("---")

                # Raw HTML
                with st.expander("View Raw HTML"):
                    st.code(current_page_html, language="html")

                # Export HTML
                col1, col2, col3 = st.columns([2, 1, 1])
                with col3:
                    st.download_button(
                        label="📥 Export HTML",
                        data=markdown_content.encode('utf-8-sig'),
                        file_name=f"{selected_doc['id']}_html.html",
                        mime="text/html",
                        use_container_width=True
                    )
        else:
                st.subheader("Markdown Preview")

                if not markdown_content:
                    st.info("No markdown content available for this document.")
                else:
                    if page_count > 1:
                        col_prev, col_label, col_next = st.columns([1, 2, 1])
                        page_state_key = f"{selected_doc['id']}_docling_page"
                        page_idx = st.session_state.get(page_state_key, 1)
                        page_idx = max(1, min(page_idx, page_count))
                        with col_prev:
                            if st.button("◀", key=f"prev_docling_{selected_doc['id']}", use_container_width=True) and page_idx > 1:
                                page_idx -= 1
                        with col_label:
                            st.markdown(f"<div style='text-align:center; font-weight:600;'>Page {page_idx} of {page_count}</div>", unsafe_allow_html=True)
                            page_input = st.text_input(
                                "Page",
                                value=str(page_idx),
                                key=f"{selected_doc['id']}_docling_page_input",
                                label_visibility="collapsed"
                            )
                            try:
                                page_idx = int(page_input)
                            except ValueError:
                                pass
                        with col_next:
                            if st.button("▶", key=f"next_docling_{selected_doc['id']}", use_container_width=True) and page_idx < page_count:
                                page_idx += 1
                        page_idx = int(max(1, min(page_idx, page_count)))
                        st.session_state[page_state_key] = page_idx
                    else:
                        page_idx = 1

                    current_page_md = page_segments[page_idx - 1] if page_segments else markdown_content

                # Show markdown preview
                st.markdown(current_page_md, unsafe_allow_html=True)

                st.markdown("---")

                # Raw markdown
                with st.expander("View Raw Markdown"):
                    st.code(current_page_md, language="markdown")

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
            st.switch_page("main.py")

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
