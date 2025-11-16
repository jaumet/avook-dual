import logging
from fastapi import FastAPI

from .database import Base, engine
from .routers import auth, stripe_webhooks

logging.basicConfig(level=logging.INFO)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Audiovook Magic Link API")

app.include_router(auth.router)
app.include_router(stripe_webhooks.router)
