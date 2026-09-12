import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './state/AuthContext';
import { WsProvider } from './state/WsContext';
import { QueueProvider } from './state/QueueContext';
import { Sidebar } from './components/layout/Sidebar';
import { TopHeader } from './components/layout/TopHeader';
import { DevControlDrawer } from './components/layout/DevControlDrawer';
import { ErrorBoundary } from './components/common/ErrorBoundary';

import { LoginPage } from './pages/LoginPage';
import { TellerDashboard } from './pages/teller/TellerDashboard';
import { QueuePage } from './pages/teller/QueuePage';
import { VerificationPage } from './pages/teller/VerificationPage';
import { TransactionsPage } from './pages/teller/TransactionsPage';
import { ReceiptsPage } from './pages/teller/ReceiptsPage';
import { AuditLogPage } from './pages/teller/AuditLogPage';
import { TerminalStatusPage } from './pages/teller/TerminalStatusPage';

import { ManagerDashboard } from './pages/manager/ManagerDashboard';

import './styles/global.css';
import './styles/layout.css';
import './styles/components.css';
import './styles/print.css';

export function AppContent() {
  const { user, isAuthenticated } = useAuth();
  const [currentPortal, setCurrentPortal] = useState('teller'); // 'teller' or 'manager'
  const [activeTab, setActiveTab] = useState('verification');
  const [simulatedQrPayload, setSimulatedQrPayload] = useState(null);

  useEffect(() => {
    if (user && user.portal) {
      setCurrentPortal(user.portal);
      if (user.portal === 'manager') {
        setActiveTab('dashboard');
      } else {
        setActiveTab('verification');
      }
    }
  }, [user]);

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const handleSimulateQrScan = (payloadStr) => {
    setCurrentPortal('teller');
    setActiveTab('verification');
    setSimulatedQrPayload(payloadStr);
  };

  const renderActivePage = () => {
    switch (activeTab) {
      case 'dashboard':
        return currentPortal === 'manager' 
          ? <ManagerDashboard /> 
          : <TellerDashboard onNavigateToVerification={() => setActiveTab('verification')} />;
      case 'queue':
        return <QueuePage onNavigateToVerification={() => setActiveTab('verification')} />;
      case 'verification':
        return (
          <VerificationPage 
            simulatedQrPayload={simulatedQrPayload} 
            onClearSimulatedPayload={() => setSimulatedQrPayload(null)} 
          />
        );
      case 'transactions':
        return <TransactionsPage />;
      case 'receipts':
        return <ReceiptsPage />;
      case 'audit':
        return <AuditLogPage />;
      case 'security':
        return <TerminalStatusPage />;
      default:
        return currentPortal === 'manager' ? <ManagerDashboard /> : <VerificationPage />;
    }
  };

  return (
    <ErrorBoundary>
      <div className="app-container">
        <Sidebar 
          currentPortal={currentPortal}
          setCurrentPortal={setCurrentPortal}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />

        <div className="main-wrapper">
          <TopHeader 
            currentPortal={currentPortal}
            activeTab={activeTab}
          />

          <main className="page-content">
            {renderActivePage()}
          </main>
        </div>

        <DevControlDrawer onSimulateQrScan={handleSimulateQrScan} />
      </div>
    </ErrorBoundary>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <WsProvider>
          <QueueProvider>
            <AppContent />
          </QueueProvider>
        </WsProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
}
