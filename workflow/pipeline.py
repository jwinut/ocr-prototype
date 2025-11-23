from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from .config import WorkflowConfig
from .preprocess import pdf_to_images
from .ocr import PaddleOCREngine, write_ocr_json, run_ocrmypdf
from .tables import extract_tables

LOGGER = logging.getLogger(__name__)


class OCRWorkflow:
    """Coordinates preprocessing, OCR, and table extraction."""

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.config.ensure_dirs()

    def build_pdf_context(self, pdf_path: Path) -> Dict[str, Path]:
        relative = pdf_path.relative_to(self.config.source_root)
        base_stem = pdf_path.stem
        temp_dir = self.config.temp_root / relative.parent / base_stem
        output_dir = self.config.output_root / relative.parent / base_stem
        return {
            "images": temp_dir / "images",
            "ocr_json": output_dir / "ocr" / f"{base_stem}.json",
            "ocr_pdf": output_dir / "ocr" / f"{base_stem}.pdf",
            "tables": output_dir / "tables",
            "text": output_dir / f"{base_stem}.txt",
        }

    def preprocess(self, pdf_path: Path) -> List[Path]:
        ctx = self.build_pdf_context(pdf_path)
        return pdf_to_images(pdf_path, ctx["images"], dpi=self.config.dpi)

    def paddle_ocr(self, pdf_path: Path, image_paths: List[Path]) -> Path:
        ctx = self.build_pdf_context(pdf_path)
        engine = PaddleOCREngine(self.config)
        results = []
        for image_path in image_paths:
            results.append(engine.process_image(image_path))
        write_ocr_json(results, ctx["ocr_json"])
        return ctx["ocr_json"]

    def ocrmypdf(self, pdf_path: Path) -> Path:
        ctx = self.build_pdf_context(pdf_path)
        completed = run_ocrmypdf(pdf_path, ctx["ocr_pdf"], self.config)
        if completed.returncode != 0:
            raise RuntimeError(f"OCRmyPDF failed for {pdf_path}")
        return ctx["ocr_pdf"]

    def tables(self, pdf_path: Path) -> List[Path]:
        ctx = self.build_pdf_context(pdf_path)
        return extract_tables(pdf_path, ctx["tables"])

    def process_pdf(self, pdf_path: Path) -> Dict[str, Path]:
        LOGGER.info("Processing %s", pdf_path)
        images = self.preprocess(pdf_path)
        json_path = self.paddle_ocr(pdf_path, images)
        ocr_pdf = self.ocrmypdf(pdf_path)
        table_paths = self.tables(ocr_pdf)
        return {
            "json": str(json_path),
            "pdf": str(ocr_pdf),
            "tables": [str(path) for path in table_paths],
        }

    def run_batch(self) -> List[Dict[str, Path]]:
        results = []
        for pdf in self.config.iter_pdfs():
            results.append(self.process_pdf(pdf))
        return results
