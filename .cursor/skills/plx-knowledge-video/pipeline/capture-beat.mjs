// Clean per-beat capture: preloads the page OFF-camera (so page-load white
// screens are never recorded), then records a single loaded page with an
// "activeHold" (continuous subtle cursor motion) so the change-driven CDP
// screencast keeps emitting frames and passes the compose FPS gate. Optional
// smart zoom (focus) on a target selector. Composes to a framed clip.
//
// Usage:
//   node demos/capture-beat.mjs --slug swimlane --url /mrp/sop-flows \
//     --clickText "Procure-to-Pay" --focusText "Procure-to-Pay" --hold 6 --scrollTo "BC AP"
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'
import { chromium } from 'playwright'
import { loadConfig } from './_engine/config.mjs'
import { createTimeline } from './_engine/timeline.mjs'
import { createFilmContext, prepareFilmPage, startFilmRecording, finishFilmRecording } from './_engine/record.mjs'
import { focus, wide, filmMove, settle } from './_engine/actions.mjs'
import { pause } from './_engine/motion.mjs'
import { buildDemoSession, waitForAppReady } from './_lib/auth.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const config = loadConfig(process.cwd())
const baseUrl = process.env.DEMO_BASE_URL ?? config.app.baseUrl
const viewport = config.app?.viewport ?? { width: 1600, height: 900 }

function arg(name, def) {
  const i = process.argv.indexOf(`--${name}`)
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def
}

const slug = arg('slug', 'beat')
const url = arg('url', '/')
const clickText = arg('clickText', '')
const focusText = arg('focusText', '')
const scrollTo = arg('scrollTo', '')
const endOnFocus = process.argv.includes('--endOnFocus')
const holdSec = parseFloat(arg('hold', '6'))
const renderDir = join(__dirname, 'clips', slug)

// Keep the screencast alive during a hold by nudging the cursor on a tiny
// Lissajous path — imperceptible, but every move repaints the cursor overlay
// so frame intervals stay < the gate's p90 budget.
async function activeHold(page, timeline, seconds, cx, cy) {
  const end = Date.now() + seconds * 1000
  let i = 0
  while (Date.now() < end) {
    const dx = Math.sin(i / 2.7) * 7
    const dy = Math.cos(i / 3.3) * 5
    await filmMove(page, timeline, Math.round(cx + dx), Math.round(cy + dy))
    await pause(45)
    i++
  }
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-background-timer-throttling', '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding'],
  })
  const storageState = await buildDemoSession(browser, { baseUrl })
  const context = await createFilmContext(browser, renderDir, { storageState, viewport })
  const page = await context.newPage()
  await prepareFilmPage(page, config.cursor)

  // --- OFF-CAMERA preload: navigate + wait for full render before recording ---
  await page.goto(`${baseUrl}${url}`, { waitUntil: 'commit' }).catch(() => {})
  await waitForAppReady(page)
  await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {})
  if (clickText) {
    try {
      await page.getByText(new RegExp(clickText, 'i')).first().click({ timeout: 6000 })
      await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
    } catch {}
  }
  if (scrollTo) {
    try {
      await page.getByText(new RegExp(scrollTo, 'i')).first().scrollIntoViewIfNeeded({ timeout: 6000 })
    } catch {}
  }
  await settle(page).catch(() => {})
  await pause(500)

  const vp = page.viewportSize() ?? viewport
  const cx = Math.round(vp.width / 2)
  const cy = Math.round(vp.height / 2)

  // --- RECORD: page is already fully rendered, so no load-white is captured ---
  const timeline = createTimeline()
  const recorder = await startFilmRecording(page, renderDir, timeline)
  await wide(page, timeline, `${slug}-wide`)
  await activeHold(page, timeline, Math.max(1.2, holdSec * 0.45), cx, cy)

  if (focusText) {
    try {
      const target = page.getByText(new RegExp(focusText, 'i')).first()
      await target.waitFor({ state: 'visible', timeout: 5000 })
      await focus(page, timeline, target, `${slug}-focus`)
      const box = await target.boundingBox()
      const fcx = box ? Math.round(box.x + box.width / 2) : cx
      const fcy = box ? Math.round(box.y + Math.min(box.height / 2, 120)) : cy
      // Hold on the zoomed key content for the remainder (endOnFocus), so the
      // freeze in assembly rests on the payoff — not a wide shot.
      await activeHold(page, timeline, Math.max(2.0, holdSec * (endOnFocus ? 0.55 : 0.5)), fcx, fcy)
      if (!endOnFocus) {
        await wide(page, timeline, `${slug}-wide2`)
        await activeHold(page, timeline, 0.8, cx, cy)
      }
    } catch {
      await activeHold(page, timeline, Math.max(1.5, holdSec * 0.5), cx, cy)
    }
  } else {
    await activeHold(page, timeline, Math.max(1.5, holdSec * 0.55), cx, cy)
  }

  timeline.dump(join(renderDir, 'timeline.json'))
  const rec = await finishFilmRecording(context, page, renderDir, recorder)
  await browser.close()
  if (!rec.ok) { console.error('capture failed'); process.exit(1) }
  console.log(`BEAT ${slug}: recorded ${rec.capturedFps} fps -> ${renderDir}`)
}

main().catch((e) => { console.error(e); process.exit(1) })
