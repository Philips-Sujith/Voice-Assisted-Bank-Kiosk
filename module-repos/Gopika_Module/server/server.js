import 'dotenv/config'
import cors from 'cors'
import express from 'express'
import textToSpeech from '@google-cloud/text-to-speech'

const app = express()
const port = Number(process.env.TTS_PORT || 8787)
let ttsClient = null
if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
  try {
    ttsClient = new textToSpeech.TextToSpeechClient()
  } catch (err) {
    console.warn('[tts-server] GCP TTS client initialization skipped:', err.message)
  }
}

app.use(cors())
app.use(express.json({ limit: '32kb' }))

app.post('/api/tts', async (req, res) => {
  const { text, language = 'ta' } = req.body || {}

  if (language !== 'ta' || typeof text !== 'string' || !text.trim()) {
    res.status(400).json({ error: 'Tamil TTS requires a non-empty text value.' })
    return
  }

  if (ttsClient) {
    try {
      const [response] = await ttsClient.synthesizeSpeech({
        input: { text: text.trim() },
        voice: { languageCode: 'ta-IN', ssmlGender: 'NEUTRAL' },
        audioConfig: { audioEncoding: 'MP3' },
      })

      if (response && response.audioContent) {
        res.set('Content-Type', 'audio/mpeg').send(response.audioContent)
        return
      }
    } catch (gcpError) {
      console.warn('[tts-server] GCP TTS failed:', gcpError.message)
    }
  }

  try {
    const fallbackUrl = `https://translate.google.com/translate_tts?ie=UTF-8&tl=ta&client=tw-ob&q=${encodeURIComponent(text.trim())}`
    const fallbackRes = await fetch(fallbackUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
    })

    if (!fallbackRes.ok) {
      throw new Error(`Fallback TTS returned status ${fallbackRes.status}`)
    }

    const arrayBuffer = await fallbackRes.arrayBuffer()
    res.set('Content-Type', 'audio/mpeg').send(Buffer.from(arrayBuffer))
  } catch (fallbackError) {
    console.error('[tts-server] Tamil cloud TTS request failed:', fallbackError.message)
    res.status(502).json({ error: 'Tamil cloud TTS is currently unavailable.' })
  }
})

app.listen(port, () => {
  console.log(`[tts-server] Tamil TTS endpoint listening on http://localhost:${port}`)
})
