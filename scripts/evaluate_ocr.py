#!/usr/bin/env python3
"""Measure OCR accuracy on bond image samples.

Usage:
    python scripts/evaluate_ocr.py
    python scripts/evaluate_ocr.py --fixtures tests/fixtures --min-exact 0.7
    python scripts/evaluate_ocr.py --real

Any auto-save of a wrong serial exits non-zero: that is the safety invariant.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ocr import OcrUnavailable, engine  # noqa: E402


def load_manifest(path: Path) -> list[dict]:
    manifest = path / "manifest.json"
    if not manifest.is_file():
        return []
    return json.loads(manifest.read_text(encoding="utf-8"))


def run_synthetic(fixtures: Path, limit: int | None) -> tuple[int, int, int, int]:
    items = load_manifest(fixtures)
    if not items:
        print(f"No manifest.json in {fixtures}; generate samples first:")
        print("  python scripts/generate_samples.py --out tests/fixtures --count 20")
        return 0, 0, 0, 0
    if limit:
        items = items[:limit]

    rows = []
    latencies = []
    auto_ok = auto_wrong = uncertain = exact = 0
    print(f"{'expected':10s} {'read':10s} {'status':10s} {'conf':>5s} {'ms':>5s}")
    print("-" * 46)
    for item in items:
        image = cv2.imread(str(ROOT / item["strip"]))
        if image is None:
            print(f"missing: {item['strip']}")
            continue
        started = time.perf_counter()
        outcome = engine.recognize(image)
        elapsed = int((time.perf_counter() - started) * 1000)
        latencies.append(elapsed)
        correct = outcome.serial == item["serial"]
        exact += int(correct)
        if outcome.accepted:
            if correct:
                auto_ok += 1
            else:
                auto_wrong += 1
        elif outcome.serial:
            uncertain += 1
        rows.append((item["serial"], outcome.serial, outcome.status, outcome.confidence, elapsed))
        flag = "" if correct else "  <-- miss"
        print(
            f"{item['serial']:10s} {str(outcome.serial):10s} {outcome.status:10s} "
            f"{outcome.confidence or 0:5.0f} {elapsed:5d}{flag}"
        )

    total = len(rows)
    print("-" * 46)
    print(f"Samples:            {total}")
    print(f"Exact reads:        {exact}/{total} ({exact / total * 100:.1f}%)")
    print(f"Auto-saved correct: {auto_ok}")
    print(f"Auto-saved WRONG:   {auto_wrong}")
    print(f"Needs review:       {uncertain}")
    if latencies:
        print(
            f"Latency:            avg {sum(latencies) / len(latencies):.0f} ms, "
            f"max {max(latencies)} ms"
        )
    if auto_wrong:
        print("\nSAFETY FAILURE: a wrong serial was auto-saved.", file=sys.stderr)
        sys.exit(2)
    return exact, total, auto_ok, auto_wrong


def run_real() -> None:
    metadata_path = ROOT / "tests/fixtures/real/real_sample.json"
    if not metadata_path.is_file():
        print("No real sample fixture found.")
        return
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    image_path = ROOT / metadata["image"]
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"Could not read {image_path}")
        return
    outcome = engine.recognize(image)
    print("\nReal sample:", image_path.name)
    print(f"  expected: {metadata['expected_serial']}  (manually read)")
    print(f"  read:     {outcome.serial}  status={outcome.status} confidence={outcome.confidence:.0f}%")
    print(f"  note:     {metadata.get('note', '')}")
    if outcome.accepted and outcome.serial != metadata["expected_serial"]:
        print("SAFETY FAILURE: wrong serial auto-saved from real sample.", file=sys.stderr)
        sys.exit(2)
    if outcome.serial is None:
        print("  The engine refused to guess from this low-resolution press photo (expected).")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", default=str(ROOT / "tests/fixtures"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-exact", type=float, default=0.0,
                        help="Fail if exact-read ratio is below this (0-1)")
    parser.add_argument("--real", action="store_true", help="Also test the real press photo")
    args = parser.parse_args()

    try:
        info = engine.info(refresh=True)
    except OcrUnavailable as exc:
        print(exc, file=sys.stderr)
        return 3
    if not info.available:
        print(f"OCR unavailable: {info.error}", file=sys.stderr)
        return 3
    print(f"Tesseract {info.version} · languages {info.active_languages}\n")

    exact, total, _, _ = run_synthetic(Path(args.fixtures), args.limit)
    if args.real:
        run_real()
    if total and exact / total < args.min_exact:
        print(
            f"\nAccuracy {exact / total:.1%} is below --min-exact {args.min_exact:.1%}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
