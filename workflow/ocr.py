from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from .config import WorkflowConfig

LOGGER = logging.getLogger(__name__)


class PaddleOCREngine:
    """Wrapper around PaddleOCR for Thai/English recognition."""

    def __init__(self, config: WorkflowConfig):
        try:
            from paddleocr import PaddleOCR  # type: ignore
        except ImportError as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "paddleocr is required. Install with `pip install paddleocr`"
            ) from exc
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang=config.paddle_lang,
            use_gpu=config.use_gpu,
            show_log=False,
        )

    def process_image(self, image_path: Path) -> Dict[str, Any]:
        LOGGER.debug("Running PaddleOCR on %s", image_path)
        result = self.ocr.ocr(str(image_path), cls=True)
        return {
            "image": str(image_path),
            "results": result,
        }


def write_ocr_json(results: List[Dict[str, Any]], output_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def run_ocrmypdf(pdf_path: Path, output_pdf: Path, config: WorkflowConfig) -> subprocess.CompletedProcess[str]:
    """Execute OCRmyPDF to embed a text layer."""
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        config.ocrmypdf_binary,
        "--language",
        config.languages,
        "--deskew",
        "--clean",
        str(pdf_path),
        str(output_pdf),
    ]
    LOGGER.info("Running %s", " ".join(cmd))
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        LOGGER.error("OCRmyPDF failed for %s: %s", pdf_path, completed.stderr)
    return completed
