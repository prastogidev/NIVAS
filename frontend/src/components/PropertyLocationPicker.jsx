import React, { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Search, Loader2, AlertCircle } from 'lucide-react';

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
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markerInstanceRef = useRef(null);
  const isInternalUpdateRef = useRef(false);

  // Search input state
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [reverseError, setReverseError] = useState('');

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
            mapInstanceRef.current.setView([newLat, newLon], 16);
            markerInstanceRef.current.setLatLng([newLat, newLon]);
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

  // Initialize Leaflet map once
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [validLat, validLon],
        zoom: initialZoom,
        zoomControl: true,
        attributionControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      const marker = L.marker([validLat, validLon], {
        icon: createNivasMarkerIcon(),
        draggable: true,
        autoPan: true,
      }).addTo(map);

      // Marker dragend event
      marker.on('dragend', () => {
        const pos = marker.getLatLng();
        isInternalUpdateRef.current = true;
        reverseGeocode(pos.lat, pos.lng);
      });

      // Map click event
      map.on('click', (e) => {
        const { lat, lng } = e.latlng;
        marker.setLatLng([lat, lng]);
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
            placeholder="Search address or locality (e.g. Indirapuram, Ghaziabad)..."
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
        <div className="location-picker-notice notice-error">
          <AlertCircle size={13} />
          <span>{searchError}</span>
        </div>
      )}

      {/* Reverse Geocode Warning / Status Notice */}
      {reverseError && (
        <div className="location-picker-notice notice-warning">
          <AlertCircle size={13} />
          <span>{reverseError}</span>
        </div>
      )}

      {/* Interactive Map Box */}
      <div
        ref={mapContainerRef}
        className="location-map-wrapper interactive-location-map"
        style={{ height: mapHeight }}
      />

      <div className="location-picker-help">
        <span>Click anywhere or drag marker to pinpoint exact location</span>
      </div>
    </div>
  );
}
