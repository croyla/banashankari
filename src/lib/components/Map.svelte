<script lang="ts">
    import maplibregl from 'maplibre-gl';
    import 'maplibre-gl/dist/maplibre-gl.css';
    import {onMount, tick} from 'svelte';
    import {setPlatforms} from '$lib/stores/platforms';
    import {setRoutes} from '$lib/stores/routes';
    import {results, setResults} from '$lib/stores/results';
    import {displayedLiveArrivals, focusedLiveBus} from '$lib/stores/liveArrivals';
    import {get} from 'svelte/store';
    import {Platform} from '$lib/types/Platform';
    import {previousSelectedItem, selectedItem} from '$lib/stores/selectedItem';

    const banashankari_CENTER: maplibregl.LngLatLike = [77.5736529, 12.917500]; // [lng, lat]
    let showResetBounds = false;
    let platformBounds: maplibregl.LngLatBounds | null = null;

    // // Raster overlay boundaries
    // let overlayBounds = [
    //     [
    //         77.57002448255838,
    //         12.979030212561781
    //     ],
    //     [
    //         77.57465645568396,
    //         12.979030212561781
    //     ],
    //     [
    //         77.57465645568396,
    //         12.977137224193143
    //     ],
    //     [
    //         77.57002448255838,
    //         12.977137224193143
    //     ]
    // ];

    let map: maplibregl.Map | undefined;
    let platformsGeoJson: GeoJSON.FeatureCollection | null = null;

    function getFitBoundsPadding(): number {
        const el = document.getElementById('map');
        if (!el) return 60;
        return Math.max(20, Math.floor(Math.min(el.clientWidth, el.clientHeight) * 0.12));
    }

    function updatePlatformColors() {
        if (!map || !platformsGeoJson) return;
        // Use the global search value to determine if a search is active
        const currentResults = get(results);
        const resultRouteIds = new Set(currentResults ? currentResults.map(r => r.number) : []);

        // Check if there's a platform filter active
        const currentSelectedItem = get(selectedItem);
        const activePlatformFilter = currentSelectedItem?.platformNumber?.toUpperCase() || null;

        // Clone the geojson
        const updated = JSON.parse(JSON.stringify(platformsGeoJson));
        for (const feature of updated.features) {
            // Store original color
            if (!feature.properties.OriginalColor) {
                feature.properties.OriginalColor = feature.properties.Color;
            }
            const platformRoutes = (feature.properties && Array.isArray(feature.properties.Routes)) ? feature.properties.Routes : [];
            const platformNumber = feature.properties.Platform?.toString().toUpperCase() || '';

            // If platform filter is active, only highlight that specific platform
            let isGray;
            if (activePlatformFilter) {
                isGray = platformNumber !== activePlatformFilter;
            } else {
                // Otherwise, use route matching logic
                isGray = !platformRoutes.some((route) => Object.hasOwn(route, 'Route') && resultRouteIds.has(route.Route));
            }

            feature.properties.isGray = isGray;
            feature.properties.Color = isGray ? '#D2D2D2' : feature.properties.OriginalColor || feature.properties.Color;
        }
        // Update the map source
        if (map.getSource('platforms')) {
            (map.getSource('platforms')! as maplibregl.GeoJSONSource).setData(updated);
        }
    }

    onMount(() => {

        map = new maplibregl.Map({
            container: 'map',
            style: {
                version: 8,
                glyphs: 'glyphs/{fontstack}/{range}.pbf',
                sources: {
                    carto: {
                        type: 'raster',
                        tiles: [
                            'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'
                        ],
                        tileSize: 256,
                        attribution: '© OpenStreetMap contributors, © CartoDB'
                    }
                },
                layers: [
                    {
                        id: 'carto',
                        type: 'raster',
                        source: 'carto'
                    }
                ]
            },
            center: banashankari_CENTER,
            zoom: 16.8,
            dragRotate: false,
            bearing: 0,
            pitch: 0,
            maxPitch: 0,
            minPitch: 0
        });
        // Subscribe to results and update platform colors on change
        const unsubResults = results.subscribe(() => {
            if (map && platformsGeoJson) {
                updatePlatformColors();
            }
        });

        // Subscribe to selectedItem to update when platform filter changes
        const unsubSelected = selectedItem.subscribe(() => {
            if (map && platformsGeoJson) {
                updatePlatformColors();
            }
        });

        // Subscribe to displayed live arrivals and update bus markers on the map
        const unsubLive = displayedLiveArrivals.subscribe(arrivals => {
            if (!map) return;
            const features: GeoJSON.Feature[] = arrivals
                .filter(a => a.location)
                .map(a => ({
                    type: 'Feature' as const,
                    geometry: { type: 'Point' as const, coordinates: [a.location!.lng, a.location!.lat] },
                    properties: {
                        bus_no: a.bus_no || '',
                        display_number: a.display_number,
                        vehicle_id: String(a.vehicle_id || '')
                    }
                }));
            const geojson: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features };
            if (map.getSource('live-buses')) {
                (map.getSource('live-buses') as maplibregl.GeoJSONSource).setData(geojson);
            }
        });

        // Subscribe to focusedLiveBus and pan map to that bus location
        const unsubFocused = focusedLiveBus.subscribe(bus => {
            if (!map || !bus || !bus.location) return;
            map.easeTo({
                center: [bus.location.lng, bus.location.lat],
                zoom: Math.max(map.getZoom(), 17),
                duration: 600
            });
            showResetBounds = true;
        });

        // Prevent rotation and pitch changes
        map.on('rotate', () => {
            map.setBearing(0);
        });
        
        map.on('pitch', () => {
            map.setPitch(0);
        });
        
        map.on('load', () => {
            // map.addSource('majestic-overlay', {
            //     type: 'image',
            //     url: '/data/majestic-alpha-overlay.png',
            //     coordinates: overlayBounds
            // });
            //
            // map.addLayer({
            //     id: 'majestic-overlay-layer',
            //     type: 'raster',
            //     source: 'majestic-overlay',
            //     paint: {
            //         'raster-opacity': 1
            //     }
            // });
            const urlParams = new URLSearchParams(window.location.search);
            const paramType = urlParams.get('pf') ? 'pf' : urlParams.get('r') ? 'r' : urlParams.get('s') ? 's' : urlParams.get('a') ? 'a' : undefined;
            const paramValue = paramType ? urlParams.get(paramType) : undefined;

            // Add platforms geojson
            fetch('/data/platforms-routes-banashankari.geojson')
                .then(r => r.json())
                .then((data: GeoJSON.FeatureCollection) => {
                    if(!map) return;
                    // Set isGray property for all features initially
                    const currentResults = get(results);
                    const resultRouteIds = new Set(currentResults ? currentResults.map(r => r.number) : []);
                    const bounds = new maplibregl.LngLatBounds();
                    for (const feature of data.features) {
                        bounds.extend((feature.geometry as GeoJSON.Point).coordinates);
                        const platformRoutes = (feature.properties && Array.isArray(feature.properties.Routes)) ? feature.properties.Routes : [];
                        feature.properties!.isGray = !platformRoutes.some((route) => Object.hasOwn(route, 'Route') && resultRouteIds.has(route.Route));
                    }
                    map.fitBounds(bounds, {padding: getFitBoundsPadding()});
                    platformsGeoJson = data;
                    // Store platforms as Platform class instances
                    const platformsArr = (data.features || []).map(feature => {
                        const platformNumber = feature.properties?.Platform?.toString().toUpperCase() || '';
                        const color = feature.properties?.Color || '#008F45';
                        const icon = feature.properties?.Icon || null;
                        const routes = (feature.properties?.Routes || []).map(route => {
                            // Convert stops
                            const stops = (route.Stops || []).map((s) => ({ name: s.name, nameKannada: s.name_kn}));
                            // Convert via
                            const via = { name: route.Via, nameKannada: route.KannadaVia };
                            // Convert area
                            const area = { name: route.Area, nameKannada: route.KannadaArea };
                            return {
                                number: route.Route,
                                area,
                                stops,
                                via,
                                destination: route.Destination,
                                kannadaDestination: route.KannadaDestination,
                                platformNumber: route.PlatformNumber.toUpperCase()
                            };
                        });
                        return new Platform({ platformNumber, color, icon, routes });
                    });
                    setPlatforms(platformsArr);

                    // Flatten all routes from all platforms, convert to Route types
                    const allRoutes = [];
                    for (const platform of platformsArr) {
                        for (const route of platform.routes) {
                            allRoutes.push(route);
                        }
                    }
                    setRoutes(allRoutes);

                    map.addSource('platforms', {
                        type: 'geojson',
                        data
                    });
                    // Add gray platforms layer (bottom)
                    map.addLayer({
                        id: 'platform-circles-gray',
                        type: 'circle',
                        source: 'platforms',
                        filter: ['==', ['get', 'isGray'], true],
                        paint: {
                            'circle-radius': [
                                'interpolate',
                                ['linear'],
                                ['zoom'],
                                13.7, 2,
                                14.7, 2.25,
                                15.7, 6,
                                16.7, 16
                            ],
                            'circle-color': '#D2D2D2'
                        }
                    });
                    // Add gray platform labels (just above gray circles)
                    map.addLayer({
                        id: 'platform-labels-gray',
                        type: 'symbol',
                        source: 'platforms',
                        filter: ['==', ['get', 'isGray'], true],
                        layout: {
                            'text-field': ['to-string', ['get', 'Icon']],
                            'text-size': 16,
                            'text-font': ['Manrope SemiBold'],
                            'text-offset': [0, 0],
                            'text-anchor': 'center',
                            'text-allow-overlap': true
                        },
                        paint: {
                            'text-color': '#fff',
                            'text-halo-width': 0,
                            'text-opacity': [
                                'interpolate',
                                ['linear'],
                                ['zoom'],
                                16.5, 0,
                                16.7, 1
                            ]
                        }
                    });
                    // Add colored platforms layer (top)
                    map.addLayer({
                        id: 'platform-circles-colored',
                        type: 'circle',
                        source: 'platforms',
                        filter: ['==', ['get', 'isGray'], false],
                        paint: {
                            'circle-radius': [
                                'interpolate',
                                ['linear'],
                                ['zoom'],
                                // 12.7, 0.31,
                                13.7, 2,
                                14.7, 2.25,
                                15.7, 6,
                                16.7, 16
                            ],
                            'circle-color': [
                                'coalesce',
                                ['get', 'Color'],
                                '#008F45'
                            ]
                        }
                    });
                    // Add colored platform labels (just above colored circles)
                    map.addLayer({
                        id: 'platform-labels-colored',
                        type: 'symbol',
                        source: 'platforms',
                        filter: ['==', ['get', 'isGray'], false],
                        layout: {
                            'text-field': ['to-string', ['get', 'Icon']],
                            'text-size': 16
                            //     [
                            //     'interpolate',
                            //     ['linear'],
                            //     ['zoom'],
                            //     12, 1,
                            //     13, 2,
                            //     14, 4,
                            //     15, 8,
                            //     16.5, 16
                            // ]
                            ,
                            'text-font': ['Manrope SemiBold'],
                            'text-offset': [0, 0],
                            'text-anchor': 'center',
                            'text-allow-overlap': true
                        },
                        paint: {
                            'text-color': '#fff',
                            'text-halo-width': 0,
                            'text-opacity': [
                                'interpolate',
                                ['linear'],
                                ['zoom'],
                                16.5, 0,
                                16.7, 1
                            ]
                        }
                    });
                    // Remove the original single platform-circles and platform-labels layers if present
                    if (map.getLayer('platform-circles')) {
                        map.removeLayer('platform-circles');
                    }
                    if (map.getLayer('platform-labels')) {
                        map.removeLayer('platform-labels');
                    }

                    // Add live bus source and layers
                    map.addSource('live-buses', {
                        type: 'geojson',
                        data: { type: 'FeatureCollection', features: [] }
                    });
                    map.addLayer({
                        id: 'live-bus-circles',
                        type: 'circle',
                        source: 'live-buses',
                        paint: {
                            'circle-radius': [
                                'interpolate', ['linear'], ['zoom'],
                                13.7, 3, 15.7, 7, 16.7, 10
                            ],
                            'circle-color': '#4CAF50',
                            'circle-stroke-width': 1.5,
                            'circle-stroke-color': '#fff'
                        }
                    });
                    map.addLayer({
                        id: 'live-bus-labels',
                        type: 'symbol',
                        source: 'live-buses',
                        layout: {
                            'text-field': ['to-string', ['get', 'bus_no']],
                            'text-size': 11,
                            'text-font': ['Manrope SemiBold'],
                            'text-offset': [0, 1.6],
                            'text-anchor': 'top',
                            'text-allow-overlap': false
                        },
                        paint: {
                            'text-color': '#1A1A1A',
                            'text-halo-color': '#fff',
                            'text-halo-width': 1,
                            'text-opacity': [
                                'interpolate', ['linear'], ['zoom'],
                                16.2, 0, 16.7, 1
                            ]
                        }
                    });

                    // Store platform bounds for reset
                    platformBounds = bounds;

                    // Add click listener for platform features
                    map.on('click', (e) => {
                        const features = map.queryRenderedFeatures(e.point, { layers: ['platform-circles-gray', 'platform-circles-colored'] });
                        if (features && features.length > 0) {
                            const feature = features[0];
                            if (feature && feature.properties && feature.properties.Platform) {
                                selectedItem.set(undefined);
                                previousSelectedItem.set(undefined);
                                tick().then( () => selectedItem.set({
                                    type: 'Platform',
                                    display: feature.properties.Platform,
                                    platformNumber: feature.properties.Platform // Add platformNumber for map highlighting and live arrivals
                                }) );
                            }
                        }
                    });

                    // Add GeolocateControl to show user location if permission is granted
                    const geolocate = new maplibregl.GeolocateControl({
                        positionOptions: { enableHighAccuracy: true },
                        trackUserLocation: true,
                        // showUserHeading: true,
                        showUserLocation: true,
                        showAccuracyCircle: true,
                        fitBoundsOptions: { maxZoom: map.getZoom() }, // Prevent zooming in
                        // flyTo: false // Prevent flying to user location
                    });
                    map.addControl(geolocate);
                    setResults(allRoutes);
                    updatePlatformColors();
                    // Hide the geolocate control button via CSS
                    map.once('render', () => {
                        const controls = document.getElementsByClassName('maplibregl-ctrl-geolocate');
                        for (const ctrl of controls) {
                            ctrl.style.display = 'none';
                        }
                    });

                    // Request user location on map load, but do not fly to it
                    if (navigator.geolocation) {
                        navigator.geolocation.watchPosition(
                            (pos) => {
                                // Permission granted, update the geolocate control's marker without flying
                                // This is a workaround: set the control's _lastKnownPosition and emit the event
                                if (geolocate._updateMarker) {
                                    geolocate._updateMarker(pos);
                                }
                            },
                            () => {
                                // Permission denied or failed, do nothing
                            }
                        );
                        if(paramType === 'pf' && paramValue) {
                            const searchResult = platformsArr.find((val) => {
                                return paramValue.trim().toUpperCase() == val.platformNumber
                            })
                            if(searchResult) selectedItem.set({ type: 'Platform', display: searchResult.platformNumber });
                        } else if (paramType === 'r' && paramValue) {
                            const searchResult = allRoutes.find((val) => paramValue.trim().toUpperCase() === val.number);
                            if(searchResult) tick().then(() => selectedItem.set({type: 'Route', display: searchResult.number, value: searchResult.number}));
                        } else if (paramType === 's' && paramValue) {
                            const searchResult = allRoutes.flatMap((v => v.stops)).find((val) => paramValue.trim().toUpperCase() === val.name.toUpperCase());
                            if(searchResult) selectedItem.set({type: 'Stop', display: searchResult.name, displayKannada: searchResult.nameKannada});
                        } else if (paramType === 'a' && paramValue) {
                            const searchResult = [...allRoutes.map((v => v.area)), ...allRoutes.map((v => v.via))].find((val) => paramValue.trim().toUpperCase() === val.name.toUpperCase());
                            if(searchResult) selectedItem.set({type: 'Area', display: searchResult.name, displayKannada: searchResult.nameKannada});
                        }
                    }
                });
        });

        return () => {
            if(map)
                map.remove();
            unsubResults();
            unsubSelected();
            unsubLive();
            unsubFocused();
        };
    });

