import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import fixture from './route.json'
import { parsePlan, requestRoute, validateLocations } from '../api'
import { orderedStops } from '../types'
vi.mock('../components/Globe', () => ({ default: () => <div aria-label="Globe overview" /> }))
vi.mock('../components/RouteMap', () => ({ default: () => <div data-testid="route-map" /> }))
vi.mock('motion/react', async () => {
  const actual = await vi.importActual<object>('motion/react')
  return { ...actual, useReducedMotion: () => true }
})
const response = (data: unknown = fixture, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response()))
})
async function fillAndSubmit() {
  const user = userEvent.setup()
  await user.type(screen.getByRole('combobox', { name: 'FROM' }), 'Dallas, TX')
  await user.type(screen.getByRole('combobox', { name: 'TO' }), 'Los Angeles, CA')
  await user.click(screen.getByRole('button', { name: 'PLAN ROUTE' }))
  return user
}
describe('API boundary', () => {
  it('validates blanks and equivalent locations', () => {
    expect(validateLocations('', 'LA')).toContain('starting')
    expect(validateLocations('Dallas', ' ')).toContain('destination')
    expect(validateLocations(' Dallas, TX ', 'dallas, tx')).toContain('different')
  })
  it('constructs the exact trimmed Django POST', async () => {
    await requestRoute(' Dallas, TX ', ' Los Angeles, CA ')
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/route/',
      expect.objectContaining({
        method: 'POST',
        body: '{"start":"Dallas, TX","finish":"Los Angeles, CA"}',
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })
  it('accepts recorded backend results and preserves geometry and costs', () => {
    const plan = parsePlan(fixture)
    expect(plan.route.geometry).toEqual(fixture.route.geometry)
    expect(plan.fuel.estimated_fuel_cost_usd).toBe(426.77)
  })
  it('rejects missing geometry and invalid coordinates', () => {
    expect(() => parsePlan({ ...fixture, route: {} })).toThrow('incomplete')
    expect(() => parsePlan({ ...fixture, start: { ...fixture.start, longitude: 400 } })).toThrow(
      'incomplete',
    )
  })
  it('orders stops using backend sequence, not coordinates or array order', () => {
    expect(
      orderedStops(parsePlan({ ...fixture, fuel_stops: [...fixture.fuel_stops].reverse() })).map(
        (s) => s.sequence,
      ),
    ).toEqual([1, 2, 3])
  })
  it.each([422, 503, 504, 500])('handles HTTP %s without leaking JSON', async (status) => {
    vi.mocked(fetch).mockResolvedValueOnce(
      response({ error: { code: 'test', message: 'Cannot resolve this U.S. location.' } }, status),
    )
    await expect(requestRoute('x', 'y')).rejects.toThrow('Cannot resolve this U.S. location.')
  })
})
describe('route experience', () => {
  it('rejects empty submission without calling the API', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'PLAN ROUTE' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a starting location')
    expect(fetch).not.toHaveBeenCalled()
  })
  it('shows loading while the actual request is pending', async () => {
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(() => {}))
    render(<App />)
    await fillAndSubmit()
    expect(screen.getByRole('status')).toHaveTextContent('Finding your route')
    expect(screen.getByRole('button', { name: 'PLANNING' })).toBeDisabled()
  })
  it('shows actual summary, purchase disclosures, and accuracy metadata', async () => {
    render(<App />)
    await fillAndSubmit()
    expect(
      await screen.findByRole('heading', { name: /Dallas, TX.*Los Angeles, CA/ }),
    ).toBeVisible()
    expect(screen.getByLabelText('Route summary')).toHaveTextContent('$426.77')
    expect(screen.getByLabelText('Route summary')).toHaveTextContent('1,443')
    expect(screen.getAllByText('Approximate station area')).toHaveLength(2)
    expect(screen.getByText('Census address estimate')).toBeVisible()
    expect(screen.getByText('How origin fuel is priced')).toBeVisible()
    expect(await screen.findByTestId('route-map')).toBeVisible()
  })
  it('retains input, reports API failure, and retries successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      response({ error: { message: 'No feasible fuel itinerary.' } }, 422),
    )
    render(<App />)
    const user = await fillAndSubmit()
    expect(await screen.findByRole('alert')).toHaveTextContent('No feasible fuel itinerary.')
    expect(screen.getByRole('combobox', { name: 'FROM' })).toHaveValue('Dallas, TX')
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByLabelText('Route summary')).toHaveTextContent('$426.77')
  })
  it('allows Enter submission, keyboard switch, and resets result state', async () => {
    render(<App />)
    const user = userEvent.setup()
    await user.type(screen.getByRole('combobox', { name: 'FROM' }), 'Dallas, TX')
    await user.type(screen.getByRole('combobox', { name: 'TO' }), 'Los Angeles, CA{Escape}{Enter}')
    const toggle = await screen.findByRole('switch', { name: 'Detailed road map' })
    expect(toggle).toBeChecked()
    toggle.focus()
    await user.keyboard(' ')
    expect(toggle).not.toBeChecked()
    await user.click(screen.getByRole('button', { name: /Plan another route/ }))
    await waitFor(() => expect(screen.queryByLabelText('Route summary')).not.toBeInTheDocument())
    expect(screen.getByRole('combobox', { name: 'FROM' })).toHaveValue('Dallas, TX')
    expect(screen.getByRole('combobox', { name: 'FROM' })).toHaveFocus()
  })
})
