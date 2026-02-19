import { writable } from 'svelte/store';

export interface LiveArrivalLocation {
  lat: number;
  lng: number;
}

export interface LiveArrival {
  route_number: string;    // raw from API (e.g. "500-CA")
  display_number: string;  // formatted (e.g. "500CA")
  route_name: string;
  duration_ms: number;
  minutes_away: number;
  station_id: string;
  timestamp: number;
  bus_no: string | null;
  vehicle_id: number | null;
  location: LiveArrivalLocation | null;
}

// Store for live arrival data by platform
export const liveArrivals = writable<Record<string, LiveArrival[]>>({});

// Store for loading state by platform
export const liveArrivalsLoading = writable<Record<string, boolean>>({});

// Store for error state by platform
export const liveArrivalsError = writable<Record<string, boolean>>({});

// Store for the currently focused live bus (for map panning)
export const focusedLiveBus = writable<LiveArrival | null>(null);

// Store for the arrivals currently visible in the card list (used to filter map dots)
export const displayedLiveArrivals = writable<LiveArrival[]>([]);

// Format route number for display
// Rules: remove '-', split by ' ', take first part
// If first part has no digits, take first + second
export function formatRouteNumber(raw: string): string {
  if (!raw) return raw;
  const noDash = raw.replace(/-/g, '');
  const parts = noDash.split(' ').filter(Boolean);
  if (parts.length === 0) return noDash;
  const first = parts[0];
  if (/\d/.test(first)) return first;
  // First part has no digits (e.g. "EXP"), append second if present
  return parts.length > 1 ? `${first} ${parts[1]}` : first;
}

// Fetch arrivals for a list of station IDs
export async function fetchArrivals(stationIds: string[]): Promise<LiveArrival[]> {
  const allArrivals: LiveArrival[] = [];
  const timestamp = Date.now();

  for (const stationId of stationIds) {
    try {
      const response = await fetch(
        `https://transitrouter.pages.dev/api/bmtc/arrivals?stationid=${stationId}`
      );

      if (!response.ok) {
        console.warn(`Failed to fetch arrivals for station ${stationId}`);
        continue;
      }

      const data = await response.json();

      if (data && Array.isArray(data.services)) {
        for (const service of data.services) {
          const routeNumber = service.no || '';
          const destination = service.destination || '';
          const frequency = service.frequency || 0;

          const arrivalKeys = ['next', 'next2', 'next3'];
          for (let i = 0; i < Math.min(frequency, 3); i++) {
            const arrivalData = service[arrivalKeys[i]];
            if (arrivalData && arrivalData.duration_ms !== undefined) {
              const loc = arrivalData.location;
              allArrivals.push({
                route_number: routeNumber,
                display_number: formatRouteNumber(routeNumber),
                route_name: destination,
                duration_ms: arrivalData.duration_ms,
                minutes_away: Math.floor(arrivalData.duration_ms / 60000),
                station_id: stationId,
                timestamp,
                bus_no: arrivalData.bus_no || null,
                vehicle_id: arrivalData.vehicle_id || null,
                location: (loc && loc.lat && loc.lng) ? { lat: loc.lat, lng: loc.lng } : null,
              });
            }
          }
        }
      }
    } catch (error) {
      console.error(`Error fetching arrivals for station ${stationId}:`, error);
    }
  }

  return allArrivals;
}

// Merge and de-duplicate arrivals from multiple stations
// Deduplicate by vehicle_id if available, otherwise by route_number + duration_ms
// Prioritise arrival with lower duration_ms
export function mergeAndDeduplicateArrivals(arrivals: LiveArrival[]): LiveArrival[] {
  const arrivalMap = new Map<string, LiveArrival>();

  for (const arrival of arrivals) {
    const key = arrival.vehicle_id
      ? `vid_${arrival.vehicle_id}`
      : `${arrival.route_number.trim().toUpperCase()}_${arrival.duration_ms}`;

    if (!arrivalMap.has(key) || arrivalMap.get(key)!.duration_ms > arrival.duration_ms) {
      arrivalMap.set(key, arrival);
    }
  }

  return Array.from(arrivalMap.values()).sort((a, b) => {
    const aHasLoc = a.location ? 1 : 0;
    const bHasLoc = b.location ? 1 : 0;
    if (bHasLoc !== aHasLoc) return bHasLoc - aHasLoc; // location-available first
    return a.duration_ms - b.duration_ms;               // then by time ascending
  });
}

// Update live arrivals for a specific platform
export async function updateLiveArrivalsForPlatform(
  platformNumber: string,
  stationIds: string[]
): Promise<void> {
  const platformKey = platformNumber.toUpperCase();

  liveArrivalsLoading.update(state => ({ ...state, [platformKey]: true }));
  liveArrivalsError.update(state => ({ ...state, [platformKey]: false }));

  try {
    const arrivals = await fetchArrivals(stationIds);
    const deduplicated = mergeAndDeduplicateArrivals(arrivals);

    liveArrivals.update(state => ({ ...state, [platformKey]: deduplicated }));
    liveArrivalsError.update(state => ({ ...state, [platformKey]: false }));
  } catch (error) {
    console.error('Error updating live arrivals:', error);
    liveArrivalsError.update(state => ({ ...state, [platformKey]: true }));
  } finally {
    liveArrivalsLoading.update(state => ({ ...state, [platformKey]: false }));
  }
}

// Clear live arrivals for a specific platform
export function clearLiveArrivalsForPlatform(platformNumber: string): void {
  liveArrivals.update(state => {
    const newState = { ...state };
    delete newState[platformNumber.toUpperCase()];
    return newState;
  });
}
