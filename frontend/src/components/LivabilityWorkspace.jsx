import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import PropertyLocationPicker from './PropertyLocationPicker';
import { fetchLivabilityLocationData, sendLivabilityChatMessage } from '../services/api';
import {
  Compass,
  MapPin,
  Send,
  Info,
  MessageSquare,
  Building2,
  GraduationCap,
  HeartPulse,
  Bus,
  Wind,
  ShieldAlert,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Eye,
  Scale,
  X,
  RefreshCw,
} from 'lucide-react';
import LocalityComparisonView from './LocalityComparisonView';

/**
 * Calculate great-circle distance between two coordinates in kilometers using the Haversine formula.
 * @param {number} lat1 
 * @param {number} lon1 
 * @param {number} lat2 
 * @param {number} lon2 
 * @returns {number|null} distance in km rounded to 2 decimal places, or null if coordinates are invalid
 */
export const calculateHaversineDistanceKm = (lat1, lon1, lat2, lon2) => {
  if (
    typeof lat1 !== 'number' || isNaN(lat1) ||
    typeof lon1 !== 'number' || isNaN(lon1) ||
    typeof lat2 !== 'number' || isNaN(lat2) ||
    typeof lon2 !== 'number' || isNaN(lon2)
  ) {
    return null;
  }
  const R = 6371.0; // Earth mean radius in kilometers
  const toRad = (deg) => (deg * Math.PI) / 180.0;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c * 100) / 100;
};

/**
 * Format a distance in kilometers into a human-readable string (meters if < 1km).
 * @param {number|null} distanceKm 
 * @returns {string}
 */
export const formatFacilityDistance = (distanceKm) => {
  if (typeof distanceKm !== 'number' || isNaN(distanceKm)) {
    return 'Distance unavailable';
  }
  if (distanceKm < 1.0) {
    const meters = Math.round(distanceKm * 1000);
    return `${meters} m`;
  }
  return `${distanceKm.toFixed(2)} km`;
};

export const SUGGESTED_PROMPTS = [
  'Neighborhoods in South Delhi with best metro connectivity',
  'What healthcare facilities are nearby?',
  'How far away is the nearest mapped transit facility?',
  'What infrastructure is available in this area?',
  'What does the available air-quality data tell us?',
  'What information is missing for this locality?',
];

const safeStorage = {
  getItem: (key) => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        return window.localStorage.getItem(key);
      }
    } catch (e) {}
    return null;
  },
  setItem: (key, val) => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(key, val);
      }
    } catch (e) {}
  },
};

