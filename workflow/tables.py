from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List

import pdfplumber

LOGGER = logging.getLogger(__name__)


def extract_tables(pdf_path: Path, output_dir: Path) -> List[Path]:
    """Extract tables with pdfplumber; return CSV paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_paths: List[Path] = []
    LOGGER.info("Extracting tables from %s", pdf_path.name)
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table_index, table in enumerate(tables, start=1):
                csv_path = output_dir / f"page-{page_index:02d}-table-{table_index:02d}.csv"
                with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
                    writer = csv.writer(csvfile)
                    for row in table:
                        writer.writerow(row)
                csv_paths.append(csv_path)
    return csv_paths
