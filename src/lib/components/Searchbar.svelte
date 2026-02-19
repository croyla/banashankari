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

  function formatPlatformLabel(platformNumber: string): string {
    if (!platformNumber) return '';
    const pf = platformNumber.trim();
    // If it's a number, show "Platform <num>"
    if (/^\d+$/.test(pf)) return `Platform ${pf}`;
    // Otherwise it's a named platform like "WEST", "SOUTH" — show "Banashankari <Name>"
    return `Banashankari ${pf.charAt(0).toUpperCase()}${pf.slice(1).toLowerCase()}`;
  }
  let dropdownRef;

  onMount(() => {
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
    selectedItem.set(undefined);
    previousSelectedItem.set(undefined);
    tick().then( () => {
      search.set(s.display);
      searchFocused = false;
      voiceSearchActive = false;
      dispatch('select', s);
    });
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

    suggestions = [
      ...sortedRouteSuggestions,
      ...stopSuggestions,
      ...areaSuggestions,
    ];
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
  <Dropdown bind:this={dropdownRef} {suggestions} {$search} onSelect={handleSelectSuggestion} />
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