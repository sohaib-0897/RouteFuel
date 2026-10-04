import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readFileSync } from 'node:fs'
const fixture = JSON.parse(
  readFileSync(new URL('../src/test/route.json', import.meta.url), 'utf8').replace(/^\uFEFF/, ''),
)
import { mkdirSync } from 'node:fs'
const folder = '../artifacts/routefuel-redesign'
mkdirSync(folder, { recursive: true })
test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/locations/**', (route) => {
    const query = new URL(route.request().url()).searchParams.get('q') || ''
    const dallas = /dall/i.test(query)
    return route.fulfill({
      json: {
        results: dallas
          ? [
              { id: 'dallas', name: 'Dallas', context: 'Dallas, Texas', query: 'Dallas, TX' },
              {
                id: 'airport',
                name: 'Dallas Love Field',
                context: 'Dallas, Texas',
                query: 'Dallas Love Field, Dallas, TX',
              },
            ]
          : [
              {
                id: 'la',
                name: 'Los Angeles',
                context: 'Los Angeles, California',
                query: 'Los Angeles, CA',
              },
            ],
      },
    })
  })
})
test('real WebGL route experience, keyboard, errors, and mobile layouts', async ({ page }) => {
  test.setTimeout(180000)
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })
  let requests = 0
  let releaseResponse!: () => void
  const responseGate = new Promise<void>((resolve) => {
    releaseResponse = resolve
  })
  await page.route('**/api/v1/route/', async (route) => {
    requests++
    expect(route.request().method()).toBe('POST')
    expect(route.request().postDataJSON()).toEqual({
      start: 'Dallas, TX',
      finish: 'Los Angeles, CA',
    })
    await responseGate
    await route.fulfill({ json: fixture })
  })
  await page.goto('/static/routefuel/')
  await expect(page.getByRole('heading', { name: 'EVERY MILE. OPTIMIZED.' })).toBeVisible()
  await page.waitForFunction(() => !!document.querySelector('.globe-canvas canvas'))
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(1800)
  for (const [name, width, height] of [
    ['desktop', 1440, 900],
    ['wide', 1920, 1080],
    ['tablet', 820, 1180],
    ['mobile', 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height })
    await page.screenshot({ path: folder + '/hero-' + name + '.png', fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.getByRole('button', { name: 'PLAN ROUTE' }).click()
  await expect(page.getByRole('alert')).toContainText('Enter a starting location')
  await page.screenshot({ path: folder + '/validation-error.png' })
  await page.getByRole('combobox', { name: 'FROM' }).fill('Dallas, TX')
  await expect(page.getByRole('option')).toHaveCount(2)
  await page.getByRole('combobox', { name: 'FROM' }).press('ArrowDown')
  await page.getByRole('combobox', { name: 'FROM' }).press('Enter')
  await page.getByRole('combobox', { name: 'TO' }).fill('Los Angeles, CA')
  await expect(page.getByRole('option')).toHaveCount(1)
  await page.getByRole('combobox', { name: 'TO' }).press('Enter')
  await page.getByRole('button', { name: 'PLAN ROUTE' }).click()
  await expect(page.getByRole('status')).toContainText(
    /Finding your route|Locating viable fuel stops|Optimizing fuel cost/,
  )
  await page.screenshot({ path: folder + '/loading.png' })
  releaseResponse()
  await expect(page.getByLabel('Route summary')).toContainText('$426.77')
  await expect(page.getByTestId('route-map')).toHaveAttribute('data-drawn', 'true')
  await expect(page.locator('.fuel-marker')).toHaveCount(3)
  await expect(page.locator('.fuel-marker').last()).toBeVisible()
  expect(requests).toBe(1)
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(1800)
  await page.screenshot({ path: folder + '/result-desktop.png', fullPage: true })
  await page.screenshot({ path: folder + '/result-desktop-viewport.png' })
  const a11y = await new AxeBuilder({ page }).analyze()
  expect(a11y.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.html) }))).toEqual([])
  await page.getByRole('button', { name: /Focus stop 2:/ }).click()
  await expect(page.locator('#stop-2')).toHaveClass(/selected/)
  await expect(page.locator('.fuel-marker').nth(1)).toHaveClass(/is-active/)
  await page.locator('.fuel-marker').nth(1).click()
  await expect(page.locator('.maplibregl-popup')).toContainText('Approximate station area')
  await page.screenshot({ path: folder + '/station-detail.png' })
  await page.getByRole('button', { name: 'Close popup' }).click()
  const toggle = page.getByRole('switch', { name: 'Detailed road map' })
  await toggle.focus()
  await page.keyboard.press('Space')
  await expect(toggle).not.toBeChecked()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: folder + '/globe-overview.png' })
  await page.keyboard.press('Space')
  await expect(toggle).toBeChecked()
  await expect(page.getByTestId('route-map')).toHaveAttribute('data-drawn', 'true')
  for (const [name, width, height] of [
    ['wide', 1920, 1080],
    ['tablet', 820, 1180],
    ['mobile', 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height })
    await page.evaluate(() => scrollTo(0, 0))
    await page.getByRole('button', { name: 'Fit route' }).click()
    await page.waitForTimeout(800)
    await page.screenshot({ path: folder + '/result-' + name + '.png', fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.getByRole('button', { name: /Plan another route/ }).click()
  await expect(page.getByRole('combobox', { name: 'FROM' })).toHaveValue('Dallas, TX')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('button', { name: 'PLAN ROUTE' }).click()
  await expect(page.getByTestId('route-map')).toHaveAttribute('data-drawn', 'true')
  await page.screenshot({ path: folder + '/reduced-motion.png', fullPage: true })
  expect(errors).toEqual([])
})
test('service errors keep inputs and allow retry', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  let attempt = 0
  await page.route('**/api/v1/route/', (route) =>
    ++attempt === 1
      ? route.fulfill({
          status: 503,
          json: {
            error: {
              code: 'provider_unavailable',
              message: 'The routing service is unavailable. Please try again shortly.',
            },
          },
        })
      : route.fulfill({ json: fixture }),
  )
  await page.goto('/static/routefuel/')
  await page.getByRole('combobox', { name: 'FROM' }).fill('Dallas, TX')
  await page.getByRole('combobox', { name: 'TO' }).fill('Los Angeles, CA')
  await page.getByRole('button', { name: 'PLAN ROUTE' }).click()
  await expect(page.getByRole('alert')).toContainText('routing service is unavailable')
  await page.screenshot({ path: folder + '/service-error.png' })
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByLabel('Route summary')).toContainText('$426.77')
})

