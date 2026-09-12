import React from 'react';
import { useQueue } from '../../state/QueueContext';
import { ShieldCheck, Clock, CheckCircle2, Lock, Cpu } from 'lucide-react';

export const AuditLogPage = () => {
  const { auditLogs } = useQueue();

  return (
    <div className="card">
      <div className="card-title flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck size={20} style={{ color: '#10B981' }} />
          <span>Security Audit Trail Log</span>
        </div>
        <span className="badge badge-completed">✓ Immutable Audit Enabled</span>
      </div>
      <div className="card-subtitle">
        Real-time security timeline logging all QR scans, HMAC verification calls, staff authorizations, and receipt prints.
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        {auditLogs.map((log) => (
          <div 
            key={log.id} 
            className="flex items-start gap-4" 
            style={{ 
              backgroundColor: '#F8FAFC', 
              border: '1px solid #E2E8F0', 
              borderRadius: 'var(--radius-sm)', 
              padding: '0.85rem 1.15rem' 
            }}
          >
            <div 
              style={{ 
                minWidth: 90, 
                fontSize: '0.78rem', 
                fontWeight: 700, 
                color: '#1E4976', 
                fontFamily: 'monospace',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
                marginTop: '0.1rem'
              }}
            >
              <Clock size={13} />
              <span>{log.time}</span>
            </div>

            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#17212B' }}>
                {log.event}
              </div>
              <div style={{ fontSize: '0.82rem', color: '#64748B', marginTop: '0.15rem' }}>
                {log.details}
              </div>
            </div>

            <div style={{ fontSize: '0.72rem', color: '#94A3B8', fontWeight: 600 }}>
              ST-042
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
