// Central TTS Service handling SpeechSynthesis and Backend Audio Playback (http://localhost:8787/api/tts)
import { translate } from './translations.js'

const LANGUAGE_TAGS = { en: 'en-IN', ta: 'ta-IN', tanglish: 'en-IN' }
let activeAudio = null
let audioUnlocked = false

// Autoplay policy unlocker: unlocks browser HTML5 Audio on first user interaction
export function unlockAudioContext() {
  if (audioUnlocked || typeof window === 'undefined') return
  try {
    const silentAudio = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA')
    silentAudio.play().then(() => {
      audioUnlocked = true
      console.log('[TTS] Audio context successfully unlocked by user interaction.')
    }).catch(() => {})
  } catch (e) {}
}

if (typeof window !== 'undefined') {
  ['click', 'touchstart', 'keydown'].forEach((event) => {
    window.addEventListener(event, unlockAudioContext, { once: true })
  })
}

export function stopSpeechOutput() {
  if (typeof window === 'undefined') return
  window.speechSynthesis?.cancel()
  if (activeAudio) {
    try {
      activeAudio.pause()
      activeAudio.currentTime = 0
    } catch (e) {}
    activeAudio = null
  }
}

function getAvailableVoices() {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return []
  return window.speechSynthesis.getVoices()
}

function waitForVoices() {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return Promise.resolve([])

  const synthesis = window.speechSynthesis
  const currentVoices = getAvailableVoices()
  if (currentVoices.length > 0) return Promise.resolve(currentVoices)

  return new Promise((resolve) => {
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      synthesis.removeEventListener('voiceschanged', handleVoicesChanged)
      resolve(getAvailableVoices())
    }
    const handleVoicesChanged = () => finish()
    synthesis.addEventListener('voiceschanged', handleVoicesChanged)
    setTimeout(finish, 1500)
  })
}

async function findPreferredVoice(language) {
  const voices = await waitForVoices()
  console.debug('[TTS] available speech voices', voices.map(({ name, lang }) => ({ name, lang })))

  if (language === 'ta') {
    const tamilVoice =
      voices.find((v) => v.lang.toLowerCase().replace('_', '-') === 'ta-in') ||
      voices.find((v) => v.lang.toLowerCase().replace('_', '-').startsWith('ta')) ||
      null
    return tamilVoice
  }

  const languageTag = LANGUAGE_TAGS[language] || LANGUAGE_TAGS.en
  return (
    voices.find((voice) => voice.lang.toLowerCase().replace('_', '-') === languageTag.toLowerCase()) ||
    voices.find((voice) => voice.lang.toLowerCase().startsWith('en')) ||
    voices[0] ||
    null
  )
}

async function requestCloudTamilAudio(text) {
  unlockAudioContext()
  stopSpeechOutput()

  const targetUrls = ['/api/tts', 'http://localhost:8787/api/tts']
  let response = null
  let usedUrl = ''

  for (const url of targetUrls) {
    try {
      console.log(`[TTS] language = ta`)
      console.log(`[TTS] text = "${text}"`)
      console.log(`[TTS] requesting = ${url}`)

      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, language: 'ta' }),
      })

      if (response.ok) {
        usedUrl = url
        break
      } else {
        console.warn(`[TTS] endpoint ${url} returned status ${response.status}`)
      }
    } catch (err) {
      console.warn(`[TTS] failed to fetch from ${url}:`, err.message)
    }
  }

  if (!response || !response.ok) {
    console.error('[TTS] response status =', response ? response.status : 'FETCH_FAILED')
    console.error('[TTS] audio received = false')
    throw new Error(`Tamil cloud TTS request failed with status ${response ? response.status : 'network error'}`)
  }

  const contentType = response.headers.get('content-type') || 'audio/mpeg'
  console.log(`[TTS] response status = ${response.status}`)
  console.log(`[TTS] content type = ${contentType}`)

  const audioBlob = await response.blob()
  const audioReceived = audioBlob.size > 0
  console.log(`[TTS] audio received = ${audioReceived} (${audioBlob.size} bytes)`)

  if (!audioReceived) {
    throw new Error('Received empty audio payload from server')
  }

  const audioUrl = URL.createObjectURL(audioBlob)
  const audio = new Audio(audioUrl)
  activeAudio = audio

  console.log('[TTS] starting playback')

  return new Promise((resolve, reject) => {
    let hasEnded = false

    const cleanup = () => {
      if (hasEnded) return
      hasEnded = true
      if (activeAudio === audio) activeAudio = null
      setTimeout(() => URL.revokeObjectURL(audioUrl), 1000)
    }

    audio.onplay = () => {
      console.log('[TTS] playback started')
    }

    audio.onended = () => {
      console.log('[TTS] playback ended')
      cleanup()
      resolve(true)
    }

    audio.onerror = (e) => {
      console.error('[TTS] audio playback error:', e)
      cleanup()
      reject(new Error('Audio element playback error'))
    }

    audio.play().catch((playErr) => {
      console.error('[TTS] playback error / blocked:', playErr.message || playErr)
      cleanup()
      reject(playErr)
    })
  })
}

