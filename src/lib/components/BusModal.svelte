<script lang="ts">
  export let number: string | number;
  import RouteIcon from '../../assets/icons/route.svg';

  function formatNumber(raw: string | number): string {
    const s = String(raw);
    const noDash = s.replace(/-/g, '');
    const parts = noDash.split(' ').filter(Boolean);
    if (parts.length === 0) return noDash;
    const first = parts[0];
    if (/\d/.test(first)) return first;
    return parts.length > 1 ? `${first} ${parts[1]}` : first;
  }
</script>

<div class="busmodal-outer">
  <div class="busmodal-inner">
    <span class="busmodal-icon">
      <RouteIcon width="14" height="16.8" />
    </span>
    <span class="busmodal-number">{formatNumber(number)}</span>
  </div>
</div>

<style>
.busmodal-outer {
  /*display: flex;*/
  /*flex-direction: column;*/
  justify-content: center;
  align-items: center;
  padding: 4px;
  gap: 4.23px;
  height: 24.8px;
  background: rgba(118, 118, 128, 0.12);
  border-radius: 4px;
  flex: none;
  /*order: 1;*/
  flex-grow: 0;
}
.busmodal-inner {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 0px;
  gap: 4px;
  height: 16.8px;
  flex: none;
  /*order: 0;*/
  /* align-self: stretch; */
  flex-grow: 0;
}
.busmodal-icon {
  display: flex;
  height: 16.8px;
  flex: none;
  order: 0;
  flex-grow: 0;
}
.busmodal-number {
  display: flex;
  height: 12px;
  font-family: 'Manrope', sans-serif;
  font-style: normal;
  font-weight: 600;
  font-size: 16px;
  line-height: 22px;
  color: #000000;
  flex: none;
  order: 1;
  flex-grow: 0;
  align-items: center;
  justify-content: flex-start;
}
</style> 