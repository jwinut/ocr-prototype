from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import typer

from workflow import OCRWorkflow, WorkflowConfig

app = typer.Typer(help="Batch OCR pipeline controller")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


@app.command()
def init_config(
    config_path: Path = typer.Argument(Path("workflow.config.json")),
    source_root: Path = typer.Option(Path("Y67"), help="Folder containing source PDFs"),
    output_root: Path = typer.Option(Path("output"), help="Destination for OCR artifacts"),
    temp_root: Path = typer.Option(Path("processed"), help="Temporary working directory"),
    dpi: int = typer.Option(300, help="Render DPI for preprocessing"),
    languages: str = typer.Option("tha+eng", help="Tesseract language codes"),
    paddle_lang: str = typer.Option("thai", help="PaddleOCR language"),
    use_gpu: bool = typer.Option(False, help="Enable GPU for PaddleOCR"),
) -> None:
    """Create a reusable configuration JSON file."""
    cfg = WorkflowConfig(
        source_root=source_root,
        output_root=output_root,
        temp_root=temp_root,
        dpi=dpi,
        languages=languages,
        paddle_lang=paddle_lang,
        use_gpu=use_gpu,
    )
    cfg.to_json(config_path)
    typer.echo(f"Wrote {config_path}")


def load_cfg(config_path: Path | None) -> WorkflowConfig:
    if config_path and config_path.exists():
        return WorkflowConfig.from_json(config_path)
    return WorkflowConfig()


@app.command("preprocess")
def preprocess_cmd(
    config_path: Optional[Path] = typer.Option(None, help="Path to workflow config"),
    sample_limit: Optional[int] = typer.Option(None, help="Limit number of PDFs"),
) -> None:
    cfg = load_cfg(config_path)
    cfg.sample_limit = sample_limit
    workflow = OCRWorkflow(cfg)
    for pdf in cfg.iter_pdfs():
        workflow.preprocess(pdf)


@app.command("paddle-ocr")
def paddle_cmd(
    config_path: Optional[Path] = typer.Option(None),
    sample_limit: Optional[int] = typer.Option(None),
) -> None:
    cfg = load_cfg(config_path)
    cfg.sample_limit = sample_limit
    workflow = OCRWorkflow(cfg)
    for pdf in cfg.iter_pdfs():
        images = workflow.preprocess(pdf)
        workflow.paddle_ocr(pdf, images)


@app.command("ocrmypdf")
def ocrmypdf_cmd(
    config_path: Optional[Path] = typer.Option(None),
    sample_limit: Optional[int] = typer.Option(None),
) -> None:
    cfg = load_cfg(config_path)
    cfg.sample_limit = sample_limit
    workflow = OCRWorkflow(cfg)
    for pdf in cfg.iter_pdfs():
        workflow.ocrmypdf(pdf)


@app.command("tables")
def tables_cmd(
    config_path: Optional[Path] = typer.Option(None),
    sample_limit: Optional[int] = typer.Option(None),
) -> None:
    cfg = load_cfg(config_path)
    cfg.sample_limit = sample_limit
    workflow = OCRWorkflow(cfg)
    for pdf in cfg.iter_pdfs():
        ctx = workflow.build_pdf_context(pdf)
        target_pdf = ctx["ocr_pdf"] if ctx["ocr_pdf"].exists() else pdf
        workflow.tables(target_pdf)


@app.command("full-run")
def full_run(
    config_path: Optional[Path] = typer.Option(None),
    sample_limit: Optional[int] = typer.Option(None),
) -> None:
    cfg = load_cfg(config_path)
    cfg.sample_limit = sample_limit
    workflow = OCRWorkflow(cfg)
    results = workflow.run_batch()
    typer.echo(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
