"""Runtime configuration for the Prize Bond Scanner backend.

Every value can be overridden with an environment variable so the same code
runs on a laptop, in Docker and in tests.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SERIAL_PATTERN = r"^[A-Z\u0985-\u09B9\u09DC-\u09DF]{0,2}\d{7}$"
LEGACY_SERIAL_PATTERN = r"^[A-Z]{0,2}\d{7}$"


def _load_dotenv() -> None:
    """Load simple KEY=VALUE lines from .env without an extra dependency."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve(path_value: str, base: Path) -> Path:
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _find_tesseract() -> tuple[str | None, str | None]:
    """Locate the tesseract binary and a tessdata directory.

    Preference order: environment, PATH, then the project-local vendor copy
    (used on machines where `apt install tesseract-ocr` is not possible).
    """
    cmd = os.environ.get("PBS_TESSERACT_CMD") or shutil.which("tesseract")
    local_bin = PROJECT_ROOT / ".vendor" / "tesseract-local" / "usr" / "bin" / "tesseract"
    if not cmd and local_bin.exists():
        cmd = str(local_bin)
    if cmd and not os.access(cmd, os.X_OK):
        cmd = None

    tessdata = os.environ.get("PBS_TESSDATA_DIR") or os.environ.get("TESSDATA_PREFIX")
    candidates = [
        Path(tessdata) if tessdata else None,
        PROJECT_ROOT / ".vendor" / "tesseract-local" / "usr" / "share" / "tesseract-ocr" / "5" / "tessdata",
        Path("/usr/share/tesseract-ocr/5/tessdata"),
        Path("/usr/share/tesseract-ocr/4.00/tessdata"),
        Path("/usr/share/tessdata"),
    ]
    if not tessdata:
        for candidate in candidates:
            if candidate and (candidate / "eng.traineddata").exists():
                tessdata = str(candidate)
                break
    return cmd, tessdata


@dataclass(frozen=True)
class Settings:
    project_root: Path
    database_path: Path
    exports_dir: Path
    captures_dir: Path
    frontend_dist: Path

    target_bonds: int
    min_confidence: float
    auto_save_confidence: float
    single_variant_confidence: float
    serial_pattern: str
    min_serial_digits: int
    max_serial_digits: int

    ocr_lang: str
    ocr_psm: int
    ocr_timeout_seconds: int
    ocr_max_width: int
    tesseract_cmd: str | None
    tessdata_dir: str | None

    frame_dedupe_seconds: float
    max_upload_mb: int
    max_exports_kept: int

    timezone: str
    cors_origins: list[str] = field(default_factory=list)
    serve_frontend: bool = True

    @classmethod
    def load(cls) -> "Settings":
        tesseract_cmd, tessdata_dir = _find_tesseract()
        serial_pattern = _env("PBS_SERIAL_PATTERN", DEFAULT_SERIAL_PATTERN)
        # Older copies of .env.example explicitly set the Latin-only default.
        if serial_pattern == LEGACY_SERIAL_PATTERN:
            serial_pattern = DEFAULT_SERIAL_PATTERN
        origins = [
            origin.strip()
            for origin in _env("PBS_CORS_ORIGINS", "*").split(",")
            if origin.strip()
        ]
        return cls(
            project_root=PROJECT_ROOT,
            database_path=_resolve(_env("PBS_DB_PATH", "database/prize_bonds.db"), PROJECT_ROOT),
            exports_dir=_resolve(_env("PBS_EXPORTS_DIR", "exports"), PROJECT_ROOT),
            captures_dir=_resolve(_env("PBS_CAPTURES_DIR", "database/captures"), PROJECT_ROOT),
            frontend_dist=_resolve(_env("PBS_FRONTEND_DIST", "frontend/dist"), PROJECT_ROOT),
            target_bonds=_env_int("PBS_TARGET", 2000),
            min_confidence=_env_float("PBS_MIN_CONFIDENCE", 55.0),
            auto_save_confidence=_env_float("PBS_AUTO_SAVE_CONFIDENCE", 72.0),
            single_variant_confidence=_env_float("PBS_SINGLE_VARIANT_CONFIDENCE", 94.0),
            # Current Bangladesh 100-taka prize bonds use a 7-digit serial.
            # Set PBS_MIN/MAX_SERIAL_DIGITS and PBS_SERIAL_PATTERN for other series.
            serial_pattern=serial_pattern,
            min_serial_digits=_env_int("PBS_MIN_SERIAL_DIGITS", 7),
            max_serial_digits=_env_int("PBS_MAX_SERIAL_DIGITS", 7),
            ocr_lang=_env("PBS_OCR_LANG", "ben+eng"),
            ocr_psm=_env_int("PBS_OCR_PSM", 7),
            ocr_timeout_seconds=_env_int("PBS_OCR_TIMEOUT", 20),
            ocr_max_width=_env_int("PBS_OCR_MAX_WIDTH", 1500),
            tesseract_cmd=tesseract_cmd,
            tessdata_dir=tessdata_dir,
            frame_dedupe_seconds=_env_float("PBS_FRAME_DEDUPE_SECONDS", 2.5),
            max_upload_mb=_env_int("PBS_MAX_UPLOAD_MB", 12),
            max_exports_kept=_env_int("PBS_MAX_EXPORTS_KEPT", 20),
            timezone=_env("PBS_TIMEZONE", "Asia/Dhaka"),
            cors_origins=origins,
            serve_frontend=_env_bool("PBS_SERVE_FRONTEND", True),
        )


settings = Settings.load()
