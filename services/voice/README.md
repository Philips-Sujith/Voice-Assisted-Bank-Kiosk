# Voice Service

Vernacular voice processing microservice for the AI Voice-Assisted Banking Kiosk platform.

## Overview
The Voice Service enables hands-free vernacular banking interactions in English, Tamil, and bilingual modes. It handles live streaming speech recognition, intent recognition, entity extraction (amounts, transaction types), and multi-lingual voice feedback.

## Capabilities
- **Speech-to-Text (STT)**: High-speed audio transcription with streaming WebSocket support.
- **Vernacular Intent Parser**: Resolves spoken natural language commands to structured banking operations:
  - `WITHDRAWAL`
  - `DEPOSIT`
  - `BALANCE_ENQUIRY`
  - `SEND_MONEY`
  - `OPEN_ACCOUNT`
- **Dynamic Amount & Unit Extraction**: Parses spoken numbers, vernacular currency denominations (Lakhs, Thousands), and numerical amounts with high precision.
- **REST & WebSocket API**:
  - `POST /api/v1/parse`: Transcribes and extracts intent from text or audio payloads.
  - `WS /ws/audio`: Low-latency real-time microphone stream connection.
  - `GET /health`: Microservice health check.

## Service Architecture
```
services/voice/
├── intent_parser.py      # Natural language intent & entity parsing engine
├── server.py             # FastAPI service & WebSocket audio streaming handler
├── stt_pipeline.py       # Speech-to-text pipeline
├── tts_pipeline.py       # Text-to-speech audio synthesis engine
├── mock_backend.py       # Local development harness
└── web_bridge/           # Browser microphone integration bridge
```

## Running the Service
```bash
python server.py
# Running on http://127.0.0.1:8002
```
