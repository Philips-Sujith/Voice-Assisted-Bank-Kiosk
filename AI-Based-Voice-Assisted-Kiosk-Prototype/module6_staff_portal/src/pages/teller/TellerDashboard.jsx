import React from 'react';
import { useQueue } from '../../state/QueueContext';
import { useWs } from '../../state/WsContext';
import { QueueTable } from '../../components/queue/QueueTable';
import { QueueCalledAlert } from '../../components/queue/QueueCalledAlert';
import { Users, CheckCircle2, Clock, QrCode, Shield } from 'lucide-react';

export const TellerDashboard = ({ onNavigateToVerification }) => {
  const { queueList } = useQueue();
  const { status: wsStatus } = useWs();

  const waitingCount = queueList.filter((q) => q.ui_status === 'WAITING' || q.ui_status === 'CALLED').length;
  const completedCount = queueList.filter((q) => q.ui_status === 'COMPLETED').length;
  const expiredCount = queueList.filter((q) => q.ui_status === 'EXPIRED').length;

  return (
    <div>
      {/* Metric Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.25rem', marginBottom: '1.75rem' }}>
        <div className="card flex items-center justify-between">
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', fontWeight: 600 }}>ACTIVE QUEUE</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#12355B', marginTop: '0.2rem' }}>{waitingCount}</div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '50%', backgroundColor: '#EFF6FF', color: '#3B82F6' }}>
            <Users size={22} />
          </div>
        </div>

        <div className="card flex items-center justify-between">
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', fontWeight: 600 }}>COMPLETED TODAY</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#059669', marginTop: '0.2rem' }}>{completedCount}</div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '50%', backgroundColor: '#ECFDF5', color: '#10B981' }}>
            <CheckCircle2 size={22} />
          </div>
        </div>

        <div className="card flex items-center justify-between">
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', fontWeight: 600 }}>EXPIRED TOKENS</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#EF4444', marginTop: '0.2rem' }}>{expiredCount}</div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '50%', backgroundColor: '#FEF2F2', color: '#EF4444' }}>
            <Clock size={22} />
          </div>
        </div>

        <div className="card flex items-center justify-between">
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', fontWeight: 600 }}>TERMINAL STATUS</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: wsStatus === 'CONNECTED' ? '#059669' : '#EF4444', marginTop: '0.4rem' }}>
              {wsStatus === 'CONNECTED' ? '● ONLINE' : '● OFFLINE'}
            </div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '50%', backgroundColor: '#F8FAFC', color: '#1E4976' }}>
            <Shield size={22} />
          </div>
        </div>
      </div>

      <QueueCalledAlert onProceedToVerification={onNavigateToVerification} />

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-title flex items-center justify-between">
          <span>Active Real-Time Customer Queue</span>
          <button 
            className="btn btn-primary"
            onClick={() => onNavigateToVerification && onNavigateToVerification()}
          >
            <QrCode size={16} />
            <span>Open Verification Terminal</span>
          </button>
        </div>
        <div className="card-subtitle">
          Synchronized live with branch WebSocket Redis Pub/Sub backend.
        </div>

        <QueueTable onSelectTokenForScan={() => onNavigateToVerification && onNavigateToVerification()} />
      </div>
    </div>
  );
};
