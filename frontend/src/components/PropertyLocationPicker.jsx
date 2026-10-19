import React, { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Search, Loader2, AlertCircle, Globe, Crosshair } from 'lucide-react';

// Custom SVG icon matching NIVAS theme
const createNivasMarkerIcon = () => {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 42" width="32" height="42">
      <defs>
        <filter id="shadow" x="-20%" y="-10%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000000" flood-opacity="0.35"/>
        </filter>
      </defs>
      <path d="M16 1 C7.716 1 1 7.716 1 16 C1 26.5 16 41 16 41 C16 41 31 26.5 31 16 C31 7.716 24.284 1 16 1 Z" 
            fill="#1E3A5F" stroke="#FFFFFF" stroke-width="2" filter="url(#shadow)"/>
      <circle cx="16" cy="16" r="6" fill="#3C5A48" stroke="#FFFFFF" stroke-width="1.5"/>
    </svg>
  `;
  return L.divIcon({
    className: 'nivas-custom-marker',
    html: svg,
    iconSize: [32, 42],
    iconAnchor: [16, 41],
    popupAnchor: [0, -36],
  });
};

// Facility category visual styles matching accessible color contrasts
const FACILITY_VISUALS = {
  school: { color: '#2563EB', icon: '🏫', border: '#1D4ED8' },
  hospital: { color: '#DC2626', icon: '🏥', border: '#B91C1C' },
  clinic: { color: '#DC2626', icon: '⚕️', border: '#B91C1C' },
  pharmacy: { color: '#DC2626', icon: '💊', border: '#B91C1C' },
  transit: { color: '#059669', icon: '🚏', border: '#047857' },
  railway: { color: '#059669', icon: '🚆', border: '#047857' },
  police: { color: '#0D9488', icon: '🛡️', border: '#0F766E' },
  fire: { color: '#D97706', icon: '🚒', border: '#B45309' },
  road: { color: '#475569', icon: '🛣️', border: '#334155' },
};

const createFacilityMarkerIcon = (category, customColor) => {
  const vis = FACILITY_VISUALS[category] || { color: '#1E3A5F', icon: '📍', border: '#0F172A' };
  const pinColor = customColor || vis.color;
  const pinBorder = customColor ? customColor : vis.border;
  const html = `
    <div class="facility-map-pin facility-${category || 'general'}" style="background-color: ${pinColor}; border-color: ${pinBorder};">
      <span class="facility-map-icon">${vis.icon}</span>
    </div>
  `;
  return L.divIcon({
    className: 'facility-marker-wrapper',
    html: html,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -14],
  });
};

/**
 * Clean up Nominatim display_name into a user-friendly Indian address
 */
const formatNominatimAddress = (data) => {
  if (!data || !data.address) return data?.display_name || '';
  const addr = data.address;
  const parts = [];

  // Building or POI
  const poi = addr.amenity || addr.building || addr.house_name || addr.shop || addr.office;
  if (poi) parts.push(poi);

  // House/Block/Road
  const streetPart = [addr.house_number, addr.road].filter(Boolean).join(' ');
  if (streetPart && !parts.includes(streetPart)) parts.push(streetPart);

  // Suburb / Locality / Sector
  const locality = addr.suburb || addr.neighbourhood || addr.residential || addr.subdistrict || addr.quarter;
  if (locality && !parts.includes(locality)) parts.push(locality);

  // City District / City
  const city = addr.city || addr.town || addr.village || addr.city_district || addr.state_district;
  if (city && !parts.includes(city)) parts.push(city);

  // State
  const state = addr.state;
  if (state && !parts.includes(state)) parts.push(state);

  // Postcode
  if (addr.postcode) parts.push(addr.postcode);

  const formatted = parts.join(', ');
  return formatted || data.display_name;
};

export default function PropertyLocationPicker({
  latitude,
  longitude,
  onLocationChange,
  mapHeight = 280,
  initialZoom = 15,
  initialView = 'local', // 'local' | 'national'
  showViewControls = false,
  districtLabel = null,
  searchQuery: propSearchQuery,
  onSearchQueryChange,
  searchPlaceholder = 'Search address or locality (e.g. Indirapuram, Ghaziabad)...',
  onSearchStatusChange,
  overlayMarkers = [],
  selectedFacilityId = null,
  onFacilitySelect = null,
  radiusCircleMeters = null,
  showRadius = true,
  showSearchRadius = undefined,
  polygonCoords = null,
  polygonStyle = null,
  geoJsonLayers = null,
  children,
}) {
  const isRadiusVisible = showSearchRadius !== undefined ? Boolean(showSearchRadius) : Boolean(showRadius);
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markerInstanceRef = useRef(null);
  const circleInstanceRef = useRef(null);
  const overlayLayerRef = useRef(null);
  const polygonLayerRef = useRef(null);
  const facilityMarkersMapRef = useRef(new Map());
  const isInternalUpdateRef = useRef(false);
  const hasAutoZoomedRef = useRef(false);
  const [currentView, setCurrentView] = useState(initialView);

  // Search input state (supports both uncontrolled and controlled modes)
  const [internalSearchQuery, setInternalSearchQuery] = useState('');
  const isControlledSearch = propSearchQuery !== undefined;
  const searchQuery = isControlledSearch ? propSearchQuery : internalSearchQuery;
  const setSearchQuery = (newVal) => {
    if (!isControlledSearch) {
      setInternalSearchQuery(newVal);
    }
    if (typeof onSearchQueryChange === 'function') {
      onSearchQueryChange(newVal);
    }
  };

  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [reverseError, setReverseError] = useState('');

  // Notify parent of search status changes if requested
  useEffect(() => {
    if (typeof onSearchStatusChange === 'function') {
      onSearchStatusChange({ isSearching, searchError, reverseError });
    }
  }, [isSearching, searchError, reverseError, onSearchStatusChange]);

  // Default Delhi center fallback if coordinates invalid
  const validLat = typeof latitude === 'number' && !isNaN(latitude) ? latitude : 28.5921;
  const validLon = typeof longitude === 'number' && !isNaN(longitude) ? longitude : 77.0460;

  // Reverse geocoding function
  const reverseGeocode = useCallback(async (lat, lon) => {
    setReverseError('');
    try {
      const url = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json&countrycodes=in`;
      const res = await fetch(url, {
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'NIVAS-Property-Inspection/1.0 (contact@nivas.app)',
        },
      });
      if (!res.ok) {
        throw new Error(`Reverse geocoding HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data && (data.display_name || data.address)) {
        const formatted = formatNominatimAddress(data);
        onLocationChange({
          latitude: lat,
          longitude: lon,
          address: formatted,
          reverseGeocoded: true,
        });
      } else {
        // Reverse geocode produced no formatted address
        setReverseError('No address found for these exact coordinates. Coordinates saved.');
        onLocationChange({
          latitude: lat,
          longitude: lon,
          reverseGeocoded: false,
        });
      }
    } catch (err) {
      console.warn('Reverse geocoding error:', err);
      setReverseError('Reverse geocoding service unavailable. Selected coordinates are preserved.');
      onLocationChange({
        latitude: lat,
        longitude: lon,
        reverseGeocoded: false,
      });
    }
  }, [onLocationChange]);

  // Handle explicit search submission (press Enter or click Search)
  const handleSearchSubmit = async (e) => {
    if (e) {
      if (typeof e.preventDefault === 'function') e.preventDefault();
      if (typeof e.stopPropagation === 'function') e.stopPropagation();
    }
    const query = searchQuery.trim();
    if (!query) return;

    setIsSearching(true);
    setSearchError('');

    try {
      const qWithCountry = query.toLowerCase().includes('india') ? query : `${query}, India`;
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(qWithCountry)}&format=json&limit=1&countrycodes=in`;
      const res = await fetch(url, {
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'NIVAS-Property-Inspection/1.0 (contact@nivas.app)',
        },
      });

      if (!res.ok) {
        throw new Error(`Search HTTP ${res.status}`);
      }

      const results = await res.json();
      if (results && results.length > 0) {
        const item = results[0];
        const newLat = parseFloat(item.lat);
        const newLon = parseFloat(item.lon);

        if (!isNaN(newLat) && !isNaN(newLon)) {
          // Update map and marker
          if (mapInstanceRef.current && markerInstanceRef.current) {
            isInternalUpdateRef.current = true;
            hasAutoZoomedRef.current = true;
            mapInstanceRef.current.setView([newLat, newLon], 16);
            markerInstanceRef.current.setLatLng([newLat, newLon]);
            if (circleInstanceRef.current) {
              circleInstanceRef.current.setLatLng([newLat, newLon]);
            }
            setCurrentView('district');
          }

          onLocationChange({
            latitude: newLat,
            longitude: newLon,
            address: item.display_name,
            reverseGeocoded: true,
          });
        } else {
          setSearchError('Invalid coordinates returned from search.');
        }
      } else {
        setSearchError(`No matching locations found for "${query}". Try adding a city name.`);
      }
    } catch (err) {
      console.warn('Location search error:', err);
      setSearchError('Location search failed. Check your network or try again.');
    } finally {
      setIsSearching(false);
    }
  };

  // View control handlers (National Overview / District Zoom)
  const handleResetToIndia = useCallback(() => {
    if (mapInstanceRef.current) {
      if (typeof mapInstanceRef.current.flyTo === 'function') {
        mapInstanceRef.current.flyTo([22.5, 79.0], 4.5, { duration: 1.0 });
      } else {
        mapInstanceRef.current.setView([22.5, 79.0], 4.5);
      }
      setCurrentView('national');
    }
  }, []);

  const handleZoomToDistrict = useCallback(() => {
    if (!mapInstanceRef.current) return;
    if (Array.isArray(polygonCoords) && polygonCoords.length >= 3 && typeof L.polygon === 'function') {
      const latLons = polygonCoords.map((pt) => [pt[1], pt[0]]);
      const poly = L.polygon(latLons);
      if (typeof mapInstanceRef.current.fitBounds === 'function') {
        mapInstanceRef.current.fitBounds(poly.getBounds(), { padding: [28, 28], maxZoom: 14 });
      } else {
        mapInstanceRef.current.setView([validLat, validLon], 14);
      }
    } else {
      if (typeof mapInstanceRef.current.flyTo === 'function') {
        mapInstanceRef.current.flyTo([validLat, validLon], 14, { duration: 1.0 });
      } else {
        mapInstanceRef.current.setView([validLat, validLon], 14);
      }
    }
    setCurrentView('district');
  }, [polygonCoords, validLat, validLon]);

  // Initialize Leaflet map once
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const defaultCenter = initialView === 'national' ? [22.5, 79.0] : [validLat, validLon];
      const defaultZoom = initialView === 'national' ? 4.5 : initialZoom;

      const map = L.map(mapContainerRef.current, {
        center: defaultCenter,
        zoom: defaultZoom,
        zoomControl: true,
        attributionControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      // Create dedicated radius circle pane below markers/overlays but above tileLayer
      if (typeof map.createPane === 'function' && (typeof map.getPane !== 'function' || !map.getPane('radiusCirclePane'))) {
        const circlePane = map.createPane('radiusCirclePane');
        if (circlePane && circlePane.style) {
          circlePane.style.zIndex = '350';
          circlePane.style.pointerEvents = 'none';
        }
      }

      const marker = L.marker([validLat, validLon], {
        icon: createNivasMarkerIcon(),
        draggable: true,
        autoPan: true,
      }).addTo(map);

      // Immediately instantiate radius circle if isRadiusVisible and radiusCircleMeters > 0
      if (isRadiusVisible && typeof radiusCircleMeters === 'number' && radiusCircleMeters > 0 && typeof L.circle === 'function') {
        const circlePane = (typeof map.getPane === 'function' && map.getPane('radiusCirclePane')) ? 'radiusCirclePane' : undefined;
        circleInstanceRef.current = L.circle([validLat, validLon], {
          radius: radiusCircleMeters,
          color: '#0284C7',
          weight: 2.5,
          opacity: 0.9,
          fillColor: '#38BDF8',
          fillOpacity: 0.18,
          interactive: false,
          pane: circlePane,
        }).addTo(map);
      }

      // Create separate overlay layer group for facility POI markers
      const overlayLayer = typeof L.layerGroup === 'function'
        ? L.layerGroup().addTo(map)
        : { clearLayers: () => {}, addLayer: () => {} };
      overlayLayerRef.current = overlayLayer;

      // Create separate layer group for boundary/hazard polygons
      const polygonLayer = typeof L.layerGroup === 'function'
        ? L.layerGroup().addTo(map)
        : { clearLayers: () => {}, addLayer: () => {} };
      polygonLayerRef.current = polygonLayer;

      // Marker drag event: dynamically follow pin while dragging
      marker.on('drag', () => {
        const pos = marker.getLatLng();
        if (circleInstanceRef.current) {
          circleInstanceRef.current.setLatLng(pos);
        }
      });

      // Marker dragend event
      marker.on('dragend', () => {
        const pos = marker.getLatLng();
        if (circleInstanceRef.current) {
          circleInstanceRef.current.setLatLng(pos);
        }
        isInternalUpdateRef.current = true;
        reverseGeocode(pos.lat, pos.lng);
      });

      // Map click event
      map.on('click', (e) => {
        const { lat, lng } = e.latlng;
        marker.setLatLng([lat, lng]);
        if (circleInstanceRef.current) {
          circleInstanceRef.current.setLatLng([lat, lng]);
        }
        isInternalUpdateRef.current = true;
        reverseGeocode(lat, lng);
      });

      mapInstanceRef.current = map;
      markerInstanceRef.current = marker;

      // Invalidate size in case of flexbox / card animation layout changes
      setTimeout(() => {
        map.invalidateSize();
      }, 200);

      // Add ResizeObserver to guarantee crisp map tiles when container resizes
      let resizeObserver;
      if (window.ResizeObserver && mapContainerRef.current) {
        resizeObserver = new ResizeObserver(() => {
          map.invalidateSize();
        });
        resizeObserver.observe(mapContainerRef.current);
      }

      mapInstanceRef.current = map;
      markerInstanceRef.current = marker;
      mapInstanceRef.current._resizeObserver = resizeObserver;
    }

    return () => {
      if (circleInstanceRef.current) {
        if (typeof circleInstanceRef.current.remove === 'function') {
          circleInstanceRef.current.remove();
        }
        circleInstanceRef.current = null;
      }
      if (overlayLayerRef.current) {
        overlayLayerRef.current.clearLayers();
        overlayLayerRef.current = null;
      }
      if (mapInstanceRef.current) {
        if (mapInstanceRef.current._resizeObserver) {
          mapInstanceRef.current._resizeObserver.disconnect();
        }
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        markerInstanceRef.current = null;
      }
    };
  }, []); // Run once on mount

  const onFacilitySelectRef = useRef(onFacilitySelect);
  useEffect(() => {
    onFacilitySelectRef.current = onFacilitySelect;
  }, [onFacilitySelect]);

  // Synchronize overlay markers whenever overlayMarkers changes
  useEffect(() => {
    if (!overlayLayerRef.current || !mapInstanceRef.current) return;

    overlayLayerRef.current.clearLayers();
    facilityMarkersMapRef.current.clear();

    if (!Array.isArray(overlayMarkers) || overlayMarkers.length === 0) {
      return;
    }

    overlayMarkers.forEach((item) => {
      if (typeof item.latitude !== 'number' || typeof item.longitude !== 'number') {
        return;
      }

      const facMarker = L.marker([item.latitude, item.longitude], {
        icon: createFacilityMarkerIcon(item.category, item.color),
        riseOnHover: true,
      });

      const isRoad = item.category === 'road';
      const popupHtml = `
        <div class="facility-popup-card">
          <span class="facility-popup-badge facility-${item.category || 'general'}">${item.category_label || item.category || 'Facility'}</span>
          <h4 class="facility-popup-title">${item.name || 'Local Facility'}</h4>
          <div class="facility-popup-coords">Coordinates: ${item.latitude.toFixed(5)}° N, ${item.longitude.toFixed(5)}° E</div>
          <div class="facility-popup-source">Verified Provider: ${item.source || 'OpenStreetMap'}</div>
          ${isRoad ? '<div class="facility-popup-disclosure">Mapped road segment centerline point from OpenStreetMap; does not indicate safety or walkability score.</div>' : ''}
        </div>
      `;

      facMarker.bindPopup(popupHtml, {
        closeButton: true,
        offset: [0, -8],
      });

      // Prevent facility marker clicks from moving the active exploration location pin
      facMarker.on('click', (e) => {
        if (e && e.originalEvent && L.DomEvent && typeof L.DomEvent.stopPropagation === 'function') {
          L.DomEvent.stopPropagation(e.originalEvent);
        }
        if (typeof onFacilitySelectRef.current === 'function') {
          onFacilitySelectRef.current(item);
        }
      });

      if (item.id) {
        facilityMarkersMapRef.current.set(String(item.id), facMarker);
      }

      if (typeof facMarker.addTo === 'function' && overlayLayerRef.current) {
        facMarker.addTo(overlayLayerRef.current);
      }
    });
  }, [overlayMarkers]);

  // Open marker popup and center map when selectedFacilityId changes without moving the exploration pin
  useEffect(() => {
    if (!selectedFacilityId || !facilityMarkersMapRef.current || !mapInstanceRef.current) return;
    const marker = facilityMarkersMapRef.current.get(String(selectedFacilityId));
    if (marker) {
      if (typeof mapInstanceRef.current.panTo === 'function') {
        mapInstanceRef.current.panTo(marker.getLatLng(), { animate: true });
      } else {
        mapInstanceRef.current.setView(marker.getLatLng(), 15);
      }
      if (typeof marker.openPopup === 'function') {
        marker.openPopup();
      }
    }
  }, [selectedFacilityId]);

  // Synchronize dynamic radius circle centered on active pin
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    if (isRadiusVisible && typeof radiusCircleMeters === 'number' && radiusCircleMeters > 0 && typeof L.circle === 'function') {
      const pinPos = markerInstanceRef.current ? markerInstanceRef.current.getLatLng() : null;
      const centerLat = pinPos ? pinPos.lat : (typeof latitude === 'number' && !isNaN(latitude) ? latitude : validLat);
      const centerLon = pinPos ? pinPos.lng : (typeof longitude === 'number' && !isNaN(longitude) ? longitude : validLon);

      const circlePane = (typeof mapInstanceRef.current.getPane === 'function' && mapInstanceRef.current.getPane('radiusCirclePane'))
        ? 'radiusCirclePane'
        : undefined;

      if (!circleInstanceRef.current) {
        circleInstanceRef.current = L.circle([centerLat, centerLon], {
          radius: radiusCircleMeters,
          color: '#0284C7',
          weight: 2.5,
          opacity: 0.9,
          fillColor: '#38BDF8',
          fillOpacity: 0.18,
          interactive: false,
          pane: circlePane,
        }).addTo(mapInstanceRef.current);
      } else {
        circleInstanceRef.current.setLatLng([centerLat, centerLon]);
        circleInstanceRef.current.setRadius(radiusCircleMeters);
        if (typeof circleInstanceRef.current.redraw === 'function') {
          circleInstanceRef.current.redraw();
        }
      }
    } else if (circleInstanceRef.current) {
      if (typeof circleInstanceRef.current.remove === 'function') {
        circleInstanceRef.current.remove();
      }
      circleInstanceRef.current = null;
    }
  }, [latitude, longitude, radiusCircleMeters, isRadiusVisible, validLat, validLon]);

  // Synchronize boundary polygon and GeoJSON hazard layers
  useEffect(() => {
    if (!polygonLayerRef.current || !mapInstanceRef.current) return;
    polygonLayerRef.current.clearLayers();

    if (Array.isArray(polygonCoords) && polygonCoords.length >= 3 && typeof L.polygon === 'function') {
      const latLons = polygonCoords.map((pt) => {
        // Support both [lon, lat] and [lat, lon]
        const lon = pt[0];
        const lat = pt[1];
        return [lat, lon];
      });

      const poly = L.polygon(latLons, polygonStyle || {
        color: '#059669',
        weight: 2,
        opacity: 0.85,
        fillColor: '#10B981',
        fillOpacity: 0.12,
        interactive: false,
      });
      polygonLayerRef.current.addLayer(poly);
    }

    if (geoJsonLayers && typeof L.geoJSON === 'function') {
      Object.entries(geoJsonLayers).forEach(([layerKey, feat]) => {
        if (!feat) return;
        const isFlood = layerKey === 'yamuna_flood_corridor';
        const layer = L.geoJSON(feat, {
          style: {
            color: isFlood ? '#DC2626' : '#D97706',
            weight: 2,
            opacity: 0.85,
            fillColor: isFlood ? '#EF4444' : '#F59E0B',
            fillOpacity: isFlood ? 0.22 : 0.28,
          },
          pointToLayer: (geoJsonPoint, latlng) => {
            return L.circleMarker(latlng, {
              radius: 6,
              fillColor: '#DC2626',
              color: '#FFFFFF',
              weight: 1.5,
              opacity: 1,
              fillOpacity: 0.9,
            });
          },
        });
        polygonLayerRef.current.addLayer(layer);
      });
    }
  }, [polygonCoords, polygonStyle, geoJsonLayers]);

  // Smoothly zoom from national overview into district boundary when polygon first becomes available
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    if (Array.isArray(polygonCoords) && polygonCoords.length >= 3 && typeof L.polygon === 'function') {
      const latLons = polygonCoords.map((pt) => [pt[1], pt[0]]);
      const poly = L.polygon(latLons);
      if (!hasAutoZoomedRef.current && initialView === 'national') {
        hasAutoZoomedRef.current = true;
        const timer = setTimeout(() => {
          if (mapInstanceRef.current && typeof mapInstanceRef.current.fitBounds === 'function') {
            mapInstanceRef.current.fitBounds(poly.getBounds(), { padding: [28, 28], maxZoom: 14 });
            setCurrentView('district');
          }
        }, 650);
        return () => clearTimeout(timer);
      }
    }
  }, [polygonCoords, initialView]);

  // Sync external coordinate changes (e.g. if parent changes lat/lon)
  useEffect(() => {
    if (isInternalUpdateRef.current) {
      isInternalUpdateRef.current = false;
      return;
    }

    if (mapInstanceRef.current && markerInstanceRef.current) {
      if (typeof latitude === 'number' && typeof longitude === 'number' && !isNaN(latitude) && !isNaN(longitude)) {
        const currentPos = markerInstanceRef.current.getLatLng();
        if (Math.abs(currentPos.lat - latitude) > 0.0001 || Math.abs(currentPos.lng - longitude) > 0.0001) {
          mapInstanceRef.current.setView([latitude, longitude], mapInstanceRef.current.getZoom() || 15);
          markerInstanceRef.current.setLatLng([latitude, longitude]);
        }
        if (circleInstanceRef.current) {
          circleInstanceRef.current.setLatLng([latitude, longitude]);
        }
      }
    }
  }, [latitude, longitude]);

  return (
    <div className="location-picker-root">
      {/* Search Input Bar (div container to prevent invalid nested form and page refresh) */}
      <div className="location-search-form" role="search">
        <div className="location-search-input-wrapper">
          <Search size={15} className="location-search-icon" />
          <input
            type="text"
            className="location-search-input"
            placeholder={searchPlaceholder}
            aria-label="Search locality or landmark in Delhi"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
                handleSearchSubmit(e);
              }
            }}
          />
          <button
            type="button"
            className="location-search-btn"
            aria-label="Search location"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleSearchSubmit(e);
            }}
            disabled={isSearching || !searchQuery.trim()}
          >
            {isSearching ? <Loader2 size={13} className="spin-icon" /> : 'Search'}
          </button>
        </div>
      </div>

      {/* Search Error Notice */}
      {searchError && (
        <div className="location-picker-notice notice-error" role="alert">
          <AlertCircle size={13} />
          <span>{searchError}</span>
        </div>
      )}

      {/* Reverse Geocode Warning / Status Notice */}
      {reverseError && (
        <div className="location-picker-notice notice-warning" role="status">
          <AlertCircle size={13} />
          <span>{reverseError}</span>
        </div>
      )}

      {children}

      {/* Map View Controls (India Overview / District Zoom) */}
      {showViewControls && (
        <div className="map-view-controls-bar" data-testid="map-view-controls">
          <div className="map-view-buttons-group">
            <button
              type="button"
              className={`map-view-toggle-btn ${currentView === 'national' ? 'active' : ''}`}
              onClick={handleResetToIndia}
              data-testid="reset-to-india-view-btn"
              title="Reset map to national overview of India"
            >
              <Globe size={13} />
              <span>Reset to India view</span>
            </button>
            <button
              type="button"
              className={`map-view-toggle-btn ${currentView === 'district' ? 'active' : ''}`}
              onClick={handleZoomToDistrict}
              data-testid="zoom-to-district-btn"
              title="Zoom into selected district boundary"
            >
              <Crosshair size={13} />
              <span>{districtLabel ? `Zoom to ${districtLabel}` : 'Zoom to selected district'}</span>
            </button>
          </div>
          <span className="map-view-status-hint">
            {currentView === 'national' ? 'National Overview (India)' : (districtLabel ? `${districtLabel} View` : 'District View')}
          </span>
        </div>
      )}

      {/* Interactive Map Box */}
      <div
        ref={mapContainerRef}
        className="location-map-wrapper interactive-location-map"
        style={{ height: mapHeight }}
        role="region"
        aria-label="Interactive locality map"
      />

      <div className="location-picker-help">
        <span>Click anywhere or drag marker to pinpoint exact location</span>
      </div>
    </div>
  );
}
