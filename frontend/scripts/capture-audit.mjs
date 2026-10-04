import { chromium } from '@playwright/test'
import { mkdirSync, readFileSync } from 'node:fs'
const folder = '../artifacts/routefuel-audit'
const backend = process.argv[2] || 'http://127.0.0.1:8001'
mkdirSync(folder, { recursive: true })
const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader'] })
const page = await browser.newPage()
await page.goto('http://127.0.0.1:5187/static/routefuel/')
await page.waitForFunction(() => document.querySelector('.globe-canvas canvas'))
await page.evaluate(() => document.fonts.ready)
await page.waitForTimeout(1400)
for (const [name, width, height] of [
  ['desktop', 1440, 900],
  ['wide', 1920, 1080],
  ['mobile', 390, 844],
]) {
  await page.setViewportSize({ width, height })
  await page.screenshot({ path: `${folder}/after-${name}.png`, fullPage: true })
}
await page.setViewportSize({ width: 1440, height: 900 })
for (const [name, tokens] of [
  ['paper-navy-orange', {}],
  [
    'stone-charcoal-petrol',
    {
      paper: '#eeeae2',
      surface: '#faf8f3',
      ink: '#273331',
      muted: '#56665f',
      route: '#20644f',
      'route-bright': '#277b5f',
      'route-tint': '#e0e9e0',
    },
  ],
  [
    'gray-ink-yellow',
    {
      paper: '#edf0f2',
      surface: '#f8fafb',
      ink: '#17324c',
      muted: '#536374',
      route: '#705d12',
      'route-bright': '#b29412',
      'route-tint': '#f1ebd1',
    },
  ],
]) {
  await page.evaluate((values) => {
    for (const [key, value] of Object.entries(values))
      document.documentElement.style.setProperty('--' + key, value)
  }, tokens)
  await page.screenshot({ path: `${folder}/palette-${name}.png` })
  await page.evaluate(() => document.documentElement.removeAttribute('style'))
}
await page.route('**/api/v1/locations/**', async (route) =>
  route.fulfill({
    response: await page.request.get(
      backend + new URL(route.request().url()).pathname + new URL(route.request().url()).search,
    ),
  }),
)
for (const [name, width, height] of [
  ['desktop', 1440, 900],
  ['mobile', 390, 844],
]) {
  await page.setViewportSize({ width, height })
  if (await page.getByRole('button', { name: 'Clear FROM' }).count())
    await page.getByRole('button', { name: 'Clear FROM' }).click()
  await page.getByRole('combobox', { name: 'FROM' }).fill('Dallas')
  await page.getByRole('option').first().waitFor()
  await page.screenshot({ path: `${folder}/search-${name}.png`, fullPage: true })
  await page.getByRole('combobox', { name: 'FROM' }).press('Escape')
}
await page.setViewportSize({ width: 1440, height: 900 })
const fixture = JSON.parse(readFileSync('src/test/route.json', 'utf8').replace(/^\uFEFF/, ''))
await page.route('**/api/v1/route/', (route) => route.fulfill({ json: fixture }))
await page.getByRole('combobox', { name: 'TO' }).fill('Los Angeles, CA')
await page.getByRole('button', { name: 'PLAN ROUTE' }).click()
await page.getByTestId('route-map').waitFor()
await page.waitForFunction(
  () => document.querySelector('[data-testid="route-map"]')?.dataset.drawn === 'true',
)
await page.screenshot({ path: `${folder}/map-palette-paper.png`, fullPage: true })
await browser.close()
