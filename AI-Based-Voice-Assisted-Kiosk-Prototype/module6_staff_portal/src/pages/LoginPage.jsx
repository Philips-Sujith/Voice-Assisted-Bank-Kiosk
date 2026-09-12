import React, { useState } from 'react';
import { useAuth, PRESET_ACCOUNTS } from '../state/AuthContext';
import { ShieldCheck, Lock, User, KeyRound, AlertCircle, ArrowRight, Building2 } from 'lucide-react';

export const LoginPage = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    setErrorMsg('');
    const res = login(username, password);
    if (!res.success) {
      setErrorMsg(res.message);
    }
  };

  const fillPreset = (account) => {
    setUsername(account.staff_id);
    setPassword(account.password);
    login(account.staff_id, account.password);
  };

  return (
    <div 
      style={{ 
        minHeight: '100vh', 
        width: '100vw', 
        backgroundColor: '#0F172A', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        padding: '1.5rem',
        backgroundImage: 'radial-gradient(circle at 50% 30%, #1E3A8A 0%, #0F172A 70%)'
      }}
    >
      <div 
        style={{ 
          width: '100%', 
          maxWidth: 440, 
          backgroundColor: '#FFFFFF', 
          borderRadius: 'var(--radius-lg)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden'
        }}
      >
        {/* Header */}
        <div 
          style={{ 
            backgroundColor: '#12355B', 
            color: '#FFFFFF', 
            padding: '2rem 1.75rem',
            textAlign: 'center',
            borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
          }}
        >
          <div 
            style={{ 
              width: 50, 
              height: 50, 
              borderRadius: 'var(--radius-md)', 
              background: 'linear-gradient(135deg, #1E4976, #0A223D)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 0.85rem auto',
              fontWeight: 800,
              fontSize: '1.4rem'
            }}
          >
            NB
          </div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: 0.5 }}>NEXA BANK</h1>
          <p style={{ fontSize: '0.8rem', color: '#94A3B8', marginTop: '0.2rem' }}>
            Secure Internal Operations Kiosk · Terminal ST-042
          </p>
        </div>

        {/* Body Form */}
        <div style={{ padding: '1.75rem' }}>
          {errorMsg && (
            <div 
              style={{ 
                backgroundColor: '#FEF2F2', 
                border: '1px solid #FCA5A5', 
                borderRadius: 'var(--radius-sm)', 
                padding: '0.75rem', 
                marginBottom: '1.25rem',
                fontSize: '0.82rem',
                color: '#991B1B',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              <AlertCircle size={16} />
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#475569', marginBottom: '0.35rem' }}>
                Staff ID / Username
              </label>
              <div style={{ position: 'relative' }}>
                <User size={16} style={{ position: 'absolute', left: 12, top: 12, color: '#64748B' }} />
                <input 
                  type="text"
                  required
                  placeholder="e.g. teller or manager"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  style={{ 
                    width: '100%', 
                    padding: '0.65rem 0.75rem 0.65rem 2.35rem', 
                    border: '1px solid #CBD5E1', 
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.9rem'
                  }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#475569', marginBottom: '0.35rem' }}>
                Security Password
              </label>
              <div style={{ position: 'relative' }}>
                <KeyRound size={16} style={{ position: 'absolute', left: 12, top: 12, color: '#64748B' }} />
                <input 
                  type="password"
                  required
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={{ 
                    width: '100%', 
                    padding: '0.65rem 0.75rem 0.65rem 2.35rem', 
                    border: '1px solid #CBD5E1', 
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.9rem'
                  }}
                />
              </div>
            </div>

            <button 
              type="submit" 
              className="btn btn-primary" 
              style={{ width: '100%', padding: '0.75rem', marginTop: '0.5rem', justifyContent: 'center' }}
            >
              <span>Authenticate & Login</span>
              <ArrowRight size={16} />
            </button>
          </form>

          {/* Quick Fill Preset Credentials Box */}
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid #E2E8F0', paddingTop: '1.25rem' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', marginBottom: '0.65rem', textAlign: 'center' }}>
              SIH Evaluation Demo Login Presets
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem' }}>
              {PRESET_ACCOUNTS.map((acc) => (
                <button
                  key={acc.staff_id}
                  className="btn btn-secondary"
                  style={{ 
                    padding: '0.6rem', 
                    flexDirection: 'column', 
                    alignItems: 'flex-start',
                    gap: '0.2rem',
                    textAlign: 'left',
                    backgroundColor: '#F8FAFC'
                  }}
                  onClick={() => fillPreset(acc)}
                >
                  <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#12355B' }}>
                    {acc.portal === 'teller' ? '👤 Bank Teller' : '👔 Branch Manager'}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#64748B' }}>
                    ID: <strong>{acc.staff_id}</strong>
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#94A3B8' }}>
                    Pass: <strong>Password@123</strong>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer Security Notice */}
        <div style={{ backgroundColor: '#F8FAFC', padding: '0.85rem 1.5rem', borderTop: '1px solid #E2E8F0', textAlign: 'center', fontSize: '0.72rem', color: '#64748B' }}>
          🔒 Authorized Nexa Bank Staff Only · All Access Sessions Audited
        </div>
      </div>
    </div>
  );
};
