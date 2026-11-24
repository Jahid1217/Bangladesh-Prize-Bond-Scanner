"""Tesseract OCR pipeline for prize bond serial strips.

The camera already crops to the serial area, so each frame is a short line of
text.  We binarise it with independent methods and only trust a serial when
two independent passes agree (or a single pass is overwhelmingly confident).
That is what keeps uncertain reads out of the database.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from string import ascii_uppercase

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

from .config import settings
from .serials import (
    BENGALI_DIGITS,
    BENGALI_LETTERS,
    Candidate,
    aggregate_candidates,
    extract_candidates,
    validate_serial,
)

MAX_TEXT_CHARS = 2000


class OcrUnavailable(RuntimeError):
    """Raised when no usable tesseract binary / language data is present."""


@dataclass
class OcrOutcome:
    status: str  # "ok" | "uncertain" | "no_serial"
    serial: str | None
    confidence: float
    raw_text: str
    variants: list[str] = field(default_factory=list)
    agreement: int = 0
    accepted: bool = False
    reason: str | None = None
    processing_ms: int = 0


@dataclass
class EngineInfo:
    available: bool
    command: str | None
    version: str | None
    requested_languages: str
    available_languages: list[str]
    active_languages: str
    tessdata_dir: str | None
    error: str | None = None


def _configure_tesseract() -> None:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    if settings.tessdata_dir:
        os.environ.setdefault("TESSDATA_PREFIX", settings.tessdata_dir)


_configure_tesseract()


def _decode(image_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
    h, w = gray.shape[:2]
    if w > settings.ocr_max_width:
        scale = settings.ocr_max_width / float(w)
        gray = cv2.resize(gray, (settings.ocr_max_width, max(1, int(h * scale))),
                          interpolation=cv2.INTER_AREA)
    elif w < 900:
        scale = min(2.5, 1100.0 / max(1, w))
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (0, 0), 2.2)
    sharpened = cv2.addWeighted(enhanced, 1.7, blurred, -0.7, 0)
    return sharpened


def _deskew(gray: np.ndarray) -> np.ndarray:
    try:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = cv2.findNonZero(binary)
        if coords is None:
            return gray
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle += 90
        if not (0.6 <= abs(angle) <= 12.0):
            return gray
        h, w = gray.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    except cv2.error:
        return gray


def _with_border(img: np.ndarray) -> np.ndarray:
    return cv2.copyMakeBorder(img, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)


def _variant_images(gray: np.ndarray) -> dict[str, np.ndarray]:
    h, w = gray.shape[:2]
    block = max(25, (w // 30) | 1)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 12
    )
    adaptive = cv2.morphologyEx(
        adaptive, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8)
    )
    return {
        "otsu": _with_border(otsu),
        "gray": _with_border(gray),
        "adaptive": _with_border(adaptive),
    }


def _tesseract_config(psm: int) -> str:
    parts = ["--oem 3", f"--psm {psm}", "-c preserve_interword_spaces=1"]
    if settings.tessdata_dir:
        parts.append(f'--tessdata-dir "{settings.tessdata_dir}"')
    return " ".join(parts)


def _group_lines(data: dict) -> list[tuple[str, float]]:
    lines: dict[tuple[int, int, int, int], list[tuple[str, float]]] = {}
    for i, text in enumerate(data.get("text", [])):
        word = (text or "").strip()
        if not word:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError, KeyError):
            conf = -1.0
        key = (
            data["block_num"][i],
            data["par_num"][i],
            data["line_num"][i],
            data["page_num"][i],
        )
        lines.setdefault(key, []).append((word, conf))

    output: list[tuple[str, float]] = []
    for words in lines.values():
        text = " ".join(word for word, _ in words)
        confs = [conf for _, conf in words if conf >= 0]
        conf = sum(confs) / len(confs) if confs else 0.0
        output.append((text, conf))
    return output


class OcrEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._info: EngineInfo | None = None
        self._info_lock = threading.Lock()

    # -- availability -----------------------------------------------------
    def info(self, refresh: bool = False) -> EngineInfo:
        with self._info_lock:
            if self._info is not None and not refresh:
                return self._info
            self._info = self._probe()
            return self._info

    def _probe(self) -> EngineInfo:
        requested = settings.ocr_lang
        if not settings.tesseract_cmd:
            return EngineInfo(
                available=False, command=None, version=None,
                requested_languages=requested, available_languages=[],
                active_languages="", tessdata_dir=settings.tessdata_dir,
                error="Tesseract binary not found. Install tesseract-ocr or set PBS_TESSERACT_CMD.",
            )
        try:
            version = str(pytesseract.get_tesseract_version())
            langs = sorted(pytesseract.get_languages(config=""))
        except Exception as exc:  # pragma: no cover - environment dependent
            return EngineInfo(
                available=False, command=settings.tesseract_cmd, version=None,
                requested_languages=requested, available_languages=[],
                active_languages="", tessdata_dir=settings.tessdata_dir,
                error=f"Tesseract is not usable: {exc}",
            )
        requested_parts = [p for p in re.split(r"[+,]", requested) if p]
        active = [p for p in requested_parts if p in langs]
        if not active and "eng" in langs:
            active = ["eng"]
        return EngineInfo(
            available=bool(active),
            command=settings.tesseract_cmd,
            version=version,
            requested_languages=requested,
            available_languages=langs,
            active_languages="+".join(active),
            tessdata_dir=settings.tessdata_dir,
            error=None if active else f"None of the OCR languages {requested} are installed",
        )

    # -- recognition ------------------------------------------------------
    def _pass(
        self, image: np.ndarray, variant: str, lang: str, psm: int = settings.ocr_psm,
    ) -> tuple[str, list[Candidate]]:
        with self._lock:
            data = pytesseract.image_to_data(
                image,
                lang=lang,
                config=_tesseract_config(psm),
                output_type=Output.DICT,
                timeout=settings.ocr_timeout_seconds,
            )
        scored: list[Candidate] = []
        texts: list[str] = []
        for text, conf in _group_lines(data):
            if not text:
                continue
            texts.append(text)
            scored.extend(extract_candidates(text, conf, variant))
        return "\n".join(texts), scored

    def recognize(self, image_bgr: np.ndarray) -> OcrOutcome:
        started = time.perf_counter()
        info = self.info()
        if not info.available:
            raise OcrUnavailable(info.error or "OCR engine unavailable")

        gray = _deskew(_decode(image_bgr))
        variants = _variant_images(gray)
        order = ["otsu", "gray", "adaptive"]
        collected: list[tuple[Candidate, float]] = []
        raw_texts: list[str] = []
        used: list[str] = []
        best_per_variant: dict[str, Candidate] = {}
        has_bengali = "ben" in info.active_languages.split("+")
        mixed_bengali = has_bengali and info.active_languages != "ben"

        for name in order:
            try:
                text, candidates = self._pass(variants[name], name, info.active_languages)
                # Mixed recognition can read the digits while mistaking the
                # Bangla prefix for Latin text. Retry with the Bangla model.
                if mixed_bengali and (
                    not candidates or any(ch in BENGALI_DIGITS for ch in text)
                ) and not any(c.serial[0] in BENGALI_LETTERS for c in candidates):
                    bengali_text, bengali_candidates = self._pass(variants[name], name, "ben")
                    digit_runs = {c.serial.lstrip(ascii_uppercase) for c in candidates}
                    recovered = [
                        c for c in bengali_candidates
                        if c.serial[0] in BENGALI_LETTERS and (
                            not digit_runs or c.serial.lstrip(BENGALI_LETTERS) in digit_runs
                        )
                    ]
                    if recovered:
                        text = bengali_text
                        candidates = recovered
            except pytesseract.TesseractNotFoundError as exc:
                raise OcrUnavailable(str(exc)) from exc
            used.append(name)
            if text:
                raw_texts.append(text)
            collected.extend((c, c.confidence) for c in candidates)
            if candidates:
                best = max(candidates, key=lambda c: c.confidence)
                best_per_variant[name] = best

            # Cheap early exit: one pass that is very confident and valid.
            if (
                len(used) == 1
                and candidates
                and max(c.confidence for c in candidates)
                >= settings.single_variant_confidence
            ):
                break

            # Give a third pass a chance to confirm a low-confidence match.
            if len(best_per_variant) == 2:
                serials = {c.serial for c in best_per_variant.values()}
                if len(serials) == 1:
                    winner = aggregate_candidates(collected)
                    if (
                        winner and len(winner.variants) >= 2
                        and round(winner.confidence, 1) >= settings.auto_save_confidence
                    ):
                        break

        winner = aggregate_candidates(collected)
        needs_review = False
        if winner is None and has_bengali and settings.ocr_psm != 13:
            # Raw-line mode bypasses some line segmentation heuristics that
            # can drop small characters from a tight camera crop.
            recovered: list[tuple[Candidate, float]] = []
            try:
                for name in ("gray", "otsu"):
                    label = f"{name}-raw-line"
                    text, candidates = self._pass(variants[name], label, "ben", psm=13)
                    used.append(label)
                    if text:
                        raw_texts.append(text)
                    recovered.extend(
                        (c, c.confidence) for c in candidates
                        if c.serial[0] in BENGALI_LETTERS
                    )
            except pytesseract.TesseractNotFoundError as exc:
                raise OcrUnavailable(str(exc)) from exc
            recovered_winner = aggregate_candidates(recovered)
            if recovered_winner and len(recovered_winner.variants) == 2:
                collected = recovered
                winner = recovered_winner
                needs_review = True

        raw_text = "\n".join(dict.fromkeys(raw_texts))[:MAX_TEXT_CHARS]
        elapsed = int((time.perf_counter() - started) * 1000)

        if winner is None:
            return OcrOutcome(
                status="no_serial", serial=None, confidence=0.0, raw_text=raw_text,
                variants=used, agreement=0, reason="No valid serial number found in the frame",
                processing_ms=elapsed,
            )

        validation = validate_serial(winner.serial)
        confidence = round(winner.confidence, 1)
        agreement = len(winner.variants)
        rival_serials = {c.serial for c, _ in collected} - {winner.serial}
        auto_accepted = validation.valid and not needs_review and (
            (agreement >= 2 and confidence >= settings.auto_save_confidence)
            or (
                not rival_serials
                and confidence >= settings.single_variant_confidence
            )
        )
        reason = None
        if not validation.valid:
            reason = validation.error
        elif needs_review:
            reason = "Confirm the Bangla letters and digits before saving"
        elif not auto_accepted:
            reason = (
                f"Low confidence read ({confidence:.0f}%): confirm manually or rescan"
            )
        return OcrOutcome(
            status="ok" if auto_accepted else "uncertain",
            serial=validation.serial if validation.valid else winner.serial,
            confidence=confidence,
            raw_text=raw_text,
            variants=used,
            agreement=agreement,
            accepted=auto_accepted,
            reason=reason,
            processing_ms=elapsed,
        )


engine = OcrEngine()
