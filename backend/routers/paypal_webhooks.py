from urllib.parse import parse_qs

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..catalog import normalize_package_ids
from ..database import get_db
from ..models import User, UserPackage
from ..settings import get_settings

router = APIRouter(prefix="/webhooks/paypal", tags=["paypal"])
settings = get_settings()


async def _verify_ipn(payload: bytes) -> bool:
    """Send the raw IPN payload back to PayPal to validate authenticity."""

    verify_url = settings.paypal_ipn_verify_url
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                verify_url,
                content=b"cmd=_notify-validate&" + payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError:
        return False

    return resp.status_code == status.HTTP_200_OK and resp.text.strip() == "VERIFIED"


@router.post("")
async def paypal_ipn(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty IPN body")

    if not await _verify_ipn(payload):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PayPal IPN")

    params = parse_qs(payload.decode())
    payer_email = (params.get("payer_email") or [""])[0].strip().lower()
    payment_status = (params.get("payment_status") or [""])[0].strip().lower()
    raw_packages = (params.get("custom") or [""])[0]
    package_ids = normalize_package_ids(
        [pkg.strip() for pkg in raw_packages.split(",") if pkg.strip()]
    )

    if payment_status == "completed" and payer_email and package_ids:
        _grant_user_packages(db, payer_email, package_ids)

    return {"ok": True}


def _grant_user_packages(db: Session, email: str, package_ids: list[str]) -> User:
    email_norm = email.strip().lower()
    user = db.query(User).filter(User.email == email_norm).first()
    if not user:
        user = User(email=email_norm, full_access=False, is_active=True)
        db.add(user)
        db.flush()

    existing = set(user.packages)
    new_links = [pkg for pkg in package_ids if pkg not in existing]
    for package_id in new_links:
        user.package_links.append(UserPackage(package_id=package_id))

    user.is_active = True
    db.commit()
    db.refresh(user)
    return user
