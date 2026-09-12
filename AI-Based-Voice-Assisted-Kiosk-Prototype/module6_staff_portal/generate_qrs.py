"""
generate_qrs.py
Generates 5 plain, scannable QR tokens for the Nexa Bank Staff Portal prototype.
Plain white background, no image manipulation — guaranteed scannable.
Output -> sample_qrs/
"""

import json, os, qrcode

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "sample_qrs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TOKENS = [
    {
        "filename": "customer_8821_withdraw.png",
        "payload": {
            "token": "VALID_HMAC_SIG_8821_WITHDRAW",
            "token_id": "TXN-2026-008821",
            "customer_display_name": "Customer #8821",
            "transaction_type": "withdraw",
            "amount": 100000,
            "account_balance": 285000,
            "queue_position": 1
        }
    },
    {
        "filename": "customer_3277_transfer.png",
        "payload": {
            "token": "VALID_HMAC_SIG_3277_TRANSFER",
            "token_id": "TXN-2026-003277",
            "customer_display_name": "Customer #3277",
            "transaction_type": "transfer",
            "amount": 50000,
            "account_balance": 192500,
            "queue_position": 2
        }
    },
    {
        "filename": "customer_1104_deposit.png",
        "payload": {
            "token": "VALID_HMAC_SIG_1104_DEPOSIT",
            "token_id": "TXN-2026-001104",
            "customer_display_name": "Customer #1104",
            "transaction_type": "deposit",
            "amount": 25000,
            "account_balance": 48000,
            "queue_position": 3
        }
    },
    {
        "filename": "customer_5590_withdraw_insufficient.png",
        "payload": {
            "token": "VALID_HMAC_SIG_5590_WITHDRAW",
            "token_id": "TXN-2026-005590",
            "customer_display_name": "Customer #5590",
            "transaction_type": "withdraw",
            "amount": 150000,
            "account_balance": 75000,
            "queue_position": 4
        }
    },
    {
        "filename": "customer_7412_document.png",
        "payload": {
            "token": "VALID_HMAC_SIG_7412_DOCUMENT",
            "token_id": "TXN-2026-007412",
            "customer_display_name": "Customer #7412",
            "transaction_type": "document_collection",
            "amount": 0,
            "account_balance": 134000,
            "queue_position": 5
        }
    },
]

for t in TOKENS:
    payload_str = json.dumps(t["payload"])

    qr = qrcode.QRCode(
        version=None,                          # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,                              # standard quiet zone = 4 modules
    )
    qr.add_data(payload_str)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    out_path = os.path.join(OUTPUT_DIR, t["filename"])
    img.save(out_path)
    print(f"[OK] {t['filename']}  ->  {t['payload']['token_id']}")

print(f"\nAll 5 QR codes saved to: {OUTPUT_DIR}")
