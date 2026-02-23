<script lang="ts">
  import { routes } from '$lib/stores/routes';
  import { get } from 'svelte/store';
  import { createEventDispatcher, onMount } from 'svelte';
  import { search } from '$lib/stores/search';
  import { previousSelectedItem } from "$lib/stores/selectedItem";
  import LanguageSwitcher from "$lib/components/LanguageSwitcher.svelte";
  import { messages } from "$lib/stores/messages";

  export let searchFocused: boolean;
  export let searchInput: HTMLInputElement | null = null;
  export let selectedItem: any = null;
  export let showBackButton: boolean = false;

  const dispatch = createEventDispatcher();

  // Dropdown suggestions
  let suggestions: { type: string; value: string; display: string; distance?: number; lat?: number; lon?: number; }[] = [];
  let isLoading = false;
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let stopsCoordinates: { [key: string]: { name: string; lat: number; lon: number } } = {};
  let selectedLocation: { lat: number; lon: number; name: string } | null = null;
  let nearbyStops: { name: string; distance: number; lat: number; lon: number }[] = [];

  // Haversine distance calculation
  function getDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371; // Earth radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c * 1000; // Return in meters
  }

  // Load stops coordinates on mount
  onMount(async () => {
    try {
      const response = await fetch('/data/stops-coordinates.json');
      stopsCoordinates = await response.json();
    } catch (error) {
      console.error('Failed to load stops coordinates:', error);
    }
  });

  // Search Nominatim API
  async function searchNominatim(query: string) {
    if (!query || query.trim().length < 3) {
      suggestions = [];
      return;
    }

    isLoading = true;
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=5&viewbox=77.5,12.85,77.65,13.0&bounded=1`,
        {
          headers: {
            'User-Agent': 'Banashankari Transit App'
          }
        }
      );

      if (!response.ok) {
        throw new Error('Nominatim API request failed');
      }

      const data = await response.json();
      suggestions = data.map((result: any) => ({
        type: 'Location',
        value: result.display_name,
        display: result.display_name,
        lat: parseFloat(result.lat),
        lon: parseFloat(result.lon)
      }));
    } catch (error) {
      console.error('Nominatim search error:', error);
      suggestions = [];
    } finally {
      isLoading = false;
    }
  }

  // Find nearby stops
  function findNearbyStops(lat: number, lon: number) {
    const allRoutes = get(routes);
    const stopsMap = new Map<string, { lat: number; lon: number; distance: number }>();

    // Collect all unique stops from routes
    for (const route of allRoutes) {
      if (route.stops && Array.isArray(route.stops)) {
        for (const stop of route.stops) {
          // Skip Banashankari Bus Station
          if (stop.name === "Banashankari Bus Station" || stop.name === "Banashankari") {
            continue;
          }

          // Find stop coordinates from the loaded data
          // We need to match by name since the route stops don't always have stop_id
          const matchingStopId = Object.keys(stopsCoordinates).find(
            id => stopsCoordinates[id].name === stop.name
          );

          if (matchingStopId) {
            const stopData = stopsCoordinates[matchingStopId];
            const distance = getDistance(lat, lon, stopData.lat, stopData.lon);

            // Keep the closest occurrence of each stop
            if (!stopsMap.has(stop.name) || distance < stopsMap.get(stop.name)!.distance) {
              stopsMap.set(stop.name, {
                lat: stopData.lat,
                lon: stopData.lon,
                distance
              });
            }
          }
        }
      }
    }

    // Convert to array and sort by distance
    nearbyStops = Array.from(stopsMap.entries())
      .map(([name, data]) => ({
        name,
        lat: data.lat,
        lon: data.lon,
        distance: data.distance
      }))
      .sort((a, b) => a.distance - b.distance)
      .slice(0, 10); // Show top 10 nearest stops

    return nearbyStops;
  }

  function clearSearch() {
    search.set('');
    selectedItem.set(undefined);
    previousSelectedItem.set(undefined);
    selectedLocation = null;
    nearbyStops = [];
    suggestions = [];
    searchInput?.focus();
  }

  function handleBack() {
    selectedItem.set(undefined);
    previousSelectedItem.set(undefined);
    search.set('');
    searchFocused = false;
    selectedLocation = null;
    nearbyStops = [];
    suggestions = [];
    dispatch('back');
    dispatch('closeSheet');
    searchInput?.blur();
  }

  function handleSelectSuggestion(s: any) {
    if (s.type === 'Location') {
      // Location selected - find nearby stops
      selectedLocation = { lat: s.lat, lon: s.lon, name: s.display };
      search.set(s.display);
      const nearby = findNearbyStops(s.lat, s.lon);

      // Create suggestions from nearby stops
      suggestions = [
        {
          type: 'LocationHeader',
          value: s.display,
          display: s.display,
          lat: s.lat,
          lon: s.lon
        },
        ...nearby.map(stop => ({
          type: 'Stop',
          value: stop.name,
          display: stop.name,
          distance: Math.round(stop.distance)
        }))
      ];
    } else if (s.type === 'Stop') {
      // Stop selected - dispatch selection
      selectedItem.set(undefined);
      previousSelectedItem.set(undefined);
      dispatch('select', s);
      searchFocused = false;
    }
  }

  // Debounced search
  $: if ($search && $search.trim().length > 0 && !selectedLocation) {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(() => {
      searchNominatim($search.trim());
    }, 300);
  } else if (!$search) {
    suggestions = [];
    selectedLocation = null;
    nearbyStops = [];
  }
</script>

<!-- Back button row -->
{#if showBackButton}
  <div class="cupertino-back-row">
    <button class="cupertino-back-text" on:click={handleBack} aria-label="Back">
      <span class="material-icons" aria-hidden="true">chevron_left</span>{$messages.back()}
    </button>
    <div class="language-switcher">
      <LanguageSwitcher />
    </div>
  </div>
{/if}

<!-- Search bar -->
<div class="cupertino-bar-row">
  <div class="cupertino-bar-flex">
    <div class="cupertino-searchbar {searchFocused ? 'cupertino-searchbar-focused' : ''}">
      <span class="material-icons cupertino-search-icon">search</span>
      <input
        bind:this={searchInput}
        class="cupertino-input"
        type="text"
        placeholder="Search location..."
        bind:value={$search}
        autofocus={searchFocused}
        on:focus={() => searchFocused = true}
        autocomplete="off"
      />
      {#if $search}
        <button class="material-icons cupertino-clear" type="button" on:click={clearSearch} aria-label="Clear">close</button>
      {/if}
    </div>
  </div>
</div>

<!-- Dropdown with location results or nearby stops -->
{#if searchFocused && suggestions.length > 0}
  <div class="cupertino-suggestions-dropdown" role="listbox">
    {#each suggestions as s, i}
      {#if s.type === 'LocationHeader'}
        <div class="location-header">
          <span class="material-icons">place</span>
          <span class="location-name">{s.display}</span>
        </div>
        <div class="nearby-stops-header">Nearby Stops</div>
      {:else if s.type === 'Location'}
        <button
          type="button"
          class="cupertino-suggestion-item"
          role="option"
          aria-label={s.display}
          on:click={() => handleSelectSuggestion(s)}
        >
          <span class="material-icons suggestion-icon">place</span>
          <span class="cupertino-suggestion-main">{s.display}</span>
        </button>
      {:else if s.type === 'Stop'}
        <button
          type="button"
          class="cupertino-suggestion-item stop-item"
          role="option"
          aria-label={`${s.display} - ${s.distance}m away`}
          on:click={() => handleSelectSuggestion(s)}
        >
          <span class="material-icons suggestion-icon">directions_bus</span>
          <span class="stop-info">
            <span class="cupertino-suggestion-main">{s.display}</span>
            <span class="stop-distance">{s.distance}m</span>
          </span>
        </button>
      {/if}
    {/each}
  </div>
{:else if searchFocused && isLoading}
  <div class="cupertino-suggestions-dropdown">
    <div class="loading-state">
      <span class="material-icons loading-icon">hourglass_empty</span>
      <span>Searching...</span>
    </div>
  </div>
{/if}

<style>
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600&display=swap');

.cupertino-back-row {
  width: 100%;
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.cupertino-back-text {
  background: none;
  border: none;
  color: #007aff;
  font-size: 1rem;
  font-weight: 400;
  font-family: -apple-system,BlinkMacSystemFont,sans-serif;
  padding: 4px 12px 4px 0;
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.15s;
  outline: none;
  text-align: left;
  display: flex;
  align-items: center;
}

.cupertino-back-text:active {
  background: rgba(229, 229, 234, 0.3);
}

.cupertino-back-text .material-icons {
  font-size: 28px;
  margin-right: 2px;
  vertical-align: middle;
  line-height: 1;
}

.cupertino-bar-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  position: relative;
  z-index: 100;
}

.cupertino-bar-flex {
  flex: 1 1 0%;
  display: flex;
  padding-left: 8px;
  padding-right: 8px;
}

.language-switcher {
  margin-left: auto;
}

.cupertino-searchbar {
  display: flex;
  align-items: center;
  background: #FFFFFF;
  border-radius: 14px;
  border: 1px solid #e0e0e5;
  box-shadow: 0 1px 6px 0 rgba(60,60,67,0.06);
  padding: 0 10px;
  height: 44px;
  width: 100%;
  font-family: Manrope, sans-serif;
  font-weight: 400;
  transition: box-shadow 0.2s, background 0.2s;
  position: relative;
  z-index: 100;
}

.cupertino-search-icon {
  color: #8e8e93;
  font-size: 22px;
  margin-right: 4px;
}

.cupertino-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 17px;
  color: #222;
  padding: 0 6px;
  font-family: Manrope, sans-serif;
}

.cupertino-input::placeholder {
  color: #8e8e93;
  opacity: 1;
  font-weight: 400;
}

.cupertino-clear {
  background: none;
  border: none;
  color: #8e8e93;
  font-size: 22px;
  margin-left: 2px;
  cursor: pointer;
  padding: 4px;
}

.cupertino-suggestions-dropdown {
  position: absolute;
  left: 0;
  right: 0;
  top: 100%;
  margin-top: 4px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px 0 rgba(60,60,67,0.10);
  z-index: 200;
  padding: 8px 0;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'Manrope', sans-serif;
}

.cupertino-suggestion-item {
  padding: 14px 20px;
  font-size: 16px;
  color: #222;
  cursor: pointer;
  transition: background 0.15s;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 48px;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
}

.cupertino-suggestion-item:hover, .cupertino-suggestion-item:focus {
  background: #f1f1f3;
  outline: none;
}

.suggestion-icon {
  font-size: 20px;
  color: #8e8e93;
  flex-shrink: 0;
}

.cupertino-suggestion-main {
  font-size: 17px;
  color: #222;
  font-weight: 400;
  line-height: 1.3;
}

.location-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: #f8f8f8;
  border-bottom: 1px solid #e0e0e5;
}

.location-header .material-icons {
  font-size: 20px;
  color: #007aff;
}

.location-name {
  font-size: 15px;
  color: #222;
  font-weight: 500;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nearby-stops-header {
  padding: 12px 20px 8px;
  font-size: 13px;
  color: #8e8e93;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stop-item {
  padding-left: 20px;
}

.stop-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  gap: 2px;
}

.stop-distance {
  font-size: 14px;
  color: #007aff;
  font-weight: 500;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  color: #8e8e93;
  font-size: 15px;
}

.loading-icon {
  font-size: 20px;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
