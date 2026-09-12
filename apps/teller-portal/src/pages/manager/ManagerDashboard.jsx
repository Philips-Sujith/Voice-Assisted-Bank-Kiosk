import React from 'react';
import { useQueue } from '../../state/QueueContext';
import { useWs } from '../../state/WsContext';
import { formatCurrency, formatTimeOnly } from '../../utils/formatters';
import { Users, CheckCircle2, Clock, ShieldCheck, UserCheck, Activity } from 'lucide-react';

export const ManagerDashboard = () => {
  const { queueList } = useQueue();
  const { status: wsStatus } = useWs();

  const activeQueue = queueList.filter((q) => q.ui_status === 'WAITING');
  const calledQueue = queueList.filter((q) => q.ui_status === 'CALLED');
  const completedQueue = queueList.filter((q) => q.ui_status === 'COMPLETED');
  const expiredQueue = queueList.filter((q) => q.ui_status === 'EXPIRED');

  // Derive teller activity strictly from queue_called events
  const tellerActivityMap = {};
  calledQueue.forEach((q) => {
    if (q.called_teller_id) {
      tellerActivityMap[q.called_teller_id] = {
        teller_id: q.called_teller_id,
        current_customer: q.customer_display_name,
        token_id: q.token_id,
        transaction_type: q.transaction_type,
        status: 'SERVING'
      };
    }
  });

  return (
    <div>
      {/* Overview KPI Header */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.25rem', marginBottom: '1.75rem' }}>
        <div className="card flex items-center justify-between">
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', fontWeight: 600 }}>WAITING IN QUEUE</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#12355B', marginTop: '0.2rem' }}>{activeQueue.length}</div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '50%', backgroundColor: '#EFF6FF', color: '#3B82F6' }}>
            <Users size={22} />
          </div>
        </div>

        <div className="card flex items-center justify-between">
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', fontWeight: 600 }}>CURRENTLY CALLED</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#D97706', marginTop: '0.2rem' }}>{calledQueue.length}</div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '50%', backgroundColor: '#FEF3C7', color: '#F59E0B' }}>
            <Activity size={22} />
          </div>
        </div>

        <div className="card flex items-center justify-between">
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', fontWeight: 600 }}>COMPLETED TRANSACTIONS</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#059669', marginTop: '0.2rem' }}>{completedQueue.length}</div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '50%', backgroundColor: '#ECFDF5', color: '#10B981' }}>
            <CheckCircle2 size={22} />
          </div>
        </div>

        <div className="card flex items-center justify-between">
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', fontWeight: 600 }}>EXPIRED TOKENS</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#EF4444', marginTop: '0.2rem' }}>{expiredQueue.length}</div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '50%', backgroundColor: '#FEF2F2', color: '#EF4444' }}>
            <Clock size={22} />
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.75rem', marginBottom: '1.75rem' }}>
        {/* Real-time Queue Monitor */}
        <div className="card">
          <div className="card-title">Live Queue Overview</div>
          <div className="card-subtitle">Synchronized real-time event stream</div>

          <div className="table-container">
            <table className="banking-table">
              <thead>
                <tr>
                  <th>Pos</th>
                  <th>Customer</th>
                  <th>Type</th>
                  <th>Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {queueList.length === 0 ? (
                  <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748B' }}>No entries in queue</td></tr>
                ) : (
                  queueList.map((entry, idx) => (
                    <tr key={entry.token_id}>
                      <td style={{ fontWeight: 700 }}>#{String(idx + 1).padStart(2, '0')}</td>
                      <td style={{ fontWeight: 600 }}>{entry.customer_display_name}</td>
                      <td style={{ textTransform: 'capitalize' }}>{entry.transaction_type}</td>
                      <td style={{ fontWeight: 600 }}>{formatCurrency(entry.amount)}</td>
                      <td>
                        <span className={`badge ${entry.ui_status === 'COMPLETED' ? 'badge-completed' : entry.ui_status === 'CALLED' ? 'badge-called' : entry.ui_status === 'EXPIRED' ? 'badge-expired' : 'badge-waiting'}`}>
                          {entry.ui_status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Teller Activity Monitor */}
        <div className="card">
          <div className="card-title">Teller Activity Monitor</div>
          <div className="card-subtitle">Derived strictly from queue_called event teller_id field</div>

          <div className="table-container">
            <table className="banking-table">
              <thead>
                <tr>
                  <th>Teller ID</th>
                  <th>Status</th>
                  <th>Current Customer</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(tellerActivityMap).length === 0 ? (
                  <tr>
                    <td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: '#64748B' }}>
                      No active tellers currently serving customers.
                    </td>
                  </tr>
                ) : (
                  Object.values(tellerActivityMap).map((act) => (
                    <tr key={act.teller_id}>
                      <td style={{ fontWeight: 700, color: '#1E4976' }}>{act.teller_id}</td>
                      <td><span className="badge badge-called">SERVING</span></td>
                      <td style={{ fontWeight: 600 }}>{act.current_customer}</td>
                      <td style={{ textTransform: 'capitalize' }}>{act.transaction_type}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
