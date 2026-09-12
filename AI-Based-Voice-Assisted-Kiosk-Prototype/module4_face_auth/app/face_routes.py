from __future__ import annotations

import logging
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.db import (
    clear_customer_embeddings,
    enroll_face_sample,
    get_customer,
    get_customer_enrollment,
    get_fake_accounts,
    list_face_embeddings,
    log_face_verification,
    upsert_customer,
)
from app.face_service import engine
from app.schemas import FaceEnrollRequest, FaceVerifyRequest, FixedBackendPayload

router = APIRouter(prefix="/face-auth", tags=["face-auth"])
logger = logging.getLogger("FaceAuthRoute")


def _payload(
    session_id: str,
    auth_status: str,
    liveness_passed: bool,
    customer_id: str | None,
    face_score: float,
    customer_name: str | None = None,
) -> dict:
    result = FixedBackendPayload(
        session_id=session_id,
        auth_status=auth_status,
        methods_used=["face", "blink_liveness"],
        confidence_scores={"face": round(float(face_score), 4)},
        liveness_passed=liveness_passed,
        customer_id=customer_id,
        customer_name=customer_name,
    )
    return result.model_dump()


async def _forward_to_backend(body: dict) -> dict | None:
    backend_url = getattr(settings, "backend_url", "http://localhost:8000")
    if backend_url:
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.post(f"{backend_url}/api/v1/biometrics", json=body)
                logger.info("[FACE] Forwarded biometrics to backend for session %s (status=%d)", body.get("session_id"), res.status_code)
                if res.is_success:
                    return res.json()
        except Exception as exc:
            logger.warning("[FACE] Could not forward biometrics to backend: %s", exc)
    return None


@router.get("/capabilities")
def face_capabilities() -> dict:
    return engine.capabilities()


@router.get("/fake-accounts")
def fake_accounts() -> dict:
    return {"rows": get_fake_accounts()}


@router.get("/enrollment-status/{customer_id}")
def get_enrollment_status(customer_id: str) -> dict:
    """
    Check real database persistence for a customer's face enrollment.
    Returns customer info, registration status, and sample count without exposing raw embeddings.
    """
    enrollment = get_customer_enrollment(customer_id)
    return {
        "status": "ok",
        "customer_id": customer_id,
        "customer_name": enrollment.get("customer_name"),
        "registered": enrollment.get("registered", False),
        "sample_count": enrollment.get("sample_count", 0),
        "samples": enrollment.get("samples", []),
    }


@router.post("/detect-face")
def detect_single_face(payload: dict) -> dict:
    """
    Fast pre-check to assess face presence and centering before prompting for a blink.
    """
    img_b64 = payload.get("image_b64")
    if not img_b64:
        raise HTTPException(status_code=400, detail="image_b64 is required")
    try:
        frame = engine.decode_image(img_b64)
        geom = engine.assess_single_centered_face(frame)
        return {
            "status": "ok",
            "face_detected": geom.ok,
            "reason": geom.reason,
            "bbox": geom.bbox,
        }
    except Exception as exc:
        logger.warning("[FACE] detect_single_face error: %s", exc)
        return {
            "status": "ok",
            "face_detected": False,
            "reason": str(exc),
            "bbox": None,
        }


