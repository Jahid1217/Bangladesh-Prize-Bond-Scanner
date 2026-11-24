from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ManualBondIn(BaseModel):
    serial: str = Field(min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=500)
    attempt_id: int | None = None


class BondUpdateIn(BaseModel):
    serial: str = Field(min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=500)


class FrameResult(BaseModel):
    status: Literal["saved", "duplicate", "uncertain", "failed", "skipped"]
    ocr_status: str
    serial: str | None = None
    confidence: float | None = None
    raw_text: str = ""
    reason: str | None = None
    attempt: dict | None = None
    bond: dict | None = None
    stats: dict = {}


class BondResult(BaseModel):
    status: str
    serial: str | None = None
    reason: str | None = None
    bond: dict | None = None
    stats: dict | None = None
