import { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import LocationSearch from '../components/LocationSearch'
const places = [
  { id: 'dallas', name: 'Dallas', context: 'Dallas, Texas', query: 'Dallas, TX' },
  {
    id: 'airport',
    name: 'Dallas Love Field',
    context: 'Dallas, Texas',
    query: 'Dallas Love Field, Dallas, TX',
  },
]
function Harness({ initialValue = '' }: { initialValue?: string }) {
  const [value, setValue] = useState(initialValue)
  return (
    <LocationSearch
      label="FROM"
      letter="A"
      value={value}
      onChange={setValue}
      disabled={false}
      invalid={false}
    />
  )
}
beforeEach(() =>
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ results: places }))),
  ),
)
it('keeps restored route fields closed on focus until edited', async () => {
  const user = userEvent.setup()
  render(<Harness initialValue="Dallas, TX" />)
  const input = screen.getByRole('combobox', { name: 'FROM' })
  await user.click(input)
  expect(input).toHaveAttribute('aria-expanded', 'false')
  expect(fetch).not.toHaveBeenCalled()
  await user.type(input, 'x')
  expect(input).toHaveAttribute('aria-expanded', 'true')
})
it('debounces typing and uses server results with name and context', async () => {
  render(<Harness />)
  const input = screen.getByRole('combobox', { name: 'FROM' })
  fireEvent.change(input, { target: { value: 'Da' } })
  fireEvent.change(input, { target: { value: 'Dall' } })
  fireEvent.change(input, { target: { value: 'Dallas' } })
  expect(fetch).not.toHaveBeenCalled()
  await screen.findByRole('option', { name: /Dallas Love Field/ })
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch).toHaveBeenCalledWith(
    '/api/v1/locations/?q=Dallas',
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  )
  expect(screen.getAllByText('Dallas, Texas')).toHaveLength(2)
})
it('supports arrow navigation, Enter selection, Escape and clear', async () => {
  const user = userEvent.setup()
  render(<Harness />)
  const input = screen.getByRole('combobox', { name: 'FROM' })
  await user.type(input, 'Dallas')
  await screen.findByRole('option', { name: /Dallas Love Field/ })
  await user.keyboard('{ArrowUp}')
  expect(screen.getByRole('option', { name: /Dallas Love Field/ })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await user.keyboard('{ArrowDown}{Enter}')
  expect(input).toHaveValue('Dallas, TX')
  expect(input).toHaveAttribute('aria-expanded', 'false')
  await user.click(screen.getByRole('button', { name: 'Clear FROM' }))
  expect(input).toHaveValue('')
  await user.type(input, 'Dallas')
  await screen.findByRole('listbox')
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})
it('ignores an aborted late response after the query changes', async () => {
  let resolve!: (response: Response) => void
  vi.mocked(fetch).mockImplementationOnce(
    () =>
      new Promise((r) => {
        resolve = r
      }),
  )
  render(<Harness />)
  const input = screen.getByRole('combobox', { name: 'FROM' })
  fireEvent.change(input, { target: { value: 'Dallas' } })
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
  const signal = vi.mocked(fetch).mock.calls[0][1]?.signal
  fireEvent.change(input, { target: { value: 'Los' } })
  expect(signal?.aborted).toBe(true)
  resolve(new Response(JSON.stringify({ results: [places[1]] })))
  expect(screen.queryByRole('option', { name: /Dallas Love Field/ })).not.toBeInTheDocument()
})
it('shows errors and permits a search retry', async () => {
  vi.mocked(fetch).mockRejectedValueOnce(new TypeError('offline'))
  const user = userEvent.setup()
  render(<Harness />)
  await user.type(screen.getByRole('combobox', { name: 'FROM' }), 'Dallas')
  await user.click(await screen.findByRole('button', { name: 'Retry place search' }))
  expect(await screen.findByRole('option', { name: /Dallas Love Field/ })).toBeVisible()
})
