from __future__ import annotations

import logging
from pathlib import Path
from typing import List

LOGGER = logging.getLogger(__name__)


def pdf_to_images(pdf_path: Path, output_dir: Path, dpi: int = 300) -> List[Path]:
    """Render a PDF into individual page images."""
    from pdf2image import convert_from_path

    output_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Rendering %s -> %s", pdf_path.name, output_dir)
    images = convert_from_path(str(pdf_path), dpi=dpi)
    saved_paths: List[Path] = []
    for idx, page in enumerate(images, start=1):
        image_path = output_dir / f"page-{idx:04d}.png"
        page.save(str(image_path), format="PNG")
        saved_paths.append(image_path)
    return saved_paths
