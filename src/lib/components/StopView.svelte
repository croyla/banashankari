<script lang="ts">
  import { get } from 'svelte/store';
  import { platforms } from '$lib/stores/platforms';
  import { routes as allRoutes } from '$lib/stores/routes';
  import { selectedItem, previousSelectedItem } from '$lib/stores/selectedItem';
  import {language} from "$lib/stores/language";
  import {messages} from "$lib/stores/messages";
  import BusRow from './BusRow.svelte';
  import LiveBusRow from './LiveBusRow.svelte';
  import type {Route} from "$lib/types/Route";
  import {results, setResults} from "$lib/stores/results";
  import {tick, onDestroy} from "svelte";
  import { liveArrivals, liveArrivalsLoading, liveArrivalsError, displayedLiveArrivals, updateLiveArrivalsForPlatform, clearLiveArrivalsForPlatform } from '$lib/stores/liveArrivals';
  import { getStationIdsForPlatform } from '$lib/config/platformStations';

  // Helper to get platform color
  function getPlatformColor(platformNumber) {
    const pf = get(platforms).find(p => p.platformNumber == platformNumber);
    return pf ? pf.color : '#F68511';
  }

  // Format platform label like search results
  function formatPlatformLabel(platformNumber: string): string {
    if (!platformNumber) return '';
    const pf = platformNumber.trim();
    // If it's a number, show "Platform <num>"
    if (/^\d+$/.test(pf)) return `Platform ${pf}`;
    // Otherwise it's a named platform like "WEST", "SOUTH" — show "Banashankari <Name>"
    return `Banashankari ${pf.charAt(0).toUpperCase()}${pf.slice(1).toLowerCase()}`;
  }

  // Live arrivals management
  let liveArrivalsTimeout: number | null = null;
  let isQueryInProgress = false;
  let hasLoadedOnce = false;
  let currentPlatform: string | null = null;

  // Fetch live arrivals for the current platform
  async function fetchLiveData() {
    const platform = platformId;
    if (!platform) return;
    if (isQueryInProgress) return; // Prevent overlapping queries

    const stationIds = getStationIdsForPlatform(platform);
    if (stationIds.length === 0) return;

    isQueryInProgress = true;
    try {
      await updateLiveArrivalsForPlatform(platform, stationIds);
      hasLoadedOnce = true; // Mark as successfully loaded
    } finally {
      isQueryInProgress = false;
      // Schedule next query 1 minute after this one completes
      scheduleNextQuery();
    }
  }

  // Schedule the next query
  function scheduleNextQuery() {
    // Clear any existing timeout
    if (liveArrivalsTimeout) {
      clearTimeout(liveArrivalsTimeout);
      liveArrivalsTimeout = null;
    }

    // Only schedule if we still have a platform selected and it matches current
    const platform = platformId;
    if (platform && platform === currentPlatform) {
      liveArrivalsTimeout = setTimeout(() => {
        fetchLiveData();
      }, 60000) as unknown as number;
    }
  }

  // Manual retry function
  function retryFetch() {
    if (liveArrivalsTimeout) {
      clearTimeout(liveArrivalsTimeout);
      liveArrivalsTimeout = null;
    }
    fetchLiveData();
  }

  // Set up live arrivals polling when platform is available
  $: if (platformId) {
    const newPlatform = platformId;

    // Only initiate new polling if platform changed
    if (newPlatform !== currentPlatform) {
      // Clear previous timeout if any
      if (liveArrivalsTimeout) {
        clearTimeout(liveArrivalsTimeout);
        liveArrivalsTimeout = null;
      }

      // Reset state for new platform
      currentPlatform = newPlatform;
      hasLoadedOnce = false;
      isQueryInProgress = false;

      // Fetch immediately for new platform
      fetchLiveData();
    }
  } else {
    // Clear timeout if no platform selected
    if (liveArrivalsTimeout) {
      clearTimeout(liveArrivalsTimeout);
      liveArrivalsTimeout = null;
    }
    currentPlatform = null;
    hasLoadedOnce = false;
    isQueryInProgress = false;
  }

  // Cleanup on destroy
  onDestroy(() => {
    if (liveArrivalsTimeout) {
      clearTimeout(liveArrivalsTimeout);
    }
    isQueryInProgress = false;
    if (currentPlatform) {
      clearLiveArrivalsForPlatform(currentPlatform);
    }
    displayedLiveArrivals.set([]);
  });
  // Filtering logic
  const all = get(allRoutes);
  let mainRoutes = [];
  let areaRoutes = [];

  if ($selectedItem) {
    if($selectedItem.type === 'Platform') {
      // For platform view, get the platform identifier from display or platformNumber
      const platformId = ($selectedItem.platformNumber || $selectedItem.display).trim();
      mainRoutes = all.filter(r => r.platformNumber.trim() === platformId);
    }
    if ($selectedItem.type === 'Stop') {
      mainRoutes = all
              .filter(r => {
                const hasStop = r.stops && r.stops.some(s => s.name === $selectedItem.display);
                // If platformNumber is specified, also filter by platform
                if ($selectedItem.platformNumber && hasStop) {
                  return r.platformNumber === $selectedItem.platformNumber;
                }
                return hasStop;
              })
              .sort((a: Route, b: Route) =>
                      a.stops.slice(Math.max(0, a.stops.findIndex((s) => s.name === 'Kempegowda Bus Station')), a.stops.findIndex((s) => s.name === $selectedItem.display)).length - b.stops.slice(Math.max(0, b.stops.findIndex(s => s.name === 'Kempegowda Bus Station')), b.stops.findIndex((s) => s.name === $selectedItem.display)).length)
      ;
      // areaRoutes = all.filter(r => {
      //   const matchesArea = ((r.area && r.area.name.trim() === $selectedItem.display.trim()) || (r.via && r.via.name.trim() === $selectedItem.display.trim()));
      //   const notInMain = !mainRoutes.includes(r);
      //   // If platformNumber is specified, also filter by platform
      //   if ($selectedItem.platformNumber && matchesArea && notInMain) {
      //     return r.platformNumber === $selectedItem.platformNumber;
      //   }
      //   return matchesArea && notInMain;
      // });
      // console.log("ROUTES SORTED", mainRoutes.map(s =>
      // {
      //   return {
      //     number: s.number,
      //     stops: s.stops.slice(Math.max(0, s.stops.findIndex((c) => c.name === 'Kempegowda Bus Station')), s.stops.findIndex((c) => c.name === $selectedItem.display))
      //   }
      // }));
    } else if ($selectedItem.type === 'Area') {
      mainRoutes = all.filter(r => {
        const matchesArea = ((r.area && r.area.name === $selectedItem.display) || (r.via && r.via.name === $selectedItem.display));
        // If platformNumber is specified, also filter by platform
        if ($selectedItem.platformNumber && matchesArea) {
          return r.platformNumber === $selectedItem.platformNumber;
        }
        return matchesArea;
      });
    }

    // De-duplicate routes: if no platformNumber filter is specified, show each route only once (first occurrence)
    if (!$selectedItem.platformNumber && mainRoutes.length > 0) {
      const seenRoutes = new Set();
      mainRoutes = mainRoutes.filter(r => {
        if (seenRoutes.has(r.number)) {
          return false;
        }
        seenRoutes.add(r.number);
        return true;
      });
    }

    tick().then(() => setResults(mainRoutes))
    // updatePlatformColors();
  }

  function handleRouteClick(route) {
    previousSelectedItem.set($selectedItem);
    selectedItem.set({ value: route.number, type: 'Route' });
  }

  // Get platform identifier (works for both direct platform clicks and filtered views)
  $: platformId = $selectedItem
    ? ($selectedItem.platformNumber || ($selectedItem.type === 'Platform' ? $selectedItem.display : null))
    : null;

  // Get loading state for current platform
  $: isLoadingLiveData = platformId
    ? ($liveArrivalsLoading[platformId.toUpperCase()] || false)
    : false;

  // Get error state for current platform
  $: hasLoadingError = platformId
    ? ($liveArrivalsError[platformId.toUpperCase()] || false)
    : false;

  // Get all live arrivals for current platform
  $: allPlatformArrivals = platformId
    ? ($liveArrivals[platformId.toUpperCase()] || [])
    : [];

  // Create a set of valid route numbers from mainRoutes for filtering
  $: validRouteNumbers = new Set(mainRoutes.map(r => r.number.trim().toUpperCase()));

  // Map route number -> expected destination (from static routes for this platform/context)
  // Used to filter live arrivals to the correct direction when the same route runs both ways
  $: routeDestinationMap = new Map<string, string>(
    mainRoutes.map(r => [r.number.trim().toUpperCase(), (r.destination || '').trim().toUpperCase()])
  );

  function destinationMatches(liveRouteName: string, expectedDest: string): boolean {
    if (!expectedDest) return true;
    const live = liveRouteName.trim().toUpperCase();
    const expected = expectedDest.trim().toUpperCase();
    return live.includes(expected) || expected.includes(live);
  }

  // Filter live arrivals to only show routes that belong to this platform/search context
  // Also filter by destination to avoid showing opposite-direction arrivals for the same route number
  $: currentPlatformArrivals = allPlatformArrivals.filter(arrival => {
    const routeKey = arrival.route_number.trim().toUpperCase();
    if (!validRouteNumbers.has(routeKey)) return false;
    const expectedDest = routeDestinationMap.get(routeKey);
    return destinationMatches(arrival.route_name, expectedDest || '');
  });

  // Keep the map in sync with what's currently shown in the card list
  $: displayedLiveArrivals.set(currentPlatformArrivals);

  // Get set of route numbers that have live arrivals
  $: liveRouteNumbers = new Set(currentPlatformArrivals.map(a => a.route_number.trim().toUpperCase()));

  // Filter static routes to exclude those with live arrivals
  $: staticRoutes = mainRoutes.filter(r => !liveRouteNumbers.has(r.number.trim().toUpperCase()));
