import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode';
import { Camera, CameraOff, Upload, RefreshCw, CheckCircle2, ScanLine, Loader2 } from 'lucide-react';
import { robustDecodeQR } from '../../utils/qrDecoder';

export const TokenScanner = ({ onScanSuccess, onScanError, resetTrigger }) => {
  const [isCameraActive, setIsCameraActive] = useState(false);
  // scanPhase: 'STANDBY', 'SCANNING', 'DETECTED', 'ERROR'
  const [scanPhase, setScanPhase] = useState('STANDBY');
  const [errorMessage, setErrorMessage] = useState('');
  const [uploadedFileName, setUploadedFileName] = useState('');
  
  const qrScannerRef = useRef(null);
  const isLockedRef = useRef(false);

  // Unlock and reset scanning lock whenever resetTrigger changes
  useEffect(() => {
    isLockedRef.current = false;
    if (isCameraActive) {
      setScanPhase('SCANNING');
    }
  }, [resetTrigger, isCameraActive]);

  const startScanner = async () => {
    setErrorMessage('');
    isLockedRef.current = false;
    setScanPhase('SCANNING');

    try {
      if (!qrScannerRef.current) {
        qrScannerRef.current = new Html5Qrcode('qr-reader-element', {
          formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
          verbose: false
        });
      }

      // Configuration for high-tolerance scanning:
      // Omit qrbox to enable full camera frame decoding (locates QR anywhere in view)
      const config = {
        fps: 20,
        aspectRatio: 1.0,
        disableFlip: false,
        experimentalFeatures: {
          useBarCodeDetectorIfSupported: true
        }
      };

      // Camera constraints: request crisp resolution and continuous focus where supported
      const cameraConstraints = {
        facingMode: 'environment',
        width: { ideal: 1280, max: 1920 },
        height: { ideal: 720, max: 1080 }
      };

      await qrScannerRef.current.start(
        cameraConstraints,
        config,
        (decodedText) => {
          // DUPLICATE SCAN PROTECTION: Lock scanner immediately on first successful detection
          if (isLockedRef.current) {
            return;
          }
          isLockedRef.current = true;
          setScanPhase('DETECTED');
          console.log('[QR Code Detected]:', decodedText.slice(0, 30));

          if (onScanSuccess) {
            onScanSuccess(decodedText);
          }
        },
        () => {
          // Ignore transient frame decode failures — continuously scan smoothly
        }
      );
      setIsCameraActive(true);
      setScanPhase('SCANNING');
    } catch (err) {
      console.error('[Camera Access Error]:', err);
      setScanPhase('ERROR');
      setIsCameraActive(false);
      setErrorMessage('Camera access unavailable or permission denied. Try uploading a QR image.');
      if (onScanError) onScanError(err);
    }
  };

  const stopScanner = async () => {
    if (qrScannerRef.current && isCameraActive) {
      try {
        await qrScannerRef.current.stop();
        setIsCameraActive(false);
        setScanPhase('STANDBY');
        isLockedRef.current = false;
      } catch (err) {
        console.warn('Error stopping scanner:', err);
      }
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadedFileName(file.name);
    setScanPhase('DETECTED');
    isLockedRef.current = true;

    try {
      const decodedText = await robustDecodeQR(file);

      if (decodedText) {
        console.log('[QR Image Upload Scanned Successfully]:', decodedText.slice(0, 30));
        if (onScanSuccess) {
          onScanSuccess(decodedText);
        }
      } else {
        throw new Error('Unable to decode QR code from the uploaded image.');
      }
    } catch (err) {
      console.error('[QR Image Decode Error]:', err);
      isLockedRef.current = false;
      setScanPhase(isCameraActive ? 'SCANNING' : 'STANDBY');
      alert('Unable to decode this QR code. Please try a clearer image or reposition the QR.');
    } finally {
      e.target.value = '';
    }
  };

  useEffect(() => {
    return () => {
      if (qrScannerRef.current && isCameraActive) {
        qrScannerRef.current.stop().catch(() => {});
      }
    };
  }, [isCameraActive]);

  return (
    <div className="card">
      <div className="card-title flex items-center justify-between">
        <span>Scan Customer QR Token</span>
        <span 
          style={{ 
            fontSize: '0.75rem', 
            fontWeight: 600,
            padding: '0.2rem 0.6rem',
            borderRadius: 12,
            backgroundColor: scanPhase === 'DETECTED' ? '#EFF6FF' : isCameraActive ? '#ECFDF5' : '#F1F5F9',
            color: scanPhase === 'DETECTED' ? '#2563EB' : isCameraActive ? '#059669' : '#64748B'
          }}
        >
          {scanPhase === 'DETECTED' ? '● QR Detected' : isCameraActive ? '● Scanning Active' : scanPhase === 'ERROR' ? '✕ Camera Error' : 'Camera Standby'}
        </span>
      </div>
      
      <div className="card-subtitle">
        {scanPhase === 'DETECTED' 
          ? 'QR detected — verifying security token with backend...' 
          : isCameraActive 
          ? 'Scanning... Position the QR code anywhere inside the camera frame.'
          : 'Position the customer QR token inside the frame or upload an image to verify.'}
      </div>

      <div className="scanner-container">
        <div id="qr-reader-element" style={{ width: '100%', height: '100%' }} />
        <div id="qr-reader-file-temp" style={{ display: 'none' }} />

        {/* Framing & Dynamic Reticle Overlay */}
        {isCameraActive && (
          <div className="scanner-frame-overlay" style={{
            borderColor: scanPhase === 'DETECTED' ? '#10B981' : 'rgba(255, 255, 255, 0.85)',
            transition: 'border-color 0.2s ease'
          }}>
            <div className="corner-bracket corner-tl" style={{ borderColor: scanPhase === 'DETECTED' ? '#10B981' : '#38BDF8' }} />
            <div className="corner-bracket corner-tr" style={{ borderColor: scanPhase === 'DETECTED' ? '#10B981' : '#38BDF8' }} />
            <div className="corner-bracket corner-bl" style={{ borderColor: scanPhase === 'DETECTED' ? '#10B981' : '#38BDF8' }} />
            <div className="corner-bracket corner-br" style={{ borderColor: scanPhase === 'DETECTED' ? '#10B981' : '#38BDF8' }} />
            {scanPhase !== 'DETECTED' && <div className="scan-line" />}
          </div>
        )}

        {/* Live Status Badge overlay inside camera viewport */}
        {isCameraActive && (
          <div 
            style={{
              position: 'absolute',
              bottom: 12,
              backgroundColor: scanPhase === 'DETECTED' ? 'rgba(16, 185, 129, 0.92)' : 'rgba(15, 23, 42, 0.82)',
              color: '#FFFFFF',
              padding: '0.35rem 0.85rem',
              borderRadius: 20,
              fontSize: '0.8rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              zIndex: 15,
              backdropFilter: 'blur(4px)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
            }}
          >
            {scanPhase === 'DETECTED' ? (
              <>
                <CheckCircle2 size={15} style={{ color: '#FFFFFF' }} />
                <span>QR detected — verifying...</span>
              </>
            ) : (
              <>
                <ScanLine size={15} style={{ color: '#38BDF8' }} />
                <span>Scanning...</span>
              </>
            )}
          </div>
        )}

        {!isCameraActive && scanPhase !== 'ERROR' && (
          <div className="flex flex-col items-center gap-3" style={{ color: '#94A3B8' }}>
            <Camera size={48} style={{ opacity: 0.6 }} />
            <p style={{ fontSize: '0.85rem' }}>Position the QR code inside the frame</p>
          </div>
        )}

        {scanPhase === 'ERROR' && (
          <div className="flex flex-col items-center gap-3" style={{ color: '#EF4444', padding: '1.5rem', textAlign: 'center' }}>
            <CameraOff size={44} />
            <p style={{ fontSize: '0.85rem' }}>{errorMessage}</p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between" style={{ marginTop: '1.25rem' }}>
        {!isCameraActive ? (
          <button className="btn btn-primary" onClick={startScanner}>
            <Camera size={16} />
            <span>Start Camera</span>
          </button>
        ) : (
          <button className="btn btn-secondary" onClick={stopScanner}>
            <CameraOff size={16} />
            <span>Stop Camera</span>
          </button>
        )}

        <label className="btn btn-secondary" style={{ cursor: 'pointer' }}>
          <Upload size={16} />
          <span>{uploadedFileName ? `Re-upload (${uploadedFileName.slice(0, 12)}...)` : 'Upload Image'}</span>
          <input type="file" accept="image/*" onChange={handleFileUpload} style={{ display: 'none' }} />
        </label>
      </div>
    </div>
  );
};
