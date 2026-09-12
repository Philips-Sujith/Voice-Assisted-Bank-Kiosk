"""
Module 2: Vernacular Voice AI — Intent & Entity Parser
Extracts banking intents and entities from English, Tamil, and Tanglish transcripts.
Conforms strictly to the Kiosk Interface Contract v0.1.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

# Supported intent constants
INTENT_WITHDRAW = "withdraw"
INTENT_DEPOSIT = "deposit"
INTENT_SEND_MONEY = "send_money"
INTENT_BALANCE_CHECK = "balance_check"
INTENT_OPEN_ACCOUNT = "open_account"
INTENT_UNKNOWN = "unknown"

VALID_INTENTS = {
    INTENT_WITHDRAW,
    INTENT_DEPOSIT,
    INTENT_SEND_MONEY,
    INTENT_BALANCE_CHECK,
    INTENT_OPEN_ACCOUNT,
    INTENT_UNKNOWN,
}

# Intents that mandate an amount entity
AMOUNT_REQUIRED_INTENTS = {INTENT_WITHDRAW, INTENT_DEPOSIT, INTENT_SEND_MONEY}

# Word to number mapping (Tamil & English)
WORD_TO_NUMBER: list[tuple[re.Pattern, int]] = [
    # Tamil word amounts
    (re.compile(r"ஒரு\s*கோடி|கோடி", re.IGNORECASE), 10000000),
    (re.compile(r"ஒன்றரை\s*லட்சம்", re.IGNORECASE), 150000),
    (re.compile(r"இரண்டு\s*லட்சம்|ரெண்டு\s*லட்சம்", re.IGNORECASE), 200000),
    (re.compile(r"ஒரு\s*லட்சம்|லட்சம்", re.IGNORECASE), 100000),
    (re.compile(r"ஐம்பதாயிரம்", re.IGNORECASE), 50000),
    (re.compile(r"இருபதாயிரம்", re.IGNORECASE), 20000),
    (re.compile(r"பத்தாயிரம்", re.IGNORECASE), 10000),
    (re.compile(r"ஐந்தாயிரம்|அஞ்சாயிரம்", re.IGNORECASE), 5000),
    (re.compile(r"நான்காயிரம்", re.IGNORECASE), 4000),
    (re.compile(r"மூவாயிரம்", re.IGNORECASE), 3000),
    (re.compile(r"இரண்டாயிரம்|ரெண்டாயிரம்", re.IGNORECASE), 2000),
    (re.compile(r"ஆயிரம்", re.IGNORECASE), 1000),
    (re.compile(r"ஐந்நூறு|அந்நூறு", re.IGNORECASE), 500),
    (re.compile(r"நூறு", re.IGNORECASE), 100),
    # English word amounts
    (re.compile(r"\bone\s*lakh\b", re.IGNORECASE), 100000),
    (re.compile(r"\bfifty\s*thousand\b", re.IGNORECASE), 50000),
    (re.compile(r"\btwenty\s*thousand\b", re.IGNORECASE), 20000),
    (re.compile(r"\bten\s*thousand\b", re.IGNORECASE), 10000),
    (re.compile(r"\bfive\s*thousand\b", re.IGNORECASE), 5000),
    (re.compile(r"\bfour\s*thousand\b", re.IGNORECASE), 4000),
    (re.compile(r"\bthree\s*thousand\b", re.IGNORECASE), 3000),
    (re.compile(r"\btwo\s*thousand\b", re.IGNORECASE), 2000),
    (re.compile(r"\bone\s*thousand\b", re.IGNORECASE), 1000),
    (re.compile(r"\bfive\s*hundred\b", re.IGNORECASE), 500),
    (re.compile(r"\bone\s*hundred\b", re.IGNORECASE), 100),
]

# Intent classification patterns
INTENT_RULES: list[tuple[str, list[Any]]] = [
    (
        INTENT_BALANCE_CHECK,
        [
            re.compile(r"\bbalance\b", re.IGNORECASE),
            "இருப்பு",
            "இருப்பை",
            re.compile(r"\biruppu\w*", re.IGNORECASE),
            re.compile(r"\bcheck\s*balance\b", re.IGNORECASE),
        ],
    ),
    (
        INTENT_WITHDRAW,
        [
            re.compile(r"\bwithdraw\w*", re.IGNORECASE),
            "எடுக்க",
            "எடுக்கனும்",
            "பணம் எடு",
            re.compile(r"\bedukka\w*", re.IGNORECASE),
            re.compile(r"\bwithdraw\b", re.IGNORECASE),
        ],
    ),
    (
        INTENT_DEPOSIT,
        [
            re.compile(r"\bdeposit\w*", re.IGNORECASE),
            "டெபாசிட்",
            "செலுத்த",
            "போடு",
            re.compile(r"\bpodu\w*", re.IGNORECASE),
            re.compile(r"\bpodanum\b", re.IGNORECASE),
        ],
    ),
    (
        INTENT_SEND_MONEY,
        [
            re.compile(r"\bsend\b", re.IGNORECASE),
            re.compile(r"\btransfer\w*", re.IGNORECASE),
            "அனுப்பு",
            "பரிமாற்றம்",
            re.compile(r"\banuppu\w*", re.IGNORECASE),
        ],
    ),
    (
        INTENT_OPEN_ACCOUNT,
        [
            re.compile(r"\bopen\s*(?:an?\s*)?account\b", re.IGNORECASE),
            re.compile(r"\bnew\s*account\b", re.IGNORECASE),
            "புதிய கணக்கு",
            "கணக்கு தொடங்க",
            re.compile(r"\baccount\s*open\b", re.IGNORECASE),
        ],
    ),
]


def normalize_transcript(text: str) -> str:
    """Normalize raw speech transcript: lowercase, strip, collapse whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    return re.sub(r"\s+", " ", text)


