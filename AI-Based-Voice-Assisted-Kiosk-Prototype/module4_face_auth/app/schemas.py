from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class FaceEnrollRequest(BaseModel):
    customer_id: str
    customer_name: Optional[str] = None
    image_b64: Optional[str] = None
    samples_b64: Optional[List[str]] = None
    sample_index: int = 1
    sample_label: Optional[str] = None


class FaceVerifyRequest(BaseModel):
    session_id: Optional[str] = None
    frames_b64: List[str]


class FixedBackendPayload(BaseModel):
    session_id: str
    status: str = "ok"
    auth_status: str = Field(pattern="^(pass|fail|pending)$")
    methods_used: List[str]
    confidence_scores: Dict[str, float]
    liveness_passed: bool
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
