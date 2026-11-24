from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..scan_service import (
    get_bond_corrections,
    list_bonds,
    save_bond,
    update_bond,
)
from ..schemas import BondUpdateIn, ManualBondIn

router = APIRouter(prefix="/api/bonds", tags=["bonds"])


@router.get("")
def get_bonds(
    search: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return list_bonds(search=search, limit=limit, offset=offset)


@router.post("")
def create_bond(payload: ManualBondIn):
    result = save_bond(
        payload.serial,
        note=payload.note,
        attempt_id=payload.attempt_id,
    )
    if result["status"] == "invalid":
        raise HTTPException(status_code=422, detail=result["reason"])
    if result["status"] == "duplicate":
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Serial {result['serial']} is already recorded",
                "serial": result["serial"],
                "bond": result.get("bond"),
                "stats": result.get("stats"),
            },
        )
    return result


@router.patch("/{bond_id}")
def edit_bond(bond_id: int, payload: BondUpdateIn):
    result = update_bond(bond_id, payload.serial, payload.note)
    if result is None:
        raise HTTPException(status_code=404, detail="Bond not found")
    if result["status"] == "invalid":
        raise HTTPException(status_code=422, detail=result["reason"])
    if result["status"] == "duplicate":
        raise HTTPException(
            status_code=409,
            detail={"message": result["reason"], "existing_id": result.get("existing_id")},
        )
    return result


@router.get("/{bond_id}/corrections")
def bond_corrections(bond_id: int):
    return {"items": get_bond_corrections(bond_id)}