// Speaks translated UI guidance with installed browser voice or backend audio server fallback
export async function speakText(text, language = 'en') {
  if (!text || typeof window === 'undefined') return false

  unlockAudioContext()
  const voice = await findPreferredVoice(language)

  if (language === 'ta') {
    console.log(`Language: ${language}`)
    console.log(`Text: ${text}`)
    if (voice) {
      console.log(`Voice: ${voice.name}`)
      console.log(`Voice language: ${voice.lang}`)
      console.log(`Tamil TTS voice: FOUND`)
    } else {
      console.log(`Tamil TTS voice: NOT FOUND`)
    }
  } else {
    console.log(`Language: ${language}`)
    console.log(`Text: ${text}`)
    if (voice) {
      console.log(`Voice: ${voice.name}`)
      console.log(`Voice language: ${voice.lang}`)
    }
  }

  if (language === 'ta' && !voice) {
    console.warn('[TTS] No Tamil browser voice installed. Requesting backend TTS audio from http://localhost:8787...')
    try {
      await requestCloudTamilAudio(text)
      return true
    } catch (error) {
      console.warn('[TTS] Tamil cloud TTS playback failed:', error.message)
      return false
    }
  }

  if (!('speechSynthesis' in window)) return false

  stopSpeechOutput()
  console.log(`[TTS] starting SpeechSynthesis playback (language=${language})`)
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = LANGUAGE_TAGS[language] || LANGUAGE_TAGS.en
  if (voice) utterance.voice = voice

  return new Promise((resolve) => {
    utterance.onstart = () => console.log('[TTS] playback started')
    utterance.onend = () => {
      console.log('[TTS] playback ended')
      resolve(true)
    }
    utterance.onerror = (e) => {
      console.error('[TTS] SpeechSynthesis error:', e)
      resolve(false)
    }
    window.speechSynthesis.speak(utterance)
  })
}

export function speakTranslation(language, key) {
  const text = translate(language, key)
  speakText(typeof text === 'function' ? text() : text, language)
}

export function speakGuidance(language, stage) {
  const translations = translate(language, 'voiceGuidance')
  speakText(translations?.[stage], language)
}

export function replayVoiceResponse(response, preferredLanguage = 'en') {
  if (!response) return
  unlockAudioContext()

  const audioUrl =
    response.audio_url || response.audioUrl || response.tts_audio_url || response.ttsAudioUrl

  if (audioUrl) {
    stopSpeechOutput()
    const audio = new Audio(audioUrl)
    activeAudio = audio
    audio.play().catch((error) => {
      console.warn('[TTS] could not replay Voice AI audio:', error)
    })
    return
  }

  speakText(response.spoken_text, response.language || preferredLanguage)
}