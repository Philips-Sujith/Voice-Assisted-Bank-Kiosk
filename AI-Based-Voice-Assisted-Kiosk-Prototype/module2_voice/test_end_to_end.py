"""
Module 2: Vernacular Voice AI — Comprehensive Unit and End-to-End Tests
Tests STT, Intent & Entity Extraction, Contract Compliance, and Error Thresholds.
"""
import sys
import unittest
from pathlib import Path

# Add module2_voice to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from intent_parser import (
    INTENT_BALANCE_CHECK,
    INTENT_DEPOSIT,
    INTENT_OPEN_ACCOUNT,
    INTENT_SEND_MONEY,
    INTENT_UNKNOWN,
    INTENT_WITHDRAW,
    extract_amount,
    normalize_transcript,
    parse_intent_and_entities,
)
from stt_pipeline import pcm_to_wav_bytes


class TestIntentParser(unittest.TestCase):
    def test_english_withdrawal(self):
        res = parse_intent_and_entities("Withdraw 5000 rupees", "en")
        self.assertEqual(res["intent"], INTENT_WITHDRAW)
        self.assertEqual(res["entities"]["amount"], 5000)
        self.assertGreaterEqual(res["confidence"], 0.7)
        self.assertTrue(res["requires_auth"])
        self.assertIn("withdraw 5000 rupees", res["spoken_text"])

    def test_tamil_withdrawal(self):
        res = parse_intent_and_entities("ஐந்தாயிரம் ரூபாய் எடுக்க வேண்டும்", "ta")
        self.assertEqual(res["intent"], INTENT_WITHDRAW)
        self.assertEqual(res["entities"]["amount"], 5000)
        self.assertGreaterEqual(res["confidence"], 0.7)
        self.assertTrue(res["requires_auth"])
        self.assertIn("ஐந்தாயிரம்", res["spoken_text"])

    def test_tanglish_deposit(self):
        res = parse_intent_and_entities("Enakku 10000 rupees deposit pannanum", "tanglish")
        self.assertEqual(res["intent"], INTENT_DEPOSIT)
        self.assertEqual(res["entities"]["amount"], 10000)
        self.assertGreaterEqual(res["confidence"], 0.7)
        self.assertTrue(res["requires_auth"])
        self.assertIn("10000 rupees deposit", res["spoken_text"])

    def test_balance_inquiry_does_not_require_amount(self):
        res = parse_intent_and_entities("Check my account balance", "en")
        self.assertEqual(res["intent"], INTENT_BALANCE_CHECK)
        self.assertIsNone(res["entities"]["amount"])
        self.assertGreaterEqual(res["confidence"], 0.7)
        self.assertFalse(res["requires_auth"])

    def test_tamil_balance_inquiry(self):
        res = parse_intent_and_entities("என் கணக்கு இருப்பை பார்க்க வேண்டும்", "ta")
        self.assertEqual(res["intent"], INTENT_BALANCE_CHECK)
        self.assertGreaterEqual(res["confidence"], 0.7)
        self.assertFalse(res["requires_auth"])

    def test_send_money(self):
        res = parse_intent_and_entities("Send 2500 rupees to Ramesh", "en")
        self.assertEqual(res["intent"], INTENT_SEND_MONEY)
        self.assertEqual(res["entities"]["amount"], 2500)
        self.assertEqual(res["entities"]["recipient"], "Ramesh")
        self.assertFalse(res["requires_auth"])

    def test_open_account(self):
        res = parse_intent_and_entities("I want to open a new account", "en")
        self.assertEqual(res["intent"], INTENT_OPEN_ACCOUNT)
        self.assertFalse(res["requires_auth"])

    def test_unknown_intent_confidence_below_threshold(self):
        res = parse_intent_and_entities("What is the weather today?", "en")
        self.assertEqual(res["intent"], INTENT_UNKNOWN)
        self.assertLess(res["confidence"], 0.7)

    def test_withdrawal_missing_amount_confidence_below_threshold(self):
        res = parse_intent_and_entities("I want to withdraw money", "en")
        self.assertEqual(res["intent"], INTENT_WITHDRAW)
        self.assertIsNone(res["entities"]["amount"])
        self.assertLess(res["confidence"], 0.7)

    def test_extract_amount_commas_and_words(self):
        self.assertEqual(extract_amount("1,000 rupees"), 1000)
        self.assertEqual(extract_amount("25,000"), 25000)
        self.assertEqual(extract_amount("பத்தாயிரம் ரூபாய்"), 10000)
        self.assertEqual(extract_amount("இரண்டாயிரம்"), 2000)
        self.assertEqual(extract_amount("five thousand rupees"), 5000)


class TestAudioPipeline(unittest.TestCase):
    def test_pcm_to_wav_conversion(self):
        raw_pcm = b"\x00\x00" * 8000  # 0.5s of silence at 16kHz mono 16-bit
        wav_bytes = pcm_to_wav_bytes(raw_pcm, sample_rate=16000)
        self.assertTrue(wav_bytes.startswith(b"RIFF"))
        self.assertIn(b"WAVE", wav_bytes[:16])
        self.assertGreater(len(wav_bytes), len(raw_pcm))


if __name__ == "__main__":
    unittest.main()
