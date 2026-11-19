// Usage: [APP_URL=http://localhost:5173/] [CHROME_PATH=...] node scripts/cdp-pan-check.mjs [--url U] [--out DIR] [--rounds 5]
// Requires `yarn dev` running. Plan: .omc/plans/chunk-rendering.md §9 (AC 6-12).
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const argv = process.argv.slice(2)
const arg = (n, d) => (argv.includes(n) ? argv[argv.indexOf(n) + 1] : d)
const URL_ = arg('--url', process.env.APP_URL ?? 'http://localhost:5173/')
const OUT = arg('--out', join(tmpdir(), 'lc-cdp'))
const ROUNDS = Number(arg('--rounds', 5))
const PERF = argv.includes('--perf-table')
const withCitizens = (n) => { const u = new URL(URL_); u.searchParams.set('citizens', String(n)); return u.toString() }
const CHROME = process.env.CHROME_PATH ??
  '/Users/ian/Library/Caches/ms-playwright/chromium-1234/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const withTimeout = (p, ms, msg) =>
  Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error(`timeout ${ms}ms: ${msg}`)), ms))])
const freePort = () => new Promise((res, rej) => {
  const s = createServer().listen(0, () => { const { port } = s.address(); s.close(() => res(port)) })
  s.on('error', rej)
})

const report = { url: URL_, rounds: [], clicks: {}, fps: {}, errors: [], criteria: {}, screenshots: [] }
const crit = (name, pass, detail) => { report.criteria[name] = { pass: !!pass, detail } }

