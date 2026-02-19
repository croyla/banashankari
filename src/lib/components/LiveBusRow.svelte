<script lang="ts">
  import type { LiveArrival } from '$lib/stores/liveArrivals';
  import { focusedLiveBus } from '$lib/stores/liveArrivals';

  export let arrival: LiveArrival;
  export let searchedStop: string | null = null; // The stop being searched, for "via X" display

  $: hasLocation = !!arrival.location;

  function handleClick() {
    if (hasLocation) {
      focusedLiveBus.set(arrival);
    }
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="live-row" class:has-location={hasLocation} on:click={handleClick}>
  <div class="col-line">
    <div class="route-number">{arrival.display_number}</div>
    {#if arrival.bus_no}
      <div class="bus-number">{arrival.bus_no}</div>
    {/if}
  </div>

  <div class="col-dest">
    <div class="destination">{arrival.route_name}</div>
    {#if searchedStop}
      <div class="via-stop">Via {searchedStop}</div>
    {/if}
  </div>

  <div class="col-arrival">
    <div class="arrival-time">{arrival.minutes_away} min{arrival.minutes_away !== 1 ? 's' : ''}</div>
    {#if hasLocation}
      <span class="location-dot pulsing"></span>
    {/if}
  </div>
</div>

<style>
.live-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: #EEEEEE;
  border-radius: 8px;
  min-width: 0;
}
.live-row.has-location {
  cursor: pointer;
}
.col-line {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  min-width: 0;
}
.route-number {
  font-family: 'Manrope', sans-serif;
  font-size: 16px;
  font-weight: 700;
  color: #1A1A1A;
  white-space: nowrap;
}
.bus-number {
  font-family: 'Manrope', sans-serif;
  font-size: 12px;
  font-weight: 400;
  color: #888;
  white-space: nowrap;
}
.col-dest {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  overflow: hidden;
}
.destination {
  font-family: 'Manrope', sans-serif;
  font-size: 15px;
  font-weight: 400;
  color: #1A1A1A;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.via-stop {
  font-family: 'Manrope', sans-serif;
  font-size: 12px;
  font-weight: 400;
  color: #888;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.col-arrival {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}
.arrival-time {
  font-family: 'Manrope', sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: #1A1A1A;
  white-space: nowrap;
}
.location-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: #4CAF50;
  border-radius: 50%;
}
.pulsing {
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.7); }
}
</style>
