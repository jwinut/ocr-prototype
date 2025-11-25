"""
SQLAlchemy database schema for Thai Financial Document OCR.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    String, Integer, Float, Text, DateTime, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class DocumentStatus(str, enum.Enum):
    """Document processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DataType(str, enum.Enum):
    """Cell data type enumeration."""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    UNKNOWN = "unknown"


class Company(Base):
    """Company entity - represents Thai companies from Y67 folders."""
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name_th: Mapped[str] = mapped_column(String(500), nullable=False)
    name_en: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    fiscal_years: Mapped[List["FiscalYear"]] = relationship(
        "FiscalYear", back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Company(code={self.company_code}, name_th={self.name_th[:30]})>"


class FiscalYear(Base):
    """Fiscal year entity - groups documents by company and year."""
    __tablename__ = "fiscal_years"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    year_be: Mapped[int] = mapped_column(Integer, nullable=False)  # Buddhist Era
    year_ce: Mapped[int] = mapped_column(Integer, nullable=False)  # Common Era
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="fiscal_years")
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="fiscal_year", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FiscalYear(company_id={self.company_id}, year_be={self.year_be})>"


class Document(Base):
    """Document entity - individual PDF files."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_years.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # SHA256 hash for change detection
    file_modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # File modification time
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True
    )
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    fiscal_year: Mapped["FiscalYear"] = relationship("FiscalYear", back_populates="documents")
    extracted_tables: Mapped[List["ExtractedTable"]] = relationship(
        "ExtractedTable", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, type={self.document_type}, status={self.status.value})>"


class ExtractedTable(Base):
    """Extracted table entity - tables found in documents."""
    __tablename__ = "extracted_tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    table_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-based index within document
    table_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "balance_sheet", "income_statement"
    headers_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of column headers
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    col_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    markdown_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Markdown representation
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Average OCR confidence
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="extracted_tables")
    cells: Mapped[List["TableCell"]] = relationship(
        "TableCell", back_populates="table", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ExtractedTable(id={self.id}, doc_id={self.document_id}, idx={self.table_index})>"


class TableCell(Base):
    """Table cell entity - individual cells within extracted tables."""
    __tablename__ = "table_cells"

    id: Mapped[int] = mapped_column(primary_key=True)
    extracted_table_id: Mapped[int] = mapped_column(ForeignKey("extracted_tables.id"), nullable=False, index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    col_index: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_type: Mapped[DataType] = mapped_column(
        SQLEnum(DataType),
        default=DataType.TEXT,
        nullable=False
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_header: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    table: Mapped["ExtractedTable"] = relationship("ExtractedTable", back_populates="cells")

    def __repr__(self) -> str:
        return f"<TableCell(table_id={self.extracted_table_id}, pos=[{self.row_index},{self.col_index}])>"


class ProcessedDocumentCache(Base):
    """Cache for processed documents from session state.

    Persists session-based processing results between app restarts.
    Tracks file changes via hash to invalidate stale results.
    """
    __tablename__ = "processed_document_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 hash
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Processing results
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failed
    tables_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_blocks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Full extracted data as JSON

    # Timestamps
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ProcessedDocumentCache(path={self.file_path}, status={self.status})>"
