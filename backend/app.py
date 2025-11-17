import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import auth, catalog, stripe_webhooks
from .settings import get_settings

logging.basicConfig(level=logging.INFO)

Base.metadata.create_all(bind=engine)

settings = get_settings()

app = FastAPI(title="Audiovook Magic Link API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(stripe_webhooks.router)
