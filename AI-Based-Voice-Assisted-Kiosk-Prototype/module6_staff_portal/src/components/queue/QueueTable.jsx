import React from 'react';
import { useQueue } from '../../state/QueueContext';
import { formatCurrency, formatTimeOnly } from '../../utils/formatters';
import { UserCheck, QrCode, ArrowRight } from 'lucide-react';

export const QueueTable = ({ onSelectTokenForScan }) => {
  const { queueList, selectedTokenId, setSelectedTokenId, currentTellerId } = useQueue();

  return (
    <div className="table-container">
      <table className="banking-table">
        <thead>
          <tr>
            <th>Position</th>
            <th>Customer</th>
            <th>Transaction</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Issued At</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {queueList.length === 0 ? (
            <tr>
              <td colSpan={7} style={{ textAlign: 'center', padding: '2.5rem', color: '#64748B' }}>
                No active queue entries. Use Dev Controls or wait for WebSocket incoming customer tokens.
              </td>
            </tr>
          ) : (
            queueList.map((entry, idx) => {
              const isCalled = entry.ui_status === 'CALLED';
              const isMine = entry.called_teller_id === currentTellerId;
              const isSelected = selectedTokenId === entry.token_id;

              let badgeClass = 'badge-waiting';
              if (entry.ui_status === 'CALLED') badgeClass = 'badge-called';
              if (entry.ui_status === 'COMPLETED') badgeClass = 'badge-completed';
              if (entry.ui_status === 'EXPIRED') badgeClass = 'badge-expired';

              return (
                <tr 
                  key={entry.token_id}
                  className={isCalled && isMine ? 'highlight-called' : ''}
                  style={isSelected ? { backgroundColor: '#F0F9FF' } : {}}
                >
                  <td style={{ fontWeight: 700, color: '#12355B' }}>
                    #{String(idx + 1).padStart(2, '0')}
                  </td>
                  <td style={{ fontWeight: 600 }}>
                    {entry.customer_display_name}
                  </td>
                  <td style={{ textTransform: 'capitalize' }}>
                    {entry.transaction_type}
                  </td>
                  <td style={{ fontWeight: 600 }}>
                    {formatCurrency(entry.amount)}
                  </td>
                  <td>
                    <span className={`badge ${badgeClass}`}>
                      {entry.ui_status}
                    </span>
                    {isCalled && (
                      <span style={{ fontSize: '0.72rem', color: '#64748B', marginLeft: '0.4rem' }}>
                        ({entry.called_teller_id || 'unassigned'})
                      </span>
                    )}
                  </td>
                  <td style={{ fontSize: '0.82rem', color: '#64748B' }}>
                    {formatTimeOnly(entry.issued_at)}
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.35rem 0.65rem', fontSize: '0.78rem' }}
                      onClick={() => {
                        setSelectedTokenId(entry.token_id);
                        if (onSelectTokenForScan) onSelectTokenForScan(entry);
                      }}
                    >
                      <QrCode size={14} />
                      <span>Select Token</span>
                    </button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
};
