"""Serial number normalization, validation and OCR text extraction.

Bangladesh prize bonds print the serial in Bengali digits, English digits or a
mixture of both, sometimes with a short alphabetic prefix.  Everything is
canonicalised to ASCII upper-case before it touches the database, but the raw
OCR text is preserved alongside it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .config import settings

BENGALI_DIGITS = "০১২৩৪৫৬৭৮৯"
BENGALI_ZERO = 0x09E6
# Bengali consonants and independent vowels that can appear as a serial prefix.
BENGALI_LETTERS = "অআইঈউঊঋঌএঐওঔকখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহড়ঢ়য়"
ARABIC_INDIC_ZERO = 0x0660
EXTENDED_ARABIC_INDIC_ZERO = 0x06F0

_DIGIT_TRANSLATION: dict[int, int] = {}
for _offset in range(10):
    _DIGIT_TRANSLATION[BENGALI_ZERO + _offset] = ord(str(_offset))
    _DIGIT_TRANSLATION[ARABIC_INDIC_ZERO + _offset] = ord(str(_offset))
    _DIGIT_TRANSLATION[EXTENDED_ARABIC_INDIC_ZERO + _offset] = ord(str(_offset))

# Characters OCR commonly injects around a serial line.
_JUNK_CHARS = re.compile(r"[\s\-_.:•·|/\\'\"`~,]+")
# Bengali letters may be separated by spaces on real bonds ("ঘ গ ০৭৫২৮৮২").
_PREFIX_LETTERS = f"[A-Za-z{BENGALI_LETTERS}]"
_CANDIDATE_RE = re.compile(
    rf"(?<![A-Za-z0-9{BENGALI_LETTERS}])"
    rf"(?P<prefix>(?:{_PREFIX_LETTERS}\s*){{1,2}}[-.]?\s*)?"
    r"(?P<digits>\d(?:[\s.\-]?\d){5,7})"
    r"(?![0-9])"
)

_NOISE_LATIN = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "|": "1",
                "S": "5", "B": "8", "Z": "2", "G": "6", "T": "7"}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    serial: str
    error: str | None = None
    digits: int = 0


@dataclass
class Candidate:
    serial: str
    confidence: float
    variants: set[str] = field(default_factory=set)
    raw_text: str = ""


def to_ascii_digits(text: str) -> str:
    """Convert Bengali / Arabic-Indic digits to ASCII, leaving other text alone."""
    return unicodedata.normalize("NFKC", text).translate(_DIGIT_TRANSLATION)


def to_bengali_digits(text: str) -> str:
    return "".join(
        BENGALI_DIGITS[int(ch)] if (ch.isdigit() and ch.isascii()) else ch
        for ch in text
    )


def normalize_serial(value: str) -> str:
    """Canonical form: NFKC, ASCII digits, upper-case, alphanumerics only."""
    text = unicodedata.normalize("NFKC", value or "")
    text = text.translate(_DIGIT_TRANSLATION).upper()
    return re.sub(rf"[^A-Z0-9{BENGALI_LETTERS}]", "", text)


def count_digits(serial: str) -> int:
    return sum(1 for ch in serial if ch.isdigit())


def validate_serial(value: str) -> ValidationResult:
    serial = normalize_serial(value)
    if not serial:
        return ValidationResult(False, "", "Serial number is empty")
    digits = count_digits(serial)
    if digits < settings.min_serial_digits:
        return ValidationResult(
            False, serial,
            f"Serial needs at least {settings.min_serial_digits} digits (got {digits})",
            digits,
        )
    if digits > settings.max_serial_digits:
        return ValidationResult(
            False, serial,
            f"Serial has too many digits ({digits}, max {settings.max_serial_digits})",
            digits,
        )
    if not re.fullmatch(settings.serial_pattern, serial):
        return ValidationResult(
            False, serial,
            "Serial format does not match the expected prize bond pattern",
            digits,
        )
    return ValidationResult(True, serial, None, digits)


def best_effort_serial(value: str) -> str | None:
    """Repair a token OCR produced, only for presentation as a suggestion."""
    serial = normalize_serial(value)
    if not serial:
        return None
    if validate_serial(serial).valid:
        return serial
    # Only normalise letter/digit confusions when the result validates; this is
    # never used to auto-save, just to pre-fill a review input.
    repaired = "".join(_NOISE_LATIN.get(ch, ch) for ch in serial)
    return repaired if validate_serial(repaired).valid else None


def extract_candidates(text: str, confidence: float, variant: str) -> list[Candidate]:
    """Extract plausible serial numbers from one OCR pass."""
    if not text:
        return []
    flat = to_ascii_digits(text).upper()
    candidates: list[Candidate] = []

    for line in flat.splitlines():
        cleaned = line.replace("No.", " ").replace("NO.", " ")
        for match in _CANDIDATE_RE.finditer(cleaned):
            digits = re.sub(r"\D", "", match.group("digits"))
            if not (settings.min_serial_digits <= len(digits) <= settings.max_serial_digits):
                continue
            prefix = re.sub(rf"[^A-Z{BENGALI_LETTERS}]", "", match.group("prefix") or "")
            serial = f"{prefix}{digits}"
            result = validate_serial(serial)
            if not result.valid:
                continue
            candidates.append(
                Candidate(serial=result.serial, confidence=confidence,
                          variants={variant}, raw_text=line.strip())
            )

    # Fallback: the whole line is a serial (including spaced Bengali groups).
    if not candidates:
        compact = _JUNK_CHARS.sub("", flat)
        result = validate_serial(compact)
        if result.valid:
            candidates.append(
                Candidate(serial=result.serial, confidence=max(0.0, confidence - 8),
                          variants={variant}, raw_text=flat.strip())
            )
    return candidates


def aggregate_candidates(scored: list[tuple[Candidate, float]]) -> Candidate | None:
    """Merge candidates collected across preprocessing variants.

    Each tuple is (candidate, line_confidence).  Agreement between independent
    binarisations is a much stronger signal than a single high tesseract score.
    """
    merged: dict[str, Candidate] = {}
    confidences: dict[str, list[float]] = {}
    for candidate, conf in scored:
        if candidate.serial not in merged:
            merged[candidate.serial] = Candidate(
                serial=candidate.serial, confidence=0.0,
                raw_text=candidate.raw_text,
            )
            confidences[candidate.serial] = []
        merged[candidate.serial].variants |= set(candidate.variants)
        confidences[candidate.serial].append(conf)

    best: Candidate | None = None
    best_score = -1.0
    for serial, candidate in merged.items():
        values = confidences[serial]
        mean_conf = sum(values) / len(values)
        agreement = len(candidate.variants)
        score = mean_conf + 10.0 * (agreement - 1) + min(len(values), 3) * 1.5
        if score > best_score:
            best_score = score
            best = Candidate(
                serial=serial,
                confidence=min(99.0, mean_conf + 6.0 * (agreement - 1)),
                variants=set(candidate.variants),
                raw_text=candidate.raw_text,
            )
    return best
