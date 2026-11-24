from __future__ import annotations

import json
from pathlib import Path

import cv2
import pytest

from app.ocr import engine
from tests.support import frame_array

ROOT = Path(__file__).resolve().parents[1]
BENGALI_FONT = Path("/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf")
OCR_READY = engine.info().available


@pytest.mark.skipif(not OCR_READY, reason="Tesseract not available")
def test_english_serials_read_exactly():
    accepted = 0
    for serial in ["1023456", "7891234", "0456789", "5550001"]:
        outcome = engine.recognize(frame_array(serial, bengali=False))
        assert outcome.serial == serial
        if outcome.accepted:
            assert outcome.status == "ok"
            accepted += 1
    assert accepted >= 3


@pytest.mark.skipif(not BENGALI_FONT.exists(), reason="Bengali font not installed")
@pytest.mark.skipif(not OCR_READY, reason="Tesseract not available")
def test_bengali_serials_never_save_a_wrong_number():
    """The engine may be uncertain, but it must never auto-accept a wrong serial."""
    serials = ["1435003", "9674421", "1075954", "5711097", "8325127"]
    exact = 0
    for serial in serials:
        outcome = engine.recognize(frame_array(serial, bengali=True))
        if outcome.serial == serial:
            exact += 1
        if outcome.accepted:
            assert outcome.serial == serial, "auto-save accepted a wrong Bengali serial"
    assert exact >= 3, f"Bengali OCR accuracy regressed: {exact}/{len(serials)}"


@pytest.mark.skipif(not BENGALI_FONT.exists(), reason="Bengali font not installed")
@pytest.mark.skipif("ben" not in engine.info().active_languages.split("+"),
                    reason="Bengali OCR data not available")
def test_bengali_serial_with_spaced_prefix():
    outcome = engine.recognize(frame_array("ঘ গ  0752882", bengali=True))
    assert outcome.serial == "ঘগ0752882"
    assert outcome.status in {"ok", "uncertain"}


@pytest.mark.skipif(not BENGALI_FONT.exists(), reason="Bengali font not installed")
@pytest.mark.skipif("ben" not in engine.info().active_languages.split("+"),
                    reason="Bengali OCR data not available")
def test_small_bengali_serial_is_recognized():
    image = frame_array("ঘ গ  0752882", bengali=True)
    height, width = image.shape[:2]
    small = cv2.resize(image, (int(width * 0.3), int(height * 0.3)),
                       interpolation=cv2.INTER_AREA)
    frame = cv2.copyMakeBorder(small, 10, 10, 20, 20, cv2.BORDER_REPLICATE)
    outcome = engine.recognize(frame)
    assert outcome.serial == "ঘগ0752882"
    if "gray-raw-line" in outcome.variants:
        assert outcome.status == "uncertain"
        assert not outcome.accepted


@pytest.mark.skipif(
    not (ROOT / "tests/fixtures/real/prize_bond_100_bangladeshpost.jpg").exists(),
    reason="real sample fixture missing",
)
@pytest.mark.skipif(not OCR_READY, reason="Tesseract not available")
def test_real_bond_photo_is_handled_safely():
    """Low-resolution real sample: either read it correctly or refuse to save."""
    metadata = json.loads(
        (ROOT / "tests/fixtures/real/real_sample.json").read_text(encoding="utf-8")
    )
    image = cv2.imread(str(ROOT / metadata["image"]))
    assert image is not None
    outcome = engine.recognize(image)
    if outcome.accepted:
        assert outcome.serial == metadata["expected_serial"]
