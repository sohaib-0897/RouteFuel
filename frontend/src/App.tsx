import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { apiUrl, requestRoute, validateLocations } from './api'
import { money, number, orderedStops, type RoutePlan, type ViewMode } from './types'
import { Arrow, ReadyStatus, RouteLoader, ViewSwitch } from './components/Controls'
import WebGLBoundary from './components/WebGLBoundary'
import LocationSearch from './components/LocationSearch'

const Globe = lazy(() => import('./components/Globe'))
const loadRouteMap = () => import('./components/RouteMap')
const RouteMap = lazy(loadRouteMap)
gsap.registerPlugin(ScrollTrigger)
const github = import.meta.env.VITE_GITHUB_URL
export default function App() {
  const [start, setStart] = useState('')
  const [finish, setFinish] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [plan, setPlan] = useState<RoutePlan | null>(null)
  const [mode, setMode] = useState<ViewMode>('globe')
  const [revealing, setRevealing] = useState(false)
  const [mapReady, setMapReady] = useState(false)
  const [active, setActive] = useState<number | null>(null)
  const [walkthrough, setWalkthrough] = useState(false)
  const reduce = !!useReducedMotion()
  const controller = useRef<AbortController | null>(null)
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const focusPlannerAfterReset = useRef(false)
  const shell = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const resultHeading = useRef<HTMLHeadingElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const stops = plan ? orderedStops(plan) : []
  const mapDidDraw = useCallback(() => setMapReady(true), [])
  useEffect(() => {
    if (loading) void loadRouteMap().catch(() => undefined)
  }, [loading])
  useEffect(
    () => () => {
      controller.current?.abort()
      if (timeout.current) clearTimeout(timeout.current)
    },
    [],
  )
  useEffect(() => {
    if (!plan && focusPlannerAfterReset.current) {
      focusPlannerAfterReset.current = false
      input.current?.focus()
    }
  }, [plan])
  useEffect(() => {
    if (!plan || !revealing) return
    // GSAP owns the geographic wrapper; Motion owns the content inside it.
    const ctx = gsap.context(() => {
      const timeline = gsap.timeline({
        onComplete: () => {
          setMode('map')
          setRevealing(false)
          requestAnimationFrame(() => resultHeading.current?.focus({ preventScroll: true }))
        },
      })
      if (reduce) timeline.to(stage.current, { opacity: 1, duration: 0 })
      else
        timeline
          .to(stage.current, { scale: 1.04, duration: 1.7, ease: 'power2.inOut' })
          .to(stage.current, { opacity: 0, duration: 0.25 })
    }, shell)
    return () => ctx.revert()
  }, [plan, revealing, reduce])
  useEffect(() => {
    if (!plan || !walkthrough || mode !== 'map') return
    const mm = gsap.matchMedia()
    mm.add('(min-width: 1000px) and (prefers-reduced-motion: no-preference)', () => {
      shell.current?.querySelectorAll<HTMLElement>('[data-story]').forEach((el) => {
        ScrollTrigger.create({
          trigger: el,
          start: 'top 60%',
          end: 'bottom 60%',
          onEnter: () => setActive(Number(el.dataset.story)),
          onEnterBack: () => setActive(Number(el.dataset.story)),
        })
      })
    })
    return () => mm.revert()
  }, [plan, walkthrough, mode])
  const chooseStop = useCallback(
    (sequence: number | null) => {
      setActive(sequence)
      document
        .getElementById('stop-' + sequence)
        ?.scrollIntoView({ behavior: reduce ? 'instant' : 'smooth', block: 'nearest' })
    },
    [reduce],
  )
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (loading) return
    const invalid = validateLocations(start, finish)
    if (invalid) {
      setError(invalid)
      if (!start.trim()) input.current?.focus()
      return
    }
    controller.current?.abort()
    const request = new AbortController()
    controller.current = request
    setError('')
    setLoading(true)
    timeout.current = setTimeout(() => request.abort('timeout'), 100000)
    try {
      const result = await requestRoute(start, finish, request.signal)
      if (request.signal.aborted) return
      setPlan(result)
      setMapReady(false)
      setActive(null)
      setMode(reduce ? 'map' : 'globe')
      setRevealing(!reduce)
      if (reduce) requestAnimationFrame(() => resultHeading.current?.focus({ preventScroll: true }))
    } catch (e) {
      if (request.signal.aborted && request.signal.reason !== 'timeout') return
      setError(
        request.signal.aborted
          ? 'The request timed out. Please try again.'
          : e instanceof TypeError
            ? 'Could not reach the route service. Check your connection and retry.'
            : e instanceof Error
              ? e.message
              : 'Could not plan this route. Please try again.',
      )
    } finally {
      if (timeout.current) clearTimeout(timeout.current)
      if (controller.current === request) setLoading(false)
    }
  }
  function reset() {
    controller.current?.abort()
    focusPlannerAfterReset.current = true
    setPlan(null)
    setMapReady(false)
    setRevealing(false)
    setMode('globe')
    setActive(null)
    setWalkthrough(false)
    setError('')
    setLoading(false)
    window.scrollTo({ top: 0, behavior: 'instant' })
  }
  return (
    <div ref={shell} className={plan ? 'app has-route' : 'app'}>
      <a className="skip-link" href="#main">
        Skip to route planner
      </a>
      <header className="navigation">
        <a className="brand" href="/" aria-label="RouteFuel home">
          <span className="brand-mark" aria-hidden="true">
            <Arrow diagonal />
          </span>
          ROUTEFUEL
        </a>
        <span className="navigation-label">U.S. ROUTE & FUEL PLANNER</span>
        <nav aria-label="Main navigation">
          <a href={apiUrl('/api/docs/')} target="_blank" rel="noreferrer">
            API DOCS <Arrow diagonal />
          </a>
          {github && (
            <a href={github} target="_blank" rel="noreferrer">
              GITHUB <Arrow diagonal />
            </a>
          )}
        </nav>
      </header>
      <main id="main">
        {!plan || revealing ? (
          <section className="hero" aria-label="Route planner">
            <div className="hero-coordinate">
              ROUTE PLANNING
              <br />
              <strong>ACROSS THE UNITED STATES</strong>
            </div>
            <p className="globe-caption">
              GEOGRAPHIC OVERVIEW
              <span>
                {plan ? 'Overview arc only · not the driving route' : 'Drag to explore the globe ↗'}
              </span>
            </p>
            <div className="hero-globe" ref={stage}>
              <WebGLBoundary fallback={<div className="globe-fallback" />}>
                <Suspense fallback={<div className="globe-fallback" />}>
                  <Globe plan={plan} reduced={reduce} />
                </Suspense>
              </WebGLBoundary>
            </div>
            <motion.div
              className="hero-content"
              initial={reduce ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: revealing ? 0 : 1, y: revealing ? -8 : 0 }}
              transition={{ duration: 0.24 }}
            >
              <div className="floating-copy">
                <h1>
                  EVERY MILE.<span>OPTIMIZED.</span>
                </h1>
                <p className="hero-description">The road ahead. The fuel along the way.</p>
              </div>
              <form
                className="route-form"
                onSubmit={submit}
                aria-label="Plan a fuel route"
                noValidate
              >
                <LocationSearch
                  label="FROM"
                  letter="A"
                  value={start}
                  onChange={setStart}
                  inputRef={input}
                  disabled={loading || revealing}
                  invalid={!!error}
                />
                <LocationSearch
                  label="TO"
                  letter="B"
                  value={finish}
                  onChange={setFinish}
                  disabled={loading || revealing}
                  invalid={!!error}
                />
                <motion.button
                  type="submit"
                  className="plan-button"
                  disabled={loading || revealing}
                  whileTap={reduce ? undefined : { scale: 0.985 }}
                >
                  <span className="shine">{loading ? 'PLANNING' : 'PLAN ROUTE'}</span>
                  <Arrow />
                </motion.button>
              </form>
              <div className="feedback-slot">
                <AnimatePresence mode="wait">
                  {loading ? (
                    <RouteLoader key="loading" />
                  ) : error ? (
                    <motion.div
                      id="form-error"
                      role="alert"
                      className="form-error"
                      key="error"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                    >
                      <span>{error}</span>
                      <button
                        onClick={() =>
                          document.querySelector<HTMLButtonElement>('.plan-button')?.click()
                        }
                      >
                        Retry <Arrow />
                      </button>
                    </motion.div>
                  ) : (
                    <p className="form-note" key="note">
                      Search U.S. cities, airports or addresses.
                    </p>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
            <div className="hero-bottom">
              <span>
                <i className="signal-dot" /> ROUTEFUEL / U.S.
              </span>
              <span className="hero-assumptions">
                500 MI RANGE <b>/</b> 10 MPG <b>/</b> 50 GAL TANK
              </span>
              <a href={apiUrl('/api/docs/')} target="_blank" rel="noreferrer">
                DJANGO API <Arrow diagonal />
              </a>
            </div>
          </section>
        ) : (
          <section className="results" aria-label="Route results">
            <div className="result-heading">
              <div>
                <p className="eyebrow">
                  {revealing ? 'YOUR ROUTE, IN PERSPECTIVE' : 'THE ROAD AHEAD'}
                </p>
                <h1 ref={resultHeading} tabIndex={-1}>
                  {plan.start.query}
                  <span className="destination-arrow"> → </span>
                  {plan.finish.query}
                </h1>
              </div>
              <button className="text-button" onClick={reset}>
                Plan another route <Arrow diagonal />
              </button>
            </div>
            <motion.div
              className="summary"
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              aria-label="Route summary"
            >
              <div>
                <span>DRIVING DISTANCE</span>
                <strong>
                  {number(plan.route.distance_miles)} <small>mi</small>
                </strong>
              </div>
              <div>
                <span>FUEL STOPS</span>
                <strong>
                  {stops.length.toString().padStart(2, '0')} <small>planned</small>
                </strong>
              </div>
              <div>
                <span>MODELED FUEL USE</span>
                <strong>
                  {number(plan.fuel.estimated_gallons_consumed, 1)} <small>gal</small>
                </strong>
              </div>
              <div className="total-cost">
                <span>ESTIMATED FUEL COST</span>
                <motion.strong
                  key={plan.fuel.estimated_fuel_cost_usd}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  {money(plan.fuel.estimated_fuel_cost_usd)}
                </motion.strong>
              </div>
            </motion.div>
            <div className="workspace">
              <div className="map-column">
                <div className="map-toolbar">
                  <span className="eyebrow">01 / ROUTE OVERVIEW</span>
                  <ViewSwitch
                    value={mode}
                    onChange={(v) => {
                      setRevealing(false)
                      setMode(v)
                    }}
                  />
                </div>
                <div className="map-stage" ref={stage}>
                  {mode === 'globe' ? (
                    <>
                      <WebGLBoundary
                        fallback={
                          <div className="map-fallback">
                            <p>Globe preview unavailable.</p>
                            <button onClick={() => setMode('map')}>Open road map</button>
                          </div>
                        }
                      >
                        <Suspense fallback={<div className="globe-fallback" />}>
                          <Globe plan={plan} reduced={reduce} />
                        </Suspense>
                      </WebGLBoundary>
                      <p className="overview-label">
                        CINEMATIC OVERVIEW · ARC IS NOT THE DRIVING ROUTE
                      </p>
                    </>
                  ) : (
                    <WebGLBoundary fallback={<MapFallback url={plan.map_url} />}>
                      <Suspense fallback={<div className="map-fallback">Preparing your map…</div>}>
                        <RouteMap
                          plan={plan}
                          active={active}
                          onSelect={chooseStop}
                          reduced={reduce}
                          onReady={mapDidDraw}
                        />
                      </Suspense>
                    </WebGLBoundary>
                  )}
                </div>
                <div className="map-caption">
                  {mapReady ? (
                    <ReadyStatus />
                  ) : (
                    <span role="status" className="map-preparing">
                      Drawing the road route…
                    </span>
                  )}
                  <span>
                    Provider road route ·{' '}
                    <a href={apiUrl(plan.map_url)} target="_blank" rel="noreferrer">
                      Open fallback map <Arrow diagonal />
                    </a>
                  </span>
                </div>
                <p className="map-accessibility sr-only">
                  Driving route from {plan.start.query} to {plan.finish.query}:{' '}
                  {number(plan.route.distance_miles)} miles, {stops.length} fuel stops,{' '}
                  {money(plan.fuel.estimated_fuel_cost_usd)} estimated fuel cost. Each stop is
                  available in the adjacent fuel itinerary.
                </p>
                <div className="model-note">
                  <span className="signal-dot" /> {number(plan.fuel.longest_leg_miles, 1)} mi
                  longest modeled leg <span> / {plan.vehicle.max_range_miles} mi maximum</span>
                </div>
              </div>
              <aside className="itinerary" aria-label="Fuel stop itinerary">
                <div className="itinerary-heading">
                  <span className="eyebrow">YOUR FUEL ITINERARY</span>
                  <button
                    className="walkthrough-button"
                    aria-pressed={walkthrough}
                    onClick={() => setWalkthrough(!walkthrough)}
                  >
                    {walkthrough ? 'Stop walkthrough' : 'Follow on scroll'}{' '}
                    <span aria-hidden="true">↓</span>
                  </button>
                </div>
                <article className="origin-stop">
                  <span className="timeline-node">A</span>
                  <p className="eyebrow">INITIAL FUEL · AT ORIGIN</p>
                  <h2>{plan.start.query}</h2>
                  <p>
                    {number(plan.initial_fueling.gallons_purchased, 1)} gal <span>·</span>{' '}
                    {money(plan.initial_fueling.estimated_cost)}
                  </p>
                  <details>
                    <summary>How origin fuel is priced</summary>
                    <p>
                      Fuel is charged at the origin using{' '}
                      {plan.initial_fueling.price_reference_station.name} as a nearby price
                      reference ({number(plan.initial_fueling.reference_distance_miles, 1)} mi).
                      This is not a planned station visit.
                    </p>
                  </details>
                </article>
                {stops.map((stop) => (
                  <motion.article
                    key={stop.sequence}
                    id={'stop-' + stop.sequence}
                    data-story={stop.sequence}
                    className={'stop-item ' + (active === stop.sequence ? 'selected' : '')}
                  >
                    <button
                      className="stop-select"
                      onClick={() => {
                        setActive(stop.sequence)
                        setMode('map')
                      }}
                      aria-pressed={active === stop.sequence}
                      aria-label={'Focus stop ' + stop.sequence + ': ' + stop.name}
                    >
                      <span className="timeline-node">
                        {String(stop.sequence).padStart(2, '0')}
                      </span>
                      <span className="eyebrow">
                        {stop.city}, {stop.state}
                      </span>
                      <h2>{stop.name}</h2>
                      <Arrow diagonal />
                    </button>
                    <p className="station-address">{stop.address}</p>
                    <div className="stop-price">
                      <strong>
                        {money(stop.retail_price_per_gallon)}
                        <small> / gal</small>
                      </strong>
                      <span>MILE {number(stop.route_mile)}</span>
                    </div>
                    <div className="purchase-row">
                      <span>{number(stop.gallons_purchased, 1)} gal to purchase</span>
                      <strong>{money(stop.estimated_cost)}</strong>
                    </div>
                    <p className="accuracy">
                      <span aria-hidden="true">◌</span>{' '}
                      {stop.location_is_approximate || stop.geocoding_source === 'city_centroid'
                        ? 'Approximate station area'
                        : 'Census address estimate'}
                    </p>
                    <p className="detour">
                      {number(stop.detour_miles, 1)} mi{' '}
                      {stop.detour_basis === 'city_centroid_uncertainty_budget'
                        ? 'access uncertainty budget'
                        : stop.detour_is_estimated
                          ? 'estimated round-trip access'
                          : 'round-trip access'}
                      <br />
                      <span>Confirm station location and road access.</span>
                    </p>
                  </motion.article>
                ))}
                {!stops.length && (
                  <p className="no-stops">
                    No additional fuel stops needed under the model. Your origin fuel covers this
                    route.
                  </p>
                )}
                <article className="destination-stop" data-story={-1}>
                  <button
                    className="stop-select"
                    onClick={() => {
                      setActive(-1)
                      setMode('map')
                    }}
                  >
                    <span className="timeline-node destination-node">B</span>
                    <span className="eyebrow">DESTINATION</span>
                    <h2>{plan.finish.query}</h2>
                    <Arrow diagonal />
                  </button>
                  <p>{number(plan.route.distance_miles)} road miles. Route complete.</p>
                </article>
              </aside>
            </div>
            <details className="assumptions">
              <summary>Planning assumptions & coordinate accuracy</summary>
              <p>
                {plan.vehicle.max_range_miles}-mile range · {plan.vehicle.fuel_economy_mpg} MPG ·{' '}
                {plan.vehicle.tank_capacity_gallons}-gallon tank. Origin fuel is included in the
                total. {number(plan.fuel.estimated_driving_miles_including_detours, 1)} modeled
                miles including estimated access. Fuel purchases follow a cost-aware itinerary;
                global itinerary optimality is not claimed.
              </p>
              {plan.warnings.map((w) => (
                <p key={w}>{w}</p>
              ))}
            </details>
          </section>
        )}
      </main>
      <footer className="page-footer">
        <span>
          ROUTEFUEL <span className="muted">/</span> ROUTE & FUEL PLANNING
        </span>
        <span>
          U.S. ROAD ATLAS <span className="muted">·</span> ESTIMATED FUEL PURCHASES
        </span>
      </footer>
    </div>
  )
}
function MapFallback({ url }: { url: string }) {
  return (
    <div className="map-fallback">
      <p>The interactive map is unavailable on this device.</p>
      <a href={apiUrl(url)} target="_blank" rel="noreferrer">
        Open the Leaflet route map ↗
      </a>
      <p>The complete fuel itinerary remains available below.</p>
    </div>
  )
}
