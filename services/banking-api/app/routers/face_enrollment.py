"""
Face Enrollment with Passbook Verification Router.
Provides secure passbook verification gate, short-lived enrollment sessions,
demo fixture integration for test accounts, and face sample registration
linked directly to the verified backend customer record.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

# Ensure bank_db can be imported
_candidate_data_dirs = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")),
]
for _d in _candidate_data_dirs:
    if os.path.exists(_d) and _d not in sys.path:
        sys.path.insert(0, _d)

import bank_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/face-enrollment", tags=["Face Enrollment"])

# URL of Face Auth / Identity service
FACE_AUTH_SERVICE_URL = os.getenv("FACE_AUTH_URL", "http://127.0.0.1:8003")

# Max upload size: 10 MB
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".pdf"}


def get_demo_fixtures_dir() -> Path:
    """Resolve demo fixtures directory from various candidate root paths."""
    curr = Path(__file__).resolve()
    candidates = [
        curr.parents[4] / "data" / "demo",
        curr.parents[3] / "data" / "demo",
        curr.parents[2] / "data" / "demo",
        Path.cwd() / "data" / "demo",
    ]
    for p in candidates:
        if p.exists() and (p / "manifest.json").exists():
            return p
    return candidates[0]


def load_demo_fixtures_manifest() -> Dict[str, Any]:
    """Load demo fixtures manifest defining authorized test fixtures."""
    fdir = get_demo_fixtures_dir()
    manifest_path = fdir / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("[FIXTURE] Failed to parse demo fixture manifest: %s", exc)
    return {"fixtures": []}


def check_demo_fixture(file_bytes: bytes, filename: str) -> Optional[Dict[str, Any]]:
    """
    Checks whether an uploaded passbook matches an authorized demo test fixture.
    Matches either by SHA-256 content hash or exact fixture filename (e.g. passbook_01.png).
    Returns fixture details or None.
    """
    manifest = load_demo_fixtures_manifest()
    file_sha = hashlib.sha256(file_bytes).hexdigest()
    base_name = os.path.basename(filename).lower()

    for item in manifest.get("fixtures", []):
        fixture_file = item.get("file", "").lower()
        fixture_sha = item.get("sha256", "")
        if file_sha == fixture_sha or base_name == fixture_file:
            logger.info("[FIXTURE] Upload matched demo test fixture: %s", item.get("file"))
            return item
    return None


class FaceRegisterRequest(BaseModel):
    enrollment_session_id: str = Field(..., description="Short-lived verified session ID")
    samples_b64: List[str] = Field(..., min_items=4, max_items=4, description="Exactly 4 captured face samples")


class DetectFaceRequest(BaseModel):
    image_b64: str = Field(..., description="Base64 encoded camera frame")


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text lines from an uploaded PDF document using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        extracted = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                extracted.append(t)
        return "\n".join(extracted)
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return ""


async def extract_text_from_image(image_bytes: bytes) -> List[str]:
    """
    Extract text lines from an image using Windows native OCR (winsdk).
    Works 100% locally and offline without external cloud calls.
    """
    try:
        from PIL import Image
        import winsdk.windows.graphics.imaging as imaging
        import winsdk.windows.media.ocr as ocr
        import winsdk.windows.storage.streams as streams

        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        bio = io.BytesIO()
        pil_img.save(bio, format="PNG")
        png_data = bio.getvalue()

        writer = streams.DataWriter()
        writer.write_bytes(png_data)
        buf = writer.detach_buffer()

        stream = streams.InMemoryRandomAccessStream()
        await stream.write_async(buf)
        stream.seek(0)

        decoder = await imaging.BitmapDecoder.create_async(stream)
        software_bitmap = await decoder.get_software_bitmap_async()

        engine = ocr.OcrEngine.try_create_from_user_profile_languages()
        ocr_result = await engine.recognize_async(software_bitmap)

        lines = [line.text.strip() for line in ocr_result.lines if line.text.strip()]
        return lines
    except Exception as exc:
        logger.warning("Native image OCR failed: %s", exc)
        return []


def parse_passbook_data(lines: List[str]) -> Dict[str, Optional[str]]:
    """
    Extract account number and customer name from passbook text lines using
    defensive regular expressions and heuristics.
    """
    extracted_name = None
    extracted_account = None

    full_blob = "\n".join(lines)

    # 1. Search for Account Number
    for line in lines:
        acc_match = re.search(
            r"(?:account|acc(?:ount)?\.?|a\/c)\s*(?:no|num|number)?\s*[:\-]?\s*([0-9\s\-]{4,24})",
            line,
            re.IGNORECASE,
        )
        if acc_match:
            cand = re.sub(r"\D", "", acc_match.group(1))
            if len(cand) >= 4:
                extracted_account = cand
                break

    # Fallback: search for any standalone 8-18 digit number
    if not extracted_account:
        raw_digits_match = re.findall(r"\b(\d{8,18})\b", full_blob)
        if raw_digits_match:
            extracted_account = raw_digits_match[0]

    # 2. Search for Customer / Account Holder Name
    for line in lines:
        name_match = re.search(
            r"(?:customer\s+name|account\s+holder|name)\s*[:\-]?\s*([A-Za-z\s\.\']{2,40})",
            line,
            re.IGNORECASE,
        )
        if name_match:
            cand = name_match.group(1).strip()
            if cand.lower() not in {"savings", "current", "bank", "account", "branch"}:
                extracted_name = cand
                break

    return {
        "extracted_name": extracted_name,
        "extracted_account": extracted_account,
    }


@router.get("/demo-fixtures")
async def list_demo_fixtures():
    """Returns available demo passbook fixtures for easy 1-click testing."""
    manifest = load_demo_fixtures_manifest()
    return manifest


@router.get("/demo-fixture/{filename}")
async def get_demo_fixture_file(filename: str):
    """Retrieve demo passbook image file content for frontend preview."""
    fdir = get_demo_fixtures_dir() / "passbooks"
    target = fdir / os.path.basename(filename)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Demo fixture not found")
    data = target.read_bytes()
    return Response(content=data, media_type="image/png")


@router.post("/verify-passbook")
async def verify_passbook(passbook: UploadFile = File(...)):
    """
    Upload and securely verify a bank passbook.
    Flow:
    1. Validate file format and size in-memory.
    2. Check if file is an authorized demo fixture (DEMO FIXTURE MODE).
    3. Otherwise extract passbook text via local Windows OCR.
    4. Match against customer database.
    5. Check if customer already has a registered face (prevents silent overwrite).
    6. Issue a short-lived verified enrollment session.
    """
    filename = passbook.filename or "passbook"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Accepted formats: JPG, JPEG, PNG, PDF.",
        )

    content = await passbook.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size ({MAX_UPLOAD_SIZE // (1024*1024)} MB).",
        )

    # Check for registered Demo Test Fixture (Explicit development/testing mode)
    fixture = check_demo_fixture(content, filename)
    if fixture:
        demo_cust_id = fixture.get("customer_id")
        cust = bank_db.get_customer(demo_cust_id) if demo_cust_id else None
        if not cust and fixture.get("account_number"):
            cust = bank_db.get_customer_by_account_and_name(fixture.get("account_number"))

        if cust:
            customer_id = cust["customer_id"]
            customer_name = cust["display_name"]
            masked_account = bank_db.mask_account_number(cust["account_number"])

            # Check if this demo customer is already enrolled
            if bank_db.has_registered_face(customer_id):
                logger.warning(
                    "[DEMO FIXTURE] Customer '%s' (%s) already has registered biometric face record.",
                    customer_id, customer_name
                )
                del content
                return {
                    "status": "already_enrolled",
                    "verified": False,
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "account_number_masked": masked_account,
                    "message": f"Face already enrolled for {customer_name} ({customer_id}). Reset demo enrollments to re-enroll.",
                }

            # In demo fixture mode, issue verified session
            session = bank_db.create_enrollment_session(
                customer_id=customer_id,
                customer_name=customer_name,
                account_number_masked=masked_account,
                ttl_seconds=900,
            )

            logger.info(
                "[DEMO FIXTURE] Verified demo customer '%s' (%s) using fixture '%s'. Session: %s",
                customer_id, customer_name, fixture.get("file"), session["session_id"]
            )

            # In-memory content cleared
            del content

            return {
                "status": "ok",
                "verified": True,
                "is_demo_fixture": True,
                "fixture_name": fixture.get("file"),
                "enrollment_session_id": session["session_id"],
                "customer_id": customer_id,
                "customer_name": customer_name,
                "account_number_masked": masked_account,
                "expires_at": session["expires_at"],
                "message": f"Demo account verified ✓ (Customer: {customer_name})",
            }

    # ── Non-fixture: Standard Local OCR Verification ───────────────────────────
    if ext == ".pdf":
        raw_text = await extract_text_from_pdf(content)
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    else:
        lines = await extract_text_from_image(content)

    del content

    if not lines:
        logger.warning("[PASSBOOK] OCR failed to detect readable text in uploaded document.")
        return {
            "status": "failed",
            "verified": False,
            "message": "Passbook verification failed. Could not extract readable text. Please upload a clearer image.",
        }

    parsed = parse_passbook_data(lines)
    extracted_account = parsed["extracted_account"]
    extracted_name = parsed["extracted_name"]

    logger.info(
        "[PASSBOOK] OCR extraction results — Account present: %s, Name present: %s",
        bool(extracted_account),
        bool(extracted_name),
    )

    if not extracted_account:
        return {
            "status": "failed",
            "verified": False,
            "message": "Passbook verification failed. Account number could not be found. Please ensure account number is clearly visible.",
        }

    cust = bank_db.get_customer_by_account_and_name(
        account_number_input=extracted_account,
        name_input=extracted_name,
    )

    if not cust:
        logger.warning("[PASSBOOK] Verification rejected: Extracted data does not match any active bank customer.")
        return {
            "status": "failed",
            "verified": False,
            "message": "Passbook verification failed. Account details do not match bank customer records.",
        }

    customer_id = cust["customer_id"]
    customer_name = cust["display_name"]
    masked_account = bank_db.mask_account_number(cust["account_number"])

    # Security check: Does customer already have a registered face?
    already_enrolled = bank_db.has_registered_face(customer_id)
    if already_enrolled:
        logger.warning("[PASSBOOK] Customer '%s' (%s) already has registered biometric face record.", customer_id, customer_name)
        return {
            "status": "already_enrolled",
            "verified": False,
            "customer_id": customer_id,
            "customer_name": customer_name,
            "account_number_masked": masked_account,
            "message": f"Face already enrolled for {customer_name} ({customer_id}). Reset demo enrollments to re-enroll.",
        }

    # Verification succeeded — create short-lived enrollment session (15 mins TTL)
    session = bank_db.create_enrollment_session(
        customer_id=customer_id,
        customer_name=customer_name,
        account_number_masked=masked_account,
        ttl_seconds=900,
    )

    logger.info("[PASSBOOK] Verification SUCCESS for customer '%s'. Session created: %s", customer_id, session["session_id"])

    return {
        "status": "ok",
        "verified": True,
        "is_demo_fixture": False,
        "enrollment_session_id": session["session_id"],
        "customer_id": customer_id,
        "customer_name": customer_name,
        "account_number_masked": masked_account,
        "expires_at": session["expires_at"],
        "message": "Identity Verified. You can now securely register your face.",
    }


@router.get("/session/{session_id}")
async def get_session_status(session_id: str):
    """Check status and expiration of an active enrollment session."""
    session = bank_db.get_enrollment_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment session not found.",
        )
    return {
        "session_id": session["session_id"],
        "customer_id": session["customer_id"],
        "customer_name": session["customer_name"],
        "account_number_masked": session["account_number_masked"],
        "expires_at": session["expires_at"],
        "is_valid": session["is_valid"],
        "is_expired": session["is_expired"],
        "used": bool(session["used"]),
    }


def _local_detect_face_fallback(image_b64: str) -> dict:
    """Local YuNet fallback detection if Module 4 service is restarting or unreachable."""
    try:
        import cv2
        import numpy as np

        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        raw = base64.b64decode(image_b64)
        np_data = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        if frame is None:
            return {"status": "ok", "face_detected": False, "reason": "No face detected", "bbox": None}

        curr = Path(__file__).resolve()
        yunet_candidates = [
            curr.parents[4] / "services" / "identity" / "models" / "face_detection_yunet_2023mar.onnx",
            curr.parents[3] / "services" / "identity" / "models" / "face_detection_yunet_2023mar.onnx",
            curr.parents[2] / "identity" / "models" / "face_detection_yunet_2023mar.onnx",
            Path.cwd() / "services" / "identity" / "models" / "face_detection_yunet_2023mar.onnx",
        ]
        yunet_path = next((str(p) for p in yunet_candidates if p.exists()), None)
        if yunet_path:
            h, w = frame.shape[:2]
            detector = cv2.FaceDetectorYN.create(yunet_path, "", (w, h), 0.5, 0.3, 5000)
            detector.setInputSize((w, h))
            _, faces = detector.detect(frame)
            if faces is None or len(faces) == 0:
                return {"status": "ok", "face_detected": False, "reason": "No face detected", "bbox": None}
            if len(faces) > 1:
                sorted_f = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                if sorted_f[1][2] * sorted_f[1][3] > 0.35 * sorted_f[0][2] * sorted_f[0][3]:
                    return {"status": "ok", "face_detected": False, "reason": "More than one face visible", "bbox": None}
            primary = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[0]
            x, y, bw, bh = primary[:4]
            cx, cy = x + bw / 2.0, y + bh / 2.0
            if bw < 0.08 * w:
                return {"status": "ok", "face_detected": False, "reason": "Move closer — face is too small", "bbox": [float(x), float(y), float(x + bw), float(y + bh)]}
            if abs(cx - w / 2) > 0.40 * w or abs(cy - h / 2) > 0.42 * h:
                return {"status": "ok", "face_detected": False, "reason": "Center your face in the frame", "bbox": [float(x), float(y), float(x + bw), float(y + bh)]}
            return {"status": "ok", "face_detected": True, "reason": None, "bbox": [float(x), float(y), float(x + bw), float(y + bh)]}
    except Exception as exc:
        logger.debug("Local face fallback error: %s", exc)
    return {"status": "ok", "face_detected": False, "reason": "Face detection service offline / initializing", "bbox": None}


@router.post("/detect-face")
async def proxy_detect_face(payload: DetectFaceRequest):
    """
    Proxies face detection and centering pre-check to Module 4 Face Auth.
    Checks face presence, centering, and ensures only one person is in view.
    Includes local YuNet fallback if Module 4 is temporarily unavailable.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{FACE_AUTH_SERVICE_URL}/face-auth/detect-face",
                json={"image_b64": payload.image_b64},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        logger.debug("Detect face proxy call failed: %s (using local YuNet fallback)", exc)

    return _local_detect_face_fallback(payload.image_b64)