test('mobile reduced motion, long station names and visible keyboard focus', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const longFixture = structuredClone(fixture)
  longFixture.fuel_stops[0].name =
    'A VERY LONG TRUCKSTOP NAME FOR MOBILE LAYOUT AND ACCESSIBILITY VERIFICATION'
  await page.route('**/api/v1/route/', (route) => route.fulfill({ json: longFixture }))
  await page.goto('/static/routefuel/')
  const start = page.getByRole('combobox', { name: 'FROM' })
  await start.focus()
  await page.screenshot({ path: folder + '/keyboard-focus.png' })
  const heroAudit = await new AxeBuilder({ page }).analyze()
  expect(heroAudit.violations).toEqual([])
  await start.fill('Dallas, TX')
  await page.getByRole('combobox', { name: 'TO' }).fill('Los Angeles, CA')
  await page.getByRole('combobox', { name: 'TO' }).press('Escape')
  await page.getByRole('combobox', { name: 'TO' }).press('Enter')
  await expect(page.getByTestId('route-map')).toHaveAttribute('data-drawn', 'true')
  expect(await page.locator('canvas').count()).toBe(1)
  await expect(page.getByRole('button', { name: /Focus stop 1:/ })).toContainText(
    'A VERY LONG TRUCKSTOP',
  )
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: folder + '/reduced-motion-long-name.png', fullPage: true })
  const resultAudit = await new AxeBuilder({ page }).analyze()
  expect(resultAudit.violations).toEqual([])
})

test('autocomplete keyboard, pointer, clear and mobile accessibility', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/static/routefuel/')
  const input = page.getByRole('combobox', { name: 'FROM' })
  await input.fill('Dallas')
  await expect(page.getByRole('option')).toHaveCount(2)
  await input.press('ArrowUp')
  await expect(page.getByRole('option').last()).toHaveAttribute('aria-selected', 'true')
  await page.screenshot({ path: folder + '/autocomplete-mobile.png', fullPage: true })
  const audit = await new AxeBuilder({ page }).analyze()
  expect(audit.violations).toEqual([])
  await input.press('Enter')
  await expect(input).toHaveValue('Dallas Love Field, Dallas, TX')
  await expect(input).toHaveAttribute('aria-expanded', 'false')
  await page.getByRole('button', { name: 'Clear FROM' }).click()
  await expect(input).toHaveValue('')
  await input.fill('Dallas')
  await expect(page.getByRole('option')).toHaveCount(2)
  await input.press('Escape')
  await expect(page.getByRole('listbox')).toHaveCount(0)
  await input.press('ArrowDown')
  await expect(page.getByRole('option')).toHaveCount(2)
  await page.getByRole('option').first().click()
  await expect(input).toHaveValue('Dallas, TX')
})
