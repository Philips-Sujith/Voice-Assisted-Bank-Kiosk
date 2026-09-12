import { useEffect, useRef, useState } from 'react'

// SCREEN 2: LANGUAGE SELECTION
// Customer picks how they want to speak with the assistant.
// This value becomes "preferred_language" in the fixed contract
// we send to Voice AI: ta | en | tanglish
//
// onSelect(code) is called with the exact same values as before -
// the only addition is a brief visible "selected" state (a checkmark
// + highlighted panel) before we hand off, so the choice feels
// confirmed rather than instant and jarring.

const LANGUAGES = [
  { code: 'ta', label: 'தமிழ்', sub: 'Tamil', greeting: 'வணக்கம்', icon: 'த' },
  { code: 'en', label: 'English', sub: 'English', greeting: 'Welcome', icon: 'EN' },
  { code: 'tanglish', label: 'Tanglish', sub: 'Tamil + English', greeting: 'Vanakkam', icon: 'TG' },
]

export default function LanguageSelection({ onSelect }) {
  const [selectedCode, setSelectedCode] = useState(null)
  const timeoutRef = useRef(null)

  const handlePick = (code) => {
    if (selectedCode) return // already confirming a choice
    setSelectedCode(code)
    timeoutRef.current = setTimeout(() => onSelect(code), 420)
  }

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  return (
    <section className="screen screen--language">
      <div className="progress-dots" aria-hidden="true">
        <span className="active" />
        <span />
        <span />
        <span />
      </div>
      <p className="eyebrow">Step 1 of 4</p>
      <h2 className="screen__title">Choose Your Language</h2>
      <p className="screen__subtitle">உங்கள் மொழியை தேர்ந்தெடுக்கவும்</p>

      <div className="lang-panels">
        {LANGUAGES.map((lang) => (
          <button
            key={lang.code}
            className={`lang-panel ${selectedCode === lang.code ? 'lang-panel--selected' : ''}`}
            onClick={() => handlePick(lang.code)}
            aria-label={`Continue in ${lang.sub}`}
            aria-pressed={selectedCode === lang.code}
          >
            {selectedCode === lang.code && (
              <span className="lang-panel__check" aria-hidden="true">✓</span>
            )}
            <span className="lang-panel__icon" aria-hidden="true">{lang.icon}</span>
            <span className="lang-panel__name">{lang.label}</span>
            <span className="lang-panel__sub">{lang.sub}</span>
            <span className="lang-panel__greeting">“{lang.greeting}”</span>
          </button>
        ))}
      </div>
    </section>
  )
}
