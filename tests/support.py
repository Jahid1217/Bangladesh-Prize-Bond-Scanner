from __future__ import annotations

import cv2
import numpy as np

from scripts.generate_samples import render_bond, serial_crop


def frame_bytes(serial: str, *, bengali: bool = False, denomination: int = 200,
                quality: int = 92, rotation: float = 0.0) -> bytes:
    image = render_bond(serial, bengali=bengali, denomination=denomination)
    crop = cv2.cvtColor(np.array(serial_crop(image)), cv2.COLOR_RGB2BGR)
    if rotation:
        height, width = crop.shape[:2]
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), rotation, 1.0)
        crop = cv2.warpAffine(crop, matrix, (width, height),
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(250, 250, 244))
    ok, encoded = cv2.imencode(
        ".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, quality]
    )
    assert ok
    return encoded.tobytes()


def frame_array(serial: str, *, bengali: bool = False, denomination: int = 200):
    image = render_bond(serial, bengali=bengali, denomination=denomination)
    crop = np.array(serial_crop(image))
    return cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)
