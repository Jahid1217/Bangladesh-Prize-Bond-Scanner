#!/usr/bin/env python3
"""Run the scanner OCR pipeline on a single image and print the result.

Usage:
    python scripts/ocr_image.py path/to/frame.jpg
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ocr import engine  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = Path(sys.argv[1])
    image = cv2.imread(str(path))
    if image is None:
        print(f"Could not read {path}", file=sys.stderr)
        return 2
    outcome = engine.recognize(image)
    print(json.dumps(
        {
            "serial": outcome.serial,
            "status": outcome.status,
            "confidence": outcome.confidence,
            "agreement": outcome.agreement,
            "auto_save": outcome.accepted,
            "reason": outcome.reason,
            "variants": outcome.variants,
            "processing_ms": outcome.processing_ms,
            "raw_text": outcome.raw_text,
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
