import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_current_full_access_user
from ..models import User

router = APIRouter(prefix="/catalog", tags=["catalog"])

ROOT_DIR = Path(__file__).resolve().parents[2]
PREMIUM_PATH = ROOT_DIR / "audios.json"
FREE_PATH = ROOT_DIR / "audios-free.json"


def _load_catalog(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Missing catalog file: {path.name}",
        ) from exc


@router.get("/free")
def get_free_catalog() -> dict:
    """Return the catalog entries that are public for everyone."""

    return _load_catalog(FREE_PATH)


@router.get("/premium")
def get_premium_catalog(current_user: User = Depends(get_current_full_access_user)) -> dict:
    """Return the full catalog for authenticated subscribers."""

    return _load_catalog(PREMIUM_PATH)
