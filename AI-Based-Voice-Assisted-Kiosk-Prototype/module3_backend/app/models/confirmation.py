from typing import Optional
from pydantic import BaseModel, ConfigDict


class ConfirmationBody(BaseModel):
    """
    Body for POST /api/v1/session/{session_id}/confirm.
    Sent by Voice AI or frontend after customer confirmation.

    confirmed=True  → fire customer_confirmed → FSM proceeds to signing
    confirmed=False → fire customer_rejected  → FSM resets to idle
    """
    model_config = ConfigDict(extra="ignore")

    session_id: str
    confirmed: bool
    amount: Optional[float] = None
    transaction_type: Optional[str] = None
    customer_id: Optional[str] = None