@router.post("/enroll")
def enroll_face(payload: FaceEnrollRequest) -> dict:
    """
    Enroll a customer with face samples.
    Supports:
    - Multiple samples at once (e.g. 4 multi-angle face samples in samples_b64)
    - Single sample enrollment (image_b64 with sample_index)
    Registers customer record and persists normalized face embeddings into database.
    """
    logger.info("[FACE] Enrollment initiated for customer_id='%s', name='%s'", payload.customer_id, payload.customer_name)
    customer_name = payload.customer_name or payload.customer_id
    upsert_customer(payload.customer_id, customer_name)

    enrolled_samples = 0

    # Multi-sample list passed
    if payload.samples_b64 and len(payload.samples_b64) > 0:
        # Clear previous embeddings for a clean multi-sample re-enrollment
        clear_customer_embeddings(payload.customer_id)
        sample_errors = []
        for idx, img_b64 in enumerate(payload.samples_b64, start=1):
            try:
                frame = engine.decode_image(img_b64)
            except Exception as exc:
                logger.warning("[FACE] Sample %d decode failure for %s: %s", idx, payload.customer_id, exc)
                sample_errors.append(f"Sample {idx}: Image decoding failed ({exc})")
                continue

            try:
                embedding = engine.extract_embedding(frame)
            except ValueError as exc:
                logger.warning("[FACE] Sample %d face validation failure for %s: %s", idx, payload.customer_id, exc)
                sample_errors.append(f"Sample {idx}: {exc}")
                continue
            except RuntimeError as exc:
                logger.error("[FACE] Sample %d model/runtime failure for %s: %s", idx, payload.customer_id, exc)
                raise HTTPException(status_code=500, detail=f"Face Authentication internal model failure: {exc}")

            try:
                enroll_face_sample(
                    customer_id=payload.customer_id,
                    embedding=embedding.tolist(),
                    sample_index=idx,
                    sample_label=f"sample_{idx}",
                )
                enrolled_samples += 1
                logger.info("[FACE] Enrolled sample %d/%d for %s", idx, len(payload.samples_b64), payload.customer_id)
            except Exception as exc:
                logger.error("[FACE] Sample %d database storage failure for %s: %s", idx, payload.customer_id, exc)
                raise HTTPException(status_code=500, detail=f"Database storage failure saving face sample {idx}: {exc}")

        if enrolled_samples == 0:
            detail_msg = "; ".join(sample_errors) if sample_errors else "Could not detect a valid face in any submitted samples"
            logger.error("[FACE] Enrollment failed for %s: %s", payload.customer_id, detail_msg)
            raise HTTPException(status_code=400, detail=detail_msg)

        logger.info("[FACE] Successfully registered %d face samples in database for %s (%s)", enrolled_samples, customer_name, payload.customer_id)
        return {
            "status": "ok",
            "customer_id": payload.customer_id,
            "customer_name": customer_name,
            "enrolled_samples": enrolled_samples,
            "message": f"Successfully enrolled {enrolled_samples} face samples for {customer_name}",
        }

    # Single sample passed
    if not payload.image_b64:
        raise HTTPException(status_code=400, detail="Either image_b64 or samples_b64 is required")

    try:
        frame = engine.decode_image(payload.image_b64)
        embedding = engine.extract_embedding(frame)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    enroll_face_sample(
        customer_id=payload.customer_id,
        embedding=embedding.tolist(),
        sample_index=payload.sample_index,
        sample_label=payload.sample_label or f"sample_{payload.sample_index}",
    )
    logger.info("[FACE] Enrolled single sample %d for %s", payload.sample_index, payload.customer_id)
    return {
        "status": "ok",
        "customer_id": payload.customer_id,
        "customer_name": customer_name,
        "sample_index": payload.sample_index,
        "message": f"Face sample {payload.sample_index} enrolled for {customer_name}",
    }


