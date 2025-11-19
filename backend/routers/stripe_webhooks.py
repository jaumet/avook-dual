from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import stripe

from ..catalog import normalize_package_ids, package_lookup_maps
from ..database import get_db
from ..models import User, UserPackage
from ..settings import get_settings

router = APIRouter(prefix="/webhooks/stripe", tags=["stripe"])
settings = get_settings()


@router.post("")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=500, detail="Stripe webhook secret is not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.stripe_webhook_secret,
        )
    except Exception as exc:  # pragma: no cover - Stripe SDK raises multiple types
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook") from exc

    if event["type"] == "checkout.session.completed":
        data = event["data"]["object"]
        customer_email = data.get("customer_details", {}).get("email")
        package_ids = _extract_package_ids(data)
        if customer_email and package_ids:
            _grant_user_packages(db, customer_email, package_ids)

    return {"ok": True}


def _extract_package_ids(session: dict) -> list[str]:
    """Map Stripe line items or metadata to package IDs."""

    metadata = session.get("metadata") or {}
    package_ids = []
    meta_single = metadata.get("package_id")
    meta_many = metadata.get("package_ids")
    if meta_single:
        package_ids.append(meta_single)
    if meta_many:
        package_ids.extend([pkg.strip() for pkg in meta_many.split(",") if pkg.strip()])

    product_map, price_map = package_lookup_maps()
    line_items = (session.get("line_items") or {}).get("data") or []

    if not line_items and settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key
        try:
            response = stripe.checkout.Session.list_line_items(
                session["id"], limit=100
            )
            line_items = response.get("data", [])
        except Exception:  # pragma: no cover - Stripe SDK raises various errors
            line_items = []

    for item in line_items:
        price_obj = item.get("price") or {}
        if isinstance(price_obj, str):
            price_id = price_obj
            product_id = None
        else:
            price_id = price_obj.get("id")
            product_id = price_obj.get("product")

        if price_id and price_id in price_map:
            package_ids.append(price_map[price_id])
        elif product_id and product_id in product_map:
            package_ids.append(product_map[product_id])

    return normalize_package_ids(package_ids)


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
