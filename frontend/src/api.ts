import type { RoutePlan } from './types'
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
export const apiUrl = (path: string) => API_BASE + path

export function validateLocations(start: string, finish: string) {
  if (!start.trim()) return 'Enter a starting location.'
  if (!finish.trim()) return 'Enter a destination.'
  if (start.trim().toLocaleLowerCase() === finish.trim().toLocaleLowerCase())
    return 'Choose two different locations.'
  return ''
}
const object = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === 'object' && !Array.isArray(v)
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const position = (v: unknown) =>
  object(v) &&
  finite(v.longitude) &&
  Math.abs(v.longitude) <= 180 &&
  finite(v.latitude) &&
  Math.abs(v.latitude) <= 90
const numbers = (v: unknown, keys: string[]) => object(v) && keys.every((k) => finite(v[k]))
const station = (v: unknown) =>
  object(v) &&
  position(v) &&
  ['name', 'address', 'city', 'state'].every((k) => typeof v[k] === 'string') &&
  numbers(v, ['retail_price_per_gallon', 'opis_truckstop_id']) &&
  ['census', 'city_centroid'].includes(String(v.geocoding_source)) &&
  typeof v.location_is_approximate === 'boolean'
export function parsePlan(data: unknown): RoutePlan {
  if (
    !object(data) ||
    !position(data.start) ||
    !position(data.finish) ||
    !object(data.start) ||
    typeof data.start.query !== 'string' ||
    !object(data.finish) ||
    typeof data.finish.query !== 'string' ||
    !numbers(data.route, ['distance_miles', 'duration_hours']) ||
    !object(data.route) ||
    !object(data.route.geometry) ||
    data.route.geometry.type !== 'LineString' ||
    !Array.isArray(data.route.geometry.coordinates) ||
    data.route.geometry.coordinates.length < 2 ||
    !data.route.geometry.coordinates.every(
      (p) =>
        Array.isArray(p) &&
        p.length >= 2 &&
        finite(p[0]) &&
        Math.abs(p[0]) <= 180 &&
        finite(p[1]) &&
        Math.abs(p[1]) <= 90,
    ) ||
    !numbers(data.fuel, [
      'estimated_driving_miles_including_detours',
      'estimated_gallons_consumed',
      'estimated_fuel_cost_usd',
      'estimated_arrival_fuel_gallons',
      'longest_leg_miles',
    ]) ||
    !numbers(data.vehicle, ['max_range_miles', 'fuel_economy_mpg', 'tank_capacity_gallons']) ||
    !object(data.initial_fueling) ||
    !station(data.initial_fueling.price_reference_station) ||
    !numbers(data.initial_fueling, [
      'gallons_purchased',
      'estimated_cost',
      'reference_distance_miles',
    ]) ||
    !Array.isArray(data.fuel_stops) ||
    !data.fuel_stops.every(
      (s) =>
        station(s) &&
        numbers(s, [
          'sequence',
          'route_mile',
          'detour_miles',
          'gallons_purchased',
          'estimated_cost',
        ]) &&
        object(s) &&
        typeof s.detour_is_estimated === 'boolean' &&
        ['city_centroid_uncertainty_budget', 'geodesic_road_access_estimate'].includes(
          String(s.detour_basis),
        ),
    ) ||
    !Array.isArray(data.warnings) ||
    !data.warnings.every((s) => typeof s === 'string') ||
    typeof data.map_url !== 'string' ||
    !data.map_url.startsWith('/api/v1/route/')
  ) {
    throw new Error('The route service returned an incomplete result. Please try again.')
  }
  return data as unknown as RoutePlan
}
function errorMessage(data: unknown, status: number): string {
  if (object(data)) {
    if (object(data.error) && typeof data.error.message === 'string') return data.error.message
    const values = Object.values(data).flat()
    const message = values.find((v) => typeof v === 'string')
    if (typeof message === 'string') return message
  }
  if (status === 504) return 'The routing service timed out. Please try again.'
  if (status === 429) return 'Too many requests. Please wait a moment before trying again.'
  if (status === 503 || status === 502)
    return 'The routing service is unavailable. Please try again shortly.'
  return 'We could not plan this route. Please try again.'
}
export async function requestRoute(
  start: string,
  finish: string,
  signal?: AbortSignal,
): Promise<RoutePlan> {
  const response = await fetch(apiUrl('/api/v1/route/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start: start.trim(), finish: finish.trim() }),
    signal,
  })
  const data: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new Error(errorMessage(data, response.status))
  return parsePlan(data)
}