</script>

{#if $selectedItem && ($selectedItem.type === 'Stop' || $selectedItem.type === 'Platform' || $selectedItem.type === 'Area')}
  <div class="stopview-content">
    <div class="stopview-header">{$selectedItem.type === 'Platform' ? formatPlatformLabel($selectedItem?.display) : $messages.buses_to().replace('%1', $language === 'en' ? $selectedItem?.display : $selectedItem?.displayKannada ?? $selectedItem?.display)}</div>
    {#if $selectedItem.type !== 'Platform' && platformId}
      <div class="stopview-subheader">{$messages.from().replace('%1', formatPlatformLabel(platformId))}</div>
    {/if}
    <div class="stopview-list">
      {#if isLoadingLiveData && !hasLoadedOnce && platformId}
        <!-- Loading indicator - only show on first load -->
        <div class="loading-indicator">
          <div class="spinner"></div>
          <span class="loading-text">Loading live arrivals...</span>
        </div>
      {/if}

      {#if hasLoadingError && !isLoadingLiveData && platformId}
        <!-- Error with retry button - only show when not loading and error occurred -->
        <div class="error-indicator">
          <span class="error-text">Failed to load live arrivals</span>
          <button class="retry-button" on:click={retryFetch}>Retry</button>
        </div>
      {/if}

      {#if currentPlatformArrivals.length > 0}
        <!-- Live arrivals -->
        {#each currentPlatformArrivals as arrival}
          <LiveBusRow
            {arrival}
            searchedStop={$selectedItem.type === 'Stop' ? $selectedItem.display : null}
          />
        {/each}
      {/if}

      <!-- Static routes (those without live data) -->
      {#each staticRoutes as route}
        <BusRow {route} {getPlatformColor} {handleRouteClick} />
      {/each}
    </div>
    {#if $selectedItem?.type === 'Stop' && areaRoutes.length}
      <div class="section-header">{$messages.other_buses_to().replace('%1', $language === 'en' ? $selectedItem?.display : $selectedItem?.displayKannada ?? $selectedItem?.display)}</div>
      <div class="stopview-list">
        {#each areaRoutes as route}
          <BusRow {route} {getPlatformColor} {handleRouteClick} />
        {/each}
      </div>
    {/if}
  </div>
{:else}
  <div>Panic: selectedItem is undefined or not a stop/area/platform</div>
{/if}

<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600&display=swap');
.stopview-content {
  padding: 32px 20px 20px 20px;
}
.stopview-header {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 8px;
  margin-top: 8px;
}
.stopview-subheader {
  font-size: 15px;
  font-weight: 400;
  color: #666;
  margin-bottom: 20px;
  margin-top: 4px;
}
.section-header {
  font-size: 16px;
  font-weight: 500;
  margin: 32px 0 12px 0;
  color: #222;
}
.stopview-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.loading-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #F5F5F5;
  border-radius: 8px;
  margin-bottom: 8px;
}
.spinner {
  width: 20px;
  height: 20px;
  border: 3px solid #E0E0E0;
  border-top-color: #4CAF50;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.loading-text {
  font-family: 'Manrope', sans-serif;
  font-size: 14px;
  color: #666;
  font-weight: 400;
}
.error-indicator {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  background: #FFEBEE;
  border-radius: 8px;
  margin-bottom: 8px;
  border-left: 3px solid #F44336;
}
.error-text {
  font-family: 'Manrope', sans-serif;
  font-size: 14px;
  color: #C62828;
  font-weight: 400;
}
.retry-button {
  background: #F44336;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-family: 'Manrope', sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.retry-button:hover {
  background: #D32F2F;
}
.retry-button:active {
  background: #C62828;
}
</style> 