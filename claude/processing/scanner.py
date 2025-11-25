"""
Document Scanner - File discovery and metadata extraction
Scans Y67 directory structure and extracts metadata from paths/filenames
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class DocumentInfo:
    """Metadata for a discovered financial document"""
    file_path: Path
    file_name: str
    company_code: str
    company_name: str
    fiscal_year: str  # e.g., "Y67"
    document_type: str  # BS, PL, CashFlow, etc.
    file_size: int

    def __repr__(self) -> str:
        return (
            f"DocumentInfo(company={self.company_code}, "
            f"year={self.fiscal_year}, type={self.document_type})"
        )


# Document type detection patterns
DOCUMENT_TYPE_PATTERNS = {
    'BS': r'_BS\d{2}\.pdf$',  # Balance Sheet: _BS67.pdf
    'PL': r'_PL\d{2}\.pdf$',  # Profit & Loss: _PL67.pdf
    'Compare BS': r'_Compare BS\.pdf$',
    'Compare PL': r'_Compare PL\.pdf$',
    'Cash Flow': r'_Cash Flow\.pdf$',
    'Gen Info': r'_Gen Info\.pdf$',
    'Ratio': r'_Ratio\.pdf$',
    'Related': r'_Related\.pdf$',
    'Shareholders': r'_Shareholders\.pdf$',
    'Others': r'_Others\.pdf$',
}


def parse_company_folder(folder_name: str) -> Tuple[str, str]:
    """
    Extract company_code and company_name from folder like:
    '10002819 บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด'

    Args:
        folder_name: Folder name with format '{code} {thai_company_name}'

    Returns:
        Tuple of (company_code, company_name)

    Examples:
        >>> parse_company_folder('10002819 บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด')
        ('10002819', 'บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด')
    """
    # Pattern: digits at start, followed by space, then Thai company name
    match = re.match(r'^(\d+)\s+(.+)$', folder_name)

    if not match:
        # Fallback: return folder name as both code and name
        return folder_name, folder_name

    company_code = match.group(1)
    company_name = match.group(2).strip()

    return company_code, company_name


def detect_document_type(filename: str) -> str:
    """
    Detect document type from filename patterns.

    Args:
        filename: PDF filename

    Returns:
        Document type string (BS, PL, Cash Flow, etc.) or 'Unknown'

    Examples:
        >>> detect_document_type('บริษัท โฮชุง_BS67.pdf')
        'BS'
        >>> detect_document_type('บริษัท โฮชุง_Compare PL.pdf')
        'Compare PL'
    """
    for doc_type, pattern in DOCUMENT_TYPE_PATTERNS.items():
        if re.search(pattern, filename):
            return doc_type

    return 'Unknown'


def scan_directory(base_path: str, target_year: str = "Y67") -> List[DocumentInfo]:
    """
    Scan Y67 directory structure and extract metadata from paths/filenames.

    Directory structure:
        Y67/
        └── {company_code} {company_name}/
            └── Y67/
                ├── {company_name}_BS67.pdf
                ├── {company_name}_Compare BS.pdf
                └── ...

    Args:
        base_path: Root path containing company folders
        target_year: Fiscal year to scan (default: Y67)

    Returns:
        List of DocumentInfo objects for all discovered PDFs

    Example:
        >>> docs = scan_directory('/Users/nut/ocr-prototype/Y67')
        >>> len(docs)
        466
        >>> docs[0].company_code
        '10002819'
    """
    base = Path(base_path)
    discovered_docs: List[DocumentInfo] = []

    if not base.exists():
        raise FileNotFoundError(f"Base path does not exist: {base_path}")

    # Iterate over company folders
    for company_folder in sorted(base.iterdir()):
        if not company_folder.is_dir():
            continue

        # Skip hidden folders and non-company folders
        if company_folder.name.startswith('.'):
            continue

        # Parse company info from folder name
        company_code, company_name = parse_company_folder(company_folder.name)

        # Look for target year subfolder
        year_folder = company_folder / target_year
        if not year_folder.exists() or not year_folder.is_dir():
            continue

        # Scan PDFs in year folder
        for pdf_file in sorted(year_folder.glob('*.pdf')):
            if pdf_file.is_file():
                doc_type = detect_document_type(pdf_file.name)

                doc_info = DocumentInfo(
                    file_path=pdf_file,
                    file_name=pdf_file.name,
                    company_code=company_code,
                    company_name=company_name,
                    fiscal_year=target_year,
                    document_type=doc_type,
                    file_size=pdf_file.stat().st_size
                )

                discovered_docs.append(doc_info)

    return discovered_docs


def filter_by_document_type(
    docs: List[DocumentInfo],
    doc_types: List[str]
) -> List[DocumentInfo]:
    """
    Filter documents by type.

    Args:
        docs: List of DocumentInfo
        doc_types: List of document types to include (e.g., ['BS', 'PL'])

    Returns:
        Filtered list of DocumentInfo
    """
    return [doc for doc in docs if doc.document_type in doc_types]


def filter_by_company(
    docs: List[DocumentInfo],
    company_codes: List[str]
) -> List[DocumentInfo]:
    """
    Filter documents by company code.

    Args:
        docs: List of DocumentInfo
        company_codes: List of company codes to include

    Returns:
        Filtered list of DocumentInfo
    """
    return [doc for doc in docs if doc.company_code in company_codes]


def group_by_company(docs: List[DocumentInfo]) -> dict[str, List[DocumentInfo]]:
    """
    Group documents by company code.

    Args:
        docs: List of DocumentInfo

    Returns:
        Dict mapping company_code to list of documents
    """
    grouped = {}
    for doc in docs:
        if doc.company_code not in grouped:
            grouped[doc.company_code] = []
        grouped[doc.company_code].append(doc)
    return grouped


def get_statistics(docs: List[DocumentInfo]) -> dict:
    """
    Get statistics about scanned documents.

    Args:
        docs: List of DocumentInfo

    Returns:
        Dict with statistics
    """
    doc_types = {}
    total_size = 0

    for doc in docs:
        doc_types[doc.document_type] = doc_types.get(doc.document_type, 0) + 1
        total_size += doc.file_size

    return {
        'total_documents': len(docs),
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'unique_companies': len(set(doc.company_code for doc in docs)),
        'document_types': doc_types,
    }
