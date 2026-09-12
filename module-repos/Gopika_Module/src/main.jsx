import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import FaceEnrollmentApp from './pages/FaceEnrollmentApp.jsx'
import './index.css'

function RootRouter() {
  const [route, setRoute] = useState(() => {
    const p = window.location.pathname
    const h = window.location.hash
    if (p.includes('/face-enrollment') || h.includes('face-enrollment')) {
      return 'face-enrollment'
    }
    return 'kiosk'
  })

  useEffect(() => {
    const handleLocationChange = () => {
      const p = window.location.pathname
      const h = window.location.hash
      if (p.includes('/face-enrollment') || h.includes('face-enrollment')) {
        setRoute('face-enrollment')
      } else {
        setRoute('kiosk')
      }
    }

    window.addEventListener('popstate', handleLocationChange)
    window.addEventListener('hashchange', handleLocationChange)
    return () => {
      window.removeEventListener('popstate', handleLocationChange)
      window.removeEventListener('hashchange', handleLocationChange)
    }
  }, [])

  if (route === 'face-enrollment') {
    return <FaceEnrollmentApp />
  }

  return <App />
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RootRouter />
  </React.StrictMode>,
)

