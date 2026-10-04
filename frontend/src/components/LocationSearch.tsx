import { useEffect, useId, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { searchLocations, type Place } from '../api'

export default function LocationSearch({
  label,
  letter,
  value,
  onChange,
  disabled,
  invalid,
  inputRef,
}: {
  label: string
  letter: string
  value: string
  onChange: (value: string) => void
  disabled: boolean
  invalid: boolean
  inputRef?: RefObject<HTMLInputElement | null>
}) {
  const id = useId()
  const ownRef = useRef<HTMLInputElement>(null)
  const ref = inputRef || ownRef
  const dropdown = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState<Place[]>([])
  const [active, setActive] = useState(-1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Place | null>(null)
  const [retry, setRetry] = useState(0)
  const [placement, setPlacement] = useState({ left: 0, top: 0, width: 340, maxHeight: 360 })
  useEffect(() => {
    if (!open || disabled || value.trim().length < 2 || selected?.query === value) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setBusy(true)
      setError('')
      searchLocations(value.trim(), controller.signal)
        .then((places) => {
          if (!controller.signal.aborted) {
            setResults(places)
            setActive(-1)
          }
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setError('Place search unavailable. Retry or enter a full U.S. location.')
        })
        .finally(() => {
          if (!controller.signal.aborted) setBusy(false)
        })
    }, 275)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [value, open, disabled, selected, retry])
  function select(place: Place) {
    setSelected(place)
    onChange(place.query)
    setOpen(false)
    setActive(-1)
    setBusy(false)
    ref.current?.focus()
  }
  const expanded = open && !disabled && value.trim().length >= 2 && selected?.query !== value
  useLayoutEffect(() => {
    if (!expanded) return
    const position = () => {
      if (!ref.current) return
      const rect = ref.current.closest('.location-search')!.getBoundingClientRect()
      const width = Math.min(Math.max(rect.width, 340), window.innerWidth - 32)
      const height = dropdown.current?.offsetHeight || 100
      const viewport = window.visualViewport
      const viewportTop = viewport?.offsetTop || 0
      const viewportHeight = viewport?.height || window.innerHeight
      const bottom = viewportHeight + viewportTop
      const top =
        rect.bottom + height + 8 < bottom
          ? rect.bottom + 8
          : Math.max(viewportTop + 8, rect.top - height - 8)
      setPlacement({
        left: Math.max(16, Math.min(rect.left, window.innerWidth - width - 16)),
        top,
        width,
        maxHeight: Math.max(80, viewportHeight - 24),
      })
    }
    position()
    window.addEventListener('resize', position)
    window.addEventListener('scroll', position, true)
    window.visualViewport?.addEventListener('resize', position)
    window.visualViewport?.addEventListener('scroll', position)
    return () => {
      window.removeEventListener('resize', position)
      window.removeEventListener('scroll', position, true)
      window.visualViewport?.removeEventListener('resize', position)
      window.visualViewport?.removeEventListener('scroll', position)
    }
  }, [expanded, results, error, busy, ref])
  useEffect(() => {
    if (expanded && active >= 0)
      document.getElementById(id + '-option-' + active)?.scrollIntoView({ block: 'nearest' })
  }, [active, expanded, id])
  return (
    <div
      className="location-search"
      onBlur={(event) => {
        if (
          !event.currentTarget.contains(event.relatedTarget) &&
          !dropdown.current?.contains(event.relatedTarget)
        ) {
          setOpen(false)
          setBusy(false)
        }
      }}
    >
      <label htmlFor={id}>
        <span className="endpoint-letter" aria-hidden="true">
          {letter}
        </span>
        <span>{label}</span>
      </label>
      <input
        id={id}
        ref={ref}
        name={label === 'FROM' ? 'start' : 'finish'}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={expanded}
        aria-controls={expanded ? id + '-list' : undefined}
        aria-activedescendant={expanded && active >= 0 ? id + '-option-' + active : undefined}
        aria-invalid={invalid}
        aria-describedby={invalid ? 'form-error' : id + '-hint'}
        autoComplete="off"
        placeholder={label === 'FROM' ? 'City, airport or address' : 'Where are you headed?'}
        value={value}
        maxLength={120}
        disabled={disabled}
        onFocus={() => {
          if (!selected && !value) setOpen(true)
        }}
        onChange={(event) => {
          onChange(event.target.value)
          setSelected(null)
          setResults([])
          setActive(-1)
          setError('')
          setBusy(false)
          setOpen(true)
        }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            setOpen(true)
            if (results.length)
              setActive((index) =>
                event.key === 'ArrowDown'
                  ? (index + 1) % results.length
                  : index <= 0
                    ? results.length - 1
                    : index - 1,
              )
          } else if (event.key === 'Enter' && expanded) {
            event.preventDefault()
            if (results[active >= 0 ? active : 0]) select(results[active >= 0 ? active : 0])
            else {
              setOpen(false)
              setBusy(false)
            }
          } else if (event.key === 'Escape') {
            event.preventDefault()
            setOpen(false)
            setBusy(false)
            setActive(-1)
          }
        }}
      />
      <span id={id + '-hint'} className="sr-only">
        Search U.S. places. Use arrow keys and Enter to select.
      </span>
      {value && !disabled && (
        <button
          type="button"
          className="location-clear"
          aria-label={'Clear ' + label}
          onClick={() => {
            onChange('')
            setSelected(null)
            setResults([])
            setOpen(false)
            setBusy(false)
            ref.current?.focus()
          }}
        >
          ×
        </button>
      )}
      {expanded &&
        createPortal(
          <div
            ref={dropdown}
            className="location-dropdown"
            role="region"
            aria-label={label + ' place search'}
            style={placement}
            onBlur={(event) => {
              if (
                !dropdown.current?.contains(event.relatedTarget) &&
                event.relatedTarget !== ref.current
              )
                setOpen(false)
            }}
          >
            <div className="search-heading">U.S. LOCATIONS</div>
            <ul id={id + '-list'} role="listbox" aria-label={label + ' suggestions'}>
              {results.map((place, index) => (
                <li
                  role="option"
                  key={place.id + index}
                  id={id + '-option-' + index}
                  aria-selected={index === active}
                  className={index === active ? 'location-option active' : 'location-option'}
                  onPointerDown={(event) => event.preventDefault()}
                  onClick={() => select(place)}
                  onPointerMove={() => setActive(index)}
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 21s7-6 7-12a7 7 0 1 0-14 0c0 6 7 12 7 12Z" />
                    <circle cx="12" cy="9" r="2.5" />
                  </svg>
                  <span>
                    <strong>{place.name}</strong>
                    <small>{place.context}</small>
                  </span>
                  <span className="option-enter" aria-hidden="true">
                    ↵
                  </span>
                </li>
              ))}
            </ul>
            <p className="search-status" role="status">
              {busy
                ? 'Searching places…'
                : error ||
                  (!results.length
                    ? 'No matches yet. Try a city, airport or full address.'
                    : '↑ ↓ to navigate · Enter to select')}
            </p>
            {error && (
              <button type="button" className="search-retry" onClick={() => setRetry((n) => n + 1)}>
                Retry place search
              </button>
            )}
          </div>,
          document.body,
        )}
    </div>
  )
}
