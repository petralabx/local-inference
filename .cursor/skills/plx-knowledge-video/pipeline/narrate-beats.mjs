// Narration-first: render one ElevenLabs mp3 per beat and record its duration.
// The per-beat duration then sizes each beat's on-screen hold, so audio and
// video stay in sync with no time-stretching.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'
import { execFileSync } from 'child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const cfg = JSON.parse(readFileSync(join(__dirname, 'beats.json'), 'utf8'))
const apiKey = process.env.ELEVENLABS_API_KEY
if (!apiKey) { console.error('ELEVENLABS_API_KEY not set'); process.exit(1) }
const audioDir = join(__dirname, 'clips', 'audio')
mkdirSync(audioDir, { recursive: true })

function ffprobeDur(p) {
  const out = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', p], { encoding: 'utf8' })
  return parseFloat(out.trim())
}

const durations = {}
for (const b of cfg.beats) {
  const out = join(audioDir, `${b.slug}.mp3`)
  const res = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${cfg.voice}?output_format=mp3_44100_128`, {
    method: 'POST',
    headers: { 'xi-api-key': apiKey, 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: b.narration, model_id: cfg.model, voice_settings: { stability: 0.5, similarity_boost: 0.8, use_speaker_boost: true } }),
  })
  if (!res.ok) { console.error(`TTS failed for ${b.slug}: ${res.status} ${await res.text()}`); process.exit(1) }
  const buf = Buffer.from(await res.arrayBuffer())
  writeFileSync(out, buf)
  durations[b.slug] = ffprobeDur(out)
  console.log(`narrated ${b.slug}: ${durations[b.slug].toFixed(2)}s -> ${out}`)
}
writeFileSync(join(audioDir, 'durations.json'), JSON.stringify(durations, null, 2))
console.log('wrote durations.json')
