"""
Module 2: Vernacular Voice AI — Speech-to-Text Pipeline
Transcribes chunked 16kHz PCM/WAV audio using Faster-Whisper.
"""
from __future__ import annotations

import io
import logging
import wave
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_whisper_model = None


def get_whisper_model(model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
    """Lazy-load faster-whisper model singleton."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading Faster-Whisper model '%s' on %s (%s)...", model_size, device, compute_type)
            _whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("Faster-Whisper model loaded successfully.")
        except Exception as exc:
            logger.warning("Could not load Faster-Whisper model: %s", exc)
            _whisper_model = None
    return _whisper_model


def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Convert raw PCM audio bytes to WAV format."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    buf.seek(0)
    return buf.read()


def transcribe_audio_buffer(
    audio_bytes: bytes,
    language: Optional[str] = None,
    sample_rate: int = 16000,
) -> Tuple[str, float]:
    """
    Transcribe audio bytes (either WAV with header or raw PCM).
    Returns (transcript, confidence).
    """
    if not audio_bytes:
        return "", 0.0

    # Ensure WAV container
    if not audio_bytes.startswith(b"RIFF"):
        wav_data = pcm_to_wav_bytes(audio_bytes, sample_rate=sample_rate)
    else:
        wav_data = audio_bytes

    model = get_whisper_model()
    if model is None:
        logger.warning("Whisper model unavailable. Returning fallback.")
        return "", 0.0

    try:
        audio_stream = io.BytesIO(wav_data)
        lang_code = "ta" if language in ("ta", "tanglish") else ("en" if language == "en" else None)

        segments, info = model.transcribe(
            audio_stream,
            beam_size=3,
            language=lang_code,
            condition_on_previous_text=False,
        )

        texts = []
        confidences = []
        for segment in segments:
            texts.append(segment.text.strip())
            # Convert avg_logprob to approximate confidence in [0, 1]
            prob = max(0.0, min(1.0, 1.0 + (segment.avg_logprob / 5.0)))
            confidences.append(prob)

        full_text = " ".join(texts).strip()
        avg_confidence = sum(confidences) / len(confidences) if confidences else info.language_probability
        return full_text, round(float(avg_confidence), 2)
    except Exception as exc:
        logger.error("STT transcription failed: %s", exc)
        return "", 0.0
