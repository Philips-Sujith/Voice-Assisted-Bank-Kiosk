"""
Banking Kiosk Backend — Module 4
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.error_handler import global_exception_handler
from app.routers import (
    biometrics,
    confirmation,
    face_enrollment,
    session,
    teller,
    token_verify,
    voice_intent,
    ws_dashboard,
)
from app.services.redis_publisher import close_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Banking Kiosk Backend starting up.")
    import os
    import sys
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    if data_dir not in sys.path:
        sys.path.insert(0, data_dir)
    try:
        import bank_db
        bank_db.init_db()
        logger.info("Unified bank_db schema verified and initialized.")
    except Exception as exc:
        logger.warning(f"Failed to auto-initialize bank_db: {exc}")
    yield
    logger.info("Shutting down — closing Redis connection.")
    await close_redis()



app = FastAPI(
    title="Banking Kiosk Backend",
    description=(
        "Orchestration hub for the voice-assisted banking kiosk (Module 4). "
        "Receives from Voice AI and Biometrics; sends to Security and Staff Portal."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception → standard error envelope
app.add_exception_handler(Exception, global_exception_handler)

# ── REST routers ──────────────────────────────────────────────────────────────
PREFIX = "/api/v1"
app.include_router(voice_intent.router,     prefix=PREFIX, tags=["Voice AI"])
app.include_router(biometrics.router,       prefix=PREFIX, tags=["Biometrics"])
app.include_router(confirmation.router,     prefix=PREFIX, tags=["Confirmation"])
app.include_router(teller.router,           prefix=PREFIX, tags=["Teller"])
app.include_router(session.router,          prefix=PREFIX, tags=["Session"])
app.include_router(token_verify.router,     prefix=PREFIX, tags=["Token"])
app.include_router(face_enrollment.router,  prefix=PREFIX, tags=["Face Enrollment"])
app.include_router(face_enrollment.router,  prefix="/api", tags=["Face Enrollment Direct"])

# ── WebSocket router (no prefix — WS path is /ws/dashboard) ──────────────────
app.include_router(ws_dashboard.router, tags=["Dashboard WebSocket"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": "banking-kiosk-backend",
        "version": "0.1.0",
    }
