from __future__ import annotations

import re

import pytest

from app.config import Settings
from app.serials import (
    best_effort_serial,
    extract_candidates,
    normalize_serial,
    to_bengali_digits,
    validate_serial,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("০৭১২৩৪৫", "0712345"),
        ("১৪৩৫০০৩", "1435003"),
        ("0712345", "0712345"),
        (" 07-12-345 ", "0712345"),
        ("No. 0712345", "NO0712345"),
        ("AB 0712345", "AB0712345"),
        ("٠٧١٢٣٤٥", "0712345"),
    ],
)
def test_normalize_serial(raw, expected):
    assert normalize_serial(raw) == expected


def test_validate_leading_zero_serial():
    result = validate_serial("০০৭৮৬৩৪")
    assert result.valid
    assert result.serial == "0078634"
    assert result.digits == 7


def test_validate_rejects_short_and_long():
    assert not validate_serial("12345").valid
    assert not validate_serial("123456789").valid
    assert not validate_serial("").valid
    assert not validate_serial("ABC").valid


def test_validate_allows_prefixed_serial():
    assert validate_serial("AB1234567").valid
    assert validate_serial("AB1234567").serial == "AB1234567"


def test_bengali_roundtrip():
    assert to_bengali_digits("0712345") == "০৭১২৩৪৫"


def test_bengali_prefixed_serial_normalizes():
    assert normalize_serial("ঘ গ  ০৭৫২৮৮২") == "ঘগ0752882"
    result = validate_serial("ঘ গ  ০৭৫২৮৮২")
    assert result.valid
    assert result.serial == "ঘগ0752882"
    assert result.digits == 7
    assert to_bengali_digits("ঘগ0752882") == "ঘগ০৭৫২৮৮২"


def test_legacy_example_pattern_allows_bengali_prefix(monkeypatch):
    monkeypatch.setenv("PBS_SERIAL_PATTERN", r"^[A-Z]{0,2}\d{7}$")
    assert re.fullmatch(Settings.load().serial_pattern, "ঘগ0752882")


def test_extract_candidates_from_noisy_lines():
    text = "প্রাইজ বন্ড ক্রমিক নং ০৭ ১২ ৩৪৫ মূল্য ১০০ টাকা"
    candidates = extract_candidates(text, 88.0, "otsu")
    assert candidates
    assert candidates[0].serial == "0712345"
    assert candidates[0].confidence == 88.0


def test_extract_candidates_ignores_prize_amounts():
    candidates = extract_candidates("মূল্য ১০০ টাকা / Taka 100", 90.0, "gray")
    assert candidates == []


def test_best_effort_only_when_valid():
    assert best_effort_serial("O712345") == "0712345"
    assert best_effort_serial("XYZ") is None