</script>

<div id="map" class="fixed inset-0 w-screen h-screen z-0"></div>

{#if showResetBounds}
  <button
    class="reset-bounds-btn"
    aria-label="Recenter map"
    on:click={() => {
      if (map && platformBounds) {
        map.fitBounds(platformBounds, { padding: getFitBoundsPadding(), duration: 500 });
        showResetBounds = false;
        focusedLiveBus.set(null);
      }
    }}
  >
    <span class="material-icons reset-icon">my_location</span>
  </button>
{/if}

<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;700&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');
/* Hide the geolocate control button */
.maplibregl-ctrl-geolocate { display: none !important; }
.reset-bounds-btn {
  position: fixed;
  bottom: 32px;
  right: 16px;
  z-index: 201;
  background: #fff;
  border: none;
  border-radius: 50%;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.18);
  cursor: pointer;
  transition: box-shadow 0.15s, background 0.15s;
}
.reset-bounds-btn:hover {
  background: #f5f5f7;
  box-shadow: 0 4px 18px rgba(0,0,0,0.22);
}
.reset-icon {
  font-family: 'Material Icons';
  font-size: 22px;
  color: #1A1A1A;
  line-height: 1;
  display: block;
  font-style: normal;
  font-weight: normal;
  letter-spacing: normal;
  -webkit-font-feature-settings: 'liga';
  font-feature-settings: 'liga';
}
</style>