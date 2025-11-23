from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import List, Optional

from workflow import OCRWorkflow, WorkflowConfig

LOGGER = logging.getLogger("workflow.cli")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def probe_binary(name: str) -> bool:
    return shutil.which(name) is not None


def probe_module(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


def cmd_check_deps(_: argparse.Namespace) -> None:
    report = {
        "binaries": {
            name: probe_binary(name)
            for name in ["tesseract", "ocrmypdf", "pdftoppm", "pdftocairo", "convert"]
        },
        "modules": {
            name: probe_module(name)
            for name in ["paddleocr", "pdf2image", "PIL", "pdfplumber"]
        },
    }
    print(json.dumps(report, indent=2))


def cmd_init_config(args: argparse.Namespace) -> None:
    cfg = WorkflowConfig(
        source_root=args.source_root,
        output_root=args.output_root,
        temp_root=args.temp_root,
        dpi=args.dpi,
        languages=args.languages,
        paddle_lang=args.paddle_lang,
        use_gpu=args.use_gpu,
    )
    cfg.to_json(args.config_path)
    print(f"Wrote {args.config_path}")


def load_cfg(path: Optional[Path]) -> WorkflowConfig:
    if path and Path(path).exists():
        return WorkflowConfig.from_json(Path(path))
    return WorkflowConfig()


def iter_with_limit(cfg: WorkflowConfig, sample_limit: Optional[int]):
    cfg.sample_limit = sample_limit
    return cfg.iter_pdfs()


def build_workflow(args: argparse.Namespace) -> OCRWorkflow:
    cfg = load_cfg(args.config_path)
    if args.sample_limit is not None:
        cfg.sample_limit = args.sample_limit
    return OCRWorkflow(cfg)


def cmd_preprocess(args: argparse.Namespace) -> None:
    workflow = build_workflow(args)
    for pdf in workflow.config.iter_pdfs():
        workflow.preprocess(pdf)


def cmd_paddle(args: argparse.Namespace) -> None:
    workflow = build_workflow(args)
    for pdf in workflow.config.iter_pdfs():
        images = workflow.preprocess(pdf)
        workflow.paddle_ocr(pdf, images)


def cmd_ocrmypdf(args: argparse.Namespace) -> None:
    workflow = build_workflow(args)
    for pdf in workflow.config.iter_pdfs():
        workflow.ocrmypdf(pdf)


def cmd_tables(args: argparse.Namespace) -> None:
    workflow = build_workflow(args)
    for pdf in workflow.config.iter_pdfs():
        ctx = workflow.build_pdf_context(pdf)
        target = ctx["ocr_pdf"] if Path(ctx["ocr_pdf"]).exists() else pdf
        workflow.tables(target)


def cmd_full_run(args: argparse.Namespace) -> None:
    workflow = build_workflow(args)
    results = workflow.run_batch()
    print(json.dumps(results, ensure_ascii=False, indent=2))


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch OCR pipeline controller")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_check = subparsers.add_parser("check-deps", help="Inspect required dependencies")
    parser_check.set_defaults(func=cmd_check_deps)

    parser_init = subparsers.add_parser("init-config", help="Write workflow configuration JSON")
    parser_init.add_argument("config_path", type=Path, nargs="?", default=Path("workflow.config.json"))
    parser_init.add_argument("--source-root", type=Path, default=Path("Y67"))
    parser_init.add_argument("--output-root", type=Path, default=Path("output"))
    parser_init.add_argument("--temp-root", type=Path, default=Path("processed"))
    parser_init.add_argument("--dpi", type=int, default=300)
    parser_init.add_argument("--languages", default="tha+eng")
    parser_init.add_argument("--paddle-lang", default="thai")
    parser_init.add_argument("--use-gpu", action="store_true")
    parser_init.set_defaults(func=cmd_init_config)

    def _add_common(sub):
        sub.add_argument("--config-path", type=Path, default=None)
        sub.add_argument("--sample-limit", type=int, default=None)
        sub.set_defaults(func=None)

    parser_pre = subparsers.add_parser("preprocess", help="Render PDFs to PNGs")
    _add_common(parser_pre)
    parser_pre.set_defaults(func=cmd_preprocess)

    parser_paddle = subparsers.add_parser("paddle-ocr", help="Execute PaddleOCR on rendered pages")
    _add_common(parser_paddle)
    parser_paddle.set_defaults(func=cmd_paddle)

    parser_ocrmy = subparsers.add_parser("ocrmypdf", help="Embed text layer with OCRmyPDF")
    _add_common(parser_ocrmy)
    parser_ocrmy.set_defaults(func=cmd_ocrmypdf)

    parser_tables = subparsers.add_parser("tables", help="Extract tables into CSV")
    _add_common(parser_tables)
    parser_tables.set_defaults(func=cmd_tables)

    parser_full = subparsers.add_parser("full-run", help="Run preprocessing, OCR, and tables in sequence")
    _add_common(parser_full)
    parser_full.set_defaults(func=cmd_full_run)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = create_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