def extract_amount(text: str) -> Optional[int]:
    """Extract numerical amount from text, handling Indian monetary expressions, digits, and words."""
    if not text:
        return None
    cleaned = text.lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").strip()

    word_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "twenty": 20, "twenty five": 25, "thirty": 30, "forty": 40, "fifty": 50,
        "ninety nine": 99,
    }

    # 1. Crores (e.g. "1 crore", "1.5 crore", "one crore", "ஒரு கோடி")
    crore_match = re.search(
        r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twenty|fifty|ninety\s*nine)\s*(?:crores?|cr\b|கோடி)",
        cleaned,
        re.IGNORECASE,
    )
    if crore_match:
        val_str = crore_match.group(1).lower()
        val = float(val_str) if re.match(r"^\d", val_str) else word_map.get(val_str, 1)
        return int(round(val * 10000000))

    # 2. Compound or decimal lakh (e.g. "1.5 lakh", "99 lakh", "two lakh fifty thousand", "1 lakh 20 thousand")
    compound_match = re.search(
        r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twenty|twenty\s*five|fifty|ninety\s*nine)\s*(?:lakhs?|lacs?|லட்சம்)(?:\s*(?:and\s*)?(\d+|fifty|twenty\s*five|twenty|ten)\s*thousand)?",
        cleaned,
        re.IGNORECASE,
    )
    if compound_match:
        l_str = compound_match.group(1).lower()
        th_str = compound_match.group(2)
        l_val = float(l_str) if re.match(r"^\d", l_str) else word_map.get(l_str, 1)
        th_val = 0
        if th_str:
            th_str = th_str.lower()
            th_val = float(th_str) if re.match(r"^\d", th_str) else word_map.get(th_str, 0)
        return int(round(l_val * 100000 + th_val * 1000))

    # 3. Standalone lakh / lac (e.g. "1 lakh", "one lakh", "one lac", "1 lac", "lakh")
    if re.search(r"\b(?:one|1)?\s*(?:lakh|lac|லட்சம்)\b", cleaned, re.IGNORECASE):
        return 100000

    # 4. Thousands in words or digits (e.g. "twenty five thousand", "50 thousand", "50000")
    th_match = re.search(
        r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twenty|twenty\s*five|fifty)\s*thousand",
        cleaned,
        re.IGNORECASE,
    )
    if th_match:
        th_str = th_match.group(1).lower()
        th_val = float(th_str) if re.match(r"^\d", th_str) else word_map.get(th_str, 1)
        return int(round(th_val * 1000))

    # 5. Check specific Tamil/English word amounts
    for pattern, value in WORD_TO_NUMBER:
        if pattern.search(cleaned):
            return value

    # 6. Plain digit sequences (e.g. "100000", "25000", "5000")
    digit_match = re.search(r"\b\d+\b", cleaned)
    if digit_match:
        try:
            return int(digit_match.group(0))
        except ValueError:
            pass

    return None


def extract_account_number(text: str) -> str:
    """Extract or assign default account number."""
    match = re.search(r"\b(?:acc(?:ount)?\s*(?:no\.?|num(?:ber)?)?\s*)?(\d{4,16})\b", text, re.IGNORECASE)
    if match:
        acc = match.group(1)
        if len(acc) > 4:
            return f"XXXX{acc[-4:]}"
        return f"XXXX{acc}"
    return "XXXX1234"


def extract_recipient(text: str) -> Optional[str]:
    """Extract recipient name if mentioned in transfer."""
    match = re.search(r"\bto\s+([A-Za-z]+)\b", text, re.IGNORECASE)
    if match:
        name = match.group(1).title()
        if name.lower() not in {"account", "rupees", "rs", "my"}:
            return name
    return None


def detect_intent(text: str) -> str:
    """Detect intent from normalized transcript."""
    for intent, patterns in INTENT_RULES:
        for pattern in patterns:
            if isinstance(pattern, re.Pattern):
                if pattern.search(text):
                    return intent
            elif isinstance(pattern, str):
                if pattern in text:
                    return intent
    return INTENT_UNKNOWN


