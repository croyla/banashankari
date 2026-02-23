<script lang="ts">
  import {search} from "$lib/stores/search";
  import {previousSelectedItem, selectedItem} from "$lib/stores/selectedItem";
  import BusModal from "$lib/components/BusModal.svelte";

  export let suggestions: { type: string; value: string; display: string; displayKannada?: string; displayDetail?: string; platformLabel?: string; platformNumber?: string; destination?: string; icon?: string; lat?: number; lon?: number; distance?: number; }[] = [];
  export let loading: boolean = false;
  export let onSelect: (s: any) => void = (s) => {
    previousSelectedItem.set(undefined);
    selectedItem.set(undefined);
    selectedItem.set(s);
  };

  // Expose a method to select the first suggestion
  export function selectFirst() {
    if (suggestions.length > 0) {
      onSelect(suggestions[0]);
    }
  }

  function highlightSegments(text: string, query: string) {
    if (!text || !query) return [{ text, highlight: false }];
    const idx = text.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) return [{ text, highlight: false }];
    return [
      { text: text.slice(0, idx), highlight: false },
      { text: text.slice(idx, idx + query.length), highlight: true },
      { text: text.slice(idx + query.length), highlight: false }
    ];
  }
</script>

{#if suggestions.length > 0}
  <div class="cupertino-suggestions-dropdown" role="listbox">
    {#each suggestions as s, i (s.type + '-' + (s.type === 'Location' && s.lat && s.lon ? `${s.lat}_${s.lon}` : (s.value ?? s.display ?? s.displayKannada ?? i)) + '-' + (s.platformLabel ?? ''))}
      {#if s.type !== 'Route'}
      <button
        type="button"
        class="cupertino-suggestion-item {s.type === 'Toggle' ? 'toggle-item' : ''} {s.type === 'LocationHeader' ? 'location-header-item' : ''}"
        role="option"
        aria-label={(s.platformLabel ? `${s.display}, From ${s.platformLabel}` : s.displayKannada ? `${s.display}, ${s.displayKannada}` : s.display) }
        on:click={() => s.type !== 'LocationHeader' && onSelect(s)}
        disabled={s.type === 'LocationHeader'}
      >
        {#if s.type === 'Toggle'}
          <span class="material-icons suggestion-icon">{s.icon}</span>
          <span class="cupertino-suggestion-main">{s.display}</span>
        {:else if s.type === 'Location'}
          <span class="material-icons suggestion-icon">place</span>
          <span class="cupertino-suggestion-labels">
            <span class="cupertino-suggestion-main">{s.display}</span>
            {#if s.displayDetail}
              <span class="cupertino-suggestion-secondary">{s.displayDetail}</span>
            {/if}
          </span>
        {:else if s.type === 'LocationHeader'}
          <span class="material-icons suggestion-icon">{s.icon}</span>
          <div class="location-header-content">
            <span class="location-header-title">Selected Location</span>
            <span class="location-header-name">{s.display}</span>
            <span class="nearby-stops-label">Nearby Stops</span>
          </div>
        <!--{:else if s.type === 'Route'}-->
<!--          <div class="cupertino-suggestion-prefix">-->
<!--            <BusModal number={s.display} />-->
<!--          </div>-->
<!--          <span class="cupertino-suggestion-labels">-->
<!--            {#if s.destination}-->
<!--              <span class="cupertino-suggestion-main">To {s.destination}</span>-->
<!--            {/if}-->
<!--            {#if s.platformLabel}-->
<!--              <span class="cupertino-suggestion-platform">From {s.platformLabel}</span>-->
<!--            {/if}-->
<!--          </span>-->
        {:else}
          {#if s.type === 'Stop' && s.distance !== undefined}
            <span class="material-icons suggestion-icon">directions_bus</span>
          {/if}
          <span class="cupertino-suggestion-labels">
            {#if $search && s.display && s.display.toLowerCase().includes($search.trim().toLowerCase())}
              <span class="cupertino-suggestion-main">
                {#each highlightSegments(s.display, $search) as seg}
                  {#if seg.highlight}<b>{seg.text}</b>{:else}{seg.text}{/if}
                {/each}
                {#if s.distance !== undefined}
                  <span class="stop-distance">({s.distance}m)</span>
                {/if}
              </span>
            {:else if $search && s.displayKannada && s.displayKannada.toLowerCase().includes($search.trim().toLowerCase())}
              <span class="cupertino-suggestion-main">
                {#each highlightSegments(s.displayKannada, $search) as seg}
                  {#if seg.highlight}<b>{seg.text}</b>{:else}{seg.text}{/if}
                {/each}
                {#if s.distance !== undefined}
                  <span class="stop-distance">({s.distance}m)</span>
                {/if}
              </span>
            {:else}
              {#if s.display}
                <span class="cupertino-suggestion-main">
                  {s.display}
                  {#if s.distance !== undefined}
                    <span class="stop-distance">({s.distance}m)</span>
                  {/if}
                </span>
              {/if}
            {/if}
            {#if s.platformLabel}
              <span class="cupertino-suggestion-platform">From {s.platformLabel}</span>
            {/if}
          </span>
        {/if}
      </button>
      {/if}
    {/each}

    {#if loading}
      <div class="loading-row">
        <span class="material-icons loading-spinner">hourglass_empty</span>
        <span class="loading-text">Searching...</span>
      </div>
    {/if}
  </div>
{/if}

<style>
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600&display=swap');
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
  max-height: 260px;
  overflow-y: auto;
  font-family: 'Manrope', sans-serif;
}
.cupertino-suggestion-item {
  padding: 14px 20px 14px 20px;
  font-size: 16px;
  color: #222;
  cursor: pointer;
  transition: background 0.15s;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-height: 48px;
  flex-direction: row;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
}
.cupertino-suggestion-item:hover, .cupertino-suggestion-item:focus {
  background: #f1f1f3;
  outline: none;
}
.cupertino-suggestion-prefix {
  font-size: 18px;
  font-weight: 700;
  color: #888;
  flex-shrink: 0;
  margin-right: 2px;
  margin-top: 1px;
}
.cupertino-suggestion-main {
  justify-content: center;
  font-size: 17px;
  margin-top: 2px;
  color: #222;
  font-weight: 400;
  display: block;
  line-height: 1.2;
}
.cupertino-suggestion-main b {
  font-weight: 700;
}
.cupertino-suggestion-secondary {
  display: block;
  font-size: 14px;
  color: #888;
  margin-top: 2px;
  line-height: 1.1;
}
.cupertino-suggestion-platform {
  font-size: 13px;
  color: #8e8e93;
  font-weight: 400;
  margin-top: 3px;
  line-height: 1.2;
}
.cupertino-suggestion-labels {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}
.toggle-item {
  background: #f8f8f8;
  border-bottom: 1px solid #e0e0e5;
  font-weight: 500;
}
.toggle-item:hover, .toggle-item:focus {
  background: #ececee;
}
.suggestion-icon {
  font-size: 20px;
  color: #8e8e93;
  flex-shrink: 0;
}
.loading-row {
  padding: 14px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  color: #8e8e93;
}
.loading-spinner {
  font-size: 20px;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
.loading-text {
  font-size: 15px;
  font-weight: 400;
}
.location-header-item {
  background: #f0f0f2;
  cursor: default;
  padding: 16px 20px;
}
.location-header-item:hover, .location-header-item:focus {
  background: #f0f0f2;
}
.location-header-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}
.location-header-title {
  font-size: 13px;
  color: #8e8e93;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.location-header-name {
  font-size: 15px;
  color: #1A1A1A;
  font-weight: 600;
}
.nearby-stops-label {
  font-size: 13px;
  color: #8e8e93;
  font-weight: 500;
  margin-top: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.stop-distance {
  color: #8e8e93;
  font-weight: 400;
  margin-left: 6px;
  font-size: 14px;
}
</style> 