// Mirrors routes/serializers.py; Django remains authoritative for all values.
import type { LineString } from 'geojson'
export interface Location {
  query: string
  latitude: number
  longitude: number
}
export interface Station {
  opis_truckstop_id: number
  name: string
  address: string
  city: string
  state: string
  latitude: number
  longitude: number
  retail_price_per_gallon: number
  geocoding_source: 'census' | 'city_centroid'
  location_is_approximate: boolean
}
export interface FuelStop extends Station {
  sequence: number
  route_mile: number
  detour_miles: number
  detour_is_estimated: boolean
  detour_basis: 'city_centroid_uncertainty_budget' | 'geodesic_road_access_estimate'
  centroid_to_route_miles?: number
  gallons_purchased: number
  estimated_cost: number
}
export interface RoutePlan {
  start: Location
  finish: Location
  route: { distance_miles: number; duration_hours: number; geometry: LineString }
  vehicle: { max_range_miles: number; fuel_economy_mpg: number; tank_capacity_gallons: number }
  fuel_stops: FuelStop[]
  initial_fueling: {
    assumption: string
    price_reference_station: Station
    gallons_purchased: number
    estimated_cost: number
    reference_distance_miles: number
  }
  fuel: {
    estimated_driving_miles_including_detours: number
    estimated_gallons_consumed: number
    estimated_fuel_cost_usd: number
    estimated_arrival_fuel_gallons: number
    longest_leg_miles: number
  }
  optimization: Record<string, unknown>
  warnings: string[]
  map_url: string
  map_expires_in_seconds: number
}
export type ViewMode = 'globe' | 'map'
export const money = (value: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
export const number = (value: number, digits = 0) =>
  new Intl.NumberFormat('en-US', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value)
export const orderedStops = (plan: RoutePlan) =>
  [...plan.fuel_stops].sort((a, b) => a.sequence - b.sequence)
