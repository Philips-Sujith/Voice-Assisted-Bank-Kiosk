"""
AI Smart Bank Self-Service Kiosk & Receipt Generator
-----------------------------------------------------
Bilingual (Tamil / English) voice-driven kiosk prototype.

ARCHITECTURE NOTE ON THE VOICE PIPELINE
----------------------------------------
All speech capture happens *entirely in the browser* using the Web Speech
API (`SpeechRecognition` in `ta-IN` / `en-IN`). We deliberately do NOT use
`speech_recognition` / `streamlit-mic-recorder` on the Python side, because
those libraries need a WAV/AIFF/FLAC file, while browsers only ever hand
back WebM/Ogg-Opus audio -> that mismatch is exactly what was throwing
`Audio file could not be read as PCM WAV...`. By keeping recognition in
JS and only sending the *already-transcribed text* to Python, the Windows
FFmpeg/codec problem never arises at all.

THE BUG THAT WAS TRAPPING THE TRANSCRIPT IN THE IFRAME
--------------------------------------------------------
The previous version posted a raw `streamlit:setComponentValue` message
straight to `window.parent`, but it never told Streamlit the component
had finished loading. Streamlit's frontend only opens a channel for a
custom component (and starts listening for its value) *after* it
receives a `streamlit:componentReady` handshake message with an
`apiVersion`. Without that handshake, every `setComponentValue` call is
silently dropped -> the value never reaches `st.session_state`, no
matter how correct the rest of the message looks. The fix below sends
`componentReady` on load (and re-sends it defensively), then
`setFrameHeight`, and only then `setComponentValue` -- exactly the
handshake `streamlit-component-lib` performs internally.
"""

import streamlit as st
import streamlit.components.v1 as components
import pytesseract
from PIL import Image
import numpy as np
import cv2
import qrcode
import re
import os
import io
import tempfile
import datetime
from reportlab.lib.pagesizes import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# ============================================================
# 0. RESOURCE PATH HELPER (folder this script lives in)
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 1. TESSERACT EXECUTABLE CONFIGURATION
#    Priority: a "tesseract" folder shipped next to this script (portable
#    Tesseract, optional) > standard Windows install locations.
# ============================================================
bundled_tesseract = os.path.join(BASE_DIR, "tesseract", "tesseract.exe")
default_win_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
default_win_tesseract_x86 = r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"

if os.path.exists(bundled_tesseract):
    pytesseract.pytesseract.tesseract_cmd = bundled_tesseract
elif os.path.exists(default_win_tesseract):
    pytesseract.pytesseract.tesseract_cmd = default_win_tesseract
elif os.path.exists(default_win_tesseract_x86):
    pytesseract.pytesseract.tesseract_cmd = default_win_tesseract_x86

# ============================================================
# 2. BI-DIRECTIONAL VOICE COMPONENT (correct Streamlit handshake)
#    Written to a user-writable temp folder rather than next to the
#    script/exe, since the PyInstaller bundle directory (_MEIPASS) or an
#    "installed to Program Files" copy may not be writable.
# ============================================================
COMP_DIR = os.path.join(tempfile.gettempdir(), "smart_bank_kiosk_voice_bridge")
os.makedirs(COMP_DIR, exist_ok=True)
INDEX_HTML = os.path.join(COMP_DIR, "index.html")

