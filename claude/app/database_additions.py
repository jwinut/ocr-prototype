"""
Additional database methods for saving full OCR results.

This file contains the new method to be added to DatabaseManager class.
"""

def save_full_ocr_results(
    self,
    file_path: str,
    file_name: str,
    ocr_result,
    doc_id: str
) -> Optional[int]:
    """
    Save full OCR results to normalized database tables.

    Creates or updates Document record and stores all extracted tables
    with their data in the normalized schema.

    Args:
        file_path: Full path to the PDF file
        file_name: Original filename
        ocr_result: ProcessedDocument from OCR processor
        doc_id: Document identifier

    Returns:
        Document ID if successful, None on failure
    """
    with self.get_session() as session:
        try:
            # Get or create default company/fiscal year for uncategorized documents
            default_company = self.get_or_create_company(
                company_code="UNCATEGORIZED",
                name_th="ไม่ระบุบริษัท",
                name_en="Uncategorized"
            )

            # Use current year as default fiscal year
            from datetime import datetime
            current_year_be = datetime.now().year + 543
            default_fiscal_year = self.get_or_create_fiscal_year(
                company_id=default_company.id,
                year_be=current_year_be
            )

            # Check if document already exists
            stmt = select(Document).where(Document.file_path == file_path)
            document = session.scalar(stmt)

            if document:
                # Update existing document
                document.status = DocumentStatus.COMPLETED
                document.processed_at = datetime.utcnow()
                document.page_count = None  # Could be extracted from ocr_result if available

                # Delete existing tables to replace with new data
                session.execute(
                    delete(ExtractedTable).where(ExtractedTable.document_id == document.id)
                )
            else:
                # Create new document
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None

                document = Document(
                    fiscal_year_id=default_fiscal_year.id,
                    document_type="Unknown",  # Could be inferred from filename
                    file_path=file_path,
                    file_name=file_name,
                    status=DocumentStatus.COMPLETED,
                    processed_at=datetime.utcnow(),
                    file_size_bytes=file_size
                )
                session.add(document)
                session.flush()  # Get document ID

            # Store extracted tables
            if hasattr(ocr_result, 'tables') and ocr_result.tables:
                for table_idx, df in enumerate(ocr_result.tables):
                    # Extract headers and data from DataFrame
                    headers = df.columns.tolist() if hasattr(df, 'columns') else []
                    data_rows = df.values.tolist() if hasattr(df, 'values') else []

                    # Convert to list of lists of strings
                    data = [[str(cell) for cell in row] for row in data_rows]

                    # Get markdown representation if available
                    markdown = None
                    if hasattr(ocr_result, 'markdown') and ocr_result.markdown:
                        # Try to extract table-specific markdown
                        # For now, just use the full markdown
                        markdown = ocr_result.markdown

                    # Store the table using the existing method
                    # Note: store_extracted_table is called on self, not on session
                    from app.database import DatabaseManager
                    db_temp = DatabaseManager()
                    db_temp.store_extracted_table(
                        document_id=document.id,
                        table_index=table_idx,
                        headers=[str(h) for h in headers],
                        data=data,
                        markdown=markdown,
                        table_type=None,  # Could be inferred
                        confidence_score=None  # Could be extracted if available
                    )

            session.commit()
            session.refresh(document)
            return document.id

        except Exception as e:
            session.rollback()
            raise Exception(f"Failed to save OCR results: {str(e)}")
