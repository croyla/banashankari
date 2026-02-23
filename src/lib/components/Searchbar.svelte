<script lang="ts">
  import { routes } from '$lib/stores/routes';
  import { setResults } from '$lib/stores/results';
  import { get } from 'svelte/store';
  import {createEventDispatcher, onMount, tick} from 'svelte';
  import Dropdown from './Dropdown.svelte';
  import { search } from '$lib/stores/search';
  import {previousSelectedItem} from "$lib/stores/selectedItem";
  import LanguageSwitcher from "$lib/components/LanguageSwitcher.svelte";
  import {messages} from "$lib/stores/messages";
  import Fuse from 'fuse.js';
  import { searchMode } from '$lib/stores/searchMode';

  export let searchFocused: boolean;
  export let searchInput: HTMLInputElement | null = null;
  export let voiceSearchActive: boolean = false;
  export let selectedItem: any = null;
  export let showBackButton: boolean = false;

  let speechSupported = false;
  let recognizing = false;
  let recognition: SpeechRecognition | null = null;
  let lastVoiceSearch = false;

  const dispatch = createEventDispatcher();

  // Dropdown suggestions
  let suggestions: { type: string; value: string; display: string; displayKannada?: string; platformLabel?: string; platformNumber?: string; }[] = [];

  // Nominatim query state
  let nominatimResults: any[] = [];
  let nominatimLoading = false;
  let nominatimTimeout: number | null = null;

  // Nearby stops state (when location is selected)
  let selectedLocation: { display: string; lat: number; lon: number } | null = null;
  let nearbyStops: Array<{ name: string; distance: number; nameKannada?: string }> = [];
  let stopsCoordinates: Record<string, { name: string; lat: number; lon: number }> = {};
  let stopsCoordinatesByName: Map<string, { lat: number; lon: number }> = new Map();
  let viewbox = '77.5,12.85,77.65,13.0'; // Default, will be updated from geojson

  function formatPlatformLabel(platformNumber: string): string {
    if (!platformNumber) return '';
    const pf = platformNumber.trim();
    // If it's a number, show "Platform <num>"
    if (/^\d+$/.test(pf)) return `Platform ${pf}`;
    // Otherwise it's a named platform like "WEST", "SOUTH" — show "Banashankari <Name>"
    return `Banashankari ${pf.charAt(0).toUpperCase()}${pf.slice(1).toLowerCase()}`;
  }
  let dropdownRef;

  // Parse Nominatim address for display
  function parseAddress(displayName: string): { main: string; detail: string } {
    const parts = displayName.split(',').map(p => p.trim());
    if (parts.length === 0) return { main: displayName, detail: '' };

    const main = parts[0];
    // Filter out pincode, state (Karnataka), country (India, Bharat)
    const detailParts = parts.slice(1).filter(p =>
      !p.match(/^\d{6}$/) && // pincode
      !p.match(/^Karnataka$/i) && // state
      !p.match(/^India$/i) && // country
      !p.match(/^Bharat$/i) // country
    );
    const detail = detailParts.join(', ');
    return { main, detail };
  }

  // Nominatim query function
  async function queryNominatim(query: string) {
    if (!query || query.length < 3) {
      nominatimResults = [];
      return;
    }

    nominatimLoading = true;

    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?` +
        `q=${encodeURIComponent(query)}&` +
        `format=json&limit=5&` +
        `viewbox=${viewbox}&bounded=1`,
        {
          headers: {
            'User-Agent': 'Banashankari Bus Station App'
          }
        }
      );
      const data = await response.json();
      nominatimResults = data || [];
    } catch (error) {
      console.error('Nominatim error:', error);
      nominatimResults = [];
    } finally {
      nominatimLoading = false;
    }
  }

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

  onMount(async () => {
    // Load stops coordinates
    try {
      const response = await fetch('/data/stops-coordinates.json');
      stopsCoordinates = await response.json();
      // Build name-based lookup
      for (const [stopId, stopData] of Object.entries(stopsCoordinates)) {
        stopsCoordinatesByName.set(stopData.name, { lat: stopData.lat, lon: stopData.lon });
      }

      // Calculate viewbox from stops (5km buffer)
      const coords = Object.values(stopsCoordinates).map(s => ({ lat: s.lat, lon: s.lon }));
      if (coords.length > 0) {
        const lats = coords.map(c => c.lat);
        const lons = coords.map(c => c.lon);
        const minLat = Math.min(...lats);
        const maxLat = Math.max(...lats);
        const minLon = Math.min(...lons);
        const maxLon = Math.max(...lons);

        // Add ~5km buffer (roughly 0.045 degrees at this latitude)
        const buffer = 0.045;
        viewbox = `${minLon - buffer},${minLat - buffer},${maxLon + buffer},${maxLat + buffer}`;
      }
    } catch (error) {
      console.error('Failed to load stops coordinates:', error);
    }

    speechSupported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
    if (speechSupported) {
      const SpeechRecognitionClass = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;
      recognition = new SpeechRecognitionClass();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-IN';
      recognition.onstart = () => voiceSearchActive = true;
      recognition.onresult = (event: any) => {
        if (event.results && event.results[0] && event.results[0][0]) {
          search.set(event.results[0][0].transcript);
          lastVoiceSearch = true;
          setTimeout(() => {
            if (dropdownRef && typeof dropdownRef.selectFirst === 'function') {
              dropdownRef.selectFirst();
            }
          }, 0);
        }
        recognizing = false;
        voiceSearchActive = false;
      };
      recognition.onend = () => {
        recognizing = false;
        voiceSearchActive = false;
      };
      recognition.onerror = () => {
        recognizing = false;
        voiceSearchActive = false;
      };
    }
  });

  function startVoiceSearch() {
    if (recognition && !recognizing) {
      recognizing = true;
      recognition.start();
    } else if (recognition && recognizing) {
      recognition.stop();
      recognizing = false;
      voiceSearchActive = false;
    }
  }

  function clearSearch() {
    search.set('');
    selectedItem.set(undefined);
    previousSelectedItem.set(undefined);
    selectedLocation = null;
    nearbyStops = [];
    searchInput?.focus();
  }

  function handleBack() {
    selectedItem.set(undefined);
    previousSelectedItem.set(undefined);
    search.set('');
    searchFocused = false;
    voiceSearchActive = false;
    setResults(get(routes));
    dispatch('back');
    dispatch('closeSheet');
    searchInput?.blur();
  }

  function handleSelectSuggestion(s) {
    if (s.type === 'Toggle') {
      // Toggle search mode
      searchMode.update(mode => mode === 'routes' ? 'location' : 'routes');
      search.set('');
      suggestions = [];
      nominatimResults = [];
      selectedLocation = null;
      nearbyStops = [];
      return;
    }

    if (s.type === 'LocationHeader') {
      // Location header is not clickable, ignore
      return;
    }

    if (s.type === 'Location') {
      // Handle location selection - find nearby stops
      selectedLocation = { display: s.display, lat: s.lat, lon: s.lon };

      // Get all unique stops from routes
      const allRoutes = get(routes);
      const stopsMap = new Map<string, { name: string; nameKannada?: string }>();
      for (const route of allRoutes) {
        if (route.stops && Array.isArray(route.stops)) {
          for (const stop of route.stops) {
            if (stop.name !== 'Banashankari Bus Station' && stop.name !== 'Banashankari') {
              stopsMap.set(stop.name, { name: stop.name, nameKannada: stop.nameKannada });
            }
          }
        }
      }

      // Calculate distances and sort
      const stopsWithDistance = [];
      for (const [stopName, stopData] of stopsMap) {
        const stopCoord = stopsCoordinatesByName.get(stopName);
        if (stopCoord) {
          const distance = getDistance(s.lat, s.lon, stopCoord.lat, stopCoord.lon);
          stopsWithDistance.push({ ...stopData, distance });
        }
      }

      nearbyStops = stopsWithDistance
        .sort((a, b) => a.distance - b.distance)
        .slice(0, 10);

      search.set(s.display);
      return;
    }

    // Clear location selection state when selecting any item
    selectedLocation = null;
    nearbyStops = [];

    // For Stop type in location mode, find the best platform
    if (s.type === 'Stop' && $searchMode === 'location') {
      const allRoutes = get(routes);
      const routesToStop = allRoutes.filter(r =>
        r.stops && r.stops.some(stop => stop.name === s.display)
      );

      // Group by platform and count
      const platformCounts = new Map<string, number>();
      for (const route of routesToStop) {
        const platform = route.platformNumber;
        platformCounts.set(platform, (platformCounts.get(platform) || 0) + 1);
      }

      // Find platform with most routes
      let bestPlatform = '';
      let maxCount = 0;
      for (const [platform, count] of platformCounts) {
        if (count > maxCount) {
          maxCount = count;
          bestPlatform = platform;
        }
      }

      // Set selectedItem with platform filter
      selectedItem.set(undefined);
      previousSelectedItem.set(undefined);
      tick().then(() => {
        search.set(s.display);
        searchFocused = false;
        voiceSearchActive = false;
        const itemWithPlatform = {
          ...s,
          platformNumber: bestPlatform
        };
        dispatch('select', itemWithPlatform);
      });
      return;
    }

    selectedItem.set(undefined);
    previousSelectedItem.set(undefined);
    tick().then( () => {
      search.set(s.display);
      searchFocused = false;
      voiceSearchActive = false;
      dispatch('select', s);
    });
  }

  // Debounced Nominatim query
  $: if ($searchMode === 'location' && $search && $search.trim().length > 0) {
    // Clear selected location when user starts typing again (unless they're typing the selected location)
    if (selectedLocation && $search !== selectedLocation.display) {
      selectedLocation = null;
      nearbyStops = [];
    }

    if (nominatimTimeout) clearTimeout(nominatimTimeout);
    nominatimTimeout = setTimeout(() => {
      queryNominatim($search.trim());
    }, 300) as unknown as number;
  } else {
    nominatimResults = [];
    nominatimLoading = false;
  }

  // Search logic: by destination or bus number (not platform)
  $: if ($search && $search.trim().length > 0) {
    const q = $search.trim().toLowerCase();
    const allRoutes = get(routes);
    const matched = new Set();
    const areaViaSet = new Map<string, {type: string, display: string, displayKannada: string, value: string, platformLabel: string}>();
    const stopSet = new Map<string, {display: string, displayKannada: string, value: string, platformLabel: string}>();
    const routeSet = new Map<string, {display: string, value: string, platformLabel: string, destination: string}>();

    // Use fuzzy search only if lastVoiceSearch is true
    let filteredRoutes = allRoutes;
    let didVoiceSelect = false;
    if (lastVoiceSearch) {
      const fuse = new Fuse(allRoutes, {
        keys: [
          'number',
          'destination',
          'kannadaDestination',
          'area.name',
          'area.nameKannada',
          'via.name',
          'via.nameKannada',
          'stops.name',
          'stops.nameKannada'
        ],
        threshold: 0.4
      });
      filteredRoutes = fuse.search(q).map(r => r.item);
      lastVoiceSearch = false;
      didVoiceSelect = true;
    } else {
      filteredRoutes = allRoutes;
    }

    for (const route of filteredRoutes) {
      const pfLabel = formatPlatformLabel(route.platformNumber || '');
      // Area
      if (route.area) {
        if (
          (route.area.name && route.area.name.toLowerCase().includes(q)) ||
          (route.area.nameKannada && route.area.nameKannada.toLowerCase().includes(q))
        ) {
          if (route.area.name) {
            const key = `${route.area.name}__${route.platformNumber || ''}`;
            areaViaSet.set(key, {type: 'Area', display: route.area.name, displayKannada: route.area.nameKannada || '', value: route.area.name, platformLabel: pfLabel});
            matched.add(route);
          }
        }
      }
      // Via (handle both array and object)
      if (route.via) {
        if (Array.isArray(route.via)) {
          for (const v of route.via) {
            if (
              (v.name && v.name.toLowerCase().includes(q)) ||
              (v.nameKannada && v.nameKannada.toLowerCase().includes(q))
            ) {
              if (v.name) {
                const key = `${v.name}__${route.platformNumber || ''}`;
                areaViaSet.set(key, {type: 'Area', display: v.name, displayKannada: v.nameKannada || '', value: v.name, platformLabel: pfLabel});
                matched.add(route);
              }
            }
          }
        } else if (
          (route.via.name && route.via.name.toLowerCase().includes(q)) ||
          (route.via.nameKannada && route.via.nameKannada.toLowerCase().includes(q))
        ) {
          if (route.via.name) {
            const key = `${route.via.name}__${route.platformNumber || ''}`;
            areaViaSet.set(key, {type: 'Area', display: route.via.name, displayKannada: route.via.nameKannada || '', value: route.via.name, platformLabel: pfLabel});
            matched.add(route);
          }
        }
      }
      // Stops
      if (route.stops && Array.isArray(route.stops)) {
        for (const s of route.stops) {
          if(s.name && s.name == "Banashankari Bus Station" || s.name == "Banashankari") {
            continue;
          }
          if (
            (s.name && s.name.toLowerCase().includes(q)) ||
            (s.nameKannada && s.nameKannada.toLowerCase().includes(q))
          ) {
            if (s.name) {
              const key = `${s.name}__${route.platformNumber || ''}`;
              stopSet.set(key, {display: s.name, displayKannada: s.nameKannada || '', value: s.name, platformLabel: pfLabel});
              matched.add(route);
            }
          }
        }
      }
      // Route number — create per-platform entries
      if (route.number && route.number.toLowerCase().includes(q)) {
        if (route.number) {
          const key = `${route.number}__${route.platformNumber || ''}`;
          routeSet.set(key, {display: route.number, value: route.number, platformLabel: formatPlatformLabel(route.platformNumber || ''), destination: route.destination || ''});
          matched.add(route);
        }
      }
    }
    // Remove areaViaSet entries whose display name matches a stopSet display name
    const stopDisplayNames = new Set(Array.from(stopSet.values()).map(v => v.display));
    for (const [key, val] of areaViaSet) {
      if (stopDisplayNames.has(val.display)) {
        areaViaSet.delete(key);
      }
    }
    // Sort route suggestions by shortest display, then platform label
    const sortedRouteSuggestions = Array.from(routeSet.entries())
      .map(([key, obj]) => {
        // Extract platformNumber from the key (format: "routeNumber__platformNumber")
        const platformNumber = key.split('__')[1] || '';
        return {
          type: 'Route',
          value: obj.value,
          display: obj.display,
          destination: obj.destination,
          platformLabel: obj.platformLabel,
          platformNumber: platformNumber
        };
      })
      .sort((a, b) => a.display.length - b.display.length || (a.platformLabel || '').localeCompare(b.platformLabel || ''));
    // Count routes per stop/area per platform for sorting
    const stopRouteCounts = new Map<string, number>();
    const areaRouteCounts = new Map<string, number>();

    for (const route of filteredRoutes) {
      // Count for stops
      if (route.stops && Array.isArray(route.stops)) {
        for (const s of route.stops) {
          if (s.name && s.name.toLowerCase().includes(q)) {
            const key = `${s.name}__${route.platformNumber || ''}`;
            stopRouteCounts.set(key, (stopRouteCounts.get(key) || 0) + 1);
          }
        }
      }
      // Count for areas/via
      if (route.area && route.area.name && route.area.name.toLowerCase().includes(q)) {
        const key = `${route.area.name}__${route.platformNumber || ''}`;
        areaRouteCounts.set(key, (areaRouteCounts.get(key) || 0) + 1);
      }
      if (route.via && route.via.name && route.via.name.toLowerCase().includes(q)) {
        const key = `${route.via.name}__${route.platformNumber || ''}`;
        areaRouteCounts.set(key, (areaRouteCounts.get(key) || 0) + 1);
      }
    }

    // Create stop suggestions with route counts and sort by count (descending)
    const stopSuggestions = Array.from(stopSet.entries())
      .map(([key, obj]) => {
        const platformNumber = key.split('__')[1] || '';
        const routeCount = stopRouteCounts.get(key) || 0;
        return {
          type: 'Stop',
          value: obj.value,
          display: obj.display,
          displayKannada: obj.displayKannada,
          platformLabel: obj.platformLabel,
          platformNumber: platformNumber,
          routeCount: routeCount
        };
      })
      .sort((a, b) => b.routeCount - a.routeCount);

    // Create area suggestions with route counts and sort by count (descending)
    const areaSuggestions = Array.from(areaViaSet.entries())
      .map(([key, obj]) => {
        const platformNumber = key.split('__')[1] || '';
        const routeCount = areaRouteCounts.get(key) || 0;
        return {
          ...obj,
          platformNumber: platformNumber,
          routeCount: routeCount
        };
      })
      .sort((a, b) => b.routeCount - a.routeCount);

    // Build suggestions based on search mode
    if ($searchMode === 'location') {
      // Location mode
      const toggleSuggestion = {
        type: 'Toggle',
        value: '',
        display: 'Search by Stop Name',
        icon: 'directions_bus'
      };

      if (selectedLocation && nearbyStops.length > 0) {
        // Show selected location header + nearby stops
        const locationHeader = {
          type: 'LocationHeader',
          value: selectedLocation.display,
          display: selectedLocation.display,
          icon: 'place'
        };
        const nearbyStopsSuggestions = nearbyStops.map(stop => ({
          type: 'Stop',
          value: stop.name,
          display: stop.name,
          displayKannada: stop.nameKannada,
          distance: Math.round(stop.distance)
        }));
        suggestions = [toggleSuggestion, locationHeader, ...nearbyStopsSuggestions];
      } else {
        // Show nominatim location results
        const locationSuggestions = nominatimResults.map(result => {
          const parsed = parseAddress(result.display_name);
          return {
            type: 'Location',
            value: result.display_name,
            display: parsed.main,
            displayDetail: parsed.detail,
            lat: parseFloat(result.lat),
            lon: parseFloat(result.lon)
          };
        });
        suggestions = [toggleSuggestion, ...locationSuggestions];
      }
    } else {
      // Routes mode - show toggle + route/stop/area suggestions
      const toggleSuggestion = {
        type: 'Toggle',
        value: '',
        display: 'Search by Address',
        icon: 'location_on'
      };
      suggestions = [
        toggleSuggestion,
        ...sortedRouteSuggestions,
        ...stopSuggestions,
        ...areaSuggestions,
      ];
    }
    setResults(Array.from(matched));
    // Automatically select first suggestion for voice search
    if (didVoiceSelect && suggestions.length > 0) {
      tick().then(() => {
        if (dropdownRef && typeof dropdownRef.selectFirst === 'function') {
          dropdownRef.selectFirst();
        }
      });
    }
  } else {
    setResults(get(routes));
  }
</script>

<!-- Back button row (when search is active, sheet/sidebar is open, or showBackButton is true) -->
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

<!-- Flex row: search bar only -->
<div class="cupertino-bar-row">
  <div class="cupertino-bar-flex">
    <div class="cupertino-searchbar {searchFocused || voiceSearchActive ? 'cupertino-searchbar-focused' : ''}">
      <span class="material-icons cupertino-search-icon">search</span>
      <input
        bind:this={searchInput}
        class="cupertino-input"
        type="text"
        placeholder={$messages.search()}
        bind:value={$search}
        autofocus={searchFocused || voiceSearchActive}
        on:focus={() => searchFocused = true}
        autocomplete="off"
      />
      {#if $search}
        <button class="material-icons cupertino-clear" type="button" on:click={clearSearch} aria-label="Clear">close</button>
      {/if}
      {#if speechSupported}
        <button class="material-icons cupertino-mic" type="button" on:click={startVoiceSearch} aria-label="Voice Search">{recognizing ? 'mic' : 'mic_none'}</button>
      {/if}
    </div>
  </div>
</div>

{#if (searchFocused || voiceSearchActive) && $search && suggestions.length > 0}
  <Dropdown bind:this={dropdownRef} {suggestions} {$search} onSelect={handleSelectSuggestion} loading={nominatimLoading} />
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
.cupertino-mic {
  background: none;
  border: none;
  color: #007aff;
  font-size: 22px;
  margin-left: 2px;
  cursor: pointer;
  padding: 4px;
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
</style> 