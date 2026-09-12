// SCREEN 7: ERROR / RETRY
// Shown whenever something fails: Voice AI couldn't understand the
// request, a connection error, or the user cancelled a transaction.
// Same props and the same two handlers (onRetry/onHome) as before -
// only the visual tone changed to something calmer for elderly users.
import { replayVoiceResponse } from '../services/ttsService.js'
import { translate } from '../services/translations.js'

export default function ErrorScreen({ message, preferredLanguage, onRetry, onHome }) {
  return (
    <section className="screen screen--error">
      <div className="error-stage" aria-hidden="true">
        <svg viewBox="0 0 64 64" width="34" height="34" fill="none">
          <path
            d="M32 22v16M32 42v.5"
            stroke="#f5b942"
            strokeWidth="4"
            strokeLinecap="round"
          />
        </svg>
      </div>

      <h2 className="screen__title">{translate(preferredLanguage, 'errorTitle')}</h2>
      <p className="error__message">
        {message || translate(preferredLanguage, 'errorDefault')}
      </p>
      {message && (
        <button
          className="listen-again-button"
          type="button"
          onClick={() => replayVoiceResponse({ spoken_text: message }, preferredLanguage)}
          aria-label="Listen again to the AI response"
        >
          🔊 {translate(preferredLanguage, 'listenAgain')}
        </button>
      )}

      <div className="action-bar">
        <button className="btn btn--ghost btn--lg" onClick={onHome}>
          {translate(preferredLanguage, 'goBack')}
        </button>
        <button className="btn btn--primary btn--lg" onClick={onRetry}>
          {translate(preferredLanguage, 'retry')}
        </button>
      </div>
    </section>
  )
}