@router.post("/verify-event")
async def verify_face(payload: FaceVerifyRequest) -> dict:
    session_id = payload.session_id or str(uuid4())
    logger.info("[FACE] Camera verification burst received: session_id=%s, frames=%d", session_id, len(payload.frames_b64))

    if len(payload.frames_b64) == 0:
        raise HTTPException(status_code=400, detail="At least one frame is required")

    try:
        frames = [engine.decode_image(img) for img in payload.frames_b64]
        logger.info("[FACE] Decoded %d video frames for verification pipeline", len(frames))
        liveness = engine.evaluate_liveness(frames)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 1. Liveness / Blink check
    if not liveness.passed:
        error_code = "NO_FACE_DETECTED" if liveness.reason == "No face detected" else "BLINK_NOT_DETECTED"
        logger.warning("[FACE] Liveness FAILED: %s (error_code=%s) -> Authentication: FAIL", liveness.reason, error_code)
        auth_status = "fail"
        body = _payload(session_id, auth_status, False, None, 0.0)
        body["error_code"] = error_code
        body["feedback"] = liveness.feedback or "Please look at camera and blink once naturally"
        log_face_verification(session_id, None, False, 0.0, auth_status, liveness.reason)
        await _forward_to_backend(body)
        return body

    logger.info("[FACE] Blink confirmed. Liveness: PASS")

    # 2. Anti-spoofing check
    try:
        antispoof = engine.evaluate_antispoof(frames)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not antispoof.passed:
        feedback = antispoof.reason or "Spoof detected — please use a live camera"
        logger.warning("[FACE] Anti-spoof FAILED: %s -> Authentication: FAIL", feedback)
        body = _payload(session_id, "fail", False, None, 0.0)
        body["error_code"] = "SPOOF_DETECTED"
        body["feedback"] = feedback
        body["anti_spoof_backend"] = antispoof.backend
        log_face_verification(session_id, None, False, 0.0, "fail", feedback)
        await _forward_to_backend(body)
        return body

    logger.info("[FACE] Anti-spoof PASS (backend=%s, real_score=%.2f)", antispoof.backend, antispoof.real_score)

    # 3. Embedding extraction & Gallery matching
    try:
        probe_frame = engine.pick_embedding_frame(frames)
        logger.info("[FACE] Generating probe embedding from best aligned frame")
        probe_embedding = engine.extract_embedding(probe_frame)
        gallery = list_face_embeddings()
        logger.info("[FACE] Comparing against enrolled identities (%d database samples)", len(gallery))
        match = engine.match_gallery(probe_embedding, gallery)
    except ValueError as exc:
        logger.warning("[FACE] Probe feature extraction failed: %s", exc)
        body = _payload(session_id, "fail", True, None, 0.0)
        body["error_code"] = "NO_FACE_DETECTED"
        body["feedback"] = "Could not extract face features. Please look directly at the camera."
        body["anti_spoof_backend"] = antispoof.backend
        log_face_verification(session_id, None, True, 0.0, "fail", str(exc))
        await _forward_to_backend(body)
        return body
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not match.passed:
        logger.warning("[FACE] Face match failed: score=%.3f < threshold=%.2f -> Authentication: FAIL", match.score, settings.face_match_threshold)
        body = _payload(session_id, "fail", True, None, match.score)
        body["error_code"] = "FACE_MATCH_FAILED"
        body["feedback"] = "Face not recognized in enrolled bank records"
        body["anti_spoof_backend"] = antispoof.backend
        log_face_verification(session_id, None, True, match.score, "fail", "no gallery match")
        await _forward_to_backend(body)
        return body

    # 4. Identification & Authentication PASS
    c_info = get_customer(match.customer_id)
    cust_name = (c_info["display_name"] if c_info else None) or match.customer_name or "Valued Customer"
    logger.info("[FACE] Best match: %s (%s)", match.customer_id, cust_name)
    logger.info("[FACE] Similarity: %.2f", match.score)
    logger.info("[FACE] Liveness: PASS")
    logger.info("[FACE] Authentication: PASS")

    body = _payload(
        session_id=session_id,
        auth_status="pass",
        liveness_passed=True,
        customer_id=match.customer_id,
        face_score=match.score,
        customer_name=cust_name,
    )
    body["customer_name"] = cust_name
    body["feedback"] = f"Welcome, {cust_name}"
    body["anti_spoof_backend"] = antispoof.backend
    log_face_verification(session_id, match.customer_id, True, match.score, "pass", None)
    backend_res = await _forward_to_backend(body)
    if backend_res:
        body["backend_response"] = backend_res
    return body


@router.post("/verify-simulated")
async def verify_simulated(payload: dict) -> dict:
    """
    Simulated verification for automated end-to-end testing, wrong face tests, and photo spoof tests.
    """
    session_id = payload.get("session_id", str(uuid4()))
    scenario = payload.get("scenario", "success")

    if scenario == "wrong_face":
        logger.info("[FACE] [TEST] Simulating wrong face rejection test")
        body = _payload(session_id, "fail", True, None, 0.32)
        body["error_code"] = "FACE_MATCH_FAILED"
        body["feedback"] = "Face not recognized in enrolled bank records"
        if payload.get("forward_to_backend", True):
            body["backend_response"] = await _forward_to_backend(body)
        return body

    if scenario == "photo_spoof":
        logger.info("[FACE] [TEST] Simulating photo spoof / no-blink rejection test")
        body = _payload(session_id, "fail", False, None, 0.0)
        body["error_code"] = "BLINK_NOT_DETECTED"
        body["feedback"] = "Blink check failed — no liveness detected"
        if payload.get("forward_to_backend", True):
            body["backend_response"] = await _forward_to_backend(body)
        return body

    # Success scenario
    auth_status = payload.get("auth_status", "pass")
    customer_id = payload.get("customer_id", "cust_sujith") if auth_status == "pass" else None
    liveness_passed = payload.get("liveness_passed", True)
    face_score = payload.get("face_score", 0.94)

    cust_name = None
    if customer_id:
        c_info = get_customer(customer_id)
        cust_name = (c_info["display_name"] if c_info else None) or payload.get("customer_name") or "Sujith"

    logger.info("[FACE] [TEST] Simulating authentication pass for %s (%s)", customer_id, cust_name)
    body = _payload(
        session_id=session_id,
        auth_status=auth_status,
        liveness_passed=liveness_passed,
        customer_id=customer_id,
        face_score=face_score,
        customer_name=cust_name,
    )
    body["customer_name"] = cust_name
    body["feedback"] = f"Welcome, {cust_name}" if auth_status == "pass" else "Face not recognized"
    if payload.get("forward_to_backend", True):
        body["backend_response"] = await _forward_to_backend(body)
    return body
