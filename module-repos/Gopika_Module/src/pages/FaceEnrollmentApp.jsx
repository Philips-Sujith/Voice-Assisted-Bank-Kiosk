import React, { useState, useRef, useEffect, useCallback } from 'react'
import '../styles/FaceEnrollment.css'

const BACKEND_URL = 'http://127.0.0.1:8000'

const STEP_INSTRUCTIONS = [
  'Sample 1 of 4: Look directly at the camera (Frontal)',
  'Sample 2 of 4: Turn your head slightly to the left',
  'Sample 3 of 4: Turn your head slightly to the right',
  'Sample 4 of 4: Maintain a relaxed natural expression',
]

export default function FaceEnrollmentApp() {
  // Navigation step: 'upload' | 'verifying' | 'verified' | 'capture' | 'submitting' | 'success'
  const [currentStep, setCurrentStep] = useState('upload')

  // Passbook upload state
  const [selectedFile, setSelectedFile] = useState(null)
  const [filePreview, setFilePreview] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  const [alreadyEnrolledMsg, setAlreadyEnrolledMsg] = useState(null)
  const [demoFixtures, setDemoFixtures] = useState([])
  const [selectedFixtureName, setSelectedFixtureName] = useState(null)

  // Verified session info from backend
  const [verifiedSession, setVerifiedSession] = useState(null)
  const [sessionTimeRemaining, setSessionTimeRemaining] = useState(900)

  // Camera & Video state
  const [cameraActive, setCameraActive] = useState(false)
  const [cameraError, setCameraError] = useState(null)
  const [cameraDiagnostics, setCameraDiagnostics] = useState({ resolution: '---', readyState: 0 })
  const [isVideoReady, setIsVideoReady] = useState(false)

  // Continuous Face Detection state
  const [isFaceDetected, setIsFaceDetected] = useState(false)
  const [faceStatusMessage, setFaceStatusMessage] = useState('Initializing face detector...')
  const [isDetecting, setIsDetecting] = useState(false)

  // 4 Face Samples state
  const [samples, setSamples] = useState([])
  const [enrollError, setEnrollError] = useState(null)

  const videoRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const timerIntervalRef = useRef(null)
  const detectionIntervalRef = useRef(null)
  const lastValidFrameRef = useRef(null)
  const isDetectingRef = useRef(false)

  const [resettingDemo, setResettingDemo] = useState(false)

  // Load available demo fixtures from backend on mount
  useEffect(() => {
    fetch(`${BACKEND_URL}/api/v1/face-enrollment/demo-fixtures`)
      .then((r) => r.json())
      .then((data) => {
        if (data.fixtures && Array.isArray(data.fixtures)) {
          // Varied display order on load; mapping remains 100% deterministic
          const randomized = [...data.fixtures].sort(() => Math.random() - 0.5)
          setDemoFixtures(randomized)
        }
      })
      .catch((err) => console.warn('[FIXTURES] Could not load demo fixtures manifest:', err))
  }, [])

  const handleShuffleFixtures = () => {
    setDemoFixtures((prev) => [...prev].sort(() => Math.random() - 0.5))
  }

  const handleResetDemoEnrollments = async () => {
    setResettingDemo(true)
    try {
      const resp = await fetch(`${BACKEND_URL}/api/v1/face-enrollment/reset-demo-enrollments`, {
        method: 'POST',
      })
      if (resp.ok) {
        setAlreadyEnrolledMsg(null)
        setUploadError(null)
      }
    } catch (err) {
      console.warn('[RESET] Error resetting demo enrollments:', err)
    } finally {
      setResettingDemo(false)
    }
  }

  // Clean up media stream and timers on unmount
  useEffect(() => {
    return () => {
      stopCamera()
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)
      if (detectionIntervalRef.current) clearInterval(detectionIntervalRef.current)
    }
  }, [])

  // Manage Session Expiration Countdown
  useEffect(() => {
    if (verifiedSession && verifiedSession.expires_at) {
      const expDate = new Date(verifiedSession.expires_at).getTime()
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)

      timerIntervalRef.current = setInterval(() => {
        const now = Date.now()
        const diffSecs = Math.max(0, Math.floor((expDate - now) / 1000))
        setSessionTimeRemaining(diffSecs)
        if (diffSecs <= 0) {
          clearInterval(timerIntervalRef.current)
          setEnrollError('Your verification session has expired. Please verify your passbook again.')
        }
      }, 1000)
    }
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)
    }
  }, [verifiedSession])

  // ── 1-Click Demo Fixture Loader ─────────────────────────────────────────────
  const handleSelectDemoFixture = async (fixture) => {
    setSelectedFixtureName(fixture.file)
    setUploadError(null)
    setAlreadyEnrolledMsg(null)
    try {
      const resp = await fetch(`${BACKEND_URL}/api/v1/face-enrollment/demo-fixture/${fixture.file}`)
      if (!resp.ok) throw new Error('Could not fetch demo fixture')
      const blob = await resp.blob()
      const file = new File([blob], fixture.file, { type: 'image/png' })
      setSelectedFile(file)
      setFilePreview(URL.createObjectURL(blob))
    } catch (err) {
      console.warn('[FIXTURE] Error loading fixture:', err)
      setUploadError('Could not load test fixture image.')
    }
  }

  // ── Standard File Selection ─────────────────────────────────────────────────
  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setSelectedFixtureName(null)
    processSelectedFile(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (!file) return
    setSelectedFixtureName(null)
    processSelectedFile(file)
  }

  const processSelectedFile = (file) => {
    setUploadError(null)
    setAlreadyEnrolledMsg(null)

    if (file.size > 10 * 1024 * 1024) {
      setUploadError('File size exceeds maximum limit of 10 MB.')
      return
    }

    const ext = file.name.split('.').pop().toLowerCase()
    if (!['jpg', 'jpeg', 'png', 'pdf'].includes(ext)) {
      setUploadError('Unsupported format. Please upload JPG, PNG, or PDF.')
      return
    }

    setSelectedFile(file)
    if (file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (ev) => setFilePreview(ev.target.result)
      reader.readAsDataURL(file)
    } else {
      setFilePreview(null)
    }
  }

  const handleRemoveFile = () => {
    setSelectedFile(null)
    setFilePreview(null)
    setSelectedFixtureName(null)
    setUploadError(null)
    setAlreadyEnrolledMsg(null)
  }

  // ── Passbook Verification API Call ──────────────────────────────────────────
  const handleVerifyPassbook = async () => {
    if (!selectedFile) return
    setCurrentStep('verifying')
    setUploadError(null)
    setAlreadyEnrolledMsg(null)

    try {
      const formData = new FormData()
      formData.append('passbook', selectedFile)

      const resp = await fetch(`${BACKEND_URL}/api/v1/face-enrollment/verify-passbook`, {
        method: 'POST',
        body: formData,
      })

      const data = await resp.json()

      if (!resp.ok) {
        throw new Error(data.detail || 'Passbook verification failed.')
      }

      if (data.status === 'already_enrolled') {
        setAlreadyEnrolledMsg(data.message || 'Face already registered for this account.')
        setCurrentStep('upload')
        return
      }

      if (data.verified && data.enrollment_session_id) {
        setVerifiedSession(data)
        setCurrentStep('verified')
      } else {
        setUploadError(data.message || 'Passbook verification failed. Please upload a clear image containing account details.')
        setCurrentStep('upload')
      }
    } catch (err) {
      console.error('[PASSBOOK VERIFY] Error:', err)
      setUploadError(err.message || 'Passbook verification failed. Please try again.')
      setCurrentStep('upload')
    }
  }

  // ── Camera Initialization & Readiness ───────────────────────────────────────
  const startCamera = async () => {
    setCameraError(null)
    setIsVideoReady(false)
    setIsFaceDetected(false)
    setFaceStatusMessage('Starting camera...')

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraError('Camera access API is not supported in this browser. Please use Chrome, Edge, or Firefox.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: 'user',
        },
        audio: false,
      })

      mediaStreamRef.current = stream

      if (videoRef.current) {
        const video = videoRef.current
        video.srcObject = stream

        video.onloadedmetadata = () => {
          video
            .play()
            .then(() => {
              const res = `${video.videoWidth}x${video.videoHeight}`
              console.log(`[CAMERA DIAGNOSTICS] Stream live. Resolution: ${res}, readyState: ${video.readyState}`)
              setCameraDiagnostics({ resolution: res, readyState: video.readyState })
              setIsVideoReady(true)
              setCameraActive(true)
              setFaceStatusMessage('Position your face inside the oval')
            })
            .catch((playErr) => {
              console.warn('[CAMERA] Video play error:', playErr)
              setCameraError('Camera video stream could not be played. Please check browser permissions.')
            })
        }
      }
    } catch (err) {
      console.error('[CAMERA ERROR]', err)
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setCameraError('Camera permission denied. Please allow camera access in your browser address bar.')
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setCameraError('No webcam detected. Please connect a camera.')
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        setCameraError('Camera is already in use by another application.')
      } else {
        setCameraError(`Camera could not be started: ${err.message || 'Unknown error'}`)
      }
    }
  }

  const stopCamera = () => {
    if (detectionIntervalRef.current) {
      clearInterval(detectionIntervalRef.current)
      detectionIntervalRef.current = null
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop())
      mediaStreamRef.current = null
    }
    setCameraActive(false)
    setIsVideoReady(false)
  }

  const handleContinueToCapture = () => {
    setCurrentStep('capture')
    setSamples([])
    setEnrollError(null)
    setIsFaceDetected(false)
    lastValidFrameRef.current = null
    // Mount camera after state transition
    setTimeout(() => {
      startCamera()
    }, 100)
  }

  // ── Frame Grabber (Native Coordinates, No Mirror Distortion) ─────────────────
  const grabVideoFrameB64 = useCallback(() => {
    const video = videoRef.current
    if (!video || video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) {
      return null
    }
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    // Draw original camera pixels without CSS transforms
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', 0.82)
  }, [])

  // ── Real-Time Continuous Face Detection Loop ────────────────────────────────
  useEffect(() => {
    if (currentStep !== 'capture' || !isVideoReady || samples.length >= 4) {
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current)
        detectionIntervalRef.current = null
      }
      return
    }

    const runDetectionTick = async () => {
      if (isDetectingRef.current) return
      const frameB64 = grabVideoFrameB64()
      if (!frameB64) return

      isDetectingRef.current = true
      setIsDetecting(true)

      try {
        const resp = await fetch(`${BACKEND_URL}/api/v1/face-enrollment/detect-face`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image_b64: frameB64 }),
        })
        const data = await resp.json()

        if (data.face_detected) {
          setIsFaceDetected(true)
          setFaceStatusMessage('Face detected ✓')
          lastValidFrameRef.current = frameB64
        } else {
          setIsFaceDetected(false)
          const r = data.reason ? data.reason.toLowerCase() : ''
          if (r.includes('offline') || r.includes('connect') || r.includes('service') || r.includes('init')) {
            setFaceStatusMessage('Face detector service initializing...')
          } else if (r.includes('multiple') || r.includes('more than one')) {
            setFaceStatusMessage('Only one face should be visible')
          } else if (r.includes('small') || r.includes('closer')) {
            setFaceStatusMessage('Move slightly closer to the camera')
          } else if (r.includes('center') || r.includes('off-center')) {
            setFaceStatusMessage('Center your face inside the oval')
          } else if (r.includes('no face')) {
            setFaceStatusMessage('Position your face inside the oval')
          } else {
            setFaceStatusMessage(data.reason || 'Position your face inside the oval')
          }
        }
      } catch (err) {
        console.warn('[DETECT TICK ERROR]', err)
      } finally {
        isDetectingRef.current = false
        setIsDetecting(false)
      }
    }

    // Run continuous detection every 350ms
    detectionIntervalRef.current = setInterval(runDetectionTick, 350)
    // Run immediate first tick
    runDetectionTick()

    return () => {
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current)
        detectionIntervalRef.current = null
      }
    }
  }, [currentStep, isVideoReady, samples.length, grabVideoFrameB64])

  // ── Sample Capture Action ───────────────────────────────────────────────────
  const handleCaptureSample = () => {
    if (samples.length >= 4) return
    const frame = lastValidFrameRef.current || grabVideoFrameB64()
    if (!frame) {
      setFaceStatusMessage('Camera not ready. Please ensure your face is visible.')
      return
    }

    const updated = [...samples, frame]
    setSamples(updated)

    if (updated.length < 4) {
      // Temporarily flash confirmation
      setFaceStatusMessage(`✓ Sample ${updated.length} captured!`)
      lastValidFrameRef.current = null
    } else {
      setFaceStatusMessage('All 4 samples captured! Ready to register.')
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current)
        detectionIntervalRef.current = null
      }
    }
  }

  const handleRetakeAll = () => {
    setSamples([])
    setEnrollError(null)
    setIsFaceDetected(false)
    lastValidFrameRef.current = null
    setFaceStatusMessage('Position your face inside the oval')
  }

  // ── Final Face Registration ─────────────────────────────────────────────────
  const handleSubmitEnrollment = async () => {
    if (samples.length !== 4) {
      setEnrollError('Please capture all 4 face samples before registering.')
      return
    }

    if (!verifiedSession || !verifiedSession.enrollment_session_id) {
      setEnrollError('Missing verified session. Please verify your passbook again.')
      return
    }

    if (sessionTimeRemaining <= 0) {
      setEnrollError('Your verification session has expired. Please verify your passbook again.')
      return
    }

    setCurrentStep('submitting')
    setEnrollError(null)

    try {
      const resp = await fetch(`${BACKEND_URL}/api/v1/face-enrollment/register-samples`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enrollment_session_id: verifiedSession.enrollment_session_id,
          samples_b64: samples,
        }),
      })

      const data = await resp.json()

      if (!resp.ok) {
        throw new Error(data.detail || 'Face registration failed.')
      }

      stopCamera()
      setCurrentStep('success')
    } catch (err) {
      console.error('[FACE REGISTER] Error:', err)
      setEnrollError(err.message || 'Face registration failed. Please try again.')
      setCurrentStep('capture')
    }
  }

  const handleBackToKiosk = () => {
    stopCamera()
    window.location.href = '/'
  }

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m}:${s < 10 ? '0' : ''}${s}`
  }

  return (
    <div className="face-enroll-shell">
      {/* Header */}
      <header className="face-enroll-header">
        <div className="face-enroll-header__brand">
          <div className="face-enroll-header__logo-icon">AI</div>
          <div>
            <div className="face-enroll-header__title">AI SMART BANKING</div>
            <span className="face-enroll-header__badge">Secure Face Enrollment</span>
          </div>
        </div>

        <button className="face-enroll-header__back-btn" onClick={handleBackToKiosk}>
          <span>&larr;</span> Return to Kiosk
        </button>
      </header>

      {/* Progress Stepper */}
      <div className="face-enroll-stepper">
        <div className={`stepper-node ${['upload', 'verifying'].includes(currentStep) ? 'active' : 'completed'}`}>
          <div className="stepper-num">1</div>
          <span className="stepper-label">Passbook</span>
        </div>
        <div className={`stepper-line ${!['upload', 'verifying'].includes(currentStep) ? 'completed' : ''}`} />

        <div className={`stepper-node ${currentStep === 'verified' ? 'active' : !['upload', 'verifying'].includes(currentStep) ? 'completed' : ''}`}>
          <div className="stepper-num">2</div>
          <span className="stepper-label">Verified</span>
        </div>
        <div className={`stepper-line ${['capture', 'submitting', 'success'].includes(currentStep) ? 'completed' : ''}`} />

        <div className={`stepper-node ${['capture', 'submitting'].includes(currentStep) ? 'active' : currentStep === 'success' ? 'completed' : ''}`}>
          <div className="stepper-num">3</div>
          <span className="stepper-label">Face Capture</span>
        </div>
        <div className={`stepper-line ${currentStep === 'success' ? 'completed' : ''}`} />

        <div className={`stepper-node ${currentStep === 'success' ? 'active completed' : ''}`}>
          <div className="stepper-num">4</div>
          <span className="stepper-label">Enrolled</span>
        </div>
      </div>

      {/* Main Container Card */}
      <main className="face-enroll-main">
        <div className="enroll-card">

          {/* ─────────────────────────────────────────────────────────────────
              SCREEN 1: PASSBOOK UPLOAD & DEMO FIXTURES
             ───────────────────────────────────────────────────────────────── */}
          {currentStep === 'upload' && (
            <div>
              <h1 className="enroll-card__title">Secure Face Enrollment</h1>
              <p className="enroll-card__subtitle">
                Verify your bank account with your passbook before registering your face.
              </p>

              {alreadyEnrolledMsg && (
                <div className="enroll-alert warning">
                  <span style={{ fontSize: '1.2rem' }}>⚠️</span>
                  <div style={{ flex: 1 }}>
                    <strong>Face Already Registered</strong>
                    <p style={{ marginTop: '2px', marginBottom: '8px' }}>{alreadyEnrolledMsg}</p>
                    <button
                      type="button"
                      className="btn-reset-demo"
                      onClick={handleResetDemoEnrollments}
                      disabled={resettingDemo}
                      style={{
                        background: '#dc2626',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '6px',
                        padding: '6px 14px',
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      {resettingDemo ? 'Resetting...' : '🔄 Reset Demo Face Enrollments'}
                    </button>
                  </div>
                </div>
              )}

              {uploadError && (
                <div className="enroll-alert error">
                  <span style={{ fontSize: '1.2rem' }}>✕</span>
                  <div>
                    <strong>Passbook verification failed</strong>
                    <p style={{ marginTop: '2px' }}>{uploadError}</p>
                  </div>
                </div>
              )}

              {/* Upload Dropzone */}
              {!selectedFile ? (
                <>
                  <div
                    className="upload-dropzone"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={handleDrop}
                  >
                    <div className="upload-dropzone__icon">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" y1="3" x2="12" y2="15" />
                      </svg>
                    </div>
                    <div className="upload-dropzone__text-main">Click or drag passbook image here</div>
                    <div className="upload-dropzone__text-sub">Accepted formats: JPG, PNG, PDF (Max 10 MB)</div>
                    <input
                      type="file"
                      accept=".jpg,.jpeg,.png,.pdf"
                      onChange={handleFileChange}
                      id="passbook-input"
                    />
                  </div>

                  {/* 1-Click Demo Test Fixtures */}
                  {demoFixtures.length > 0 && (
                    <div className="demo-fixtures-section">
                      <div className="demo-fixtures-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <span>Authorized Demo Passbooks (10 Fictional Accounts)</span>
                          <span style={{ color: '#71829f', fontWeight: 400, marginLeft: '8px', fontSize: '0.72rem' }}>
                            ({demoFixtures.length} Profiles Available)
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={handleShuffleFixtures}
                          style={{
                            background: 'transparent',
                            border: '1px solid #334155',
                            color: '#94a3b8',
                            borderRadius: '4px',
                            padding: '3px 8px',
                            fontSize: '0.75rem',
                            cursor: 'pointer'
                          }}
                          title="Shuffle displayed selection order"
                        >
                          🔀 Shuffle Order
                        </button>
                      </div>
                      <div className="demo-fixtures-grid">
                        {demoFixtures.map((fix) => (
                          <button
                            key={fix.file}
                            type="button"
                            className={`btn-demo-fixture ${selectedFixtureName === fix.file ? 'active' : ''}`}
                            onClick={() => handleSelectDemoFixture(fix)}
                            title={`${fix.bank_name || 'Bank'} • ${fix.account_number}`}
                          >
                            <span style={{ fontWeight: 600 }}>📄 {fix.customer_name || fix.file}</span>
                            <span style={{ fontSize: '0.70rem', color: '#94a3b8', marginTop: '1px' }}>
                              {fix.bank_name || 'Demo Bank'}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div>
                  <div className="upload-preview-card">
                    <div className="upload-preview-left">
                      {filePreview ? (
                        <img src={filePreview} alt="Passbook Preview" className="upload-preview-thumb" />
                      ) : (
                        <div className="upload-preview-thumb" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#1e293b' }}>
                          📄
                        </div>
                      )}
                      <div className="upload-preview-info">
                        <h4>{selectedFile.name}</h4>
                        <p>{(selectedFile.size / 1024).toFixed(1)} KB &bull; Passbook Document</p>
                      </div>
                    </div>
                    <button className="upload-preview-remove" onClick={handleRemoveFile}>
                      Remove
                    </button>
                  </div>

                  <button className="btn-primary-glow" onClick={handleVerifyPassbook}>
                    <span>Verify Passbook Account</span> &rarr;
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ─────────────────────────────────────────────────────────────────
              SCANNING / VERIFYING ANIMATION
             ───────────────────────────────────────────────────────────────── */}
          {currentStep === 'verifying' && (
            <div className="radar-scan-box">
              <div className="radar-spinner" />
              <h3 style={{ color: '#fff', marginBottom: '6px' }}>Verifying Passbook</h3>
              <p style={{ color: '#a3b2d1', fontSize: '0.85rem', textAlign: 'center' }}>
                Validating account details against bank customer records...
              </p>
            </div>
          )}

          {/* ─────────────────────────────────────────────────────────────────
              SCREEN 2: IDENTITY VERIFIED
             ───────────────────────────────────────────────────────────────── */}
          {currentStep === 'verified' && verifiedSession && (
            <div>
              <div className="verified-badge-container">
                <div className="verified-icon-ring">✓</div>
                <h2 style={{ color: '#ffffff', fontSize: '1.35rem', fontWeight: 700 }}>Identity Verified</h2>
                <span className="session-countdown-pill">
                  ⏱ Session valid: {formatTime(sessionTimeRemaining)}
                </span>
              </div>

              <div className="verified-card">
                <div className="verified-row">
                  <span className="verified-label">Customer Name</span>
                  <span className="verified-value highlight">{verifiedSession.customer_name}</span>
                </div>
                <div className="verified-row">
                  <span className="verified-label">Account Number</span>
                  <span className="verified-value">{verifiedSession.account_number_masked}</span>
                </div>
                <div className="verified-row">
                  <span className="verified-label">Verification Status</span>
                  <span className="verified-value" style={{ color: '#10b981' }}>
                    {verifiedSession.is_demo_fixture ? 'Demo Account Verified ✓' : 'Core Bank Match Verified ✓'}
                  </span>
                </div>
              </div>

              <p style={{ color: '#a3b2d1', fontSize: '0.88rem', textAlign: 'center', marginBottom: '1.25rem' }}>
                Your account has been successfully verified. You can now securely register your face biometrics.
              </p>

              <button className="btn-primary-glow" onClick={handleContinueToCapture}>
                <span>Continue to Face Enrollment</span> &rarr;
              </button>
            </div>
          )}

          {/* ─────────────────────────────────────────────────────────────────
              SCREEN 3: CAMERA CAPTURE (CONTINUOUS DETECTION + 4 SAMPLES)
             ───────────────────────────────────────────────────────────────── */}
          {['capture', 'submitting'].includes(currentStep) && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <h2 style={{ color: '#fff', fontSize: '1.15rem', margin: 0 }}>
                  Face Enrollment — Step {samples.length < 4 ? samples.length + 1 : 4} of 4
                </h2>
                <span className="session-countdown-pill" style={{ margin: 0 }}>
                  ⏱ {formatTime(sessionTimeRemaining)}
                </span>
              </div>

              {cameraError ? (
                <div className="enroll-alert error" style={{ flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span style={{ fontSize: '1.2rem' }}>⚠️</span>
                    <strong>Camera Access Error</strong>
                  </div>
                  <p>{cameraError}</p>
                  <button
                    className="btn-secondary-ghost"
                    style={{ marginTop: '4px', alignSelf: 'flex-start' }}
                    onClick={startCamera}
                  >
                    🔄 Allow Camera / Try Again
                  </button>
                </div>
              ) : (
                <>
                  {/* Camera Viewport with Oval Reticle */}
                  <div className="camera-container">
                    <video ref={videoRef} playsInline muted className="camera-video" />
                    <div className={`camera-reticle-oval ${isFaceDetected ? 'good' : 'bad'}`} />
                    <div className="camera-guide-banner">
                      {samples.length < 4
                        ? STEP_INSTRUCTIONS[samples.length]
                        : 'All 4 samples captured! Ready to register.'}
                    </div>
                  </div>

                  {/* Real-time Status Indicator */}
                  <div
                    style={{
                      textAlign: 'center',
                      marginBottom: '0.75rem',
                      color: isFaceDetected ? '#10b981' : '#f59e0b',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                    }}
                  >
                    <span>{isFaceDetected ? '●' : '○'}</span>
                    <span>{faceStatusMessage}</span>
                  </div>

                  {/* 4 Sample Progress Thumbnails */}
                  <div className="samples-row">
                    {[0, 1, 2, 3].map((idx) => (
                      <div
                        key={idx}
                        className={`sample-thumbnail-card ${samples.length === idx ? 'active-target' : ''}`}
                      >
                        {samples[idx] ? (
                          <>
                            <img src={samples[idx]} alt={`Sample ${idx + 1}`} />
                            <span className="sample-thumbnail-badge">✓ {idx + 1}</span>
                          </>
                        ) : (
                          <span style={{ color: '#71829f', fontSize: '0.75rem', fontWeight: 600 }}>
                            Sample {idx + 1}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>

                  {enrollError && (
                    <div className="enroll-alert error" style={{ marginBottom: '0.75rem' }}>
                      <span>✕</span>
                      <p>{enrollError}</p>
                    </div>
                  )}

                  {/* Action Buttons: 100% Zoom Accessible */}
                  <div style={{ display: 'flex', gap: '8px' }}>
                    {samples.length < 4 ? (
                      <button
                        className="btn-primary-glow"
                        style={{ marginTop: 0 }}
                        onClick={handleCaptureSample}
                        disabled={!isFaceDetected}
                      >
                        {isFaceDetected
                          ? `📸 Capture Sample ${samples.length + 1} of 4`
                          : 'Position Face in Oval to Capture'}
                      </button>
                    ) : (
                      <button
                        className="btn-primary-glow"
                        style={{ marginTop: 0 }}
                        onClick={handleSubmitEnrollment}
                        disabled={currentStep === 'submitting'}
                      >
                        {currentStep === 'submitting' ? 'Registering Face...' : '✓ Complete Face Registration'}
                      </button>
                    )}

                    {samples.length > 0 && (
                      <button className="btn-secondary-ghost" onClick={handleRetakeAll}>
                        Retake
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* ─────────────────────────────────────────────────────────────────
              SCREEN 4: SUCCESS CONFIRMATION
             ───────────────────────────────────────────────────────────────── */}
          {currentStep === 'success' && verifiedSession && (
            <div>
              <div className="verified-badge-container">
                <div className="verified-icon-ring" style={{ width: '76px', height: '76px', fontSize: '2rem' }}>
                  ✓
                </div>
                <h2 style={{ color: '#ffffff', fontSize: '1.45rem', fontWeight: 700 }}>
                  Face Enrollment Successful
                </h2>
                <p style={{ color: '#a3b2d1', fontSize: '0.85rem', marginTop: '2px' }}>
                  Your biometric profile is now securely registered.
                </p>
              </div>

              <div className="verified-card">
                <div className="verified-row">
                  <span className="verified-label">Customer Name</span>
                  <span className="verified-value highlight">{verifiedSession.customer_name}</span>
                </div>
                <div className="verified-row">
                  <span className="verified-label">Account Number</span>
                  <span className="verified-value">{verifiedSession.account_number_masked}</span>
                </div>
                <div className="verified-row">
                  <span className="verified-label">Status</span>
                  <span className="verified-value" style={{ color: '#10b981' }}>
                    Face registered successfully
                  </span>
                </div>
              </div>

              <p style={{ color: '#71829f', fontSize: '0.82rem', textAlign: 'center', marginBottom: '1.25rem', lineHeight: 1.4 }}>
                You can now use facial recognition for instant, hands-free authentication at any AI Smart Banking Kiosk.
              </p>

              <button className="btn-primary-glow" onClick={handleBackToKiosk}>
                <span>Go to Banking Kiosk</span> &rarr;
              </button>
            </div>
          )}

        </div>
      </main>
    </div>
  )
}
