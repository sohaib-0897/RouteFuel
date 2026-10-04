import { useEffect, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import type { ViewMode } from '../types'

export function RouteLoader() {
  const [stage, setStage] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setStage((s) => Math.min(s + 1, 2)), 2800)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="processing" role="status" aria-live="polite">
      <div className="cradle" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((i) => (
          <span key={i} />
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.span
          key={stage}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {['Finding your route', 'Locating viable fuel stops', 'Optimizing fuel cost'][stage]}
        </motion.span>
      </AnimatePresence>
      <span className="processing-note">Django is calculating your plan</span>
    </div>
  )
}
export function ReadyStatus() {
  const reduced = useReducedMotion()
  return (
    <span className="ready-status" role="status" aria-live="polite">
      <motion.span
        className="check-control"
        initial={reduced ? false : { scale: 1.1 }}
        animate={{ scale: 1 }}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <motion.path
            d="m6 12 4 4 8-9"
            initial={reduced ? false : { pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: reduced ? 0 : 0.24 }}
          />
        </svg>
      </motion.span>
      ROUTE READY
    </span>
  )
}
export function ViewSwitch({
  value,
  onChange,
}: {
  value: ViewMode
  onChange: (v: ViewMode) => void
}) {
  return (
    <div className="view-switch">
      <span aria-hidden="true">GLOBE</span>
      <button
        type="button"
        role="switch"
        aria-checked={value === 'map'}
        aria-label="Detailed road map"
        onClick={() => onChange(value === 'map' ? 'globe' : 'map')}
        className={value === 'map' ? 'liquid-switch checked' : 'liquid-switch'}
      >
        <span />
      </button>
      <span aria-hidden="true">MAP</span>
    </div>
  )
}
export function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      {diagonal ? <path d="M6 18 18 6M6 6h12v12" /> : <path d="M4 12h16m-6-6 6 6-6 6" />}
    </svg>
  )
}
