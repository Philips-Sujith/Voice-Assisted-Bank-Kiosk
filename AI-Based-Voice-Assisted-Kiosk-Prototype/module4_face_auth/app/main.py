import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import ROOT_DIR, settings
from app.db import init_db
from app.face_routes import router as face_router
from app.face_service import engine

logger = logging.getLogger("face_auth")

app = FastAPI(title="AI Kiosk Face Authentication")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = ROOT_DIR / "app" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates_dir = ROOT_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))
app.include_router(face_router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    try:
        status = engine.validate_startup()
        logger.info("[FACE] Startup check passed: %s", status)
    except Exception as exc:
        logger.critical("=" * 70)
        logger.critical("FACE AUTHENTICATION STARTUP CHECK FAILED")
        logger.critical(str(exc))
        logger.critical("=" * 70)
        raise


@app.get("/health")
def health() -> dict:
    caps = engine.capabilities()
    is_ready = bool(caps.get("embedding_model_ready") and caps.get("liveness_model_ready"))
    return {
        "status": "ok" if is_ready else "degraded",
        "face_auth_base_url": settings.face_auth_base_url,
        "detector": caps.get("detector"),
        "recognizer": caps.get("recognizer"),
        "embedding_model_ready": caps.get("embedding_model_ready"),
        "liveness_model_ready": caps.get("liveness_model_ready"),
        "anti_spoof": caps.get("anti_spoof"),
        "error": caps.get("embedding_model_error") or caps.get("liveness_model_error"),
    }


@app.get("/face-auth/enroll", response_class=HTMLResponse)
def enroll_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="enroll.html",
        context={"face_auth_base_url": settings.face_auth_base_url},
    )


@app.get("/face-auth/verify", response_class=HTMLResponse)
def verify_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="verify.html",
        context={"face_auth_base_url": settings.face_auth_base_url},
    )


@app.post("/mock-backend/event")
def mock_backend_event(payload: dict) -> dict:
    return {"status": "ok", "echo": payload}
