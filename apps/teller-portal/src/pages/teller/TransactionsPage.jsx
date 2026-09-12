import React, { useState } from 'react';
import { useQueue } from '../../state/QueueContext';
import { formatCurrency, maskCustomerId, formatDateTime } from '../../utils/formatters';
import { Search, Download, CheckCircle2, Clock, AlertTriangle, Layers } from 'lucide-react';

const STATUS_FILTERS = [
  { key: 'COMPLETED', label: 'Completed', icon: CheckCircle2, color: '#059669', bg: '#ECFDF5', activeBg: '#059669', activeText: '#fff' },
  { key: 'PENDING',   label: 'Pending',   icon: Clock,         color: '#D97706', bg: '#FEF3C7', activeBg: '#D97706', activeText: '#fff' },
  { key: 'WAITING',  label: 'Waiting',   icon: Clock,         color: '#3B82F6', bg: '#EFF6FF', activeBg: '#3B82F6', activeText: '#fff' },
  { key: 'FAILED',   label: 'Expired',   icon: AlertTriangle, color: '#EF4444', bg: '#FEF2F2', activeBg: '#EF4444', activeText: '#fff' },
];

export const TransactionsPage = () => {
  const { queueList } = useQueue();
  const [searchTerm, setSearchTerm] = useState('');
  // Default: only COMPLETED is active
  const [activeFilters, setActiveFilters] = useState(new Set(['COMPLETED']));

  const allTxns = queueList.map((q) => ({
    token_id: q.token_id,
    customer_display_name: q.customer_display_name,
    transaction_type: q.transaction_type,
    amount: q.amount,
    status: q.ui_status === 'COMPLETED' ? 'COMPLETED'
          : q.ui_status === 'EXPIRED'   ? 'FAILED'
          : q.ui_status === 'CALLED'    ? 'PENDING'
          : 'WAITING',
    time: formatDateTime(q.issued_at),
    queue_position: q.queue_position
  }));

  const toggleFilter = (key) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        // Always keep at least one filter active
        if (next.size === 1) return prev;
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const showAll = () => setActiveFilters(new Set(['COMPLETED', 'PENDING', 'WAITING', 'FAILED']));

  const filtered = allTxns.filter((t) => {
    const matchesStatus = activeFilters.has(t.status);
    const matchesSearch = !searchTerm ||
      t.customer_display_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.token_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.transaction_type?.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const completedCount = allTxns.filter((t) => t.status === 'COMPLETED').length;
  const pendingCount   = allTxns.filter((t) => t.status === 'PENDING').length;
  const waitingCount   = allTxns.filter((t) => t.status === 'WAITING').length;
  const failedCount    = allTxns.filter((t) => t.status === 'FAILED').length;
  const counts = { COMPLETED: completedCount, PENDING: pendingCount, WAITING: waitingCount, FAILED: failedCount };

  const isAllActive = activeFilters.size === 4;

  return (
    <div className="card">
      <div className="card-title flex items-center justify-between">
        <span>Recent Branch Ledger Transactions</span>
        <button className="btn btn-secondary flex items-center gap-1.5" style={{ fontSize: '0.78rem' }}>
          <Download size={14} />
          <span>Export Ledger</span>
        </button>
      </div>
      <div className="card-subtitle">
        Showing completed transactions by default. Use filters to view other statuses.
      </div>

      {/* Status Filter Pills */}
      <div className="flex items-center gap-2" style={{ marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#64748B', marginRight: '0.25rem' }}>
          Filter by status:
        </span>

        {STATUS_FILTERS.map(({ key, label, icon: Icon, color, bg, activeBg, activeText }) => {
          const isActive = activeFilters.has(key);
          return (
            <button
              key={key}
              onClick={() => toggleFilter(key)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.35rem 0.85rem',
                borderRadius: 20,
                fontSize: '0.78rem',
                fontWeight: 600,
                border: `1.5px solid ${isActive ? activeBg : '#E2E8F0'}`,
                backgroundColor: isActive ? activeBg : '#F8FAFC',
                color: isActive ? activeText : '#64748B',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: isActive ? `0 2px 8px ${color}33` : 'none'
              }}
            >
              <Icon size={13} />
              {label}
              <span style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                padding: '0.05rem 0.38rem',
                borderRadius: 10,
                backgroundColor: isActive ? 'rgba(255,255,255,0.25)' : bg,
                color: isActive ? activeText : color
              }}>
                {counts[key]}
              </span>
            </button>
          );
        })}

        {/* Show All button */}
        <button
          onClick={showAll}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: '0.35rem 0.85rem',
            borderRadius: 20,
            fontSize: '0.78rem',
            fontWeight: 600,
            border: `1.5px solid ${isAllActive ? '#1E4976' : '#E2E8F0'}`,
            backgroundColor: isAllActive ? '#1E4976' : '#F8FAFC',
            color: isAllActive ? '#fff' : '#64748B',
            cursor: 'pointer',
            transition: 'all 0.15s ease'
          }}
        >
          <Layers size={13} />
          All Transactions
          <span style={{
            fontSize: '0.7rem',
            fontWeight: 700,
            padding: '0.05rem 0.38rem',
            borderRadius: 10,
            backgroundColor: isAllActive ? 'rgba(255,255,255,0.2)' : '#EFF6FF',
            color: isAllActive ? '#fff' : '#1E4976'
          }}>
            {allTxns.length}
          </span>
        </button>
      </div>

      {/* Search Row */}
      <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
        <div style={{ position: 'relative', width: 300 }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: 10, color: '#64748B' }} />
          <input
            type="text"
            placeholder="Search transaction ID, customer..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem 0.75rem 0.5rem 2.25rem',
              border: '1px solid #E2E8F0',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem'
            }}
          />
        </div>
        <span style={{ fontSize: '0.82rem', color: '#64748B' }}>
          Showing <strong>{filtered.length}</strong> of <strong>{allTxns.length}</strong> records
        </span>
      </div>

      <div className="table-container">
        <table className="banking-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Transaction ID</th>
              <th>Customer</th>
              <th>Service</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '2.5rem', color: '#64748B' }}>
                  No records matching the active filters.
                </td>
              </tr>
            ) : (
              filtered.map((t, idx) => (
                <tr key={t.token_id + idx}>
                  <td style={{ fontWeight: 700, color: '#94A3B8', fontSize: '0.82rem' }}>
                    #{String(idx + 1).padStart(2, '0')}
                  </td>
                  <td style={{ fontFamily: 'monospace', fontWeight: 600, color: '#12355B' }}>
                    {t.token_id}
                  </td>
                  <td style={{ fontWeight: 600 }}>
                    {maskCustomerId(t.customer_display_name)}
                  </td>
                  <td style={{ textTransform: 'capitalize' }}>
                    {t.transaction_type}
                  </td>
                  <td style={{ fontWeight: 600 }}>
                    {t.amount ? formatCurrency(t.amount) : 'N/A'}
                  </td>
                  <td>
                    <span className={`badge ${
                      t.status === 'COMPLETED' ? 'badge-completed'
                      : t.status === 'FAILED'  ? 'badge-expired'
                      : t.status === 'PENDING' ? 'badge-called'
                      : 'badge-waiting'
                    }`}>
                      {t.status}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.82rem', color: '#64748B' }}>
                    {t.time}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
