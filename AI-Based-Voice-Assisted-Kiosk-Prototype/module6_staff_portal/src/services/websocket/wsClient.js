/**
 * Real-time WebSocket Client for Nexa Bank Staff & Manager Portals
 * Listens strictly to the fixed 4 backend events:
 * 1. new_queue_entry
 * 2. queue_called
 * 3. transaction_completed
 * 4. token_expired
 */

class WebSocketClient {
  constructor() {
    this.ws = null;
    this.primaryUrl = (typeof window !== 'undefined' && window.__WS_URL__) || 'ws://localhost:8000/ws/dashboard';
    this.fallbackUrl = 'ws://localhost:8765';
    this.url = this.primaryUrl;
    this.status = 'DISCONNECTED'; // CONNECTING, CONNECTED, DISCONNECTED, RECONNECTING
    this.listeners = new Set();
    this.statusListeners = new Set();
    this.reconnectTimer = null;
    this.failCount = 0;
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this._setStatus('CONNECTING');

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[WebSocket] Connected to', this.url);
        this._setStatus('CONNECTED');
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[WebSocket Event Received]', data);
          this._notifyListeners(data);
        } catch (e) {
          console.error('[WebSocket] Failed to parse event JSON:', e);
        }
      };

      this.ws.onerror = (err) => {
        console.warn('[WebSocket Error]', err);
      };

      this.ws.onclose = () => {
        console.log('[WebSocket] Disconnected.');
        this._setStatus('RECONNECTING');
        this._scheduleReconnect();
      };
    } catch (e) {
      console.error('[WebSocket Exception]', e);
      this._setStatus('RECONNECTING');
      this._scheduleReconnect();
    }
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._setStatus('DISCONNECTED');
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      console.log('[WebSocket] Attempting auto-reconnect...');
      this.connect();
    }, 3000);
  }

  _setStatus(newStatus) {
    this.status = newStatus;
    this.statusListeners.forEach((cb) => cb(newStatus));
  }

  onMessage(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  onStatusChange(callback) {
    this.statusListeners.add(callback);
    callback(this.status); // emit current status immediately
    return () => this.statusListeners.delete(callback);
  }

  _notifyListeners(data) {
    this.listeners.forEach((cb) => cb(data));
  }

  // Trigger dev HTTP broadcast (for Dev Toolbar testing)
  async emitDevEvent(eventData) {
    try {
      const res = await fetch('http://localhost:8766', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(eventData)
      });
      return await res.json();
    } catch (e) {
      console.warn('Dev HTTP trigger fallback to direct dispatch:', e);
      // Fallback local notify if HTTP endpoint not active
      this._notifyListeners(eventData);
      return { status: 'local_dispatch' };
    }
  }
}

export const wsClient = new WebSocketClient();
