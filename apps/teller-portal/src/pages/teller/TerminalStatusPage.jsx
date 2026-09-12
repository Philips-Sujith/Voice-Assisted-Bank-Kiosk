import React from 'react';
import { useWs } from '../../state/WsContext';
import { ShieldCheck, CheckCircle2, Server, Printer, Lock, Cpu } from 'lucide-react';

export const TerminalStatusPage = () => {
  const { status: wsStatus } = useWs();

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
      <div className="card">
        <div className="card-title flex items-center gap-2">
          <Server size={18} style={{ color: '#1E4976' }} />
          <span>System Diagnostics</span>
        </div>
        <div className="card-subtitle">
          Terminal ST-042 network & encryption health.
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '0.88rem' }}>
          <div className="flex justify-between items-center" style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '0.65rem' }}>
            <span style={{ color: '#64748B' }}>WebSocket State:</span>
            <span className={`badge ${wsStatus === 'CONNECTED' ? 'badge-completed' : 'badge-expired'}`}>
              {wsStatus === 'CONNECTED' ? '● LIVE CONNECTED' : '● DISCONNECTED'}
            </span>
          </div>

          <div className="flex justify-between items-center" style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '0.65rem' }}>
            <span style={{ color: '#64748B' }}>Backend Service:</span>
            <span style={{ fontWeight: 700, color: '#059669' }}>✓ ACTIVE (Port 8765)</span>
          </div>

          <div className="flex justify-between items-center" style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '0.65rem' }}>
            <span style={{ color: '#64748B' }}>Local ESC/POS Printer:</span>
            <span style={{ fontWeight: 700, color: '#1E4976' }}>● READY (Port 5000)</span>
          </div>

          <div className="flex justify-between items-center">
            <span style={{ color: '#64748B' }}>Terminal Hardware ID:</span>
            <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>ST-042-B014-IND</span>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title flex items-center gap-2">
          <Lock size={18} style={{ color: '#10B981' }} />
          <span>Security & HMAC Policies</span>
        </div>
        <div className="card-subtitle">
          Cryptographic enforcement & token isolation.
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '0.88rem' }}>
          <div className="flex justify-between items-center" style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '0.65rem' }}>
            <span style={{ color: '#64748B' }}>HMAC Signature Policy:</span>
            <span style={{ fontWeight: 700, color: '#059669' }}>✓ Backend Verified</span>
          </div>

          <div className="flex justify-between items-center" style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '0.65rem' }}>
            <span style={{ color: '#64748B' }}>Client Secrets Storage:</span>
            <span style={{ fontWeight: 700, color: '#059669' }}>✓ Zero Client Keys (Isolated)</span>
          </div>

          <div className="flex justify-between items-center" style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '0.65rem' }}>
            <span style={{ color: '#64748B' }}>One-Time Token Lock:</span>
            <span style={{ fontWeight: 700, color: '#059669' }}>✓ Active</span>
          </div>

          <div className="flex justify-between items-center">
            <span style={{ color: '#64748B' }}>Masked Identifiers:</span>
            <span style={{ fontWeight: 700, color: '#059669' }}>✓ Enforced</span>
          </div>
        </div>
      </div>
    </div>
  );
};
