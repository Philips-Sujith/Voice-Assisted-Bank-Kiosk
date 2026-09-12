import React from 'react';
import { useWs } from '../../state/WsContext';
import { Shield, Building2, User } from 'lucide-react';

export const TopHeader = ({ currentPortal, activeTab }) => {
  const { status: wsStatus } = useWs();

  const getPageMeta = () => {
    if (currentPortal === 'manager') {
      return {
        title: 'Manager Operations & Audit Portal',
        subtitle: 'Real-time branch monitoring, teller oversight & audit log'
      };
    }

    switch (activeTab) {
      case 'verification':
        return {
          title: 'Token Verification',
          subtitle: 'Secure customer QR verification terminal'
        };
      case 'queue':
        return {
          title: 'Teller Queue Operations',
          subtitle: 'Real-time customer queue and transaction verification'
        };
      case 'transactions':
        return {
          title: 'Recent Transactions',
          subtitle: 'Branch ledger & operation records'
        };
      case 'receipts':
        return {
          title: 'Printed Receipts Archive',
          subtitle: 'Historical transaction receipt logs'
        };
      case 'audit':
        return {
          title: 'Security Audit Log',
          subtitle: 'Immutable system event & verification trail'
        };
      case 'security':
        return {
          title: 'Terminal Security Status',
          subtitle: 'Hardware diagnostics, HMAC policy & encryption checks'
        };
      default:
        return {
          title: 'Teller Operations Dashboard',
          subtitle: 'Branch operations summary & active token queue'
        };
    }
  };

  const meta = getPageMeta();

  return (
    <header className="top-header">
      <div className="header-title-area">
        <h1>{meta.title}</h1>
        <p>{meta.subtitle}</p>
      </div>

      <div className="header-status-area">
        <div className="terminal-badge">
          <span className={`status-dot ${wsStatus.toLowerCase()}`} />
          <span style={{ fontWeight: 600 }}>
            {wsStatus === 'CONNECTED' ? '● LIVE' : wsStatus === 'RECONNECTING' ? '● RECONNECTING' : '● OFFLINE'}
          </span>
        </div>

        <div className="flex items-center gap-2" style={{ fontSize: '0.82rem', color: '#64748B' }}>
          <Building2 size={16} />
          <span>Branch 014 · ST-042</span>
        </div>

        <div className="flex items-center gap-2" style={{ fontSize: '0.85rem', fontWeight: 600, color: '#17212B' }}>
          <User size={16} />
          <span>{currentPortal === 'teller' ? 'Arun Kumar' : 'Rajesh Sharma'}</span>
        </div>
      </div>
    </header>
  );
};