def number_to_tamil_words(num: Optional[int]) -> str:
    """Convert integer amount to Tamil words for natural speech synthesis."""
    if num is None:
        return ""
    mapping = {
        100: "நூறு",
        500: "ஐந்நூறு",
        1000: "ஆயிரம்",
        2000: "இரண்டாயிரம்",
        3000: "மூவாயிரம்",
        4000: "நான்காயிரம்",
        5000: "ஐந்தாயிரம்",
        10000: "பத்தாயிரம்",
        20000: "இருபதாயிரம்",
        50000: "ஐம்பதாயிரம்",
        100000: "ஒரு லட்சம்",
        150000: "ஒன்றரை லட்சம்",
        200000: "இரண்டு லட்சம்",
        9900000: "தொண்ணூற்று ஒன்பது லட்சம்",
        10000000: "ஒரு கோடி",
    }
    return mapping.get(num, str(num))


def build_spoken_confirmation(intent: str, amount: Optional[int], language: str) -> str:
    """Generate localized prompt response for the customer."""
    lang = (language or "en").lower()
    amount_disp = number_to_tamil_words(amount) if lang == "ta" else (str(amount) if amount is not None else "")

    if intent == INTENT_WITHDRAW:
        if lang == "ta":
            return f"தயவுசெய்து உறுதிப்படுத்தவும்: {amount_disp} ரூபாய் எடுக்க விரும்புகிறீர்களா?"
        elif lang == "tanglish":
            return f"Confirm pannunga: {amount_disp} rupees withdraw pannalaama?"
        return f"Please confirm: withdraw {amount_disp} rupees?"

    elif intent == INTENT_DEPOSIT:
        if lang == "ta":
            return f"தயவுசெய்து உறுதிப்படுத்தவும்: {amount_disp} ரூபாய் டெபாசிட் செய்ய விரும்புகிறீர்களா?"
        elif lang == "tanglish":
            return f"Confirm pannunga: {amount_disp} rupees deposit pannalaama?"
        return f"Please confirm: deposit {amount_disp} rupees?"

    elif intent == INTENT_SEND_MONEY:
        if lang == "ta":
            return f"தயவுசெய்து உறுதிப்படுத்தவும்: {amount_disp} ரூபாய் அனுப்ப விரும்புகிறீர்களா?"
        elif lang == "tanglish":
            return f"Confirm pannunga: {amount_disp} rupees transfer pannalaama?"
        return f"Please confirm: send {amount_disp} rupees?"

    elif intent == INTENT_BALANCE_CHECK:
        if lang == "ta":
            return "சரி, உங்கள் கணக்கு இருப்பை சரிபார்க்கிறேன்."
        elif lang == "tanglish":
            return "Sari, unga account balance check panren."
        return "Sure, let me check your account balance."

    elif intent == INTENT_OPEN_ACCOUNT:
        if lang == "ta":
            return "புதிய கணக்கு தொடங்குவதற்கான படிவத்தை தயார் செய்கிறேன்."
        elif lang == "tanglish":
            return "Pudhiya account open panna help panren."
        return "I will help you open a new bank account."

    else:
        if lang == "ta":
            return "மன்னிக்கவும், புரியவில்லை. மீண்டும் சொல்ல முடியுமா?"
        elif lang == "tanglish":
            return "Sorry, puriyala. Innoru murai sollunga?"
        return "Sorry, I didn't understand that request. Could you please repeat it?"


def parse_intent_and_entities(
    raw_transcript: str,
    preferred_language: str = "en",
    raw_confidence: float = 0.92,
) -> Dict[str, Any]:
    """
    Main entry point: turns transcript into intent, entities, confidence,
    and spoken response.
    """
    norm = normalize_transcript(raw_transcript)
    intent = detect_intent(norm)
    amount = extract_amount(norm)
    account_number = extract_account_number(norm)
    recipient = extract_recipient(norm)

    amount_required = intent in AMOUNT_REQUIRED_INTENTS
    amount_missing = amount_required and (amount is None or amount <= 0)
    intent_unknown = intent == INTENT_UNKNOWN

    if intent_unknown or amount_missing:
        confidence = 0.45
    else:
        confidence = min(0.96, max(0.75, raw_confidence))

    spoken_text = build_spoken_confirmation(intent, amount, preferred_language)

    entities = {
        "amount": amount,
        "account_number": account_number,
        "recipient": recipient,
    }

    requires_auth = intent in {INTENT_WITHDRAW, INTENT_DEPOSIT}

    return {
        "status": "ok",
        "language": preferred_language,
        "intent": intent,
        "requires_auth": requires_auth,
        "entities": entities,
        "confidence": round(confidence, 2),
        "raw_transcript": raw_transcript,
        "spoken_text": spoken_text,
    }
