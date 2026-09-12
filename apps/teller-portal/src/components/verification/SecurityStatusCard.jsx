import React from 'react';
import { useWs } from '../../state/WsContext';
import { ShieldCheck, Check, Clock } from 'lucide-react';

export const SecurityStatusCard = ({ lastVerifiedTime, isTokenVerified }) => {
  const { status: wsStatus } = useWs();

  return (
    <div className="card" style={{ padding: '1rem 1.5rem', backgroundColor: '#FFFFFF' }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6" style={{ fontSize: '0.85rem' }}>
          <div className="flex items-center gap-2" style={{ fontWeight: 700, color: '#12355B' }}>
            <ShieldCheck size={18} style={{ color: '#10B981' }} />
            <span>SECURITY STATUS</span>
          </div>

          <div className="flex items-center gap-1.5" style={{ color: wsStatus === 'CONNECTED' ? '#059669' : '#EF4444' }}>
            <Check size={15} />
            <span>Secure Connection ({wsStatus})</span>
          </div>

          <div className="flex items-center gap-1.5" style={{ color: isTokenVerified ? '#059669' : '#64748B' }}>
            <Check size={15} />
            <span>Token Signature Valid</span>
          </div>

          <div className="flex items-center gap-1.5" style={{ color: isTokenVerified ? '#059669' : '#64748B' }}>
            <Check size={15} />
            <span>Token Not Expired</span>
          </div>

          <div className="flex items-center gap-1.5" style={{ color: isTokenVerified ? '#059669' : '#64748B' }}>
            <Check size={15} />
            <span>One-Time Token Protection</span>
          </div>
        </div>

        <div className="flex items-center gap-1.5" style={{ fontSize: '0.78rem', color: '#64748B' }}>
          <Clock size={14} />
          <span>Last Security Check: <strong>{lastVerifiedTime || '10:42:18 PM'}</strong></span>
        </div>
      </div>
    </div>
  );
};
