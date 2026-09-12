// Reusable AI visual identity: a glowing orb with rotating rings and a
// small waveform beneath it. Purely presentational - takes a `state`
// ('idle' | 'listening' | 'processing') that only changes CSS classes,
// so it never touches any voice/session logic.

export default function AIOrb({ state = 'idle', size = 220 }) {
  return (
    <div
      className={`ai-orb ai-orb--${state}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <span className="ai-orb__ring ai-orb__ring--1" />
      <span className="ai-orb__ring ai-orb__ring--2" />
      <span className="ai-orb__core" />
      <span className="ai-orb__waves">
        {Array.from({ length: 7 }).map((_, i) => (
          <span key={i} style={{ animationDelay: `${i * 0.09}s` }} />
        ))}
      </span>
    </div>
  )
}