export default function LivabilityWorkspace({
  location: propLocation,
  onLocationChange: propOnLocationChange,
  searchQuery: propSearchQuery,
  onSearchQueryChange: propOnSearchQueryChange,
}) {
  // Independent fallback state if not provided by parent
  const [internalLocation, setInternalLocation] = useState(() => {
    const saved = safeStorage.getItem('nivas_livability_location');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (typeof parsed.latitude === 'number' && typeof parsed.longitude === 'number' && parsed.address) {
          return parsed;
        }
      } catch (e) {}
    }
    return {
      latitude: 28.5921,
      longitude: 77.0460,
      address: 'Dwarka Sector 12, South West Delhi, Delhi',
    };
  });
  const [internalSearchQuery, setInternalSearchQuery] = useState(() => {
    return safeStorage.getItem('nivas_livability_search_query') || '';
  });

  const [workspaceView, setWorkspaceView] = useState(() => {
    const saved = safeStorage.getItem('nivas_livability_view');
    if (saved === 'explore' || saved === 'compare') return saved;
    return 'explore';
  });

  useEffect(() => {
    safeStorage.setItem('nivas_livability_view', workspaceView);
  }, [workspaceView]);

  const [searchStatus, setSearchStatus] = useState({
    isSearching: false,
    searchError: '',
    reverseError: '',
  });

  const selectedLocation = propLocation || internalLocation;
  const setSelectedLocation = (newLoc) => {
    if (typeof propOnLocationChange === 'function') {
      propOnLocationChange(newLoc);
    } else {
      setInternalLocation(newLoc);
      safeStorage.setItem('nivas_livability_location', JSON.stringify(newLoc));
    }
  };

  const searchQuery = propSearchQuery !== undefined ? propSearchQuery : internalSearchQuery;
  const setSearchQuery = (newQuery) => {
    if (typeof propOnSearchQueryChange === 'function') {
      propOnSearchQueryChange(newQuery);
    } else {
      setInternalSearchQuery(newQuery);
      safeStorage.setItem('nivas_livability_search_query', newQuery);
    }
  };

  const [locationData, setLocationData] = useState(null);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [dataError, setDataError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const activeRequestRef = useRef(0);

  const handleRetryTelemetry = useCallback(() => {
    setRetryCount((prev) => prev + 1);
  }, []);

  useEffect(() => {
    if (
      typeof selectedLocation.latitude !== 'number' ||
      typeof selectedLocation.longitude !== 'number'
    ) {
      return;
    }

    const requestId = ++activeRequestRef.current;
    const abortController = new AbortController();

    setIsLoadingData(true);
    setDataError(null);

    fetchLivabilityLocationData(
      {
        latitude: selectedLocation.latitude,
        longitude: selectedLocation.longitude,
        address: selectedLocation.address,
      },
      abortController.signal
    )
      .then((data) => {
        if (activeRequestRef.current === requestId) {
          setLocationData(data);
          setIsLoadingData(false);
          setDataError(null);
        }
      })
      .catch((err) => {
        if (activeRequestRef.current === requestId) {
          if (err.name !== 'CanceledError' && err.name !== 'AbortError') {
            setDataError(err.message || 'Unable to retrieve location telemetry');
            setIsLoadingData(false);
          }
        }
      });

    return () => {
      abortController.abort();
    };
  }, [selectedLocation.latitude, selectedLocation.longitude, selectedLocation.address, retryCount]);

  // Selected facility for map marker focus / two-way interaction
  const [selectedFacilityId, setSelectedFacilityId] = useState(null);

  // Verified Map Insights: Facility category filters
  const [categoryFilter, setCategoryFilter] = useState('all');

  const allFacilities = useMemo(() => {
    return locationData?.infrastructure?.facilities || [];
  }, [locationData]);

  // Enrich facilities with Haversine distance from selected exploration coordinates
  const facilitiesWithDistance = useMemo(() => {
    if (!Array.isArray(allFacilities)) return [];
    return allFacilities
      .map((fac) => {
        const distanceKm = calculateHaversineDistanceKm(
          selectedLocation.latitude,
          selectedLocation.longitude,
          fac.latitude,
          fac.longitude
        );
        return {
          ...fac,
          distanceKm,
          formattedDistance: formatFacilityDistance(distanceKm),
        };
      })
      .sort((a, b) => {
        if (a.distanceKm == null && b.distanceKm == null) return 0;
        if (a.distanceKm == null) return 1;
        if (b.distanceKm == null) return -1;
        return a.distanceKm - b.distanceKm;
      });
  }, [allFacilities, selectedLocation.latitude, selectedLocation.longitude]);

  // Group verified facilities by category for structured proximity directory
  const facilitiesByCategory = useMemo(() => {
    const groups = {
      school: { label: 'Schools & Education', icon: GraduationCap, items: [] },
      healthcare: { label: 'Healthcare & Medical', icon: HeartPulse, items: [] },
      transit: { label: 'Public Transit & Rail', icon: Bus, items: [] },
      emergency: { label: 'Emergency & Safety', icon: ShieldAlert, items: [] },
      road: { label: 'Roadways & Corridors', icon: Compass, items: [] },
    };

    facilitiesWithDistance.forEach((fac) => {
      if (fac.category === 'school') {
        groups.school.items.push(fac);
      } else if (['hospital', 'clinic', 'pharmacy'].includes(fac.category)) {
        groups.healthcare.items.push(fac);
      } else if (['transit', 'railway'].includes(fac.category)) {
        groups.transit.items.push(fac);
      } else if (['police', 'fire'].includes(fac.category)) {
        groups.emergency.items.push(fac);
      } else if (fac.category === 'road') {
        groups.road.items.push(fac);
      }
    });

    return groups;
  }, [facilitiesWithDistance]);

  const filteredFacilities = useMemo(() => {
    if (categoryFilter === 'all') return facilitiesWithDistance;
    if (categoryFilter === 'healthcare') {
      return facilitiesWithDistance.filter((f) => ['hospital', 'clinic', 'pharmacy'].includes(f.category));
    }
    if (categoryFilter === 'transit') {
      return facilitiesWithDistance.filter((f) => ['transit', 'railway'].includes(f.category));
    }
    if (categoryFilter === 'emergency') {
      return facilitiesWithDistance.filter((f) => ['police', 'fire'].includes(f.category));
    }
    return facilitiesWithDistance.filter((f) => f.category === categoryFilter);
  }, [facilitiesWithDistance, categoryFilter]);

  const schoolCount = useMemo(() => allFacilities.filter((f) => f.category === 'school').length, [allFacilities]);
  const healthcareCount = useMemo(() => allFacilities.filter((f) => ['hospital', 'clinic', 'pharmacy'].includes(f.category)).length, [allFacilities]);
  const transitCount = useMemo(() => allFacilities.filter((f) => ['transit', 'railway'].includes(f.category)).length, [allFacilities]);
  const emergencyCount = useMemo(() => allFacilities.filter((f) => ['police', 'fire'].includes(f.category)).length, [allFacilities]);
  const roadCount = useMemo(() => allFacilities.filter((f) => f.category === 'road').length, [allFacilities]);

  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [chatError, setChatError] = useState(null);
  const chatAbortControllerRef = useRef(null);
  const messagesEndRef = useRef(null);

  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'assistant',
      text: 'Welcome to the NIVAS Neighborhood AI Advisor. I answer questions about your selected location using verified OpenStreetMap civic infrastructure and atmospheric telemetry.\n\nSearch or tap on the map to choose any locality for spatial analysis.',
      time: 'Ready',
      sources: ['OpenStreetMap Overpass API'],
      isAiGenerated: false,
      providerConfigured: false,
    },
  ]);

  useEffect(() => {
    if (isChatOpen && typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isChatOpen]);

  const handleLocationChange = (loc) => {
    if (chatAbortControllerRef.current) {
      chatAbortControllerRef.current.abort();
      chatAbortControllerRef.current = null;
    }
    setIsChatLoading(false);
    setChatError(null);
    setSelectedFacilityId(null);
    const newLoc = {
      latitude: loc.latitude,
      longitude: loc.longitude,
      address: loc.address || selectedLocation.address || 'Selected Map Location',
    };
    setSelectedLocation(newLoc);

    setMessages((prev) => [
      ...prev,
      {
        id: `loc-${Date.now()}`,
        sender: 'system',
        text: `Exploration focus updated: ${newLoc.address}`,
        time: 'Pin Updated',
      },
    ]);
  };

  const handleFacilitySelect = useCallback((fac) => {
    setSelectedFacilityId(fac?.id || null);
  }, []);

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    const query = chatInput.trim();
    if (!query || isChatLoading) return;

    if (chatAbortControllerRef.current) {
      chatAbortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    chatAbortControllerRef.current = abortController;

    const userMsg = {
      id: Date.now(),
      sender: 'user',
      text: query,
      time: 'Just now',
      locationName: selectedLocation.address || 'Selected Map Location',
    };

    setMessages((prev) => [...prev, userMsg]);
    setChatInput('');
    setIsChatLoading(true);
    setChatError(null);

    const currentContext = {
      latitude: selectedLocation.latitude,
      longitude: selectedLocation.longitude,
      address: selectedLocation.address,
      locality: selectedLocation.address ? selectedLocation.address.split(',')[0].trim() : null,
      search_radius_meters: locationData?.infrastructure?.search_radius_meters || 1200,
      railway_search_radius_meters: locationData?.infrastructure?.railway_search_radius_meters || 2000,
      infrastructure_status: locationData?.infrastructure?.status || 'active',
      facilities: (facilitiesWithDistance || []).map((f) => ({
        id: f.id,
        name: f.name,
        category: f.category,
        category_label: f.category_label,
        latitude: f.latitude,
        longitude: f.longitude,
        distance_km: f.distanceKm,
        formatted_distance: f.formattedDistance,
        source: f.source || 'OpenStreetMap',
      })),
      schools_count: schoolCount,
      hospitals_count: locationData?.infrastructure?.hospitals_count || 0,
      clinics_count: locationData?.infrastructure?.clinics_count || 0,
      pharmacies_count: locationData?.infrastructure?.pharmacies_count || 0,
      police_stations_count: locationData?.infrastructure?.police_stations_count || 0,
      fire_stations_count: locationData?.infrastructure?.fire_stations_count || 0,
      public_transport_count: transitCount,
      railway_stations_count: locationData?.infrastructure?.railway_stations_count || 0,
      major_roads_count: roadCount,
      nearby_places: locationData?.infrastructure?.nearby_places || [],
      air_quality_status: locationData?.air_quality?.status || 'provider_not_configured',
      aqi_value: locationData?.air_quality?.aqi_value,
      aqi_category: locationData?.air_quality?.category,
      aqi_station: locationData?.air_quality?.station_name,
      aqi_source: locationData?.air_quality?.source,
      environmental_score: locationData?.air_quality?.environmental_score,
      retrieved_at: locationData?.retrieved_at,
      hazards_status: locationData?.environmental_hazards?.status || 'data_not_configured',
      hazards_message: locationData?.environmental_hazards?.message,
    };

    try {
      const response = await sendLivabilityChatMessage(
        {
          query,
          latitude: selectedLocation.latitude,
          longitude: selectedLocation.longitude,
          address: selectedLocation.address,
          context: currentContext,
        },
        abortController.signal
      );

      if (chatAbortControllerRef.current === abortController) {
        const replyMsg = {
          id: Date.now() + 1,
          sender: 'assistant',
          text: response.reply,
          time: 'Just now',
          sources: response.sources || [],
          isAiGenerated: Boolean(response.is_ai_generated),
          providerConfigured: Boolean(response.provider_configured),
          providerName: response.provider_name,
          locationName: selectedLocation.address || 'Selected Map Location',
        };
        setMessages((prev) => [...prev, replyMsg]);
        setIsChatLoading(false);
        chatAbortControllerRef.current = null;
      }
    } catch (err) {
      if (err.name !== 'CanceledError' && err.name !== 'AbortError' && err?.code !== 'ERR_CANCELED') {
        if (chatAbortControllerRef.current === abortController) {
          const errMsg = {
            id: Date.now() + 1,
            sender: 'assistant',
            text: `Unable to retrieve advisor response: ${err.message || 'Service unreachable'}. Coordinates and map navigation remain active.`,
            time: 'Error',
            isError: true,
          };
          setMessages((prev) => [...prev, errMsg]);
          setChatError(err.message || 'Error communicating with advisor');
          setIsChatLoading(false);
          chatAbortControllerRef.current = null;
        }
      }
    }
  };

  useEffect(() => {
    return () => {
      if (chatAbortControllerRef.current) {
        chatAbortControllerRef.current.abort();
      }
    };
  }, []);

  const handlePromptSelect = (prompt) => {
    setChatInput(prompt);
  };

  return (
    <div className="livability-workspace-root">
      {/* Workspace Header */}
      <div className="livability-workspace-header">
        <div className="livability-header-badge">
          <Compass size={14} />
          <span>Livability Workspace</span>
        </div>
        <h1 className="livability-header-title">Neighborhood Livability Intelligence</h1>
        <p className="livability-header-subtitle">
          Explore regional livability indicators, commute access, and spatial amenity distribution paired with conversational AI neighborhood discovery.
        </p>
      </div>

      {/* Workspace View Mode Bar */}
      <div className="livability-view-mode-bar" role="tablist" aria-label="Livability Workspace Views">
        <button
          type="button"
          role="tab"
          aria-selected={workspaceView === 'explore'}
          className={`livability-view-tab ${workspaceView === 'explore' ? 'active' : ''}`}
          onClick={() => setWorkspaceView('explore')}
        >
          <Compass size={14} />
          <span>Explore Neighborhood</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={workspaceView === 'compare'}
          className={`livability-view-tab ${workspaceView === 'compare' ? 'active' : ''}`}
          onClick={() => setWorkspaceView('compare')}
        >
          <Scale size={14} />
          <span>Compare Localities</span>
        </button>
      </div>

      {workspaceView === 'compare' ? (
        <LocalityComparisonView />
      ) : (
        <div className="livability-workspace-explore-wrap">
        {/* Main Full-Width Interactive Map Panel */}
        <section className="card livability-map-panel">
          <div className="map-panel-header">
            <div className="map-header-title-wrap">
              <MapPin size={18} className="map-header-icon" />
              <div>
                <h3 className="map-panel-title">Regional Locality Explorer</h3>
                <span className="map-panel-subtitle">OpenStreetMap GIS Pinpoint & Boundary Navigation</span>
              </div>
            </div>

            <div className="map-coords-indicator">
              <span className="coords-indicator-label">Active Pinpoint:</span>
              <span className="coords-indicator-val">
                {selectedLocation.latitude.toFixed(4)}° N, {selectedLocation.longitude.toFixed(4)}° E
              </span>
            </div>
          </div>

          <div className="livability-map-container">
            <PropertyLocationPicker
              latitude={selectedLocation.latitude}
              longitude={selectedLocation.longitude}
              location={selectedLocation}
              onLocationChange={handleLocationChange}
              searchQuery={searchQuery}
              onSearchQueryChange={setSearchQuery}
              onSearchStatusChange={setSearchStatus}
              overlayMarkers={filteredFacilities}
              selectedFacilityId={selectedFacilityId}
              onFacilitySelect={handleFacilitySelect}
              searchPlaceholder="Search neighborhood or locality (e.g. Hauz Khas, Vasant Kunj, Rohini)..."
              mapHeight={520}
              initialZoom={14}
            />
          </div>

          {/* Accessible Map Legend & Facility Filter Bar */}
          <div className="livability-map-legend" role="region" aria-label="Verified Map Insights Legend & Filter">
            <div className="legend-header">
              <span className="legend-title">Verified Map Insights Legend</span>
              <span className="legend-subtitle">
                {filteredFacilities.length} {filteredFacilities.length === 1 ? 'place' : 'places'} shown · Tap to filter
              </span>
            </div>
            <div className="legend-pills-row">
              <span className="legend-pin-focus" title="Active pinned coordinates">
                <span className="legend-pin-icon">📍</span>
                <span className="legend-pin-label">Active Pin</span>
              </span>

              <button
                type="button"
                className={`legend-filter-btn ${categoryFilter === 'all' ? 'active' : ''}`}
                onClick={() => setCategoryFilter('all')}
                aria-pressed={categoryFilter === 'all'}
              >
                All ({allFacilities.length})
              </button>

              <button
                type="button"
                className={`legend-filter-btn school ${categoryFilter === 'school' ? 'active' : ''}`}
                onClick={() => setCategoryFilter(categoryFilter === 'school' ? 'all' : 'school')}
                aria-pressed={categoryFilter === 'school'}
              >
                <span className="legend-dot school"></span>
                Schools ({schoolCount})
              </button>

              <button
                type="button"
                className={`legend-filter-btn healthcare ${categoryFilter === 'healthcare' ? 'active' : ''}`}
                onClick={() => setCategoryFilter(categoryFilter === 'healthcare' ? 'all' : 'healthcare')}
                aria-pressed={categoryFilter === 'healthcare'}
              >
                <span className="legend-dot healthcare"></span>
                Healthcare ({healthcareCount})
              </button>

              <button
                type="button"
                className={`legend-filter-btn transit ${categoryFilter === 'transit' ? 'active' : ''}`}
                onClick={() => setCategoryFilter(categoryFilter === 'transit' ? 'all' : 'transit')}
                aria-pressed={categoryFilter === 'transit'}
              >
                <span className="legend-dot transit"></span>
                Transit & Metro ({transitCount})
              </button>

              <button
                type="button"
                className={`legend-filter-btn emergency ${categoryFilter === 'emergency' ? 'active' : ''}`}
                onClick={() => setCategoryFilter(categoryFilter === 'emergency' ? 'all' : 'emergency')}
                aria-pressed={categoryFilter === 'emergency'}
              >
                <span className="legend-dot emergency"></span>
                Emergency ({emergencyCount})
              </button>

              <button
                type="button"
                className={`legend-filter-btn road ${categoryFilter === 'road' ? 'active' : ''}`}
                onClick={() => setCategoryFilter(categoryFilter === 'road' ? 'all' : 'road')}
                aria-pressed={categoryFilter === 'road'}
              >
                <span className="legend-dot road"></span>
                Roads ({roadCount})
              </button>
            </div>
          </div>

          {/* Selected Locality Details Card */}
          <div className="selected-locality-summary">
            <div className="locality-summary-content">
              <div className="locality-summary-header">
                <span className="summary-section-label">Selected Exploration Focus</span>
                <span className="summary-status-tag">
                  {searchStatus.isSearching
                    ? 'Searching GIS...'
                    : searchStatus.searchError
                    ? 'Search Error'
                    : searchStatus.reverseError
                    ? 'Coords Preserved'
                    : 'GIS Ready'}
                </span>
              </div>
              <h4 className="locality-summary-name">
                {selectedLocation.address || 'Selected Map Location'}
              </h4>
              <p className="locality-summary-meta">
                Coordinates: {selectedLocation.latitude.toFixed(6)}° N, {selectedLocation.longitude.toFixed(6)}° E · OpenStreetMap Public Geocoding
              </p>
              {searchStatus.reverseError && (
                <p className="locality-summary-status-notice warning">
                  {searchStatus.reverseError}
                </p>
              )}
              {searchStatus.searchError && (
                <p className="locality-summary-status-notice error">
                  {searchStatus.searchError}
                </p>
              )}
            </div>

            <div className="locality-summary-note">
              <Info size={14} />
              <span>
                Select or search any location to set the geographic focus for livability metrics, walkability analysis, and neighborhood recommendations.
              </span>
            </div>
          </div>

          {/* Verified Location Data Foundation */}
          <div className="livability-data-foundation">
            <div className="data-foundation-header">
              <div className="data-foundation-title-wrap">
                <Building2 size={16} className="data-foundation-icon" />
                <h4 className="data-foundation-title">Verified Location Data Foundation</h4>
              </div>
              {isLoadingData ? (
                <span className="data-foundation-badge loading">
                  <Loader2 size={12} className="spin-icon" /> Querying Telemetry...
                </span>
              ) : dataError ? (
                <span className="data-foundation-badge error">
                  <AlertCircle size={12} /> Sync Error
                </span>
              ) : (
                <span className="data-foundation-badge ready">
                  <CheckCircle2 size={12} /> Verified Telemetry
                </span>
              )}
            </div>

            {dataError && (
              <div className="data-foundation-error-banner">
                <AlertCircle size={14} />
                <span>{dataError} — Coordinates and map navigation remain active.</span>
              </div>
            )}

            <div className="data-foundation-grid">
              {/* Civic Infrastructure Subcard */}
              <div className="data-subcard">
                <div className="data-subcard-header">
                  <div className="data-subcard-title-group">
                    <Building2 size={15} />
                    <h5 className="data-subcard-title">Civic Infrastructure</h5>
                  </div>
                  <span className="data-source-tag">OpenStreetMap Overpass</span>
                </div>

                {isLoadingData && !locationData?.infrastructure ? (
                  <div className="data-subcard-notice">
                    <Loader2 size={13} className="spin-icon" /> Querying Overpass API nodes...
                  </div>
                ) : locationData?.infrastructure?.status === 'fetch_failed' ? (
                  <div className="data-subcard-notice error">
                    <div className="fetch-error-row">
                      <span><AlertCircle size={13} /> {locationData.infrastructure.error_message || 'Overpass API mirrors were unreachable or timed out.'}</span>
                      <button
                        type="button"
                        className="telemetry-retry-btn"
                        onClick={handleRetryTelemetry}
                        disabled={isLoadingData}
                        data-testid="retry-telemetry-btn"
                        aria-label="Retry Overpass telemetry query"
                      >
                        <RefreshCw size={11} className={isLoadingData ? 'spin-icon' : ''} />
                        <span>Retry</span>
                      </button>
                    </div>
                  </div>
                ) : locationData?.infrastructure?.status === 'empty' ? (
                  <div className="data-subcard-notice warning">
                    <Info size={13} /> 0 civic amenities recorded within search radius in OpenStreetMap.
                  </div>
                ) : locationData?.infrastructure ? (
                  <>
                    <div className="data-metrics-row">
                      <div className="data-metric-pill">
                        <span className="data-metric-val">{locationData.infrastructure.schools_count}</span>
                        <span className="data-metric-lbl">Schools</span>
                      </div>
                      <div className="data-metric-pill">
                        <span className="data-metric-val">
                          {locationData.infrastructure.hospitals_count +
                            locationData.infrastructure.clinics_count +
                            locationData.infrastructure.pharmacies_count}
                        </span>
                        <span className="data-metric-lbl">Healthcare</span>
                      </div>
                      <div className="data-metric-pill">
                        <span className="data-metric-val">
                          {locationData.infrastructure.public_transport_count +
                            locationData.infrastructure.railway_stations_count}
                        </span>
                        <span className="data-metric-lbl">Transit & Metro</span>
                      </div>
                      <div className="data-metric-pill">
                        <span className="data-metric-val">{locationData.infrastructure.major_roads_count}</span>
                        <span className="data-metric-lbl">Arterial Roads</span>
                      </div>
                    </div>

                    {locationData.infrastructure.nearby_places && locationData.infrastructure.nearby_places.length > 0 && (
                      <div>
                        <span className="data-metric-lbl">Mapped Landmarks & Places:</span>
                        <div className="data-poi-list">
                          {locationData.infrastructure.nearby_places.slice(0, 6).map((place, idx) => (
                            <span key={idx} className="data-poi-chip">{place}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="data-subcard-notice">
                    Select a location to inspect civic infrastructure.
                  </div>
                )}

                <div className="data-subcard-footer">
                  <Info size={12} />
                  <span>Real OpenStreetMap node telemetry · Zero synthetic entries</span>
                </div>
              </div>

              {/* Environmental & Air Quality Subcard */}
              <div className="data-subcard">
                <div className="data-subcard-header">
                  <div className="data-subcard-title-group">
                    <Wind size={15} />
                    <h5 className="data-subcard-title">Air Quality & Environment</h5>
                  </div>
                  <span className="data-source-tag">
                    {locationData?.air_quality?.source || 'Environmental Telemetry'}
                  </span>
                </div>

                {isLoadingData && !locationData?.air_quality ? (
                  <div className="data-subcard-notice">
                    <Loader2 size={13} className="spin-icon" /> Querying telemetry sensors...
                  </div>
                ) : locationData?.air_quality?.status === 'active' ? (
                  <>
                    <div className="data-metrics-row">
                      <div className="data-metric-pill">
                        <span className="data-metric-val">{locationData.air_quality.aqi_value}</span>
                        <span className="data-metric-lbl">AQI ({locationData.air_quality.category || 'Index'})</span>
                      </div>
                      {locationData.air_quality.environmental_score != null && (
                        <div className="data-metric-pill">
                          <span className="data-metric-val">{locationData.air_quality.environmental_score}</span>
                          <span className="data-metric-lbl">Env Score / 100</span>
                        </div>
                      )}
                    </div>
                    {locationData.air_quality.station_name && (
                      <div className="data-subcard-footer">
                        <span>Monitoring Station: {locationData.air_quality.station_name}</span>
                      </div>
                    )}
                    {locationData.retrieved_at && (
                      <div className="data-subcard-footer">
                        <span>Telemetry Retrieved: {new Date(locationData.retrieved_at).toISOString().slice(11, 19)} UTC</span>
                      </div>
                    )}
                  </>
                ) : locationData?.air_quality?.status === 'provider_not_configured' ? (
                  <div className="data-subcard-notice">
                    <Info size={13} /> Air quality API key (OpenWeather or AQICN) is not configured in backend environment. No synthetic AQI is generated.
                  </div>
                ) : locationData?.air_quality?.status === 'data_unavailable' ? (
                  <div className="data-subcard-notice warning">
                    <Info size={13} /> No active atmospheric monitoring stations within range (50 km).
                  </div>
                ) : locationData?.air_quality?.status === 'fetch_failed' ? (
                  <div className="data-subcard-notice error">
                    <AlertCircle size={13} /> {locationData.air_quality.error_message || 'Air quality telemetry service unreachable.'}
                  </div>
                ) : (
                  <div className="data-subcard-notice">
                    Select a location to inspect atmospheric telemetry.
                  </div>
                )}

                <div className="data-subcard-footer">
                  <ShieldAlert size={12} />
                  <span>Hazards: {locationData?.environmental_hazards?.message || 'Sensor network not configured'}</span>
                </div>
              </div>
            </div>

            {/* Nearby Facility Evidence Directory */}
            <div className="data-facility-directory" role="region" aria-label="Nearby Facility Context & Evidence Directory">
              <div className="directory-header">
                <div className="directory-header-titles">
                  <h5 className="directory-title">Verified Nearby Facilities & Proximity Evidence</h5>
                  <p className="directory-subtitle">
                    Civic amenities within {((locationData?.infrastructure?.search_radius_meters || 1200) / 1000).toFixed(1)} km
                    {locationData?.infrastructure?.railway_search_radius_meters ? ` (${(locationData.infrastructure.railway_search_radius_meters / 1000).toFixed(1)} km for rail/metro)` : ''} of selected pin.
                    Distances calculated using great-circle Haversine formula from exploration pin.
                  </p>
                </div>
                <span className="directory-count-badge">
                  {facilitiesWithDistance.length} {facilitiesWithDistance.length === 1 ? 'verified node' : 'verified nodes'}
                </span>
              </div>

              {isLoadingData && facilitiesWithDistance.length === 0 ? (
                <div className="directory-empty-state loading">
                  <Loader2 size={16} className="spin-icon" />
                  <span>Querying OpenStreetMap Overpass nodes...</span>
                </div>
              ) : locationData?.infrastructure?.status === 'fetch_failed' ? (
                <div className="directory-empty-state error">
                  <AlertCircle size={16} />
                  <span>Overpass API mirrors were unreachable or timed out.</span>
                  <button
                    type="button"
                    className="telemetry-retry-btn"
                    onClick={handleRetryTelemetry}
                    disabled={isLoadingData}
                    data-testid="directory-retry-btn"
                    aria-label="Retry Overpass telemetry query"
                  >
                    <RefreshCw size={12} className={isLoadingData ? 'spin-icon' : ''} />
                    <span>Retry Telemetry</span>
                  </button>
                </div>
              ) : facilitiesWithDistance.length === 0 ? (
                <div className="directory-empty-state empty">
                  <Info size={16} />
                  <span>No mapped civic amenities found within search radius ({((locationData?.infrastructure?.search_radius_meters || 1200) / 1000).toFixed(1)} km) in OpenStreetMap.</span>
                </div>
              ) : (
                <div className="directory-groups-container">
                  {Object.entries(facilitiesByCategory).map(([key, group]) => {
                    if (!group.items || group.items.length === 0) return null;
                    const GroupIcon = group.icon;
                    return (
                      <div key={key} className="directory-category-group" data-testid={`facility-group-${key}`}>
                        <div className="category-group-header">
                          <div className="category-group-title-wrap">
                            <GroupIcon size={14} className="category-group-icon" />
                            <h6 className="category-group-name">{group.label}</h6>
                          </div>
                          <span className="category-group-count">{group.items.length}</span>
                        </div>

                        <div className="directory-items-grid">
                          {group.items.map((facility) => {
                            const isSelected = String(selectedFacilityId) === String(facility.id);
                            return (
                              <div
                                key={facility.id}
                                className={`directory-item-card ${isSelected ? 'selected' : ''}`}
                                onClick={() => setSelectedFacilityId(isSelected ? null : facility.id)}
                                data-testid={`facility-card-${facility.id}`}
                              >
                                <div className="directory-item-info">
                                  <div className="directory-item-header">
                                    <span className={`facility-badge facility-${facility.category}`}>
                                      {facility.category_label || facility.category}
                                    </span>
                                    <span className="directory-item-distance" title="Calculated great-circle distance">
                                      {facility.formattedDistance}
                                    </span>
                                  </div>
                                  <h6 className="directory-item-name" title={facility.name}>
                                    {facility.name}
                                  </h6>
                                  <div className="directory-item-coords">
                                    {typeof facility.latitude === 'number' && typeof facility.longitude === 'number'
                                      ? `${facility.latitude.toFixed(4)}° N, ${facility.longitude.toFixed(4)}° E`
                                      : 'Coordinates pending'}
                                  </div>
                                </div>
                                <button
                                  type="button"
                                  className={`directory-view-btn ${isSelected ? 'active' : ''}`}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedFacilityId(isSelected ? null : facility.id);
                                  }}
                                  aria-label={`View ${facility.name} on map`}
                                >
                                  <Eye size={13} />
                                  <span>{isSelected ? 'Focused' : 'View Marker'}</span>
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Data Provenance & Methodological Disclosures */}
              <div className="data-provenance-disclosure">
                <div className="provenance-disclosure-header">
                  <Info size={14} />
                  <strong>Data Provenance & Calculation Methodology</strong>
                </div>
                <ul className="provenance-disclosure-list">
                  <li>
                    <strong>Provider Attribution:</strong> Civic amenity nodes, tags, and coordinates are queried from <em>OpenStreetMap (OSM) via Overpass API</em>.
                  </li>
                  <li>
                    <strong>Distance Metric:</strong> Distances represent straight-line, great-circle geometric distance computed via the Haversine formula (Earth radius R = 6,371 km) from the selected exploration pin. Actual walking or driving distances may vary based on route geometry, barriers, and pedestrian infrastructure.
                  </li>
                  <li>
                    <strong>Zero Inference / Risk Disclaimer:</strong> Unmapped facilities, empty search results, or absent environmental sensor readings reflect missing or unconfigured data sources and do <em>not</em> imply zero hazard, low flood risk, or guaranteed safety.
                  </li>
                  <li>
                    <strong>Telemetry Integrity:</strong> No synthetic or AI-fabricated facilities, coordinates, or composite scores are generated.
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Floating Expandable Neighborhood AI Advisor */}
        {isChatOpen ? (
          <aside
            className="floating-advisor-panel livability-chat-panel"
            role="dialog"
            aria-label="Neighborhood AI Advisor Chat"
            data-testid="floating-advisor-panel"
          >
            <div className="chat-panel-header">
              <div className="chat-header-title-wrap">
                <img
                  src="/neighborhood-ai-logo.svg"
                  alt="Neighborhood AI Advisor logo"
                  className="advisor-logo-img"
                  width="52"
                  height="52"
                  onError={(e) => {
                    e.currentTarget.onerror = null;
                    e.currentTarget.src = '/neighborhood-ai-logo.png';
                  }}
                />
                <div className="chat-header-title-text">
                  <h3 className="chat-panel-title">Neighborhood AI Advisor</h3>
                  <span className="chat-panel-status">Interactive Preview</span>
                </div>
              </div>
              <div className="chat-header-actions">
                <span className="chat-mode-pill">AI Discovery</span>
                <button
                  type="button"
                  className="chat-minimize-btn"
                  onClick={() => setIsChatOpen(false)}
                  aria-label="Minimize Advisor Chat"
                  title="Minimize Advisor"
                  data-testid="minimize-advisor-btn"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            {/* Chat Messages Body */}
            <div className="chat-messages-scroll" role="log" aria-live="polite">
              {messages.length === 0 ? (
                <div className="chat-empty-state" data-testid="chat-empty-state">
                  <p>No messages yet. Ask a question about this neighborhood's infrastructure, schools, transit, or air quality.</p>
                </div>
              ) : (
                messages.map((msg) => {
                  if (msg.sender === 'system') {
                    return (
                      <div key={msg.id} className="chat-system-pill" data-testid="chat-system-notice">
                        <MapPin size={11} />
                        <span>{msg.text}</span>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={msg.id}
                      className={`chat-bubble-row ${msg.sender === 'user' ? 'chat-row-user' : 'chat-row-assistant'}`}
                    >
                      {msg.sender === 'assistant' && (
                        <img
                          src="/neighborhood-ai-logo.svg"
                          alt="Neighborhood AI Advisor"
                          className="chat-msg-avatar"
                          width="36"
                          height="36"
                          onError={(e) => {
                            e.currentTarget.onerror = null;
                            e.currentTarget.src = '/neighborhood-ai-logo.png';
                          }}
                        />
                      )}
                      <div className={`chat-bubble ${msg.sender === 'user' ? 'bubble-user' : 'bubble-assistant'} ${msg.isError ? 'bubble-error' : ''}`}>
                        <p className="chat-bubble-text">{msg.text}</p>
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="chat-bubble-sources">
                            <span className="chat-sources-label">Sources:</span>
                            {msg.sources.map((s, idx) => (
                              <span key={idx} className="chat-source-badge">{s}</span>
                            ))}
                          </div>
                        )}
                        {msg.sender === 'assistant' && !msg.isError && (
                          <div className="chat-provenance-tag">
                            {msg.isAiGenerated ? (
                              <span className="tag-ai">AI Model: {msg.providerName || 'Generative LLM'}</span>
                            ) : (
                              <span className="tag-telemetry">Telemetry Grounded (AI Unconfigured)</span>
                            )}
                          </div>
                        )}
                        <span className="chat-bubble-time">{msg.time}</span>
                      </div>
                    </div>
                  );
                })
              )}

              {isChatLoading && (
                <div className="chat-bubble-row chat-row-assistant" data-testid="chat-loading-row">
                  <img
                    src="/neighborhood-ai-logo.svg"
                    alt="Neighborhood AI Advisor"
                    className="chat-msg-avatar"
                    width="36"
                    height="36"
                    onError={(e) => {
                      e.currentTarget.onerror = null;
                      e.currentTarget.src = '/neighborhood-ai-logo.png';
                    }}
                  />
                  <div className="chat-bubble bubble-assistant loading" role="status" aria-live="polite">
                    <div className="chat-loading-indicator">
                      <Loader2 size={13} className="spin-icon" />
                      <span>Analyzing verified location telemetry...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Quick Prompts Suggestions */}
            <div className="chat-prompts-section">
              <span className="prompts-label">Suggested Inquiries:</span>
              <div className="prompts-chips-wrapper">
                {SUGGESTED_PROMPTS.map((prompt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="prompt-chip-btn"
                    onClick={() => handlePromptSelect(prompt)}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>

            {/* Chat Input Bar */}
            <form onSubmit={handleSend} className="chat-input-form">
              <div className="chat-input-wrapper">
                <input
                  type="text"
                  className="chat-text-input"
                  placeholder="Ask about neighborhood livability, commute, schools..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={isChatLoading}
                />
                <button
                  type="submit"
                  className="chat-send-btn"
                  disabled={!chatInput.trim() || isChatLoading}
                  aria-label="Send message"
                >
                  {isChatLoading ? <Loader2 size={15} className="spin-icon" /> : <Send size={15} />}
                </button>
              </div>
              <div className="chat-input-footnote">
                <Info size={11} />
                <span>Answers grounded strictly in verified location telemetry · Zero synthetic data</span>
              </div>
            </form>
          </aside>
        ) : (
          <button
            type="button"
            className="floating-advisor-launcher"
            onClick={() => setIsChatOpen(true)}
            aria-label="Open Neighborhood AI Advisor"
            data-testid="advisor-launcher-btn"
          >
            <div className="launcher-icon-wrap">
              <MessageSquare size={18} />
            </div>
            <div className="launcher-text-wrap">
              <span className="launcher-title">Neighborhood AI Advisor</span>
              <span className="launcher-badge">Telemetry Grounded Chat</span>
            </div>
          </button>
        )}
      </div>
      )}
    </div>
  );
}
