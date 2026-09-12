import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Global connected clients set
CONNECTED_CLIENTS = set()
EVENT_LOOP = None

def get_iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

async def register(websocket):
    CONNECTED_CLIENTS.add(websocket)
    logging.info(f"Client connected. Total clients: {len(CONNECTED_CLIENTS)}")
    try:
        await websocket.wait_closed()
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        logging.info(f"Client disconnected. Total clients: {len(CONNECTED_CLIENTS)}")

async def broadcast_event(event_data):
    if not CONNECTED_CLIENTS:
        logging.info("No active WebSocket clients to broadcast to.")
        return
    message = json.dumps(event_data)
    logging.info(f"Broadcasting event: {event_data.get('event')} (token_id: {event_data.get('token_id')})")
    await asyncio.gather(*[client.send(message) for client in CONNECTED_CLIENTS], return_exceptions=True)

def trigger_broadcast_from_thread(event_data):
    if EVENT_LOOP and EVENT_LOOP.is_running():
        asyncio.run_coroutine_threadsafe(broadcast_event(event_data), EVENT_LOOP)

class DevControlHttpHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data.decode('utf-8'))
            logging.info(f"HTTP trigger received: {payload.get('event')}")
            trigger_broadcast_from_thread(payload)
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "event": payload.get('event')}).encode('utf-8'))
        except Exception as e:
            self.send_response(400)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

def run_http_control_server():
    server_address = ('', 8766)
    httpd = HTTPServer(server_address, DevControlHttpHandler)
    logging.info("Dev HTTP Control Server running on port 8766...")
    httpd.serve_forever()

async def main():
    global EVENT_LOOP
    EVENT_LOOP = asyncio.get_running_loop()
    
    # Start HTTP control server thread for Dev Drawer
    http_thread = threading.Thread(target=run_http_control_server, daemon=True)
    http_thread.start()
    
    async with websockets.serve(register, "0.0.0.0", 8765):
        logging.info("Mock WebSocket Server started on ws://localhost:8765")
        await asyncio.Future() # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("WebSocket Server stopped.")
