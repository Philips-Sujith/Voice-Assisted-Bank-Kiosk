"""
Unit tests for the Security Service.
Validates HMAC-SHA256 generation, token issuance, QR payload encoding,
one-time token consumption, and expiry semantics.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Add services/security to path
SECURITY_DIR = Path(__file__).resolve().parents[2] / "services" / "security"
if str(SECURITY_DIR) not in sys.path:
    sys.path.insert(0, str(SECURITY_DIR))

import base64
import shutil
import tempfile
from crypto import sign_hmac_sha256, verify_hmac_sha256
from models import SigningRequest
from qr_payload import build_token_data, encode_qr_payload
from session_store import SessionStore
from token_service import ExpiredTokenError, TokenService


class TestSecurityService(unittest.TestCase):
    def setUp(self):
        self.key = b"0123456789abcdef0123456789abcdef"
        self.temp_dir = tempfile.mkdtemp()
        self.store = SessionStore(Path(self.temp_dir))
        self.service = TokenService(self.key, self.store)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_hmac_signature_and_verification(self):
        data = b"transaction_data_sample_string"
        signature = sign_hmac_sha256(self.key, data)
        self.assertTrue(isinstance(signature, str))
        self.assertEqual(len(signature), 64)
        self.assertTrue(verify_hmac_sha256(self.key, data, signature))
        self.assertFalse(verify_hmac_sha256(self.key, b"tampered_data", signature))

    def test_token_issuance_and_qr_payload(self):
        now = datetime.now(timezone.utc)
        req = SigningRequest(
            session_id="sess_1001",
            customer_id="cust_sujith",
            transaction_type="WITHDRAWAL",
            amount=Decimal("5000"),
            timestamp=now,
        )
        resp = self.service.sign(req, now=now)
        self.assertEqual(resp.status, "ok")
        self.assertTrue(resp.token_id)
        self.assertTrue(resp.qr_payload)
        self.assertTrue(resp.hmac_signature)

        # Verify QR payload is decodable
        decoded = base64.b64decode(resp.qr_payload).decode("utf-8")
        self.assertIn("sess_1001", decoded)
        self.assertIn("cust_sujith", decoded)
        self.assertIn("WITHDRAWAL", decoded)

    def test_one_time_token_consumption(self):
        now = datetime.now(timezone.utc)
        req = SigningRequest(
            session_id="sess_1002",
            customer_id="cust_priya",
            transaction_type="DEPOSIT",
            amount=Decimal("10000"),
            timestamp=now,
        )
        resp = self.service.sign(req)
        token_id = resp.token_id

        # First consumption must succeed
        record = self.service.consume(token_id)
        self.assertIsNotNone(record)

        # Second consumption must fail (one-time use security guarantee)
        with self.assertRaises(ExpiredTokenError):
            self.service.consume(token_id)

    def test_expired_token_rejection(self):
        # Issue token that was generated 2 hours ago
        past_time = datetime.now(timezone.utc) - timedelta(hours=2)
        req = SigningRequest(
            session_id="sess_1003",
            customer_id="cust_arjun",
            transaction_type="BALANCE_ENQUIRY",
            amount=Decimal("0"),
            timestamp=past_time,
        )
        resp = self.service.sign(req, now=past_time)
        token_id = resp.token_id

        with self.assertRaises(ExpiredTokenError):
            self.service.consume(token_id)


if __name__ == "__main__":
    unittest.main()
