"""
Banking Kiosk Backend API
FastAPI application entry point.
"""
import logging
import os
import sys
from contextlib import asynccontextmanager

# Add unified database directory to sys.path
_candidate_data_dirs = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data")),
]
for _d in _candidate_data_dirs:
    if os.path.exists(_d) and _d not in sys.path:
        sys.path.insert(0, _d)

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
    title="Banking Kiosk Backend API",
    description=(
        "Core orchestration hub for the voice-assisted banking kiosk. "
        "Manages session FSM, account balances, biometric verification, and queue operations."
    ),
    version="1.0.0",
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
