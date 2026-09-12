from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)
CORS(app)

LINE_WIDTH = 42


def _line(char="-"):
    return char * LINE_WIDTH


def _clip(value, width=42):
    text = str(value or "N/A").replace("\n", " ").strip()
    return text if len(text) <= width else text[: width - 1] + "…"


def _kv(label, value):
    label = f"{label}:"
    text = _clip(value)
    available = LINE_WIDTH - len(label) - 1
    if len(text) <= available:
        return f"{label:<15}{text:>{available}}\n"
    # Keep long values readable instead of squeezing characters together.
    return f"{label:<15}\n{text}\n"


def print_via_escpos(data):
    """
    Attempt a physical ESC/POS thermal print.

    Development mode intentionally uses python-escpos Dummy(), which is NOT a
    physical printer. In that mode we return hardware_connected=False so the
    browser can use its one-page print fallback instead of falsely reporting a
    successful hardware print.
    """
    try:
        from escpos.printer import Dummy

        # Keep the existing development-safe Dummy printer. Replace this block
        # with Usb(...) or Network(...) only when real kiosk hardware is wired.
        printer = Dummy()
        printer.set(align="center", font="a", width=1, height=1)
        printer.text(_line("=") + "\n")
        printer.set(bold=True, width=2, height=1)
        printer.text("NEXA BANK\n")
        printer.set(bold=True, width=1, height=1)
        printer.text("TRANSACTION ACKNOWLEDGEMENT\n")
        printer.set(bold=False)
        printer.text("Terminal ST-042 · Staff ST-042\n")
        printer.text(_line("=") + "\n\n")

        printer.set(align="left", font="a", width=1, height=1)
        printer.text(_kv("Token ID", _clip(data.get("token_id"), 30)))
        printer.text(_kv("Customer", data.get("customer_display_name", "N/A")))
        transaction = str(data.get("transaction_type", "N/A")).replace("_", " ").title()
        printer.text(_kv("Transaction", transaction))
        amount = data.get("amount", 0)
        try:
            amount_text = f"INR {int(float(amount)):,}"
        except (TypeError, ValueError):
            amount_text = f"INR {amount}"
        printer.text(_kv("Amount", amount_text))
        printer.text(_kv("Token No.", f"#{data.get('token_number')}" if data.get("token_number") is not None else "N/A"))
        printer.text(_kv("Queue Position", f"#{data.get('queue_position')}" if data.get("queue_position") is not None else "N/A"))
        printer.text(_kv("Status", "COMPLETED"))

        issued = data.get("issued_at")
        if issued:
            try:
                issued_text = datetime.fromisoformat(str(issued).replace("Z", "+00:00")).astimezone().strftime("%d %b %Y, %I:%M %p")
            except ValueError:
                issued_text = str(issued)
        else:
            issued_text = datetime.now().strftime("%d %b %Y, %I:%M %p")
        printer.text(_kv("Issued At", issued_text))

        printer.text("\n" + _line() + "\n")
        printer.set(align="center", bold=True)
        printer.text("TRANSACTION COMPLETED\n")
        printer.set(bold=False)
        printer.text("Thank you for banking with us.\n")
        printer.text(_line() + "\n")
        printer.text("\n\n")

        output_text = printer.output.decode("latin-1", errors="ignore") if hasattr(printer, "output") else ""
        return False, output_text
    except Exception as e:
        logging.warning(f"Physical ESC/POS printer error: {e}")
        return False, str(e)


@app.route('/api/print', methods=['POST'])
def handle_print_receipt():
    try:
        data = request.json or {}
        logging.info("Received receipt print request for customer %s", data.get("customer_display_name"))

        hardware_connected, details = print_via_escpos(data)

        return jsonify({
            "status": "success",
            "hardware_connected": hardware_connected,
            "message": "Receipt prepared by the local print service.",
            "preview_data": details,
        }), 200
    except Exception as e:
        logging.error("Print service failure: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ONLINE", "service": "Nexa Bank ESC/POS Local Print Service"}), 200


if __name__ == "__main__":
    logging.info("Starting Python Local ESC/POS Print Service on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