@router.post("/register-samples")
async def register_face_samples(payload: FaceRegisterRequest):
    """
    Securely registers 4 captured face samples.
    Security Gate:
    - Enrollment session ID MUST be valid, unexpired, and unused.
    - Customer ID is retrieved DIRECTLY from the verified database session.
    - The client cannot forge or supply an arbitrary customer_id.
    - Once registered, the session is immediately marked used to prevent replay.
    """
    session = bank_db.get_enrollment_session(payload.enrollment_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid enrollment session. Passbook verification required.",
        )

    if session["is_expired"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your verification session has expired. Please verify your passbook again.",
        )

    if session["used"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This verification session has already been used.",
        )

    customer_id = session["customer_id"]
    customer_name = session["customer_name"]
    masked_account = session["account_number_masked"]

    if bank_db.has_registered_face(customer_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Face already registered for this account ({customer_name}). Please reset demo enrollments to re-enroll.",
        )

    # Forward to existing Module 4 Face Auth enrollment service
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            enroll_resp = await client.post(
                f"{FACE_AUTH_SERVICE_URL}/face-auth/enroll",
                json={
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "samples_b64": payload.samples_b64,
                },
            )
            if enroll_resp.status_code != 200:
                err_data = enroll_resp.json()
                logger.error("[FACE-ENROLL] Module 4 rejected enrollment: %s", err_data)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=err_data.get("detail", "Face registration failed. Please ensure face is centered and clearly visible."),
                )
    except httpx.RequestError as exc:
        logger.error("[FACE-ENROLL] Communication failure with Face Auth service: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Biometric authentication service is currently unavailable. Please try again.",
        )

    # Mark the session as used so it cannot be re-used
    bank_db.mark_enrollment_session_used(payload.enrollment_session_id)

    logger.info("[FACE-ENROLL] Registration SUCCESS for customer '%s' (%s)", customer_id, customer_name)

    return {
        "status": "ok",
        "customer_id": customer_id,
        "customer_name": customer_name,
        "account_number_masked": masked_account,
        "message": "Face registered successfully.",
    }


@router.post("/reset-demo-enrollments")
async def reset_demo_enrollments():
    """
    Resets biometric face embeddings strictly for authorized demo accounts
    (demo_cust_001 through demo_cust_010 and legacy demo accounts).
    Leaves production / normal customer data untouched.
    """
    count = bank_db.reset_demo_face_enrollments()
    logger.info("[DEMO] Reset %d face enrollment sample records for demo accounts", count)
    return {
        "status": "ok",
        "message": "Demo customer face enrollments have been reset successfully.",
        "cleared_records": count,
    }

