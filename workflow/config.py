from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List
import json


@dataclass
class WorkflowConfig:
    """Configuration object shared across workflow stages."""

    source_root: Path = Path("Y67")
    output_root: Path = Path("output")
    temp_root: Path = Path("processed")
    dpi: int = 300
    languages: str = "tha+eng"
    paddle_lang: str = "thai"
    use_gpu: bool = False
    ocrmypdf_binary: str = "ocrmypdf"
    sample_limit: int | None = None
    include_patterns: List[str] = field(default_factory=lambda: ["*.pdf"])

    def ensure_dirs(self) -> None:
        for path in (self.output_root, self.temp_root):
            Path(path).mkdir(parents=True, exist_ok=True)

    def to_json(self, path: Path) -> None:
        data = {
            "source_root": str(self.source_root),
            "output_root": str(self.output_root),
            "temp_root": str(self.temp_root),
            "dpi": self.dpi,
            "languages": self.languages,
            "paddle_lang": self.paddle_lang,
            "use_gpu": self.use_gpu,
            "ocrmypdf_binary": self.ocrmypdf_binary,
            "sample_limit": self.sample_limit,
            "include_patterns": self.include_patterns,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: Path) -> "WorkflowConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        data["source_root"] = Path(data["source_root"])
        data["output_root"] = Path(data["output_root"])
        data["temp_root"] = Path(data["temp_root"])
        data["include_patterns"] = data.get("include_patterns", ["*.pdf"])
        return cls(**data)

    def iter_pdfs(self) -> Iterable[Path]:
        """Yield PDFs under source_root respecting include patterns and sample limit."""
        root = Path(self.source_root)
        count = 0
        for pattern in self.include_patterns:
            for pdf_path in sorted(root.rglob(pattern)):
                if not pdf_path.is_file():
                    continue
                yield pdf_path
                count += 1
                if self.sample_limit and count >= self.sample_limit:
                    return
