"""
Database management layer for Thai Financial Document OCR Prototype.

Provides CRUD operations and business logic for managing companies,
fiscal years, documents, and extracted table data.
"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import json
import csv
import hashlib
import os

from sqlalchemy import create_engine, func, select, and_, or_, delete
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from app.config import config
from models.schema import (
    Base, Company, FiscalYear, Document, ExtractedTable, TableCell,
    DocumentStatus, DataType, ProcessedDocumentCache
)


class DatabaseManager:
    """Manages all database operations for the OCR prototype."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            database_url: SQLAlchemy database URL. Defaults to config value.
        """
        self.database_url = database_url or config.DATABASE_URL
        self.engine = create_engine(
            self.database_url,
            echo=False,
            connect_args={"check_same_thread": False}  # SQLite specific
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def init_db(self) -> None:
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    # Company Operations

    def get_or_create_company(
        self,
        company_code: str,
        name_th: str,
        name_en: Optional[str] = None
    ) -> Company:
        """
        Get existing company or create new one.

        Args:
            company_code: Unique company code (e.g., "10002819")
            name_th: Thai company name
            name_en: English company name (optional)

        Returns:
            Company instance
        """
        with self.get_session() as session:
            # Try to find existing company
            stmt = select(Company).where(Company.company_code == company_code)
            company = session.scalar(stmt)

            if company:
                # Update name if different
                if company.name_th != name_th or company.name_en != name_en:
                    company.name_th = name_th
                    company.name_en = name_en
                    session.commit()
                    session.refresh(company)
                return company

            # Create new company
            company = Company(
                company_code=company_code,
                name_th=name_th,
                name_en=name_en
            )
            session.add(company)
            session.commit()
            session.refresh(company)
            return company

    def get_company_by_id(self, company_id: int) -> Optional[Company]:
        """Get company by ID."""
        with self.get_session() as session:
            return session.get(Company, company_id)

    def get_all_companies(self) -> List[Company]:
        """Get all companies."""
        with self.get_session() as session:
            stmt = select(Company).order_by(Company.company_code)
            return list(session.scalars(stmt).all())

    # Fiscal Year Operations

    def get_or_create_fiscal_year(
        self,
        company_id: int,
        year_be: int
    ) -> FiscalYear:
        """
        Get existing fiscal year or create new one.

        Args:
            company_id: Company ID
            year_be: Buddhist Era year (e.g., 2567)

        Returns:
            FiscalYear instance
        """
        year_ce = year_be - 543  # Convert BE to CE

        with self.get_session() as session:
            # Try to find existing fiscal year
            stmt = select(FiscalYear).where(
                and_(
                    FiscalYear.company_id == company_id,
                    FiscalYear.year_be == year_be
                )
            )
            fiscal_year = session.scalar(stmt)

            if fiscal_year:
                return fiscal_year

            # Create new fiscal year
            fiscal_year = FiscalYear(
                company_id=company_id,
                year_be=year_be,
                year_ce=year_ce
            )
            session.add(fiscal_year)
            session.commit()
            session.refresh(fiscal_year)
            return fiscal_year

    def get_fiscal_years_by_company(self, company_id: int) -> List[FiscalYear]:
        """Get all fiscal years for a company."""
        with self.get_session() as session:
            stmt = select(FiscalYear).where(
                FiscalYear.company_id == company_id
            ).order_by(FiscalYear.year_be.desc())
            return list(session.scalars(stmt).all())

    # Document Operations

    def create_document(
        self,
        fiscal_year_id: int,
        document_type: str,
        file_path: str,
        file_name: str,
        status: DocumentStatus = DocumentStatus.PENDING,
        page_count: Optional[int] = None,
        file_size_bytes: Optional[int] = None
    ) -> Document:
        """
        Create a new document record.

        Args:
            fiscal_year_id: Fiscal year ID
            document_type: Type of document (e.g., "BS", "Compare PL")
            file_path: Full path to PDF file
            file_name: Original filename
            status: Initial status
            page_count: Number of pages
            file_size_bytes: File size in bytes

        Returns:
            Document instance
        """
        with self.get_session() as session:
            document = Document(
                fiscal_year_id=fiscal_year_id,
                document_type=document_type,
                file_path=str(file_path),
                file_name=file_name,
                status=status,
                page_count=page_count,
                file_size_bytes=file_size_bytes
            )
            session.add(document)
            session.commit()
            session.refresh(document)
            return document

    def update_document_status(
        self,
        document_id: int,
        status: DocumentStatus,
        error_message: Optional[str] = None
    ) -> Document:
        """
        Update document processing status.

        Args:
            document_id: Document ID
            status: New status
            error_message: Error message if status is FAILED

        Returns:
            Updated Document instance
        """
        with self.get_session() as session:
            document = session.get(Document, document_id)
            if not document:
                raise ValueError(f"Document {document_id} not found")

            document.status = status
            if error_message:
                document.error_message = error_message

            if status == DocumentStatus.COMPLETED:
                document.processed_at = datetime.utcnow()

            session.commit()
            session.refresh(document)
            return document

    def get_document_by_id(self, document_id: int) -> Optional[Document]:
        """Get document by ID."""
        with self.get_session() as session:
            return session.get(Document, document_id)

    def get_document_by_file_path(self, file_path: str) -> Optional[Document]:
        """
        Get document by file path.

        Args:
            file_path: Full path to the document file

        Returns:
            Document instance if found, None otherwise
        """
        with self.get_session() as session:
            stmt = select(Document).where(Document.file_path == file_path)
            return session.scalar(stmt)

    def get_documents_by_status(
        self,
        status: DocumentStatus,
        limit: Optional[int] = None
    ) -> List[Document]:
        """
        Get documents by processing status.

        Args:
            status: Document status to filter by
            limit: Maximum number of results

        Returns:
            List of Document instances
        """
        with self.get_session() as session:
            stmt = select(Document).where(Document.status == status)

            if limit:
                stmt = stmt.limit(limit)

            return list(session.scalars(stmt).all())

    def get_documents_by_fiscal_year(self, fiscal_year_id: int) -> List[Document]:
        """Get all documents for a fiscal year."""
        with self.get_session() as session:
            stmt = select(Document).where(
                Document.fiscal_year_id == fiscal_year_id
            ).order_by(Document.document_type, Document.created_at)
            return list(session.scalars(stmt).all())

    # Extracted Table Operations

    def store_extracted_table(
        self,
        document_id: int,
        table_index: int,
        headers: List[str],
        data: List[List[str]],
        markdown: Optional[str] = None,
        table_type: Optional[str] = None,
        confidence_score: Optional[float] = None
    ) -> ExtractedTable:
        """
        Store extracted table data.

        Args:
            document_id: Document ID
            table_index: 0-based table index within document
            headers: List of column headers
            data: 2D list of cell values
            markdown: Markdown representation of table
            table_type: Type of table (optional)
            confidence_score: Average OCR confidence

        Returns:
            ExtractedTable instance
        """
        with self.get_session() as session:
            # Create extracted table
            extracted_table = ExtractedTable(
                document_id=document_id,
                table_index=table_index,
                table_type=table_type,
                headers_json=json.dumps(headers, ensure_ascii=False),
                row_count=len(data),
                col_count=len(headers),
                markdown_content=markdown,
                confidence_score=confidence_score
            )
            session.add(extracted_table)
            session.flush()  # Get ID before adding cells

            # Create table cells
            for row_idx, row in enumerate(data):
                for col_idx, value in enumerate(row):
                    cell = TableCell(
                        extracted_table_id=extracted_table.id,
                        row_index=row_idx,
                        col_index=col_idx,
                        value=value,
                        data_type=DataType.TEXT,  # Default, can be improved
                        is_header=(row_idx == 0)
                    )
                    session.add(cell)

            session.commit()
            session.refresh(extracted_table)
            return extracted_table

    def get_tables_by_document(self, document_id: int) -> List[ExtractedTable]:
        """Get all extracted tables for a document."""
        with self.get_session() as session:
            stmt = select(ExtractedTable).where(
                ExtractedTable.document_id == document_id
            ).order_by(ExtractedTable.table_index)
            return list(session.scalars(stmt).all())

    def get_table_cells(self, table_id: int) -> List[TableCell]:
        """Get all cells for a table, ordered by position."""
        with self.get_session() as session:
            stmt = select(TableCell).where(
                TableCell.extracted_table_id == table_id
            ).order_by(TableCell.row_index, TableCell.col_index)
            return list(session.scalars(stmt).all())

    # Search and Query Operations

    def search_documents(
        self,
        query: str,
        document_type: Optional[str] = None,
        status: Optional[DocumentStatus] = None
    ) -> List[Document]:
        """
        Search documents by query string.

        Args:
            query: Search query (searches in company name and filename)
            document_type: Filter by document type
            status: Filter by status

        Returns:
            List of matching Document instances
        """
        with self.get_session() as session:
            # Join with fiscal year and company for searching
            stmt = (
                select(Document)
                .join(FiscalYear)
                .join(Company)
                .where(
                    or_(
                        Company.name_th.contains(query),
                        Company.name_en.contains(query),
                        Document.file_name.contains(query)
                    )
                )
            )

            if document_type:
                stmt = stmt.where(Document.document_type == document_type)

            if status:
                stmt = stmt.where(Document.status == status)

            return list(session.scalars(stmt).all())

    def get_company_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for dashboard.

        Returns:
            Dictionary with summary statistics
        """
        with self.get_session() as session:
            # Total companies
            total_companies = session.scalar(select(func.count(Company.id)))

            # Total documents
            total_documents = session.scalar(select(func.count(Document.id)))

            # Documents by status
            status_counts = {}
            for status in DocumentStatus:
                count = session.scalar(
                    select(func.count(Document.id)).where(Document.status == status)
                )
                status_counts[status.value] = count

            # Total extracted tables
            total_tables = session.scalar(select(func.count(ExtractedTable.id)))

            # Recent documents
            recent_stmt = (
                select(Document)
                .order_by(Document.created_at.desc())
                .limit(10)
            )
            recent_documents = list(session.scalars(recent_stmt).all())

            return {
                "total_companies": total_companies,
                "total_documents": total_documents,
                "status_counts": status_counts,
                "total_tables": total_tables,
                "recent_documents": recent_documents
            }

    # Export Operations

    def export_to_csv(self, document_id: int, output_path: Optional[str] = None) -> str:
        """
        Export document tables to CSV file.

        Args:
            document_id: Document ID to export
            output_path: Optional output path, auto-generated if not provided

        Returns:
            Path to created CSV file
        """
        with self.get_session() as session:
            document = session.get(Document, document_id)
            if not document:
                raise ValueError(f"Document {document_id} not found")

            tables = self.get_tables_by_document(document_id)
            if not tables:
                raise ValueError(f"No tables found for document {document_id}")

            # Generate output path if not provided
            if not output_path:
                filename = f"export_doc_{document_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                output_path = str(config.EXPORTS_PATH / filename)

            # Write CSV
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write document metadata
                writer.writerow(['Document ID', document_id])
                writer.writerow(['File Name', document.file_name])
                writer.writerow(['Document Type', document.document_type])
                writer.writerow(['Processed At', document.processed_at])
                writer.writerow([])

                # Write each table
                for table in tables:
                    writer.writerow([f'Table {table.table_index}'])
                    if table.table_type:
                        writer.writerow(['Table Type', table.table_type])

                    # Get headers
                    headers = json.loads(table.headers_json) if table.headers_json else []
                    if headers:
                        writer.writerow(headers)

                    # Get and write cells
                    cells = self.get_table_cells(table.id)
                    current_row = []
                    current_row_idx = 0

                    for cell in cells:
                        if cell.row_index != current_row_idx:
                            if current_row:
                                writer.writerow(current_row)
                            current_row = []
                            current_row_idx = cell.row_index

                        current_row.append(cell.value or '')

                    if current_row:
                        writer.writerow(current_row)

                    writer.writerow([])  # Empty row between tables

            return output_path

    def export_to_json(self, document_id: int) -> Dict[str, Any]:
        """
        Export document tables to JSON structure.

        Args:
            document_id: Document ID to export

        Returns:
            Dictionary containing document and table data
        """
        with self.get_session() as session:
            document = session.get(Document, document_id)
            if not document:
                raise ValueError(f"Document {document_id} not found")

            tables = self.get_tables_by_document(document_id)

            # Build JSON structure
            result = {
                "document_id": document.id,
                "file_name": document.file_name,
                "document_type": document.document_type,
                "status": document.status.value,
                "processed_at": document.processed_at.isoformat() if document.processed_at else None,
                "tables": []
            }

            for table in tables:
                headers = json.loads(table.headers_json) if table.headers_json else []
                cells = self.get_table_cells(table.id)

                # Organize cells into rows
                rows = []
                current_row = []
                current_row_idx = 0

                for cell in cells:
                    if cell.row_index != current_row_idx:
                        if current_row:
                            rows.append(current_row)
                        current_row = []
                        current_row_idx = cell.row_index

                    current_row.append({
                        "value": cell.value,
                        "data_type": cell.data_type.value,
                        "confidence": cell.confidence_score,
                        "is_header": cell.is_header
                    })

                if current_row:
                    rows.append(current_row)

                table_data = {
                    "table_index": table.table_index,
                    "table_type": table.table_type,
                    "headers": headers,
                    "row_count": table.row_count,
                    "col_count": table.col_count,
                    "confidence_score": table.confidence_score,
                    "markdown": table.markdown_content,
                    "rows": rows
                }

                result["tables"].append(table_data)

            return result

    # Utility Operations

    def delete_document(self, document_id: int) -> bool:
        """
        Delete a document and all related data.

        Args:
            document_id: Document ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self.get_session() as session:
            document = session.get(Document, document_id)
            if not document:
                return False

            session.delete(document)
            session.commit()
            return True

    def cleanup_failed_documents(self, older_than_days: int = 7) -> int:
        """
        Delete failed documents older than specified days.

        Args:
            older_than_days: Delete documents older than this many days

        Returns:
            Number of documents deleted
        """
        with self.get_session() as session:
            cutoff_date = datetime.utcnow().replace(
                day=datetime.utcnow().day - older_than_days
            )

            stmt = select(Document).where(
                and_(
                    Document.status == DocumentStatus.FAILED,
                    Document.created_at < cutoff_date
                )
            )

            documents = list(session.scalars(stmt).all())
            count = len(documents)

            for doc in documents:
                session.delete(doc)

            session.commit()
            return count

    # Processed Document Cache Operations

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """
        Compute SHA256 hash of a file for change detection.

        Args:
            file_path: Path to file

        Returns:
            SHA256 hex digest
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in 64kb chunks for memory efficiency
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def get_file_info(file_path: str) -> Dict[str, Any]:
        """
        Get file metadata for tracking changes.

        Args:
            file_path: Path to file

        Returns:
            Dict with hash, size, and modification time
        """
        stat = os.stat(file_path)
        return {
            "file_hash": DatabaseManager.compute_file_hash(file_path),
            "file_size_bytes": stat.st_size,
            "file_modified_at": datetime.fromtimestamp(stat.st_mtime)
        }

    def save_processed_document(
        self,
        file_path: str,
        file_name: str,
        status: str,
        tables_found: int = 0,
        text_blocks: int = 0,
        result_json: Optional[str] = None
    ) -> ProcessedDocumentCache:
        """
        Save processed document to cache for persistence across restarts.

        Args:
            file_path: Full path to the processed file
            file_name: Original filename
            status: Processing status (success/failed)
            tables_found: Number of tables extracted
            text_blocks: Number of text blocks extracted
            result_json: JSON string of extracted data

        Returns:
            ProcessedDocumentCache instance
        """
        file_info = self.get_file_info(file_path)

        with self.get_session() as session:
            # Check if already exists
            stmt = select(ProcessedDocumentCache).where(
                ProcessedDocumentCache.file_path == file_path
            )
            existing = session.scalar(stmt)

            if existing:
                # Update existing record
                existing.file_hash = file_info["file_hash"]
                existing.file_size_bytes = file_info["file_size_bytes"]
                existing.file_modified_at = file_info["file_modified_at"]
                existing.status = status
                existing.tables_found = tables_found
                existing.text_blocks = text_blocks
                existing.result_json = result_json
                existing.processed_at = datetime.utcnow()
                session.commit()
                session.refresh(existing)
                return existing

            # Create new record
            cache_entry = ProcessedDocumentCache(
                file_path=file_path,
                file_name=file_name,
                file_hash=file_info["file_hash"],
                file_size_bytes=file_info["file_size_bytes"],
                file_modified_at=file_info["file_modified_at"],
                status=status,
                tables_found=tables_found,
                text_blocks=text_blocks,
                result_json=result_json,
                processed_at=datetime.utcnow()
            )
            session.add(cache_entry)
            session.commit()
            session.refresh(cache_entry)
            return cache_entry

    def get_cached_document(self, file_path: str) -> Optional[ProcessedDocumentCache]:
        """
        Get cached processing result for a document.

        Args:
            file_path: Path to the document file

        Returns:
            ProcessedDocumentCache if found, None otherwise
        """
        with self.get_session() as session:
            stmt = select(ProcessedDocumentCache).where(
                ProcessedDocumentCache.file_path == file_path
            )
            return session.scalar(stmt)

    def is_document_processed(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a document is already processed and still valid.

        A document is considered valid if:
        1. It exists in the cache
        2. The file hash matches (file hasn't been modified)

        Args:
            file_path: Path to the document file

        Returns:
            Tuple of (is_processed, status_reason)
            - (True, 'valid') - Processed and unchanged
            - (False, 'not_found') - Never processed
            - (False, 'file_changed') - Was processed but file modified
            - (False, 'file_missing') - File doesn't exist
        """
        # Check if file exists
        if not os.path.exists(file_path):
            return False, 'file_missing'

        cached = self.get_cached_document(file_path)

        if cached is None:
            return False, 'not_found'

        # Compute current file hash
        try:
            current_hash = self.compute_file_hash(file_path)
        except Exception:
            return False, 'file_missing'

        # Compare hashes
        if cached.file_hash != current_hash:
            return False, 'file_changed'

        return True, 'valid'

    def get_all_cached_documents(self) -> List[ProcessedDocumentCache]:
        """
        Get all cached processed documents.

        Returns:
            List of ProcessedDocumentCache instances
        """
        with self.get_session() as session:
            stmt = select(ProcessedDocumentCache).order_by(
                ProcessedDocumentCache.processed_at.desc()
            )
            return list(session.scalars(stmt).all())

    def get_processed_file_paths(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all processed file paths with their status and validity.

        Returns:
            Dict mapping file_path to status info
        """
        cached = self.get_all_cached_documents()
        result = {}

        for doc in cached:
            is_valid, reason = self.is_document_processed(doc.file_path)
            result[doc.file_path] = {
                'status': doc.status,
                'tables_found': doc.tables_found,
                'text_blocks': doc.text_blocks,
                'processed_at': doc.processed_at,
                'is_valid': is_valid,
                'validity_reason': reason
            }

        return result

    def invalidate_cache(self, file_path: str) -> bool:
        """
        Remove a document from the cache.

        Args:
            file_path: Path to the document file

        Returns:
            True if removed, False if not found
        """
        with self.get_session() as session:
            stmt = delete(ProcessedDocumentCache).where(
                ProcessedDocumentCache.file_path == file_path
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount > 0

    def clear_cache(self) -> int:
        """
        Clear all cached processed documents.

        Returns:
            Number of entries deleted
        """
        with self.get_session() as session:
            stmt = delete(ProcessedDocumentCache)
            result = session.execute(stmt)
            session.commit()
            return result.rowcount

    def save_session_state(self, processed_documents: List[Dict[str, Any]]) -> int:
        """
        Save all processed documents from session state to database.

        Called on app shutdown to persist processing results.

        Args:
            processed_documents: List of processed document dicts from session

        Returns:
            Number of documents saved
        """
        saved_count = 0
        for doc in processed_documents:
            file_path = doc.get('file_path') or doc.get('path')
            if not file_path:
                continue

            # Skip if file doesn't exist
            if not os.path.exists(file_path):
                continue

            try:
                self.save_processed_document(
                    file_path=file_path,
                    file_name=doc.get('filename', os.path.basename(file_path)),
                    status=doc.get('status', 'success'),
                    tables_found=doc.get('tables_found', 0),
                    text_blocks=doc.get('text_blocks', 0),
                    result_json=json.dumps(doc, ensure_ascii=False) if doc else None
                )
                saved_count += 1
            except Exception:
                continue  # Skip failed saves

        return saved_count

    def load_session_state(self) -> List[Dict[str, Any]]:
        """
        Load valid processed documents to restore session state.

        Called on app startup to restore previous processing results.

        Returns:
            List of processed document dicts for session state
        """
        cached = self.get_all_cached_documents()
        result = []

        for doc in cached:
            is_valid, reason = self.is_document_processed(doc.file_path)

            # Only include valid (unchanged) documents
            if is_valid:
                # Try to restore from JSON, fallback to basic info
                if doc.result_json:
                    try:
                        doc_data = json.loads(doc.result_json)
                        result.append(doc_data)
                        continue
                    except json.JSONDecodeError:
                        pass

                # Basic info fallback
                result.append({
                    'id': f"cached_{doc.id}",
                    'filename': doc.file_name,
                    'file_path': doc.file_path,
                    'path': doc.file_path,
                    'status': doc.status,
                    'tables_found': doc.tables_found,
                    'text_blocks': doc.text_blocks,
                    'timestamp': doc.processed_at.strftime("%Y-%m-%d %H:%M:%S")
                })

        return result

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
        try:
            # Get or create default company/fiscal year for uncategorized documents
            default_company = self.get_or_create_company(
                company_code="UNCATEGORIZED",
                name_th="ไม่ระบุบริษัท",
                name_en="Uncategorized"
            )

            # Use current year as default fiscal year
            current_year_be = datetime.now().year + 543
            default_fiscal_year = self.get_or_create_fiscal_year(
                company_id=default_company.id,
                year_be=current_year_be
            )

            with self.get_session() as session:
                # Check if document already exists
                stmt = select(Document).where(Document.file_path == file_path)
                document = session.scalar(stmt)

                if document:
                    # Update existing document
                    document.status = DocumentStatus.COMPLETED
                    document.processed_at = datetime.utcnow()

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

                doc_id_result = document.id
                session.commit()

            # Store extracted tables (outside transaction to avoid nested session issues)
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
                        markdown = ocr_result.markdown

                    # Store the table
                    self.store_extracted_table(
                        document_id=doc_id_result,
                        table_index=table_idx,
                        headers=[str(h) for h in headers],
                        data=data,
                        markdown=markdown,
                        table_type=None,
                        confidence_score=None
                    )

            return doc_id_result

        except Exception as e:
            raise Exception(f"Failed to save OCR results: {str(e)}")
