import React from 'react';
import { useAuth } from '../../state/AuthContext';
import { 
  LayoutDashboard, 
  Users, 
  QrCode, 
  Receipt, 
  History, 
  ShieldCheck, 
  SlidersHorizontal,
  LogOut
} from 'lucide-react';

export const Sidebar = ({ currentPortal, setCurrentPortal, activeTab, setActiveTab }) => {
  const { user, logout } = useAuth();

  return (
    <aside className="sidebar">
      <div>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="logo-badge">NB</div>
            <div>
              <div className="logo-text-title">NEXA BANK</div>
              <div className="logo-text-sub">Secure Staff Portal</div>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">OVERVIEW</div>
          <button 
            className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <LayoutDashboard size={18} />
            <span>Dashboard</span>
          </button>

          <div className="nav-section-label">OPERATIONS</div>
          <button 
            className={`nav-item ${activeTab === 'queue' ? 'active' : ''}`}
            onClick={() => setActiveTab('queue')}
          >
            <Users size={18} />
            <span>Customer Queue</span>
          </button>
          
          <button 
            className={`nav-item ${activeTab === 'verification' ? 'active' : ''}`}
            onClick={() => setActiveTab('verification')}
          >
            <QrCode size={18} />
            <span>Token Verification</span>
          </button>

          <button 
            className={`nav-item ${activeTab === 'transactions' ? 'active' : ''}`}
            onClick={() => setActiveTab('transactions')}
          >
            <Receipt size={18} />
            <span>Transactions</span>
          </button>

          <button 
            className={`nav-item ${activeTab === 'receipts' ? 'active' : ''}`}
            onClick={() => setActiveTab('receipts')}
          >
            <History size={18} />
            <span>Receipts</span>
          </button>

          <div className="nav-section-label">SECURITY</div>
          <button 
            className={`nav-item ${activeTab === 'audit' ? 'active' : ''}`}
            onClick={() => setActiveTab('audit')}
          >
            <ShieldCheck size={18} />
            <span>Audit Log</span>
          </button>
          <button 
            className={`nav-item ${activeTab === 'security' ? 'active' : ''}`}
            onClick={() => setActiveTab('security')}
          >
            <SlidersHorizontal size={18} />
            <span>Terminal Status</span>
          </button>

        </nav>
      </div>

      <div className="sidebar-footer">
        <div className="flex items-center justify-between">
          <div className="staff-profile">
            <div className="staff-avatar">
              {user?.avatar || (currentPortal === 'teller' ? 'AK' : 'RS')}
            </div>
            <div>
              <div className="staff-name">
                {user?.name || (currentPortal === 'teller' ? 'Arun Kumar' : 'Rajesh Sharma')}
              </div>
              <div className="staff-role">
                {user?.role || (currentPortal === 'teller' ? 'Teller · ST-042' : 'Branch Manager · B-014')}
              </div>
            </div>
          </div>

          <button 
            onClick={logout}
            title="Log Out Terminal"
            style={{ color: '#94A3B8', padding: '0.4rem', borderRadius: '4px' }}
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </aside>
  );
};
