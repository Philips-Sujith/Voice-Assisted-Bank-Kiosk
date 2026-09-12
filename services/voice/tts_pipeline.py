"""
Module 2: Vernacular Voice AI — Text-to-Speech (TTS) Pipeline
Generates speech audio bytes and caption metadata for English, Tamil, and Tanglish.
"""
from __future__ import annotations

import io
import logging
import os
import wave
from typing import Optional

logger = logging.getLogger(__name__)

_tts_engine = None


def get_tts_engine():
    """Lazy initialization of pyttsx3 engine singleton."""
    global _tts_engine
    if _tts_engine is None:
        try:
            import pyttsx3
            _tts_engine = pyttsx3.init()
            _tts_engine.setProperty("rate", 160)
            _tts_engine.setProperty("volume", 0.9)
        except Exception as exc:
            logger.warning("pyttsx3 initialization failed: %s", exc)
            _tts_engine = None
    return _tts_engine


def synthesize_speech_wav(text: str, language: str = "en") -> Optional[bytes]:
    """
    Synthesize text to WAV audio bytes using pyttsx3 or return None if unsupported/timed out.
    Freshly creates engine and cleans up to prevent SAPI5 COM singleton deadlock on Windows.
    """
    if not text:
        return None

    try:
        import pyttsx3
        import tempfile
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)
        engine.setProperty("volume", 0.9)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        del engine

        if os.path.exists(tmp_path):
            with open(tmp_path, "rb") as f:
                data = f.read()
            os.unlink(tmp_path)
            return data
    except Exception as exc:
        logger.warning("TTS audio synthesis exception: %s", exc)

    return None
