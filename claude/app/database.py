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
    DocumentStatus, DataType
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

    def get_document_by_file_path(
        self,
        file_path: str,
        engine: Optional[str] = None
    ) -> Optional[Document]:
        """
        Get document by file path, optionally filtered by engine.

        Args:
            file_path: Full path to the document file
            engine: OCR engine name (docling/typhoon). If None, returns first match.

        Returns:
            Document instance if found, None otherwise
        """
        with self.get_session() as session:
            if engine:
                stmt = select(Document).where(
                    Document.file_path == file_path,
                    Document.engine == engine
                )
            else:
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

    def clear_all_documents(self) -> int:
        """
        Delete ALL documents from the database.

        This is a destructive operation that clears all processed documents,
        extracted tables, and related data. Use with caution.

        Returns:
            Number of documents deleted
        """
        with self.get_session() as session:
            # Count documents first
            count = session.query(Document).count()

            # Delete all documents (cascades to related tables)
            session.execute(delete(Document))
            session.commit()

            return count

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

    # Document Processing Operations (Simplified - No Cache Layer)

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

    def is_document_processed(
        self,
        file_path: str,
        engine: str = "docling"
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a document is already processed and still valid for a specific engine.

        A document is considered valid if:
        1. It exists in the documents table for the specified engine
        2. Status is COMPLETED
        3. The file hash matches (file hasn't been modified)

        Args:
            file_path: Path to the document file
            engine: OCR engine to check (required - must be specific)

        Returns:
            Tuple of (is_processed, status_reason)
            - (True, 'valid') - Processed and unchanged
            - (False, 'not_found') - Never processed by this engine
            - (False, 'file_changed') - Was processed but file modified
            - (False, 'file_missing') - File doesn't exist
        """
        # Check if file exists
        if not os.path.exists(file_path):
            return False, 'file_missing'

        with self.get_session() as session:
            # Query documents table for this specific file_path + engine combo
            stmt = select(Document).where(
                and_(
                    Document.file_path == file_path,
                    Document.engine == engine,
                    Document.status == DocumentStatus.COMPLETED
                )
            )
            document = session.scalar(stmt)

            if document is None:
                return False, 'not_found'

            # Compute current file hash
            try:
                current_hash = self.compute_file_hash(file_path)
            except Exception:
                return False, 'file_missing'

            # Compare hashes
            if document.file_hash != current_hash:
                return False, 'file_changed'

            return True, 'valid'

    def get_available_engines_for_document(self, file_path: str) -> List[str]:
        """
        Get list of engines that have processed a document.

        Args:
            file_path: Path to the document file

        Returns:
            List of engine names (e.g., ['docling', 'typhoon'])
        """
        with self.get_session() as session:
            stmt = select(Document.engine).where(
                and_(
                    Document.file_path == file_path,
                    Document.status == DocumentStatus.COMPLETED
                )
            ).distinct()
            return list(session.scalars(stmt).all())

    def get_processed_documents(
        self,
        engine: Optional[str] = None
    ) -> List[Document]:
        """
        Get all processed (completed) documents.

        Args:
            engine: Filter by OCR engine (if None, returns all)

        Returns:
            List of Document instances
        """
        with self.get_session() as session:
            stmt = select(Document).where(
                Document.status == DocumentStatus.COMPLETED
            )
            if engine:
                stmt = stmt.where(Document.engine == engine)
            stmt = stmt.order_by(Document.processed_at.desc())
            return list(session.scalars(stmt).all())

    def get_documents_with_engines(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all unique documents with their available engine versions.

        Returns:
            Dict mapping file_path to info including available engines
        """
        documents = self.get_processed_documents()
        result = {}

        for doc in documents:
            if doc.file_path not in result:
                result[doc.file_path] = {
                    'file_path': doc.file_path,
                    'file_name': doc.file_name,
                    'engines': {},
                    'latest_processed_at': doc.processed_at
                }

            result[doc.file_path]['engines'][doc.engine] = {
                'status': doc.status.value if hasattr(doc.status, 'value') else doc.status,
                'tables_found': doc.tables_found,
                'text_blocks': doc.text_blocks,
                'processed_at': doc.processed_at,
                'markdown_content': doc.markdown_content,
                'text_content': doc.text_content
            }

            # Update latest processed time
            if doc.processed_at and doc.processed_at > result[doc.file_path]['latest_processed_at']:
                result[doc.file_path]['latest_processed_at'] = doc.processed_at

        return result

    def save_session_state(
        self,
        processed_documents: List[Dict[str, Any]],
        engine: str = "docling"
    ) -> int:
        """
        Save all processed documents from session state to database.

        Called on app shutdown to persist processing results.
        Now updates the documents table directly.

        Args:
            processed_documents: List of processed document dicts from session
            engine: Default OCR engine used for processing

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
                # Use engine from doc if available, otherwise use parameter
                doc_engine = doc.get('engine', engine)
                file_info = self.get_file_info(file_path)

                with self.get_session() as session:
                    # Check if document exists for this engine
                    stmt = select(Document).where(
                        and_(
                            Document.file_path == file_path,
                            Document.engine == doc_engine
                        )
                    )
                    document = session.scalar(stmt)

                    if document:
                        # Update existing document
                        document.file_hash = file_info["file_hash"]
                        document.file_size_bytes = file_info["file_size_bytes"]
                        document.file_modified_at = file_info["file_modified_at"]
                        document.tables_found = doc.get('tables_found', 0)
                        document.text_blocks = doc.get('text_blocks', 0)
                        document.markdown_content = doc.get('markdown_content')
                        document.text_content = doc.get('text_content')
                        if doc.get('status') == 'success':
                            document.status = DocumentStatus.COMPLETED
                        session.commit()

                saved_count += 1
            except Exception:
                continue  # Skip failed saves

        return saved_count

    def load_session_state(
        self,
        engine: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Load valid processed documents to restore session state.

        Called on app startup to restore previous processing results.
        Now reads from documents table directly.

        Args:
            engine: Filter by OCR engine (if None, returns all)

        Returns:
            List of processed document dicts for session state
        """
        documents = self.get_processed_documents(engine=engine)
        result = []

        for doc in documents:
            is_valid, reason = self.is_document_processed(doc.file_path, engine=doc.engine)

            # Only include valid (unchanged) documents
            if is_valid:
                result.append({
                    'id': f"doc_{doc.id}",
                    'filename': doc.file_name,
                    'file_path': doc.file_path,
                    'path': doc.file_path,
                    'status': 'success' if doc.status == DocumentStatus.COMPLETED else 'failed',
                    'tables_found': doc.tables_found,
                    'text_blocks': doc.text_blocks,
                    'engine': doc.engine,
                    'markdown_content': doc.markdown_content,
                    'text_content': doc.text_content,
                    'timestamp': doc.processed_at.strftime("%Y-%m-%d %H:%M:%S") if doc.processed_at else None
                })

        return result

    def save_full_ocr_results(
        self,
        file_path: str,
        file_name: str,
        ocr_result,
        doc_id: str,
        engine: str = "docling"
    ) -> Optional[int]:
        """
        Save full OCR results to the documents table and extracted tables.

        Creates or updates Document record with OCR content and stores all
        extracted tables with their data. Single source of truth in documents table.

        Args:
            file_path: Full path to the PDF file
            file_name: Original filename
            ocr_result: ProcessedDocument from OCR processor
            doc_id: Document identifier
            engine: OCR engine used (docling or typhoon)

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

            # Get file info for hash tracking
            file_info = self.get_file_info(file_path)

            # Extract OCR content
            tables_count = len(ocr_result.tables) if hasattr(ocr_result, 'tables') and ocr_result.tables else 0
            text_blocks_count = len(ocr_result.text_content.split('\n\n')) if hasattr(ocr_result, 'text_content') and ocr_result.text_content else 0
            markdown_content = ocr_result.markdown if hasattr(ocr_result, 'markdown') else None
            text_content = ocr_result.text_content if hasattr(ocr_result, 'text_content') else None

            with self.get_session() as session:
                # Check if document already exists for this engine
                # Each engine gets its own document record (multi-engine support)
                stmt = select(Document).where(
                    and_(
                        Document.file_path == file_path,
                        Document.engine == engine
                    )
                )
                document = session.scalar(stmt)

                if document:
                    # Update existing document for this engine
                    document.status = DocumentStatus.COMPLETED
                    document.processed_at = datetime.utcnow()
                    document.file_hash = file_info["file_hash"]
                    document.file_size_bytes = file_info["file_size_bytes"]
                    document.file_modified_at = file_info["file_modified_at"]
                    document.markdown_content = markdown_content
                    document.text_content = text_content
                    document.tables_found = tables_count
                    document.text_blocks = text_blocks_count

                    # Delete existing tables to replace with new data
                    session.execute(
                        delete(ExtractedTable).where(ExtractedTable.document_id == document.id)
                    )
                else:
                    # Create new document for this engine
                    document = Document(
                        fiscal_year_id=default_fiscal_year.id,
                        document_type="Unknown",  # Could be inferred from filename
                        file_path=file_path,
                        file_name=file_name,
                        file_hash=file_info["file_hash"],
                        file_size_bytes=file_info["file_size_bytes"],
                        file_modified_at=file_info["file_modified_at"],
                        engine=engine,
                        status=DocumentStatus.COMPLETED,
                        processed_at=datetime.utcnow(),
                        markdown_content=markdown_content,
                        text_content=text_content,
                        tables_found=tables_count,
                        text_blocks=text_blocks_count
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
                        # Only use markdown if it's specific to this table (Docling doesn't provide per-table markdown yet)
                        # markdown = ocr_result.markdown  <-- BUG: This was assigning full doc markdown to every table
                        pass

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
