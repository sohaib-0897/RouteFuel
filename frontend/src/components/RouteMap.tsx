import { useEffect, useRef, useState } from 'react'
import {
  Map,
  Marker,
  Popup,
  NavigationControl,
  LngLatBounds,
  setWorkerUrl,
  type StyleSpecification,
} from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import 'maplibre-gl/dist/maplibre-gl.css'
import { apiUrl } from '../api'
import { money, number, orderedStops, type FuelStop, type RoutePlan } from '../types'
setWorkerUrl(workerUrl)
const emptyStyle: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#e5e5dc' } }],
}
function popupContent(stop: FuelStop) {
  const content = document.createElement('div')
  const heading = document.createElement('h3')
  heading.textContent = stop.name
  content.append(heading)
  const lines = [
    stop.address + ', ' + stop.city + ', ' + stop.state,
    money(stop.retail_price_per_gallon) + ' / gal · Mile ' + number(stop.route_mile, 1),
    number(stop.gallons_purchased, 1) + ' gal · ' + money(stop.estimated_cost),
    number(stop.detour_miles, 1) +
      ' mi ' +
      (stop.detour_basis === 'city_centroid_uncertainty_budget'
        ? 'access uncertainty budget'
        : 'estimated round-trip access'),
    stop.location_is_approximate || stop.geocoding_source === 'city_centroid'
      ? 'Approximate station area · verify location'
      : 'Census address estimate · verify road access',
  ]
  for (const line of lines) {
    const p = document.createElement('p')
    p.textContent = line
    content.append(p)
  }
  return content
}
export default function RouteMap({
  plan,
  active,
  onSelect,
  reduced,
}: {
  plan: RoutePlan
  active: number | null
  onSelect: (n: number | null) => void
  reduced: boolean
}) {
  const container = useRef<HTMLDivElement>(null)
  const instance = useRef<Map | null>(null)
  const markers = useRef(new globalThis.Map<number, Marker>())
  const [failed, setFailed] = useState(false)
  const [tileWarning, setTileWarning] = useState(false)
  const [drawn, setDrawn] = useState(false)

  const fit = useRef<() => void>(() => {})
  const activeRef = useRef(active)
  activeRef.current = active
  useEffect(() => {
    if (!container.current) return
    let map: Map
    try {
      map = new Map({
        container: container.current,
        style:
          import.meta.env.VITE_MAP_STYLE_URL || 'https://tiles.openfreemap.org/styles/positron',
        center: [-99, 37],
        zoom: 3,
        attributionControl: { compact: false },
        cooperativeGestures: true,
        renderWorldCopies: false,
      })
    } catch {
      setFailed(true)
      return
    }
    instance.current = map
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    const bounds = new LngLatBounds()
    for (const p of plan.route.geometry.coordinates) bounds.extend([p[0], p[1]])
    fit.current = () =>
      map.fitBounds(bounds, {
        padding: window.innerWidth < 600 ? 45 : 65,
        duration: reduced ? 0 : 650,
        maxZoom: 10,
      })
    let frame = 0,
      disposed = false,
      initialized = false
    const localMarkers: Marker[] = []
    const markerRegistry = markers.current
    const styleTimeout = setTimeout(() => {
      if (!initialized && !disposed) {
        setTileWarning(true)
        map.setStyle(emptyStyle)
      }
    }, 12000)
    map.on('error', () => {
      if (!disposed) setTileWarning(true)
    })
    const lost = (e: Event) => {
      e.preventDefault()
      setFailed(true)
    }
    map.getCanvas().addEventListener('webglcontextlost', lost)
    map.on('load', () => {
      if (disposed) return
      initialized = true
      clearTimeout(styleTimeout)
      map.addSource('driving-route', {
        type: 'geojson',
        lineMetrics: true,
        data: { type: 'Feature', properties: {}, geometry: plan.route.geometry },
      })
      map.addLayer({
        id: 'route-casing',
        type: 'line',
        source: 'driving-route',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#f4f1e9', 'line-opacity': 0.9, 'line-width': 7 },
      })
      map.addLayer({
        id: 'road-route',
        type: 'line',
        source: 'driving-route',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#d04b24', 'line-width': 3 },
      })
      map.addLayer({
        id: 'active-section',
        type: 'line',
        source: 'driving-route',
        layout: { 'line-join': 'round', 'line-cap': 'round', visibility: 'none' },
        paint: { 'line-color': '#172d3b', 'line-width': 5 },
      })
      map.fitBounds(bounds, {
        padding: window.innerWidth < 600 ? 45 : 65,
        duration: 0,
        maxZoom: 10,
      })
      for (const [label, location] of [
        ['A', plan.start],
        ['B', plan.finish],
      ] as const) {
        const el = document.createElement('div')
        el.className = 'endpoint-marker'
        el.textContent = label
        el.setAttribute(
          'aria-label',
          label === 'A' ? 'Start: ' + location.query : 'Destination: ' + location.query,
        )
        localMarkers.push(
          new Marker({ element: el }).setLngLat([location.longitude, location.latitude]).addTo(map),
        )
      }
      const stops = orderedStops(plan)
      for (const stop of stops) {
        const el = document.createElement('button')
        el.type = 'button'
        el.className = 'fuel-marker' + (stop.location_is_approximate ? ' is-approximate' : '')
        el.textContent = String(stop.sequence).padStart(2, '0')
        el.setAttribute(
          'aria-label',
          'Stop ' +
            stop.sequence +
            ': ' +
            stop.name +
            (stop.location_is_approximate ? ', approximate station area' : ''),
        )
        el.style.visibility = 'hidden'
        el.addEventListener('click', () => onSelect(stop.sequence))
        const marker = new Marker({ element: el })
          .setLngLat([stop.longitude, stop.latitude])
          .setPopup(
            new Popup({ offset: 22, closeButton: true, focusAfterOpen: false }).setDOMContent(
              popupContent(stop),
            ),
          )
          .addTo(map)
        markers.current.set(stop.sequence, marker)
        localMarkers.push(marker)
      }
      const start = performance.now()
      const draw = (now: number) => {
        if (disposed) return
        const progress = reduced ? 1 : Math.min((now - start) / 1050, 1)
        map.setPaintProperty('road-route', 'line-gradient', [
          'step',
          ['line-progress'],
          '#d04b24',
          Math.max(progress, 0.00001),
          'rgba(208,75,36,0)',
        ])
        for (const stop of stops) {
          const el = markers.current.get(stop.sequence)?.getElement()
          if (el && progress >= stop.route_mile / Math.max(plan.route.distance_miles, 1))
            el.style.visibility = 'visible'
        }
        if (progress < 1) frame = requestAnimationFrame(draw)
        else {
          map.setPaintProperty('road-route', 'line-gradient', undefined)
          setDrawn(true)
        }
      }
      frame = requestAnimationFrame(draw)
    })
    const observer = new ResizeObserver(() => {
      map.resize()
      if (!initialized) return
      const selected =
        activeRef.current === -1
          ? plan.finish
          : plan.fuel_stops.find((s) => s.sequence === activeRef.current)
      if (selected)
        map.jumpTo({
          center: [selected.longitude, selected.latitude],
          zoom: activeRef.current === -1 ? 8 : 7,
        })
      else
        map.fitBounds(bounds, {
          padding: window.innerWidth < 600 ? 45 : 65,
          duration: 0,
          maxZoom: 10,
        })
    })
    observer.observe(container.current)
    return () => {
      disposed = true
      cancelAnimationFrame(frame)
      clearTimeout(styleTimeout)
      observer.disconnect()
      map.getCanvas().removeEventListener('webglcontextlost', lost)
      localMarkers.forEach((marker) => marker.remove())
      markerRegistry.clear()
      map.remove()
      instance.current = null
    }
  }, [plan, reduced, onSelect])
  useEffect(() => {
    const map = instance.current
    if (!map || !drawn) return
    for (const [sequence, marker] of markers.current) {
      const selected = sequence === active
      marker.getElement().classList.toggle('is-active', selected)
      marker.getElement().setAttribute('aria-pressed', String(selected))
      if (marker.getPopup()?.isOpen() && !selected) marker.togglePopup()
    }
    if (map.getLayer('active-section')) {
      map.setLayoutProperty('active-section', 'visibility', active === null ? 'none' : 'visible')
      const stops = orderedStops(plan)
      const index = stops.findIndex((s) => s.sequence === active)
      const progress =
        active === -1 ? 1 : (stops[index]?.route_mile || 0) / plan.route.distance_miles
      const previous =
        active === -1
          ? (stops.at(-1)?.route_mile || 0) / plan.route.distance_miles
          : (stops[index - 1]?.route_mile || 0) / plan.route.distance_miles
      map.setPaintProperty('active-section', 'line-gradient', [
        'case',
        ['all', ['>=', ['line-progress'], previous], ['<=', ['line-progress'], progress]],
        '#172d3b',
        'rgba(23,45,59,0)',
      ])
    }
    if (active === null) {
      fit.current()
      return
    }
    const location =
      active === -1 ? plan.finish : plan.fuel_stops.find((s) => s.sequence === active)
    if (location)
      map.easeTo({
        center: [location.longitude, location.latitude],
        zoom: active === -1 ? 8 : 7,
        duration: reduced ? 0 : 750,
      })
  }, [active, drawn, plan, reduced])
  return (
    <>
      <div
        className="map-container"
        ref={container}
        role="region"
        aria-label="Interactive driving route map"
        data-testid="route-map"
        data-drawn={drawn}
      />
      {failed ? (
        <div className="map-fallback absolute inset-0">
          <p>Your device could not render the interactive map.</p>
          <a href={apiUrl(plan.map_url)} target="_blank" rel="noreferrer">
            Open the Leaflet route map ↗
          </a>
        </div>
      ) : (
        <div className="map-controls-extra">
          <button
            onClick={() => {
              onSelect(null)
              fit.current()
            }}
          >
            Fit route ↗
          </button>
        </div>
      )}
      {tileWarning && !failed && (
        <p className="map-status" role="status">
          Some basemap tiles are unavailable.{' '}
          <a href={apiUrl(plan.map_url)} target="_blank" rel="noreferrer">
            Open fallback map ↗
          </a>
        </p>
      )}
    </>
  )
}