let chrome, profile, ws
async function main() {
  mkdirSync(OUT, { recursive: true })
  profile = mkdtempSync(join(tmpdir(), 'lc-chrome-'))
  const port = await freePort()
  chrome = spawn(CHROME, ['--headless=new', ...(PERF ? ['--use-angle=metal'] : ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']),
    `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, PERF ? '--window-size=1920,1080' : '--window-size=1280,720', 'about:blank'], { stdio: 'ignore' })
  chrome.on('error', (e) => { report.errors.push(`chrome spawn: ${e.message}`) })

  // wait for DevTools endpoint, then open a fresh target
  let target
  for (let i = 0; i < 50 && !target; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })
      target = await r.json()
    } catch { await sleep(200) }
  }
  if (!target?.webSocketDebuggerUrl) throw new Error(`Chrome DevTools not reachable (CHROME_PATH=${CHROME})`)

  ws = new WebSocket(target.webSocketDebuggerUrl)
  await withTimeout(new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws error')) }), 10000, 'ws open')
  let id = 0
  const pending = new Map()
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data)
    if (d.id && pending.has(d.id)) { const { res, rej } = pending.get(d.id); pending.delete(d.id); if (d.error) rej(new Error(d.error.message)); else res(d.result) }
    else if (d.method === 'Runtime.exceptionThrown') report.errors.push('exception: ' + (d.params.exceptionDetails.exception?.description ?? d.params.exceptionDetails.text))
    else if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error')
      report.errors.push('console.error: ' + d.params.args.map((a) => a.value ?? a.description).join(' '))
  }
  const send = (method, params = {}) => withTimeout(new Promise((res, rej) => {
    const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params }))
  }), 30000, method)
  const ev = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })
    if (r.exceptionDetails) throw new Error('eval failed: ' + (r.exceptionDetails.exception?.description ?? expr))
    return r.result.value
  }
  const until = async (expr, ms, msg) => {
    const end = Date.now() + ms
    while (Date.now() < end) { try { if (await ev(expr)) return } catch {} await sleep(150) }
    throw new Error(`timeout ${ms}ms waiting for: ${msg}`)
  }
  const shot = async (name) => {
    const r = await send('Page.captureScreenshot', { format: 'png' })
    const p = join(OUT, name); writeFileSync(p, Buffer.from(r.data, 'base64')); report.screenshots.push(p)
  }
  const gcHeap = async () => { await send('HeapProfiler.collectGarbage'); return (await send('Runtime.getHeapUsage')).usedSize }
  const stats = () => ev('window.__lcDebug.stats()')
  const raf2 = () => ev('new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
  const drained = () => until('window.__lcDebug.stats().pendingChunks === 0', 120000, 'pendingChunks === 0')
  const mouse = (type, x, y, extra = {}) =>
    send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1, ...extra })
  const click = async (p) => { await mouse('mouseMoved', p.x, p.y, { buttons: 0 }); await mouse('mousePressed', p.x, p.y); await mouse('mouseReleased', p.x, p.y) }
  const sel = () => ev('window.__lcDebug.selectedId()')
  // on-screen tiles near the map center that isQuietTile accepts (no building / road within 2 tiles)
  const quietTiles = (cx = 256, cz = 256, r = 25) => ev(`(() => { const o = []; const D = window.__lcDebug
    for (let d = 0; d <= ${r}; d++) for (let dx = -d; dx <= d; dx++) for (const dy of (Math.abs(dx) === d ? Array.from({length: 2*d+1}, (_, k) => k - d) : [-d, d])) {
      const x = ${cx} + dx, y = ${cz} + dy; const p = D.screenPointOfTile(x, y)
      if (p && p.x > 40 && p.y > 40 && p.x < innerWidth - 40 && p.y < innerHeight - 40 && D.isQuietTile(x, y)) o.push([x, y]) }
    return o })()`)
  const D = (e) => ev(`window.__lcDebug.${e}`)
  const pnl = () => ev(`(document.body.innerText.match(/Citizen: \\S+/) || [null])[0]`)
  const load = async (n) => {
    await send('Page.navigate', { url: withCitizens(n) })
    await sleep(500)
    await until('!!window.__lcDebug && !!window.__lcDebug.stats() && !!window.__lcDebug.citizenStats()', 60000, 'lcDebug ready')
    await drained(); await sleep(1500)
  }
  const ring = function* (r) {
    for (let d = 0; d <= r; d++) for (let dx = -d; dx <= d; dx++) for (const dy of (Math.abs(dx) === d ? Array.from({ length: 2 * d + 1 }, (_, k) => k - d) : [-d, d])) yield [dx, dy]
  }
  // no id-enumeration hook exists: find a citizen by clicking tile centers near the map center
  const findCitizen = async () => {
    for (const [dx, dy] of ring(22)) {
      if (await ev(`window.__lcDebug.isQuietTile(${256 + dx}, ${256 + dy})`)) continue
      const p = await ev(`window.__lcDebug.screenPointOfTile(${256 + dx}, ${256 + dy})`)
      if (!p || p.x < 20 || p.y < 20 || p.x > 1260 || p.y > 700) continue
      await click(p); await sleep(60)
      const s = await D('selection()')
      if (s?.kind === 'citizen') return { id: s.id, p }
    }
    return null
  }
  const p3Checks = async () => {
    await load(1000)
    await ev('window.__lcDebug.panTo(256, 256)'); await raf2(); await sleep(500)
    crit('P3-AC8 citizenMeshes===1', (await D('citizenMeshes()')) === 1, await D('citizenMeshes()'))
    const c = await findCitizen()
    if (!c) { for (const n of ['P3-AC11 click citizen', 'P3-AC9 renders', 'P3-AC7 continuity']) crit(n, false, 'no citizen found by click scan'); return }
    await raf2(); await sleep(700)
    const sel1 = await D('selection()'); const panel = await pnl()
    crit('P3-AC11 click citizen -> kind citizen + panel id', sel1?.kind === 'citizen' && sel1.id === c.id && panel === `Citizen: ${c.id}`, { sel1, panel })
    {
      const p = await D(`citizenScreenPoint(${JSON.stringify(c.id)})`)
      await mouse('mouseMoved', p.x, p.y, { buttons: 0 }); await mouse('mousePressed', p.x, p.y)
      for (let i = 1; i <= 6; i++) await mouse('mouseMoved', p.x + i * 10, p.y, { buttons: 1 })
      await mouse('mouseReleased', p.x + 60, p.y); await raf2()
      crit('P3-AC11 drag over citizen keeps selection', (await D('selection()'))?.id === c.id, await D('selection()'))
      await ev('window.__lcDebug.panTo(256, 256)'); await raf2()
    }
    {
      let bid = null
      for (const [dx, dy] of ring(25)) {
        const p = await ev(`window.__lcDebug.screenPointOfTile(${256 + dx}, ${256 + dy})`)
        if (!p || p.x < 20 || p.y < 20 || p.x > 1260 || p.y > 700) continue
        await click(p); await sleep(60)
        const s = await D('selection()'); if (s?.kind === 'building') { bid = s.id; break }
      }
      await raf2(); await sleep(300)
      crit('P3-AC11 building click replaces citizen', bid !== null && (await D('selection()'))?.kind === 'building' && !(await pnl()), { bid, panel: await pnl() })
    }
    {
      const c2 = await findCitizen()
      let ok = false, tries = 0
      if (c2) for (const t of (await quietTiles()).slice(0, 5)) {
        tries++
        const p = await ev(`window.__lcDebug.screenPointOfTile(${t[0]}, ${t[1]})`)
        await click(p); await raf2()
        if ((await D('selection()')) === null) { ok = true; break }
      }
      crit('P3-AC11 quiet tile click clears citizen', ok, { found: !!c2, tries })
    }
    // P3-AC9
    const c3 = await findCitizen()
    if (!c3) crit('P3-AC9 renders', false, 'no citizen found')
    else {
      await sleep(900)
      const keys = ['CityScene', 'CitizenPanel', 'SelectionPanel', 'CitizenLayer']
      const tickText = () => ev(`(document.body.innerText.match(/Tick: \\S+/) || [null])[0]`)
      const r0 = await D('renderCounts()'); const t0 = await tickText()
      await sleep(10000)
      const r1 = await D('renderCounts()'); const t1 = await tickText()
      const deltas = Object.fromEntries(keys.map((k) => [k, (r1[k] ?? 0) - (r0[k] ?? 0)]))
      crit('P3-AC9 renders +0 over 10 s & tick text changes', keys.every((k) => deltas[k] === 0) && !!t0 && !!t1 && t0 !== t1, { deltas, t0, t1, r0, r1 })
    }
    // P3-AC10
    {
      await ev('window.__lcDebug.panTo(256, 256)'); await raf2(); await sleep(800)
      const st = await D('citizenStats()'); const sx = await stats()
      crit('P3-AC10 0 < visible < total when zoomed in', st.visible > 0 && st.visible < st.total, { visible: st.visible, total: st.total })
      const calls1000 = sx.calls
      await load(0); await ev('window.__lcDebug.panTo(256, 256)'); await raf2(); await sleep(1500)
      const calls0 = (await stats()).calls
      crit('P3-AC10 calls(1000)-calls(0)<=2', calls1000 - calls0 <= 2 && calls1000 >= calls0, { calls1000, calls0 })
      const z = await D('citizenStats()')
      crit('P3-AC12 ?citizens=0 -> total 0 visible 0', z.total === 0 && z.visible === 0, z)
    }
    // P3-AC12
    {
      await load(100)
      const base = (await stats()).geometries
      const res = []
      for (const n of [0, 100, 500, 1000, 100]) {
        await ev(`window.__lcDebug.setCitizenCount(${n})`); await sleep(1000); await raf2()
        const s = await D('citizenStats()'); res.push({ n, total: s?.total, visible: s?.visible })
      }
      const geo = (await stats()).geometries
      crit('P3-AC12 setCitizenCount totals', res.every((r) => r.total === r.n && (r.n === 0 ? r.visible === 0 : r.visible <= r.total)), res)
      crit('P3-AC12 geometries<=base+2', geo <= base + 2, { base, geo })
      await load(500)
      crit('P3-AC12 URL ?citizens=500 honoured', (await D('citizenStats()')).total === 500, await D('citizenStats()'))
    }
    // P3-AC7
    {
      await load(1000)
      await ev('window.__lcDebug.panTo(256, 256)'); await raf2(); await sleep(500)
      const c4 = await findCitizen()
      if (!c4) crit('P3-AC7 continuity', false, 'no citizen found')
      else {
        const q = JSON.stringify(c4.id)
        await ev('window.__lcDebug.setSpeed(16)')
        await ev('window.__lcDebug.panTo(32, 32)'); await raf2(); await sleep(300)
        const away = await D(`citizenInfo(${q})`)
        const s0 = await D('clockSample()')
        await sleep(32000)
        const s1 = await D('clockSample()')
        const drift = Math.abs((s1.tick - s0.tick) - ((s1.now - s0.now) * 16) / 10000)
        const cur = await D(`citizenInfo(${q})`)
        await ev(`window.__lcDebug.panTo(${cur.current.x}, ${cur.current.z})`)
        let back = null
        for (let i = 0; i < 40; i++) { await raf2(); back = await D(`citizenInfo(${q})`); if (back && back.slot !== null) break }
        const cmp = await ev(`(() => { const D = window.__lcDebug, i = D.citizenInfo(${q}); return { i, e: D.expectedFresh(${q}, i.tick) } })()`)
        const dist = cmp.i.rendered && cmp.e ? Math.hypot(cmp.i.rendered.x - cmp.e.x, cmp.i.rendered.z - cmp.e.z) : null
        crit('P3-AC7 slot===null while off-screen', away?.slot === null, { slot: away?.slot })
        crit('P3-AC7 rendered vs expectedFresh <=0.05 tiles', dist !== null && dist <= 0.05, { dist, rendered: cmp.i.rendered, expected: cmp.e, tick: cmp.i.tick, approx: cmp.i.approx })
        crit('P3-AC7 clock drift <=0.01', drift <= 0.01, { drift, dTick: s1.tick - s0.tick, dNow: s1.now - s0.now })
      }
    }
  }

  await send('Runtime.enable'); await send('HeapProfiler.enable'); await send('Page.enable')
  if (PERF) { await perfTable({ send, ev, until, sleep, mouse, gcHeap }); return }
  await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 720, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: URL_ })
  await until('!!window.__lcDebug', 60000, `window.__lcDebug at ${URL_} (is yarn dev running? is it a dev build?)`)
  await drained(); await sleep(2000)

  // baseline (AC 8, 10)
  const base = { stats: await stats(), heap: await gcHeap() }
  base.stats.activeKeysCount = (await ev('window.__lcDebug.activeKeys().length'))
  report.baseline = base
  const callsOk = (s) => s.calls <= 2 * s.activeChunks + 5
  const callPts = [{ at: 'baseline', calls: base.stats.calls, activeChunks: base.stats.activeChunks, ok: callsOk(base.stats) }]
  crit('AC7 default zoom activeChunks<=64', base.stats.activeChunks <= 64, base.stats.activeChunks)
  crit('AC6 stats keys', ['fps', 'avg', 'activeChunks', 'pendingChunks', 'calls', 'triangles', 'geometries', 'textures'].every((k) => k in base.stats), Object.keys(base.stats))
  await shot('center.png')

  // idle FPS
  await sleep(5000)
  report.fps.idleAvg = (await stats()).avg

  // AC12: consecutive real-mouse drag -> drag -> wheel -> drag (regression: controls stuck after first drag).
  // Runs first, from the untouched default view; each drag lasts 1.6 s to straddle the 0.5 s periodic re-render.
  {
    const tp = (x, z) => ev(`window.__lcDebug.screenPointOfTile(${x}, ${z})`)
    const scale = async () => { const a = await tp(256, 256), b = await tp(266, 256); return Math.hypot(b.x - a.x, b.y - a.y) }
    const drag = async (dx, dy) => {
      const [sx, sy, n] = [640, 360, 20]
      await mouse('mouseMoved', sx, sy, { buttons: 0 }); await mouse('mousePressed', sx, sy)
      for (let i = 1; i <= n; i++) { await mouse('mouseMoved', sx + (dx * i) / n, sy + (dy * i) / n, { buttons: 1 }); await sleep(80) }
      await mouse('mouseReleased', sx + dx, sy + dy, { buttons: 0 }); await sleep(1200)
    }
    const step = async (name, dir, min, act, measure) => {
      const before = await measure(); await act(); const after = await measure()
      const d = { before, after }
      const v = dir(before, after); crit(`AC12 ${name}`, v >= min, { ...d, measured: v, min })
    }
    const pos = async () => tp(256, 256)
    const moved = (axis, sign) => (a, b) => sign * (b[axis] - a[axis])
    await step('drag#1 +x', moved('x', 1), 150, () => drag(200, 0), pos)
    await step('drag#2 -x', moved('x', -1), 150, () => drag(-200, 0), pos)
    await step('wheel zoom-in >=15%', (a, b) => b / a - 1, 0.15, async () => {
      for (let i = 0; i < 5; i++) { await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 640, y: 360, deltaX: 0, deltaY: -200 }); await sleep(60) }
      await sleep(800)
    }, scale)
    await step('drag#3 +x after wheel', moved('x', 1), 100, () => drag(200, 0), pos)
    await ev('window.__lcDebug.panTo(256, 256)'); await raf2(); await sleep(500)
  }

  // pan round trips (AC 7, 8)
  const path = [[32, 256], [480, 256], [480, 480], [32, 32], [256, 256]]
  const fpsSamples = []; const keyChanges = []
  let prevKeys = new Set(await ev('window.__lcDebug.activeKeys()'))
  let cx = 256, cz = 256
  for (let r = 1; r <= ROUNDS; r++) {
    for (const [tx, tz] of path) {
      const n = Math.max(1, Math.ceil(Math.hypot(tx - cx, tz - cz) / 16))
      for (let i = 1; i <= n; i++) {
        await ev(`window.__lcDebug.panTo(${cx + ((tx - cx) * i) / n}, ${cz + ((tz - cz) * i) / n})`)
        await raf2()
        if (i % 4 === 0) fpsSamples.push((await stats()).fps)
        const keys = new Set(await ev('window.__lcDebug.activeKeys()'))
        if (r === 1) {
          const add = [...keys].filter((k) => !prevKeys.has(k)).length, rem = [...prevKeys].filter((k) => !keys.has(k)).length
          if (add || rem) keyChanges.push({ add, rem })
        }
        prevKeys = keys
      }
      cx = tx; cz = tz
    }
    await drained(); await sleep(500)
    const s = await stats(); const heap = await gcHeap()
    report.rounds.push({ round: r, geometries: s.geometries, textures: s.textures, heap, activeChunks: s.activeChunks, calls: s.calls })
    callPts.push({ at: `round${r}`, calls: s.calls, activeChunks: s.activeChunks, ok: callsOk(s) })
  }
  report.keyChangesRound1 = keyChanges.length
  report.fps.panMin = Math.min(...fpsSamples); report.fps.panAvg = fpsSamples.reduce((a, b) => a + b, 0) / (fpsSamples.length || 1)
  const last = report.rounds.at(-1)
  crit('AC7 activeKeys change while panning', keyChanges.length > 0, keyChanges.length)
  crit('AC8 geometries<=base+2', last.geometries <= base.stats.geometries + 2, `${last.geometries} vs ${base.stats.geometries}`)
  crit('AC8 textures<=base+2', last.textures <= base.stats.textures + 2, `${last.textures} vs ${base.stats.textures}`)
  crit('AC8 heap<=base*1.15', last.heap <= base.heap * 1.15, `${last.heap} vs ${base.heap} (x${(last.heap / base.heap).toFixed(3)})`)

  // min zoom (AC 10): wheel out at viewport center
  await ev('window.__lcDebug.panTo(256, 256)'); await raf2()
  for (let i = 0; i < 40; i++) { await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 640, y: 360, deltaX: 0, deltaY: 300 }); await sleep(30) }
  await drained(); await sleep(1000)
  const zs = await stats()
  report.minZoom = zs
  callPts.push({ at: 'minZoom', calls: zs.calls, activeChunks: zs.activeChunks, ok: callsOk(zs) })
  crit('AC10 calls<=2*active+5 everywhere', callPts.every((p) => p.ok), callPts)
  // restore zoom so tile/building screen points are on-screen
  for (let i = 0; i < 40; i++) { await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 640, y: 360, deltaX: 0, deltaY: -300 }); await sleep(30) }
  await ev('window.__lcDebug.panTo(256, 256)'); await drained(); await raf2(); await sleep(500)

  // click checks (AC 11): the hook contract has no building lookup, so scan tile centers near the map center.
  // Citizens can be hit (selection kind citizen): skip those candidates; empty-tile check uses isQuietTile + retry.
  const selection = () => ev('window.__lcDebug.selection()')
  let found = null
  scan: for (let d = 0; d <= 30; d++) for (let dx = -d; dx <= d; dx++) for (const dy of (Math.abs(dx) === d ? [...Array(2 * d + 1).keys()].map((k) => k - d) : [-d, d])) {
    const p = await ev(`window.__lcDebug.screenPointOfTile(${256 + dx}, ${256 + dy})`)
    if (!p || p.x < 0 || p.y < 0 || p.x > 1280 || p.y > 720) continue
    await click(p); await raf2()
    const s = await selection()
    if (s?.kind === 'building') { found = { id: s.id, p }; break scan }
  }
  if (!found) crit('AC11 building click', false, 'no building found by scanning tiles near (256,256)')
  else {
    await ev('window.__lcDebug.panTo(256, 256)')
    const p = await ev(`window.__lcDebug.screenPointOf(${JSON.stringify(found.id)})`)
    await click(p); await raf2()
    const s1 = await sel()
    const panel = await ev(`(document.body.innerText.match(/Selected: \\S+ \\([^)]*\\)/) || [null])[0]`)
    report.clicks.building = { id: found.id, selectedId: s1, panel }
    crit('AC11 click building -> selectedId===id', s1 === found.id, { s1 })
    crit('AC11 panel text', !!panel && panel.includes(found.id), panel)
    await shot('selected.png')
    // drag: press, move 60px, release -> selection kept
    await mouse('mouseMoved', p.x, p.y, { buttons: 0 }); await mouse('mousePressed', p.x, p.y)
    for (let i = 1; i <= 6; i++) await mouse('mouseMoved', p.x + i * 10, p.y, { buttons: 1 })
    await mouse('mouseReleased', p.x + 60, p.y); await raf2()
    crit('AC11 drag keeps selection', (await sel()) === found.id, await sel())
    await ev('window.__lcDebug.panTo(256, 256)'); await raf2()
  }
  {
    const quiet = await quietTiles()
    let ok = false, tries = 0
    for (const t of quiet.slice(0, 5)) {
      tries++
      const p = await ev(`window.__lcDebug.screenPointOfTile(${t[0]}, ${t[1]})`)
      if (!p) continue
      await click(p); await raf2()
      if ((await selection()) === null) { ok = true; break }
    }
    crit('AC11 click empty tile -> null', ok, { quiet: quiet.length, tries })
  }

  // border-building screenshot: pan to a chunk border (x=32) once for manual inspection
  await ev('window.__lcDebug.panTo(32, 256)'); await drained(); await raf2(); await sleep(500)
  await shot('border-building.png')

  await p3Checks()
  crit('AC5 no console.error/exceptions', report.errors.length === 0, report.errors.slice(0, 5))
}

// P3-AC13: 8 rows (citizens x speed) on a real GPU; prints a markdown table.
async function perfTable({ send, ev, until, sleep, mouse, gcHeap }) {
  await send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: withCitizens(100) })
  await until('!!window.__lcDebug', 60000, 'window.__lcDebug')
  const gpu = await ev(`(() => { const g = document.createElement('canvas').getContext('webgl'); const x = g.getExtension('WEBGL_debug_renderer_info'); return x ? g.getParameter(x.UNMASKED_RENDERER_WEBGL) : g.getParameter(g.RENDERER) })()`)
  report.gpu = gpu
  crit('P3-AC13 real GPU (no SwiftShader)', !/swiftshader/i.test(gpu), gpu)
  const rows = []
  for (const n of [0, 100, 500, 1000]) for (const sp of [1, 16]) {
    await send('Page.navigate', { url: withCitizens(n) })
    await sleep(500)
    await until('!!window.__lcDebug && !!window.__lcDebug.stats() && !!window.__lcDebug.citizenStats()', 60000, 'ready')
    await until('window.__lcDebug.stats().pendingChunks === 0', 120000, 'drained')
    await ev('window.__lcDebug.panTo(256, 256)')
    await ev(`window.__lcDebug.setSpeed(${sp})`)
    await sleep(3000)
    const fps = [], cpu = [], cpuMax = []; let q = 0, miss = 0, last, nm = 0
    const end = Date.now() + 5000
    while (Date.now() < end) {
      const r = await ev(`(() => { const D = window.__lcDebug; return { s: D.stats(), c: D.citizenStats() } })()`)
      fps.push(r.s.fps); last = r.s; cpu.push(r.c.cpu.avg); cpuMax.push(r.c.cpu.last); q = Math.max(q, r.c.perf.pathQueue); miss += r.c.perf.pathMisses; nm++
      await sleep(100)
    }
    const heap = await gcHeap()
    await ev(`window.__lt = 0; new PerformanceObserver((l) => { window.__lt += l.getEntries().length }).observe({ entryTypes: ['longtask'] })`)
    const dEnd = Date.now() + 5000; let i = 0
    await mouse('mouseMoved', 960, 540, { buttons: 0 }); await mouse('mousePressed', 960, 540)
    while (Date.now() < dEnd) {
      i++
      await mouse('mouseMoved', 960 + 200 * Math.sin(i / 8), 540 + 120 * Math.cos(i / 8), { buttons: 1 })
      if (i % 10 === 0) await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 960, y: 540, deltaX: 0, deltaY: (i / 10) % 2 ? -120 : 120 })
      await sleep(30)
    }
    await mouse('mouseReleased', 960, 540, { buttons: 0 })
    const longTasks = await ev('window.__lt')
    const avg = (a) => a.reduce((x, y) => x + y, 0) / (a.length || 1)
    rows.push({ n, sp, fps: avg(fps), calls: last.calls, tris: last.triangles, geo: last.geometries, heapMB: heap / 1048576, cpuAvg: avg(cpu), cpuMax: Math.max(...cpuMax), q, miss: miss / nm, longTasks })
  }
  report.perfRows = rows
  const f = (x, d = 2) => x.toFixed(d)
  console.log(`GPU: ${gpu}\n\n| citizens | speed | fps avg | calls | triangles | geometries | heap MB | cpu avg ms | cpu max ms | path queue max | path misses avg | long tasks (drag 5s) |\n|---|---|---|---|---|---|---|---|---|---|---|---|`)
  for (const r of rows) console.log(`| ${r.n} | x${r.sp} | ${f(r.fps, 1)} | ${r.calls} | ${r.tris} | ${r.geo} | ${f(r.heapMB, 1)} | ${f(r.cpuAvg)} | ${f(r.cpuMax)} | ${r.q} | ${f(r.miss, 1)} | ${r.longTasks} |`)
  for (const sp of [1, 16]) {
    const a = rows.find((r) => r.n === 1000 && r.sp === sp), z = rows.find((r) => r.n === 0 && r.sp === sp)
    crit(`P3-AC13 x${sp} cpu avg <2 ms`, a.cpuAvg < 2, a.cpuAvg)
    crit(`P3-AC13 x${sp} long tasks 0`, a.longTasks === 0, a.longTasks)
    crit(`P3-AC13 x${sp} calls(1000)-calls(0)<=2`, a.calls - z.calls <= 2, { a: a.calls, z: z.calls })
  }
}

let exitCode = 1
try { await main(); exitCode = Object.values(report.criteria).every((c) => c.pass) ? 0 : 1 }
catch (e) { report.errors.push('FATAL: ' + e.message); crit('script completed', false, e.message) }
finally {
  try { ws?.close() } catch {}
  chrome?.kill('SIGKILL')
  await sleep(300)
  try { rmSync(profile, { recursive: true, force: true }) } catch {}
}
console.log(JSON.stringify(report, null, 2))
for (const [k, c] of Object.entries(report.criteria)) console.log(`${c.pass ? 'PASS' : 'FAIL'}  ${k}`)
console.log(exitCode === 0 ? 'RESULT: PASS' : 'RESULT: FAIL')
process.exit(exitCode)
