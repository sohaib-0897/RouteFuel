import { chromium } from '@playwright/test'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import assert from 'node:assert/strict'
import AxeBuilder from '@axe-core/playwright'
const base = process.argv[2] || process.env.ROUTEFUEL_BASE_URL || 'http://127.0.0.1:8005'
const output = '../artifacts/routefuel-production'
mkdirSync(output, { recursive: true })
for (const path of ['/', '/health/', '/api/docs/', '/api/schema/']) {
  const response = await fetch(base + path)
  assert.equal(response.status, 200, path)
}
const browser = await chromium.launch({ headless: true, args: ['--enable-unsafe-swiftshader'] })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text())
})
await page.addInitScript(() => {
  window.__qa = { cls: 0, longTasks: [], lcp: 0 }
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) if (!e.hadRecentInput) window.__qa.cls += e.value
  }).observe({ type: 'layout-shift', buffered: true })
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) window.__qa.longTasks.push(e.duration)
  }).observe({ type: 'longtask', buffered: true })
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) window.__qa.lcp = e.startTime
  }).observe({ type: 'largest-contentful-paint', buffered: true })
})
await page.goto(base, { waitUntil: 'networkidle' })
await page.evaluate(() => document.fonts.ready)
await page.screenshot({ path: output + '/hero.png' })
const performanceResult = await page.evaluate(() => ({
  ...window.__qa,
  resources: performance
    .getEntriesByType('resource')
    .filter((e) => e.name.includes('/static/routefuel/'))
    .map((e) => ({ name: e.name.split('/').pop(), bytes: e.transferSize, duration: e.duration })),
  canvases: document.querySelectorAll('canvas').length,
}))
const timings = []
async function selectPlace(label, city, context, query) {
  const input = page.getByRole('combobox', { name: label })
  await input.fill(city)
  await page.getByRole('option').filter({ hasText: context }).first().click({ timeout: 20000 })
  assert.equal(await input.inputValue(), query)
}
for (const [name, finish] of [
  ['dallas-la', 'Los Angeles, CA'],
  ['dallas-austin', 'Austin, TX'],
]) {
  if (name !== 'dallas-la') await page.getByRole('button', { name: /Plan another route/ }).click()
  await selectPlace('FROM', 'Dallas', 'Dallas, Texas', 'Dallas, TX')
  await selectPlace(
    'TO',
    name === 'dallas-la' ? 'Los Angeles' : 'Austin',
    name === 'dallas-la' ? 'Los Angeles, California' : 'Austin, Texas',
    finish,
  )
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith('/api/v1/route/') && r.request().method() === 'POST',
    { timeout: 110000 },
  )
  const started = Date.now()
  await page.getByRole('button', { name: 'PLAN ROUTE' }).click()
  const response = await responsePromise
  assert.equal(response.status(), 200)
  const plan = await response.json()
  const seconds = (Date.now() - started) / 1000
  const baseline = JSON.parse(
    readFileSync('../artifacts/routefuel-baseline/' + name + '.json', 'utf8'),
  )
  for (const key of [
    'route',
    'fuel_stops',
    'initial_fueling',
    'vehicle',
    'fuel',
    'optimization',
    'warnings',
  ])
    assert.deepEqual(plan[key], baseline[key], key)
  await page.getByTestId('route-map').waitFor({ timeout: 40000 })
  await page.waitForFunction(
    () => document.querySelector('[data-testid="route-map"]')?.dataset.drawn === 'true',
    { timeout: 30000 },
  )
  await page.waitForTimeout(1000)
  assert.equal(await page.locator('.fuel-marker').count(), plan.fuel_stops.length)
  assert.equal(await page.locator('canvas').count(), 1)
  await page.screenshot({ path: output + '/' + name + '.png', fullPage: true })
  if (name === 'dallas-la') {
    for (const [viewport, width, height] of [
      ['wide', 1920, 1080],
      ['mobile', 390, 844],
    ]) {
      await page.setViewportSize({ width, height })
      await page.evaluate(() => scrollTo(0, 0))
      await page.getByRole('button', { name: 'Fit route' }).click()
      await page.waitForTimeout(1200)
      await page.screenshot({ path: output + '/' + name + '-' + viewport + '.png', fullPage: true })
      assert.equal(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        true,
      )
    }
    const audit = await new AxeBuilder({ page }).analyze()
    assert.deepEqual(audit.violations, [])
    await page.setViewportSize({ width: 1440, height: 900 })
  }
  const mapResponse = await fetch(base + plan.map_url)
  assert.equal(mapResponse.status, 200)
  timings.push({
    route: name,
    seconds,
    cost: plan.fuel.estimated_fuel_cost_usd,
    stops: plan.fuel_stops.length,
    exactRegressionMatch: true,
  })
}
assert.deepEqual(errors, [])
const result = {
  endpoints: 'root,health,swagger,schema and fallback map: 200',
  timings,
  consoleErrors: errors,
  performance: performanceResult,
}
writeFileSync(output + '/report.json', JSON.stringify(result, null, 2))
console.log(
  JSON.stringify(
    {
      ...result,
      performance: {
        cls: performanceResult.cls,
        lcpMs: performanceResult.lcp,
        longTasks: performanceResult.longTasks.length,
        maxLongTaskMs: Math.max(0, ...performanceResult.longTasks),
        canvases: performanceResult.canvases,
      },
    },
    null,
    2,
  ),
)
await context.close()
await browser.close()
