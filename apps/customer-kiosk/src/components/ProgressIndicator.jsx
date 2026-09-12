import { translate } from '../services/translations.js'

const STEPS = [
  ['Authentication', 'stepAuthentication'],
  ['Enter Details', 'stepDetails'],
  ['Confirmation', 'stepConfirmation'],
  ['Complete', 'stepComplete'],
]

// The indicator reflects App's existing screen state. It has no controls and
// does not create a separate transaction workflow.
export default function ProgressIndicator({ currentScreen, preferredLanguage = 'en' }) {
  const currentStep =
    currentScreen === 'language' || currentScreen === 'auth'
      ? 0
      : currentScreen === 'assistant' || currentScreen === 'error'
        ? 1
        : currentScreen === 'confirmation'
          ? 2
          : currentScreen === 'success'
            ? 3
            : -1

  if (currentStep < 0) return null

  const isFinished = currentScreen === 'success'
  return (
    <nav
      className="transaction-progress"
      aria-label="Transaction progress"
      aria-describedby="transaction-progress-status"
    >
      <p id="transaction-progress-status" className="transaction-progress__status">
        {translate(preferredLanguage, STEPS[currentStep][1])}
      </p>
      <ol className="transaction-progress__steps">
        {STEPS.map(([, stepKey], index) => {
          const isCurrent = index === currentStep && !isFinished
          const isComplete = index < currentStep || isFinished

          return (
            <li
              key={stepKey}
              className={`transaction-progress__step${isCurrent ? ' transaction-progress__step--current' : ''}${isComplete ? ' transaction-progress__step--complete' : ''}`}
              aria-current={isCurrent ? 'step' : undefined}
            >
              <span className="transaction-progress__marker" aria-hidden="true">
                {isComplete ? '✓' : index + 1}
              </span>
              <span className="transaction-progress__label">
                {translate(preferredLanguage, `${stepKey}Label`)}
              </span>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}