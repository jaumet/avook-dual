from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import stripe

from ..database import get_db
from ..models import User
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
        if customer_email:
            _upsert_user_with_full_access(db, customer_email)

    return {"ok": True}


def _upsert_user_with_full_access(db: Session, email: str) -> User:
    email_norm = email.strip().lower()
    user = db.query(User).filter(User.email == email_norm).first()
    if not user:
        user = User(email=email_norm, full_access=True, is_active=True)
        db.add(user)
    else:
        user.full_access = True
        user.is_active = True
    db.commit()
    db.refresh(user)
    return user
