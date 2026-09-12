import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary caught error]:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div 
          className="card" 
          style={{ 
            padding: '2.5rem 1.5rem', 
            textAlign: 'center', 
            backgroundColor: '#FEF2F2',
            borderColor: '#FCA5A5',
            margin: '1.5rem 0'
          }}
        >
          <div 
            style={{ 
              width: 56, 
              height: 56, 
              borderRadius: '50%', 
              backgroundColor: '#FEE2E2', 
              color: '#DC2626',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.25rem auto'
            }}
          >
            <AlertCircle size={32} />
          </div>

          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#991B1B', marginBottom: '0.5rem' }}>
            Unable to process this QR code. Please scan again.
          </h2>

          <p style={{ fontSize: '0.88rem', color: '#B91C1C', maxWidth: 440, margin: '0 auto 1.5rem auto' }}>
            An unexpected error occurred while processing the verification response. The system state has been preserved safely.
          </p>

          <button 
            className="btn btn-primary"
            style={{ 
              backgroundColor: '#DC2626', 
              borderColor: '#B91C1C',
              padding: '0.65rem 1.5rem',
              margin: '0 auto'
            }}
            onClick={this.handleReset}
          >
            <RefreshCw size={16} />
            <span>Scan Again</span>
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