VOICE_BRIDGE_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  html, body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: transparent; }
  .card { background: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155;
          display: flex; flex-direction: column; gap: 10px; box-sizing: border-box; }
  .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  button { background: #2563eb; color: #fff; border: none; padding: 10px 16px; border-radius: 6px;
           cursor: pointer; font-weight: 600; font-size: 14px; transition: background 0.2s; }
  button.listening { background: #dc2626; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
  select { padding: 9px; border-radius: 6px; background: #1e293b; color: #fff; border: 1px solid #475569; }
  #status { color: #94a3b8; font-size: 13px; margin: 0; }
</style>
</head>
<body>
  <div class="card" id="card">
    <div class="row">
      <button id="micBtn">Click to Speak / peca thodangungal</button>
      <select id="langSelect">
        <option value="ta-IN">Tamil (ta-IN)</option>
        <option value="en-IN">English India (en-IN)</option>
      </select>
    </div>
    <p id="status">Status: Microphone ready</p>
  </div>

<script>
  // ---- Minimal re-implementation of the Streamlit Component JS protocol ----
  // Every outbound message MUST include isStreamlitMessage:true and a "type".
  function _post(type, extra) {
    const payload = Object.assign({ isStreamlitMessage: true, type: type }, extra || {});
    window.parent.postMessage(payload, "*");
  }

  // Step 1 (REQUIRED): tell Streamlit this component finished loading.
  // Until this is sent, Streamlit never opens a value channel for the
  // iframe, so setComponentValue calls are silently ignored.
  function sendComponentReady() {
    _post("streamlit:componentReady", { apiVersion: 1 });
  }

  // Step 2: tell Streamlit how tall to size the iframe.
  function setFrameHeight() {
    const h = document.getElementById("card").scrollHeight + 20;
    _post("streamlit:setFrameHeight", { height: h });
  }

  // Step 3: send the actual value back to st.session_state via the
  // component's return value. dataType "json" lets Streamlit hand the
  // Python side back a plain string.
  function sendValue(val) {
    _post("streamlit:setComponentValue", { value: val, dataType: "json" });
  }

  let streamlitReady = false;

  // Streamlit re-sends a "streamlit:render" event on every rerun once the
  // handshake succeeded. We use it purely as a readiness signal.
  window.addEventListener("message", (event) => {
    const data = event.data || {};
    if (data.type === "streamlit:render") {
      streamlitReady = true;
    }
  });

  function initHandshake() {
    sendComponentReady();
    setFrameHeight();
    // Streamlit sometimes misses the very first componentReady if the
    // iframe message channel wasn't fully attached yet, so re-announce
    // readiness a couple of times defensively.
    setTimeout(sendComponentReady, 200);
    setTimeout(setFrameHeight, 250);
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    initHandshake();
  } else {
    window.addEventListener("DOMContentLoaded", initHandshake);
  }

  // ---- Web Speech API wiring ----
  const btn = document.getElementById("micBtn");
  const status = document.getElementById("status");
  const langSelect = document.getElementById("langSelect");
  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (SpeechRecognitionImpl) {
    const rec = new SpeechRecognitionImpl();
    rec.continuous = false;
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    btn.onclick = () => {
      rec.lang = langSelect.value;
      try {
        rec.start();
        btn.classList.add("listening");
        btn.innerText = "Listening... pesungal";
        status.innerText = "Listening (" + langSelect.value + ")...";
      } catch (e) {
        status.innerText = "Could not start mic: " + e.message;
      }
    };

    rec.onresult = (e) => {
      const transcript = e.results[0][0].transcript;
      status.innerText = "Captured: '" + transcript + "'";
      btn.classList.remove("listening");
      btn.innerText = "Click to Speak / peca thodangungal";
      // Send the transcript straight back to Python session_state.
      sendValue(transcript);
      setFrameHeight();
    };

    rec.onerror = (e) => {
      status.innerText = "Speech error: " + e.error;
      btn.classList.remove("listening");
      btn.innerText = "Click to Speak / peca thodangungal";
    };

    rec.onend = () => {
      btn.classList.remove("listening");
      btn.innerText = "Click to Speak / peca thodangungal";
    };
  } else {
    status.innerText = "Web Speech API not supported in this browser. Use Chrome or Edge.";
    btn.disabled = true;
  }
</script>
</body>
</html>"""

with open(INDEX_HTML, "w", encoding="utf-8") as f:
    f.write(VOICE_BRIDGE_HTML)

voice_bridge_component = components.declare_component("voice_bridge", path=COMP_DIR)

st.set_page_config(page_title="AI Smart Bank Kiosk", layout="wide", page_icon="\U0001F3E6")

# ============================================================
# 3. SESSION STATE
# ============================================================
_DEFAULTS = {
    "acc_no": "",
    "holder_name": "",
    "ifsc": "SBIN0001234",
    "amount": "5000",
    "tx_type": "Cash Deposit",
    "last_voice_cmd": "",
    "voice_cmd_count": 0,   # bumps every time a *new* transcript arrives, used for widget keys
    "app_mode": "kiosk",    # "kiosk" or "teller" -- which top-level view is showing
    "processed_txns": [],   # in-memory log of teller-approved transactions
    "rejected_txns": [],    # in-memory log of teller-flagged/rejected tokens
    "last_scanned_payload": None,   # dict parsed from the most recent QR decode
    "last_scan_raw": "",             # raw QR string, used to detect a genuinely new scan
    "teller_scan_count": 0,          # bumps on each new decoded scan, used for widget keys
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ============================================================
# 4. VOICE OUTPUT (TTS) -- never speaks the account number
# ============================================================
# Fixed, generic greeting -- deliberately never includes the OCR'd
# customer name, since free-form OCR text (mixed scripts, misreads,
# unusual spellings) is unreliable for the speech synthesizer to
# pronounce. A generic greeting also reads as more professional/consistent
# for a public kiosk.
GREETING_PROMPT = (
    "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd. "
    "\u0baa\u0ba3\u0bae\u0bcd \u0b9a\u0bc6\u0bb2\u0bc1\u0ba4\u0bcd\u0ba4 \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bbe "
    "\u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0b8e\u0b9f\u0bc1\u0b95\u0bcd\u0b95 \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bbe? "
    "\u0ba4\u0bca\u0b95\u0bc8\u0baf\u0bc8 \u0b95\u0bc2\u0bb1\u0bc1\u0b99\u0bcd\u0b95\u0bb3\u0bcd."
)  # "Greetings. Would you like to deposit or withdraw money? Please say the amount."


def speak_assistant(text: str):
    """Speak a prompt in Tamil via the Web Speech Synthesis API.
    Callers must never pass the account number into `text`."""
    clean_text = text.replace('"', '\\"').replace("'", "\\'").replace("\n", " ")
    js_code = f"""
    <script>
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance("{clean_text}");
        utterance.lang = 'ta-IN';
        utterance.rate = 0.92;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    </script>
    """
    components.html(js_code, height=0)


def mask_account(acc_no: str) -> str:
    """Partial mask for on-screen / on-receipt display, e.g. 3155XXXX4787.
    Full number is only ever placed inside the signed QR payload for the teller."""
    digits = re.sub(r"\D", "", acc_no or "")
    if len(digits) < 8:
        return acc_no
    return f"{digits[:4]}{'X' * (len(digits) - 8)}{digits[-4:]}"


# ============================================================
# 5. PASSBOOK OCR PARSER (strictly avoids CIF numbers)
# ============================================================
def parse_passbook_text(raw_text: str):
    acc_no = ""
    acc_match = re.search(
        r"(?:Account\s*No|A\/c\s*No|Account\s*Number|Acc\s*No)[:\s\.]+([0-9]{9,18})",
        raw_text, re.IGNORECASE,
    )
    if acc_match:
        acc_no = acc_match.group(1).strip()
    else:
        for line in raw_text.split("\n"):
            if "cif" not in line.lower():
                digits = re.findall(r"\b\d{11,18}\b", line)
                if digits:
                    acc_no = digits[0]
                    break
        if not acc_no:
            fallback = re.findall(r"\b\d{9,18}\b", raw_text)
            acc_no = fallback[0] if fallback else ""

    holder_name = ""
    name_match = re.search(
        r"(?:Customer\s*Name|A\/c\s*Holder|Account\s*Name|Holder\s*Name|Name)[:\s\.]+([A-Za-z\s\.\/]+)",
        raw_text, re.IGNORECASE,
    )
    if name_match:
        extracted = name_match.group(1).strip()
        cleaned = re.split(
            r"(?:CIF|Account|A\/c|S\/O|D\/O|W\/O|Address|Branch|IFSC|\n)",
            extracted, flags=re.IGNORECASE,
        )[0].strip()
        if len(cleaned) >= 3:
            holder_name = cleaned

    if not holder_name:
        for line in raw_text.split("\n"):
            line_str = line.strip()
            if re.match(r"^[A-Z\s\.]{4,35}$", line_str) and not any(
                w in line_str for w in ["BANK", "INDIA", "BRANCH", "IFSC", "ACCOUNT", "SAVINGS", "CIF"]
            ):
                holder_name = line_str
                break

    ifsc_match = re.search(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", raw_text)
    ifsc_code = ifsc_match.group(0) if ifsc_match else ""

    return acc_no, holder_name, ifsc_code


# ============================================================
# 6. BILINGUAL (TAMIL / ENGLISH / TANGLISH) INTENT + AMOUNT PARSER
# ============================================================
# Tamil-script phrases are matched as substrings (Tamil words carry
# grammatical suffixes -- எடு/எடுக்க/எடுக்கணும் are all "the same" verb).
# Latin/Tanglish single words are matched as whole tokens (so "kudos"
# doesn't accidentally match "kudu"); Latin multi-word phrases are
# matched as substrings since they're fixed expressions.
#
# NOTE ON "கொடு" / "kudu" / "kudo": in everyday kiosk/ATM speech this
# means "give (me the money)" -- i.e. WITHDRAWAL, even though a literal
# word-for-word translation ("give") sounds deposit-like. This was the
# actual gap that caused "10000 kudo" to fall through uncategorized and
# silently keep whatever type was already selected.
WITHDRAW_TAMIL = [
    "\u0b8e\u0b9f\u0bc1", "\u0b8e\u0b9f\u0bc1\u0b95\u0bcd\u0b95", "\u0b8e\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0ba3\u0bc1\u0bae\u0bcd",
    "\u0b8e\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bcb",
    "\u0bb5\u0bbe\u0baa\u0bb8\u0bcd", "\u0bb5\u0bbf\u0ba4\u0bcd\u0b9f\u0bcd\u0bb0\u0bbe", "\u0bb5\u0bbf\u0b9f\u0bcd\u0bb0\u0bbe",
    "\u0bb5\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd", "\u0bb5\u0bbe\u0b99\u0bcd\u0b95\u0ba3\u0bc1\u0bae\u0bcd", "\u0bb5\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0b99\u0bcd\u0b95",
    "\u0b95\u0bca\u0b9f\u0bc1", "\u0b95\u0bca\u0b9f\u0bc1\u0b99\u0bcd\u0b95", "\u0b95\u0bca\u0b9f\u0bc1\u0b95\u0bcd\u0b95", "\u0b95\u0bca\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0ba3\u0bc1\u0bae\u0bcd",
    "\u0ba4\u0bbe", "\u0ba4\u0bbe\u0b99\u0bcd\u0b95", "\u0ba4\u0bb0\u0ba3\u0bc1\u0bae\u0bcd",
]
WITHDRAW_LATIN_TOKENS = {
    "withdraw", "withdrawal", "edukka", "eduka", "eduthu", "edukkanum", "edukanum",
    "vaanga", "vaanganum", "vaangunga", "vaanguga", "vanganum",
    "kudu", "kudo", "koduka", "kodunga", "kudunga", "kudungale", "kodu", "kuduga",
    "thaa", "thanga", "tharanum", "debit",
}
WITHDRAW_LATIN_PHRASES = ["with draw", "cash out", "take out", "draw cash", "draw money", "give money", "give cash"]

DEPOSIT_TAMIL = [
    "\u0baa\u0bcb\u0b9f\u0bc1", "\u0baa\u0bcb\u0b9f\u0bc1\u0b99\u0bcd\u0b95", "\u0baa\u0bcb\u0b9f\u0ba3\u0bc1\u0bae\u0bcd",
    "\u0b9a\u0bc6\u0bb2\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1", "\u0b9a\u0bc6\u0bb2\u0bc1\u0ba4\u0bcd\u0ba4\u0ba3\u0bc1\u0bae\u0bcd",
    "\u0b95\u0b9f\u0bcd\u0b9f\u0bc1", "\u0b95\u0b9f\u0bcd\u0b9f\u0ba3\u0bc1\u0bae\u0bcd",
    "\u0b87\u0b9f\u0bc1", "\u0b87\u0b9f\u0bc1\u0b99\u0bcd\u0b95", "\u0bb5\u0bc8", "\u0bb5\u0bc8\u0baf\u0bc1\u0b99\u0bcd\u0b95",
    "\u0b9a\u0bc7\u0bae\u0bbf", "\u0b9a\u0bc7\u0bae\u0bbf\u0b95\u0bcd\u0b95", "\u0b9c\u0bae\u0bbe",
]
DEPOSIT_LATIN_TOKENS = {
    "deposit", "kattanum", "podanum", "selutha", "poduven", "poda", "podunga",
    "podungale", "poduga", "jama", "jamai", "credit", "save",
}
DEPOSIT_LATIN_PHRASES = ["pay in", "put in", "add money"]


def _latin_tokens(text: str):
    return set(re.findall(r"[a-z]+", text.lower()))


def extract_intent(text: str):
    """Returns 'Cash Withdrawal', 'Cash Deposit', or None.
    If both a withdrawal and deposit signal appear (rare, usually a
    misrecognition), withdrawal wins since it's the more consequential
    action to get right."""
    t = text.lower()
    tokens = _latin_tokens(t)

    withdraw_hit = (
        any(k in t for k in WITHDRAW_TAMIL)
        or bool(tokens & WITHDRAW_LATIN_TOKENS)
        or any(p in t for p in WITHDRAW_LATIN_PHRASES)
    )
    if withdraw_hit:
        return "Cash Withdrawal"

    deposit_hit = (
        any(k in t for k in DEPOSIT_TAMIL)
        or bool(tokens & DEPOSIT_LATIN_TOKENS)
        or any(p in t for p in DEPOSIT_LATIN_PHRASES)
    )
    if deposit_hit:
        return "Cash Deposit"

    return None

TAMIL_NUMBER_WORDS = {
    "\u0b92\u0bb0\u0bc1 \u0bb2\u0b9f\u0bcd\u0b9a\u0bae\u0bcd": 100000,  # oru latcham
    "\u0bb2\u0b9f\u0bcd\u0b9a\u0bae\u0bcd": 100000,                     # latcham
    "\u0ba4\u0bca\u0ba3\u0bcd\u0ba3\u0bc2\u0bb1\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 90000,
    "\u0b8e\u0ba3\u0bcd\u0baa\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 80000,
    "\u0b8e\u0bb4\u0bc1\u0baa\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 70000,
    "\u0b85\u0bb1\u0bc1\u0baa\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 60000,
    "\u0b90\u0bae\u0bcd\u0baa\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 50000,
    "\u0ba8\u0bbe\u0bb1\u0bcd\u0baa\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 40000,
    "\u0bae\u0bc1\u0baa\u0bcd\u0baa\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 30000,
    "\u0b87\u0bb0\u0bc1\u0baa\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 20000,
    "\u0baa\u0ba4\u0bcd\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 10000,
    "\u0b92\u0ba9\u0bcd\u0baa\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 9000,
    "\u0b8e\u0b9f\u0bcd\u0b9f\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 8000,
    "\u0b8f\u0bb4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 7000,
    "\u0b86\u0bb1\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 6000,
    "\u0b90\u0ba8\u0bcd\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 5000,
    "\u0ba8\u0bbe\u0bb2\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 4000,
    "\u0ba8\u0bbe\u0ba9\u0bcd\u0b95\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 4000,
    "\u0bae\u0bc2\u0ba9\u0bcd\u0bb1\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 3000,
    "\u0bae\u0bc2\u0bb5\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 3000,
    "\u0b87\u0bb0\u0ba3\u0bcd\u0b9f\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 2000,
    "\u0b92\u0bb0\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 1000,
    "\u0b86\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 1000,
    "\u0ba4\u0bca\u0bb3\u0bcd\u0bb3\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd": 900,
    "\u0b8e\u0ba3\u0bcd\u0ba3\u0bc2\u0bb1\u0bc1": 800,
    "\u0b8e\u0bb4\u0bc1\u0ba8\u0bc2\u0bb1\u0bc1": 700,
    "\u0b85\u0bb1\u0bc1\u0ba8\u0bc2\u0bb1\u0bc1": 600,
    "\u0b90\u0ba8\u0bcd\u0ba8\u0bc2\u0bb1\u0bc1": 500,
    "\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1": 400,
    "\u0bae\u0bc1\u0ba9\u0bcd\u0ba9\u0bc2\u0bb1\u0bc1": 300,
    "\u0b87\u0bb0\u0bc1\u0ba8\u0bc2\u0bb1\u0bc1": 200,
    "\u0ba8\u0bc2\u0bb1\u0bc1": 100,
}
# Longest phrase first so e.g. "இருபதாயிரம்" is matched before any shorter substring.
_TAMIL_WORDS_BY_LEN = sorted(TAMIL_NUMBER_WORDS.keys(), key=len, reverse=True)

EN_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
EN_MULTIPLIERS = {"hundred": 100, "thousand": 1000, "lakh": 100000, "lac": 100000, "lakhs": 100000}


def _words_to_number_en(text: str):
    """Turns English number phrases ('twenty five thousand five hundred')
    into an int. Returns None if no number words were found."""
    tokens = re.findall(r"[a-z]+", text.lower())
    total = 0
    current = 0
    found = False
    for tok in tokens:
        if tok in EN_NUMBER_WORDS:
            current += EN_NUMBER_WORDS[tok]
            found = True
        elif tok in EN_MULTIPLIERS:
            found = True
            mult = EN_MULTIPLIERS[tok]
            current = (current or 1) * mult
            if mult >= 1000:
                total += current
                current = 0
    total += current
    return total if found else None


def extract_amount(text: str):
    """Returns an int amount parsed from digits, Tamil number words,
    or English number words -- in that priority order. None if nothing found."""
    t = text.lower().strip()
    t_no_commas = t.replace(",", "")

    digit_match = re.search(r"\d+", t_no_commas)
    if digit_match:
        num = int(digit_match.group(0))
        remainder = t_no_commas[digit_match.end():]
        if re.search(r"lakh|lac|\u0bb2\u0b9f\u0bcd\u0b9a\u0bae\u0bcd", remainder):
            num *= 100000
        elif re.search(r"thousand|\u0b86\u0baf\u0bbf\u0bb0\u0bae\u0bcd", remainder):
            num *= 1000
        elif re.search(r"hundred|\u0ba8\u0bc2\u0bb1\u0bc1", remainder):
            num *= 100
        return num

    for word in _TAMIL_WORDS_BY_LEN:
        if word in t:
            return TAMIL_NUMBER_WORDS[word]

    en_val = _words_to_number_en(t)
    if en_val:
        return en_val

    return None


def process_voice_command(spoken_text: str):
    """Updates session_state.tx_type / amount from a spoken transcript.
    Only overwrites a field when that field was actually detected, so a
    command like 'five thousand' (amount only, no verb) doesn't wipe the
    previously-set transaction type. Returns (intent, amount) -- both may
    be None -- so the caller can show the user exactly what was (or
    wasn't) picked up, instead of a misrecognition failing silently."""
    intent = extract_intent(spoken_text)
    if intent:
        st.session_state.tx_type = intent

    amount = extract_amount(spoken_text)
    if amount is not None:
        st.session_state.amount = str(amount)

    return intent, amount


# ============================================================
# 7. 58mm THERMAL SLIP PDF (with signature box + masked account number)
# ============================================================
def generate_pdf_receipt(tx_id, acc_no, holder_name, amount, tx_type, ifsc, qr_img):
    buffer = io.BytesIO()
    slip_width = 58 * mm
    slip_height = 165 * mm
    p = canvas.Canvas(buffer, pagesize=(slip_width, slip_height))

    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(slip_width / 2, slip_height - 9 * mm, "SMART BANK KIOSK")
    p.setFont("Helvetica", 7)
    p.drawCentredString(slip_width / 2, slip_height - 13 * mm, "Digital Self-Service Token")

    p.setLineWidth(0.5)
    p.line(4 * mm, slip_height - 15 * mm, slip_width - 4 * mm, slip_height - 15 * mm)

    p.setFont("Helvetica", 7)
    now_str = datetime.datetime.now().strftime("%d-%b-%Y %H:%M")
    p.drawString(4 * mm, slip_height - 20 * mm, f"Date: {now_str}")
    p.drawString(4 * mm, slip_height - 24 * mm, f"Token: #{tx_id[-6:]}")

    masked_acc = mask_account(acc_no)
    p.drawString(4 * mm, slip_height - 28 * mm, f"Acc No: {masked_acc}")
    p.drawString(4 * mm, slip_height - 32 * mm, f"Name: {holder_name[:22]}")
    p.drawString(4 * mm, slip_height - 36 * mm, f"IFSC: {ifsc}")
    p.drawString(4 * mm, slip_height - 40 * mm, f"Type: {tx_type}")

    p.setFont("Helvetica-Bold", 8)
    p.drawString(4 * mm, slip_height - 46 * mm, f"Amount: Rs. {amount}/-")

    p.line(4 * mm, slip_height - 49 * mm, slip_width - 4 * mm, slip_height - 49 * mm)

    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_reader = ImageReader(qr_buffer)
    p.drawImage(qr_reader, (slip_width - 28 * mm) / 2, slip_height - 80 * mm, width=28 * mm, height=28 * mm)

    p.line(4 * mm, slip_height - 84 * mm, slip_width - 4 * mm, slip_height - 84 * mm)
    p.setFont("Helvetica-Oblique", 6)
    p.drawCentredString(slip_width / 2, slip_height - 88 * mm, "Please sign below before counter verification")

    p.setDash([2, 2], 0)
    p.line(8 * mm, slip_height - 105 * mm, slip_width - 8 * mm, slip_height - 105 * mm)
    p.setDash([], 0)

    p.setFont("Helvetica-Bold", 6.5)
    p.drawCentredString(slip_width / 2, slip_height - 109 * mm, "X __________________________")
    p.setFont("Helvetica", 6)
    p.drawCentredString(slip_width / 2, slip_height - 113 * mm, "(Customer Signature)")

    p.line(4 * mm, slip_height - 117 * mm, slip_width - 4 * mm, slip_height - 117 * mm)
    p.setFont("Helvetica", 5.5)
    p.drawCentredString(slip_width / 2, slip_height - 121 * mm, "Token valid for counter verification today only.")
    p.drawCentredString(slip_width / 2, slip_height - 124 * mm, "Self-Service Security Enabled.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


# ============================================================
# 8. BANK TELLER PORTAL -- QR decoding, audio feedback, ack slip
# ============================================================
def decode_qr_from_image(pil_image: Image.Image):
    """Decodes a QR code from a PIL image using OpenCV. Returns the raw
    string payload, or None if no QR code was found."""
    img_rgb = np.array(pil_image.convert("RGB"))
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img_bgr)
    return data if data else None


def parse_qr_payload(raw: str) -> dict:
    """Parses the 'ID:...|ACC:...|NAME:...|IFSC:...|AMT:...|TYPE:...'
    token format written into the customer-side QR code."""
    fields = {}
    for part in raw.split("|"):
        if ":" in part:
            key, _, value = part.partition(":")
            fields[key.strip().upper()] = value.strip()
    return fields


def txn_timestamp_from_id(tx_id: str):
    """Token IDs are 'TXN-YYYYMMDDHHMMSS' -- recover the timestamp for display."""
    try:
        raw = tx_id.replace("TXN-", "")
        return datetime.datetime.strptime(raw, "%Y%m%d%H%M%S")
    except (ValueError, AttributeError):
        return None


def play_beep(kind: str = "success"):
    """Short Web Audio API oscillator beep -- success is a single higher
    tone, reject is a lower double-beep. No audio files needed, so this
    works unmodified inside the PyInstaller-frozen exe."""
    if kind == "success":
        freqs = [880]
    else:
        freqs = [300, 300]
    js_tones = ",".join(f"{f}" for f in freqs)
    components.html(
        f"""
        <script>
        (function() {{
            const freqs = [{js_tones}];
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            let t = ctx.currentTime;
            freqs.forEach((f) => {{
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = "sine";
                osc.frequency.value = f;
                gain.gain.setValueAtTime(0.15, t);
                gain.gain.exponentialRampToValueAtTime(0.001, t + 0.18);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(t);
                osc.stop(t + 0.2);
                t += 0.22;
            }});
        }})();
        </script>
        """,
        height=0,
    )


def generate_teller_ack_pdf(txn: dict, teller_id: str) -> io.BytesIO:
    """Small counter acknowledgement slip the teller can print after
    approving a transaction -- separate from the customer's own token slip."""
    buffer = io.BytesIO()
    slip_width = 58 * mm
    slip_height = 110 * mm
    p = canvas.Canvas(buffer, pagesize=(slip_width, slip_height))

    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(slip_width / 2, slip_height - 9 * mm, "TELLER ACKNOWLEDGEMENT")
    p.setFont("Helvetica", 7)
    p.drawCentredString(slip_width / 2, slip_height - 13 * mm, "Counter-Verified Transaction")

    p.line(4 * mm, slip_height - 15 * mm, slip_width - 4 * mm, slip_height - 15 * mm)

    p.setFont("Helvetica", 7)
    now_str = datetime.datetime.now().strftime("%d-%b-%Y %H:%M")
    p.drawString(4 * mm, slip_height - 20 * mm, f"Processed: {now_str}")
    p.drawString(4 * mm, slip_height - 24 * mm, f"Token: {txn.get('ID', '')[-10:]}")
    p.drawString(4 * mm, slip_height - 28 * mm, f"Teller ID: {teller_id or 'N/A'}")

    p.drawString(4 * mm, slip_height - 34 * mm, f"Acc No: {mask_account(txn.get('ACC', ''))}")
    p.drawString(4 * mm, slip_height - 38 * mm, f"Name: {txn.get('NAME', '')[:22]}")
    p.drawString(4 * mm, slip_height - 42 * mm, f"Type: {txn.get('TYPE', '')}")
    p.setFont("Helvetica-Bold", 8)
    p.drawString(4 * mm, slip_height - 48 * mm, f"Amount: Rs. {txn.get('AMT', '')}/-")

    p.line(4 * mm, slip_height - 52 * mm, slip_width - 4 * mm, slip_height - 52 * mm)
    p.setFont("Helvetica-Bold", 9)
    p.drawCentredString(slip_width / 2, slip_height - 60 * mm, "*** APPROVED ***")

    p.setFont("Helvetica", 6)
    p.drawCentredString(slip_width / 2, slip_height - 70 * mm, "X __________________________")
    p.drawCentredString(slip_width / 2, slip_height - 74 * mm, "(Teller Signature)")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


# ============================================================
# 9. UI -- CUSTOMER KIOSK VIEW
# ============================================================
def render_customer_kiosk():
    st.title("\U0001F3E6 AI Smart Bank Assistant & Voice Kiosk")
    st.caption("Privacy-compliant multilingual self-service banking (Tamil & English)")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("\U0001F4F7 Step 1: Scan Passbook")
        img_file = st.file_uploader("Upload Passbook Image or Take Photo", type=["jpg", "png", "jpeg"])

        if img_file:
            img = Image.open(img_file)
            st.image(img, caption="Scanned Passbook Preview", use_container_width=True)

            with st.spinner("Extracting passbook details..."):
                extracted_text = pytesseract.image_to_string(img)
                acc, name, ifsc = parse_passbook_text(extracted_text)

                if acc:
                    st.session_state.acc_no = acc
                if name:
                    st.session_state.holder_name = name
                if ifsc:
                    st.session_state.ifsc = ifsc

            if st.session_state.holder_name:
                # NOTE: TTS prompts are always fixed, generic strings -- never
                # interpolated with the OCR'd customer name (which can contain
                # unpredictable spellings/scripts the speech synthesizer mispronounces)
                # and never with the account number.
                speak_assistant(GREETING_PROMPT)
                st.success(f"Passbook verified: {st.session_state.holder_name}")
            else:
                st.warning("Could not confidently read the passbook. Please check / correct the fields on the right.")

            if st.session_state.acc_no:
                st.caption(f"Detected account (masked): **{mask_account(st.session_state.acc_no)}**")

    with col2:
        st.subheader("\U0001F3A4 Step 2: Voice Command & Verification")
        st.caption("Tap the mic, say e.g. \u2018Deposit 5000\u2019 or \u2018\u0b90\u0ba8\u0bcd\u0ba4\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd \u0b8e\u0b9f\u0bc1\u0b95\u0bcd\u0b95 \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bcd\u2019 (withdraw five thousand).")

        spoken_voice = voice_bridge_component(key="voice_mic_bridge", default=None)

        if spoken_voice and spoken_voice != st.session_state.last_voice_cmd:
            st.session_state.last_voice_cmd = spoken_voice
            st.session_state.voice_cmd_count += 1
            detected_intent, detected_amount = process_voice_command(spoken_voice)
            if detected_intent or detected_amount is not None:
                bits = []
                if detected_intent:
                    bits.append(detected_intent)
                if detected_amount is not None:
                    bits.append(f"\u20b9{detected_amount}")
                st.toast(f"\u2705 Understood: {' / '.join(bits)}")
            else:
                st.toast("\u26A0\ufe0f Didn't catch a transaction type or amount -- please correct the form manually.")
            st.rerun()

        if st.session_state.last_voice_cmd:
            st.info(f"\U0001F5E3\ufe0f Last heard voice command: **'{st.session_state.last_voice_cmd}'**")

        # `voice_cmd_count` is folded into the widget keys below so that each
        # new voice command forces Streamlit to re-mount the text inputs with
        # the freshly-updated session_state values (avoids stale widget state).
        form_key_suffix = st.session_state.voice_cmd_count

        with st.form("manual_confirm_form"):
            st.markdown("**Verify transaction details:**")
            acc_val = st.text_input(
                "Account Number", value=st.session_state.acc_no, key=f"acc_in_{form_key_suffix}"
            )
            name_val = st.text_input(
                "Account Holder Name", value=st.session_state.holder_name, key=f"name_in_{form_key_suffix}"
            )
            ifsc_val = st.text_input(
                "IFSC Code", value=st.session_state.ifsc, key=f"ifsc_in_{form_key_suffix}"
            )

            type_options = ["Cash Deposit", "Cash Withdrawal", "Cheque Deposit"]
            type_idx = type_options.index(st.session_state.tx_type) if st.session_state.tx_type in type_options else 0
            tx_type_val = st.selectbox(
                "Transaction Type", type_options, index=type_idx, key=f"type_in_{form_key_suffix}"
            )

            amt_val = st.text_input(
                "Amount (INR)", value=st.session_state.amount, key=f"amt_in_{form_key_suffix}"
            )

            if acc_val:
                st.caption(f"Will print as: {mask_account(acc_val)}")

            generate_btn = st.form_submit_button("Generate & Print Thermal Slip PDF")

        if generate_btn:
            tx_id = f"TXN-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

            speak_assistant(
                f"\u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd {tx_type_val} \u0bb0\u0b9a\u0bc0\u0ba4\u0bc1 \u0ba4\u0baf\u0bbe\u0bb0\u0bbe\u0b95 \u0b89\u0bb3\u0bcd\u0bb3\u0ba4\u0bc1. "
                f"\u0ba4\u0baf\u0bb5\u0bc1\u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0bb0\u0b9a\u0bc0\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0bc8\u0baf\u0bca\u0baa\u0bcd\u0baa\u0bae\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 "
                f"\u0b95\u0bb5\u0bc1\u0ba3\u0bcd\u0b9f\u0bb0\u0bbf\u0bb2\u0bcd \u0b95\u0bca\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd."
            )

            # Full account number goes into the signed QR payload for the teller
            # only -- it is never spoken aloud and only appears masked on screen/print.
            payload = f"ID:{tx_id}|ACC:{acc_val}|NAME:{name_val}|IFSC:{ifsc_val}|AMT:{amt_val}|TYPE:{tx_type_val}"
            qr = qrcode.QRCode(box_size=5, border=1)
            qr.add_data(payload)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")

            pdf_bytes = generate_pdf_receipt(tx_id, acc_val, name_val, amt_val, tx_type_val, ifsc_val, qr_img)

            st.divider()
            st.markdown("### \U0001F5A8\ufe0f Generated Receipt Slip (Ready to Sign)")

            c_qr, c_dl = st.columns([1, 1])
            with c_qr:
                st.image(qr_img.get_image(), caption="Teller QR Token", width=160)
            with c_dl:
                st.download_button(
                    label="\U0001F4C4 Download 58mm Thermal Slip (PDF)",
                    data=pdf_bytes,
                    file_name=f"bank_token_{tx_id[-6:]}.pdf",
                    mime="application/pdf",
                )


# ============================================================
# 10. UI -- BANK TELLER PORTAL VIEW
# ============================================================
def render_teller_portal():
    st.title("\U0001F5A5\ufe0f Bank Teller Verification Portal")
    st.caption("\u0bb5\u0b99\u0bcd\u0b95\u0bbf \u0b85\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bbf \u0baa\u0b95\u0bcd\u0b95\u0bae\u0bcd \u2014 scan a customer's thermal-slip QR token to verify and process it")

    scan_col, dash_col = st.columns([1, 1.3])

    decoded_raw = None

    with scan_col:
        st.subheader("\U0001F4F8 Step 1: Scan Token QR")
        scan_mode = st.radio("Input method", ["Camera", "Upload QR image"], horizontal=True, key="teller_scan_mode")

        if scan_mode == "Camera":
            cam_img = st.camera_input("Point camera at the customer's printed QR token", key="teller_camera")
            if cam_img is not None:
                decoded_raw = decode_qr_from_image(Image.open(cam_img))
        else:
            up_img = st.file_uploader("Upload a photo of the QR token", type=["jpg", "jpeg", "png"], key="teller_upload")
            if up_img is not None:
                decoded_raw = decode_qr_from_image(Image.open(up_img))

        if decoded_raw:
            if decoded_raw != st.session_state.last_scan_raw:
                # A genuinely new scan -- parse it, beep, and remount the
                # teller-side widgets below (checklist/buttons) for it.
                st.session_state.last_scan_raw = decoded_raw
                st.session_state.last_scanned_payload = parse_qr_payload(decoded_raw)
                st.session_state.teller_scan_count += 1
                play_beep("success")
                st.toast("\u2705 QR token decoded")
        elif scan_mode == "Camera" and st.session_state.get("teller_camera") is not None:
            st.warning("No QR code detected in that frame. Try holding the slip flatter / closer.")

    with dash_col:
        st.subheader("\U0001F4CB Step 2: Verify & Process")
        txn = st.session_state.last_scanned_payload

        if not txn:
            st.info("Scan a customer token to see transaction details here.")
            return

        scan_key = st.session_state.teller_scan_count

        tx_id = txn.get("ID", "")
        acc = txn.get("ACC", "")
        name = txn.get("NAME", "")
        ifsc = txn.get("IFSC", "")
        tx_type = txn.get("TYPE", "")
        try:
            amount_val = float(re.sub(r"[^\d.]", "", txn.get("AMT", "0")) or 0)
        except ValueError:
            amount_val = 0.0

        ts = txn_timestamp_from_id(tx_id)
        ts_str = ts.strftime("%d-%b-%Y %H:%M:%S") if ts else "Unknown"

        st.markdown(f"**Token ID:** `{tx_id or 'N/A'}`  \n**Timestamp:** {ts_str}")

        d1, d2 = st.columns(2)
        with d1:
            st.metric("Account Number", acc or "N/A")
            st.metric("IFSC Code", ifsc or "N/A")
        with d2:
            st.metric("Account Holder", name or "N/A")
            st.metric("Transaction Type", tx_type or "N/A")

        if amount_val > 50000:
            st.error(f"\u26A0\ufe0f HIGH-VALUE TRANSACTION: \u20b9{amount_val:,.0f} -- additional verification required")
        else:
            st.success(f"Amount: \u20b9{amount_val:,.0f}")

        st.markdown("**Signature Verification Checklist**")
        chk1 = st.checkbox("Signature matches passbook specimen", key=f"chk_sig_{scan_key}")
        chk2 = st.checkbox("Photo ID verified against account holder name", key=f"chk_id_{scan_key}")
        chk3 = st.checkbox("Token not previously processed today", key=f"chk_dup_{scan_key}")
        all_checked = chk1 and chk2 and chk3

        teller_id = st.text_input("Teller ID / Counter No.", key=f"teller_id_{scan_key}")
        reject_reason = st.text_input(
            "Rejection reason (optional, used only if you flag this token)",
            key=f"reject_reason_{scan_key}",
        )

        b1, b2 = st.columns(2)
        with b1:
            approve_clicked = st.button(
                "\u2705 Approve & Execute Transaction",
                disabled=not all_checked,
                key=f"approve_{scan_key}",
                use_container_width=True,
            )
        with b2:
            reject_clicked = st.button(
                "\U0001F6AB Flag / Reject Token",
                key=f"reject_{scan_key}",
                use_container_width=True,
            )

        if not all_checked:
            st.caption("Complete all three checklist items to enable approval.")

        if approve_clicked:
            record = dict(txn)
            record["teller_id"] = teller_id
            record["processed_at"] = datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")
            st.session_state.processed_txns.append(record)
            st.success(f"Transaction {tx_id} approved and recorded.")

            ack_pdf = generate_teller_ack_pdf(txn, teller_id)
            st.download_button(
                "\U0001F4C4 Download Teller Counter Acknowledgement Slip",
                data=ack_pdf,
                file_name=f"teller_ack_{tx_id[-6:]}.pdf",
                mime="application/pdf",
                key=f"ack_dl_{scan_key}",
            )

        if reject_clicked:
            record = dict(txn)
            record["teller_id"] = teller_id
            record["rejected_at"] = datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")
            record["reason"] = reject_reason
            st.session_state.rejected_txns.append(record)
            play_beep("reject")
            st.warning(f"Token {tx_id} flagged / rejected.")

    st.divider()
    log_col1, log_col2 = st.columns(2)
    with log_col1:
        st.markdown("**\u2705 Processed transactions (this session)**")
        if st.session_state.processed_txns:
            st.dataframe(
                [
                    {
                        "Token": t.get("ID", ""),
                        "Name": t.get("NAME", ""),
                        "Type": t.get("TYPE", ""),
                        "Amount": t.get("AMT", ""),
                        "Teller": t.get("teller_id", ""),
                        "Processed at": t.get("processed_at", ""),
                    }
                    for t in st.session_state.processed_txns
                ],
                use_container_width=True,
            )
        else:
            st.caption("No transactions approved yet.")
    with log_col2:
        st.markdown("**\U0001F6AB Flagged / rejected tokens (this session)**")
        if st.session_state.rejected_txns:
            st.dataframe(
                [
                    {
                        "Token": t.get("ID", ""),
                        "Name": t.get("NAME", ""),
                        "Amount": t.get("AMT", ""),
                        "Teller": t.get("teller_id", ""),
                        "Reason": t.get("reason", ""),
                        "Rejected at": t.get("rejected_at", ""),
                    }
                    for t in st.session_state.rejected_txns
                ],
                use_container_width=True,
            )
        else:
            st.caption("No tokens rejected yet.")


# ============================================================
# 11. TOP-LEVEL NAVIGATION
# ============================================================
with st.sidebar:
    st.markdown("### \U0001F3E6 Smart Bank Kiosk")
    mode_choice = st.radio(
        "Select view",
        options=["kiosk", "teller"],
        format_func=lambda m: (
            "\U0001F4F1 Customer Kiosk (\u0bb5\u0bbe\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc8\u0baf\u0bbe\u0bb3\u0bb0\u0bcd \u0bae\u0bc8\u0baf\u0bae\u0bcd)"
            if m == "kiosk"
            else "\U0001F5A5\ufe0f Bank Teller Portal (\u0bb5\u0b99\u0bcd\u0b95\u0bbf \u0b85\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bbf \u0baa\u0b95\u0bcd\u0b95\u0bae\u0bcd)"
        ),
        key="app_mode",
    )
    st.divider()
    st.caption(f"Processed today: {len(st.session_state.processed_txns)}")
    st.caption(f"Flagged today: {len(st.session_state.rejected_txns)}")

if st.session_state.app_mode == "kiosk":
    render_customer_kiosk()
else:
    render_teller_portal()