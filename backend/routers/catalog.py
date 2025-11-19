from fastapi import APIRouter, Depends, HTTPException, status

from ..catalog import (
    CatalogConfigError,
    build_catalog_for_package_id,
    build_catalog_response,
    get_free_package_definition,
)
from ..dependencies import get_current_user
from ..models import User

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _handle_catalog_error(exc: CatalogConfigError) -> HTTPException:
    detail = str(exc)
    if "Unknown package id" in detail:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail or "Catalog configuration error",
    )


@router.get("/free")
def get_free_catalog() -> dict:
    try:
        package = get_free_package_definition()
        return build_catalog_response(package)
    except CatalogConfigError as exc:  # pragma: no cover - runtime validation
        raise _handle_catalog_error(exc) from exc


@router.get("/packages/{package_id}")
def get_package_catalog(
    package_id: str, current_user: User = Depends(get_current_user)
) -> dict:
    try:
        catalog = build_catalog_for_package_id(package_id)
    except CatalogConfigError as exc:  # pragma: no cover - runtime validation
        raise _handle_catalog_error(exc) from exc

    if not current_user.can_access_package(package_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subscription required",
        )

    return catalog
