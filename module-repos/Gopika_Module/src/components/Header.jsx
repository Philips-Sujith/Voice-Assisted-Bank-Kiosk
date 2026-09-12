// APPLICATION HEADER
// Shown on every screen except Welcome (which carries its own hero
// branding). Purely presentational - no session/state logic lives
// here, it only displays the preferredLanguage value it's given.

import { translate } from '../services/translations.js'

const LANGUAGE_LABEL = { ta: 'தமிழ்', en: 'English', tanglish: 'Tanglish' }

export default function Header({ preferredLanguage }) {
  return (
    <header className="app-header">
      <div className="app-header__brand">
        <span className="app-header__logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
            <circle cx="12" cy="12" r="10" stroke="#04101f" strokeWidth="1.8" />
            <path
              d="M7 13c0.7-3.5 2.8-5.5 5-5.5s4.3 2 5 5.5"
              stroke="#04101f"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
            <circle cx="12" cy="9" r="1.4" fill="#04101f" />
          </svg>
        </span>
        <span className="app-header__title">{translate(preferredLanguage, 'appTitle')}</span>
      </div>

      <p className="app-header__tagline">{translate(preferredLanguage, 'appTagline')}</p>

      <div className="app-header__lang">
        {preferredLanguage ? (
          <span className="language-pill">
            {LANGUAGE_LABEL[preferredLanguage] || preferredLanguage}
          </span>
        ) : (
          <span className="app-header__lang-placeholder">—</span>
        )}
      </div>
    </header>
  )
}
