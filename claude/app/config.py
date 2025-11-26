"""
Application configuration for Thai Financial Document OCR Prototype.
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class Config:
    """Centralized configuration for the OCR prototype application."""

    # Path Configuration
    PROJECT_ROOT: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    @property
    def Y67_BASE_PATH(self) -> Path:
        """Path to Y67 source documents directory."""
        return self.PROJECT_ROOT.parent / "Y67"

    @property
    def DATABASE_PATH(self) -> Path:
        """SQLite database file path."""
        return self.PROJECT_ROOT / "data" / "prototype.db"

    @property
    def EXPORTS_PATH(self) -> Path:
        """Directory for exported files."""
        return self.PROJECT_ROOT / "data" / "exports"

    # OCR Configuration
    OCR_LANGUAGES: Tuple[str, ...] = ("th", "en")
    OCR_CONFIDENCE_THRESHOLD: float = 0.5
    TABLE_MODE: str = "ACCURATE"  # PaddleOCR table mode

    # OCR Engine Selection
    OCR_ENGINE: str = "docling"  # "docling" or "typhoon"
    OCR_ENGINES_AVAILABLE: Tuple[str, ...] = ("docling", "typhoon")

    # Typhoon OCR Settings
    TYPHOON_RATE_LIMIT_DELAY: float = 3.0  # seconds between API calls
    TYPHOON_CONVERT_TABLES: bool = True  # Convert HTML tables to DataFrames

    # Processing Configuration
    MAX_BATCH_SIZE: int = 10
    PROCESSING_TIMEOUT: int = 300  # seconds
    PAGE_SIZE: int = 20  # pagination default
    MAX_UPLOAD_SIZE_MB: int = 200

    # Document Types
    VALID_DOCUMENT_TYPES: Tuple[str, ...] = (
        "BS",           # Balance Sheet
        "Compare BS",   # Comparative Balance Sheet
        "Compare PL",   # Comparative Profit & Loss
        "Cash Flow",    # Cash Flow Statement
        "Gen Info",     # General Information
        "Ratio",        # Financial Ratios
        "Related",      # Related Party Transactions
        "Shareholders"  # Shareholders Information
    )

    # Database Configuration
    DATABASE_URL: str = field(init=False)

    def __post_init__(self):
        """Initialize derived configuration values."""
        self.DATABASE_URL = f"sqlite:///{self.DATABASE_PATH}"

        # Ensure required directories exist
        self.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.EXPORTS_PATH.mkdir(parents=True, exist_ok=True)

    def validate_paths(self) -> bool:
        """Validate that critical paths exist."""
        if not self.Y67_BASE_PATH.exists():
            raise FileNotFoundError(f"Y67 directory not found: {self.Y67_BASE_PATH}")
        return True


# Global configuration instance
config = Config()
