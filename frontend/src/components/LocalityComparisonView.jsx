import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import PropertyLocationPicker from './PropertyLocationPicker';
import { fetchLivabilityLocationData } from '../services/api';
import { calculateHaversineDistanceKm, formatFacilityDistance } from './LivabilityWorkspace';
import {
  Scale,
  MapPin,
  Building2,
  GraduationCap,
  HeartPulse,
  Bus,
  Wind,
  ShieldAlert,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Info,
  RefreshCw,
  Search,
} from 'lucide-react';

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

export const formatCivicMetricValue = (infra, count, singularLabel, pluralLabel) => {
  if (!infra) return '—';
  if (infra.status === 'fetch_failed' || infra.status === 'data_unavailable') {
    return '—';
  }
  const num = typeof count === 'number' ? count : 0;
  if (infra.status === 'empty' || num === 0) {
    return `0 ${pluralLabel}`;
  }
  return `${num} ${num === 1 ? singularLabel : pluralLabel}`;
};

/**
 * Find the nearest facility among the specified categories and calculate straight-line Haversine distance.
 */
export const findNearestFacility = (facilities, categories, userLat, userLon) => {
  if (!Array.isArray(facilities) || facilities.length === 0) return null;
  if (typeof userLat !== 'number' || typeof userLon !== 'number' || isNaN(userLat) || isNaN(userLon)) {
    return null;
  }
  const filtered = facilities.filter(
    (f) =>
      f &&
      categories.includes(f.category) &&
      typeof f.latitude === 'number' &&
      typeof f.longitude === 'number' &&
      !isNaN(f.latitude) &&
      !isNaN(f.longitude) &&
      typeof f.name === 'string' &&
      f.name.trim().length > 0
  );
  if (filtered.length === 0) return null;

  let nearest = null;
  let minDistance = Infinity;

  filtered.forEach((f) => {
    const dist = calculateHaversineDistanceKm(userLat, userLon, f.latitude, f.longitude);
    if (dist !== null && dist < minDistance) {
      minDistance = dist;
      nearest = {
        ...f,
        distanceKm: dist,
        formattedDistance: formatFacilityDistance(dist),
      };
    }
  });

  return nearest;
};

/**
 * Deterministically generate comparison observations based strictly on verified telemetry differences.
 * Never invents scores, safety ratings, or missing numbers.
 */
export const generateLocalityEvidenceSummary = (locA, dataA, locB, dataB) => {
  const nameA = locA?.address?.split(',')[0]?.trim() || 'Locality A';
  const nameB = locB?.address?.split(',')[0]?.trim() || 'Locality B';

  const notes = [];
  const infraA = dataA?.infrastructure;
  const infraB = dataB?.infrastructure;

  // 1. Schools
  if (!infraA || !infraB) {
    notes.push({
      category: 'Schools & Education',
      status: 'incomplete',
      text: 'School telemetry is loading or not yet retrieved.',
    });
  } else if (infraA.status === 'fetch_failed' || infraB.status === 'fetch_failed') {
    const failedNames = [
      infraA.status === 'fetch_failed' ? nameA : null,
      infraB.status === 'fetch_failed' ? nameB : null,
    ].filter(Boolean).join(' and ');
    notes.push({
      category: 'Schools & Education',
      status: 'incomplete',
      text: `School comparison incomplete: OpenStreetMap query failed for ${failedNames}.`,
    });
  } else if (infraA.status === 'data_unavailable' || infraB.status === 'data_unavailable') {
    notes.push({
      category: 'Schools & Education',
      status: 'incomplete',
      text: `School telemetry is unavailable for one or both locations.`,
    });
  } else {
    const sA = infraA.schools_count || 0;
    const sB = infraB.schools_count || 0;
    let text = '';
    if (sA > sB) {
      text = `${nameA} has more mapped schools (${sA}) than ${nameB} (${sB}) within the 1.2 km radius.`;
    } else if (sB > sA) {
      text = `${nameB} has more mapped schools (${sB}) than ${nameA} (${sA}) within the 1.2 km radius.`;
    } else {
      text = `Both localities report ${sA} mapped schools within the 1.2 km radius.`;
    }
    notes.push({
      category: 'Schools & Education',
      status: 'comparable',
      text,
    });
  }

  // 2. Healthcare
  if (!infraA || !infraB) {
    notes.push({
      category: 'Healthcare Facilities',
      status: 'incomplete',
      text: 'Healthcare telemetry is loading or not yet retrieved.',
    });
  } else if (infraA.status === 'fetch_failed' || infraB.status === 'fetch_failed') {
    notes.push({
      category: 'Healthcare Facilities',
      status: 'incomplete',
      text: `Healthcare comparison incomplete due to Overpass telemetry failure for one or both locations.`,
    });
  } else if (infraA.status === 'data_unavailable' || infraB.status === 'data_unavailable') {
    notes.push({
      category: 'Healthcare Facilities',
      status: 'incomplete',
      text: `Healthcare telemetry is unavailable for one or both locations.`,
    });
  } else {
    const hA = (infraA.hospitals_count || 0) + (infraA.clinics_count || 0) + (infraA.pharmacies_count || 0);
    const hB = (infraB.hospitals_count || 0) + (infraB.clinics_count || 0) + (infraB.pharmacies_count || 0);
    let text = '';
    if (hA > hB) {
      text = `${nameA} has higher healthcare amenity count (${hA} facilities: ${infraA.hospitals_count} hospitals, ${infraA.clinics_count} clinics, ${infraA.pharmacies_count} pharmacies) vs ${nameB} (${hB} facilities).`;
    } else if (hB > hA) {
      text = `${nameB} has higher healthcare amenity count (${hB} facilities: ${infraB.hospitals_count} hospitals, ${infraB.clinics_count} clinics, ${infraB.pharmacies_count} pharmacies) vs ${nameA} (${hA} facilities).`;
    } else {
      text = `Both localities report ${hA} mapped healthcare amenities within the 1.2 km radius.`;
    }
    notes.push({
      category: 'Healthcare Facilities',
      status: 'comparable',
      text,
    });
  }

  // 3. Transit & Commute Access
  if (!infraA || !infraB) {
    notes.push({
      category: 'Transit & Commute Access',
      status: 'incomplete',
      text: 'Transit telemetry is loading or not yet retrieved.',
    });
  } else if (infraA.status === 'fetch_failed' || infraB.status === 'fetch_failed') {
    notes.push({
      category: 'Transit & Commute Access',
      status: 'incomplete',
      text: `Transit comparison incomplete due to Overpass telemetry failure.`,
    });
  } else if (infraA.status === 'data_unavailable' || infraB.status === 'data_unavailable') {
    notes.push({
      category: 'Transit & Commute Access',
      status: 'incomplete',
      text: `Transit telemetry is unavailable for one or both locations.`,
    });
  } else {
    const rA = infraA.railway_stations_count || 0;
    const rB = infraB.railway_stations_count || 0;
    const tA = (infraA.public_transport_count || 0) + rA;
    const tB = (infraB.public_transport_count || 0) + rB;
    let text = '';
    if (rA > 0 && rB === 0) {
      text = `${nameA} has immediate rail/metro station access (${rA} stations within 2.0 km) whereas ${nameB} has 0 mapped rail/metro stations within 2.0 km (total transit nodes: ${tA} vs ${tB}).`;
    } else if (rB > 0 && rA === 0) {
      text = `${nameB} has immediate rail/metro station access (${rB} stations within 2.0 km) whereas ${nameA} has 0 mapped rail/metro stations within 2.0 km (total transit nodes: ${tB} vs ${tA}).`;
    } else if (tA > tB) {
      text = `${nameA} shows higher mapped transit stop density (${tA} total stops, ${rA} rail/metro) vs ${nameB} (${tB} stops, ${rB} rail/metro).`;
    } else if (tB > tA) {
      text = `${nameB} shows higher mapped transit stop density (${tB} total stops, ${rB} rail/metro) vs ${nameA} (${tA} stops, ${rA} rail/metro).`;
    } else {
      text = `Both localities report comparable transit stop density (${tA} mapped transit nodes within search radii).`;
    }
    notes.push({
      category: 'Transit & Commute Access',
      status: 'comparable',
      text,
    });
  }

  // 4. Emergency Services
  if (!infraA || !infraB) {
    notes.push({
      category: 'Emergency Services',
      status: 'incomplete',
      text: 'Emergency telemetry is loading or not yet retrieved.',
    });
  } else if (infraA.status === 'fetch_failed' || infraB.status === 'fetch_failed') {
    notes.push({
      category: 'Emergency Services',
      status: 'incomplete',
      text: `Emergency services data could not be verified due to telemetry failure.`,
    });
  } else if (infraA.status === 'data_unavailable' || infraB.status === 'data_unavailable') {
    notes.push({
      category: 'Emergency Services',
      status: 'incomplete',
      text: `Emergency telemetry is unavailable for one or both locations.`,
    });
  } else {
    const eA = (infraA.police_stations_count || 0) + (infraA.fire_stations_count || 0);
    const eB = (infraB.police_stations_count || 0) + (infraB.fire_stations_count || 0);
    notes.push({
      category: 'Emergency Services',
      status: 'comparable',
      text: `${nameA} reports ${eA} mapped emergency stations (${infraA.police_stations_count} police, ${infraA.fire_stations_count} fire) vs ${nameB} with ${eB} mapped stations (${infraB.police_stations_count} police, ${infraB.fire_stations_count} fire). Civic counts reflect mapped public infrastructure; fewer stations does NOT indicate higher safety.`,
    });
  }

  // 5. Major Arterial Roads
  if (!infraA || !infraB) {
    notes.push({
      category: 'Major Arterial Roads',
      status: 'incomplete',
      text: 'Road network telemetry is loading or not yet retrieved.',
    });
  } else if (infraA.status === 'fetch_failed' || infraB.status === 'fetch_failed') {
    notes.push({
      category: 'Major Arterial Roads',
      status: 'incomplete',
      text: 'Road network comparison incomplete due to Overpass query failure.',
    });
  } else if (infraA.status === 'data_unavailable' || infraB.status === 'data_unavailable') {
    notes.push({
      category: 'Major Arterial Roads',
      status: 'incomplete',
      text: 'Road telemetry is unavailable for one or both locations.',
    });
  } else {
    const rA = infraA.major_roads_count || 0;
    const rB = infraB.major_roads_count || 0;
    let text = '';
    if (rA > rB) {
      text = `${nameA} has more mapped arterial thoroughfares (${rA}) within 1.2 km vs ${nameB} (${rB}).`;
    } else if (rB > rA) {
      text = `${nameB} has more mapped arterial thoroughfares (${rB}) within 1.2 km vs ${nameA} (${rA}).`;
    } else {
      text = `Both localities report ${rA} mapped arterial thoroughfares within 1.2 km.`;
    }
    notes.push({
      category: 'Major Arterial Roads',
      status: 'comparable',
      text,
    });
  }

  // 6. Air Quality & Atmosphere
  const aqiA = dataA?.air_quality;
  const aqiB = dataB?.air_quality;
  if (!aqiA || !aqiB) {
    notes.push({
      category: 'Air Quality & Atmosphere',
      status: 'incomplete',
      text: 'Air quality telemetry is loading or unavailable.',
    });
  } else if (aqiA.status === 'active' && aqiB.status === 'active' && aqiA.aqi_value != null && aqiB.aqi_value != null) {
    if (aqiA.scale && aqiB.scale && aqiA.scale !== aqiB.scale) {
      notes.push({
        category: 'Air Quality & Atmosphere',
        status: 'incomplete',
        text: `Both localities have active atmospheric reporting but use different measurement scales (${aqiA.scale} vs ${aqiB.scale}); direct numerical index comparison is not equivalent. ${nameA} reports "${aqiA.category || 'Index'}" and ${nameB} reports "${aqiB.category || 'Index'}".`,
      });
    } else {
      let text = '';
      if (aqiA.aqi_value < aqiB.aqi_value) {
        text = `${nameA} reported lower AQI (${aqiA.aqi_value}, ${aqiA.category || 'Index'}) via station "${aqiA.station_name || 'Regional'}" compared to ${nameB} (${aqiB.aqi_value}, ${aqiB.category || 'Index'}) via station "${aqiB.station_name || 'Regional'}".`;
      } else if (aqiB.aqi_value < aqiA.aqi_value) {
        text = `${nameB} reported lower AQI (${aqiB.aqi_value}, ${aqiB.category || 'Index'}) via station "${aqiB.station_name || 'Regional'}" compared to ${nameA} (${aqiA.aqi_value}, ${aqiA.category || 'Index'}) via station "${aqiA.station_name || 'Regional'}".`;
      } else {
        text = `Both localities report identical AQI reading (${aqiA.aqi_value}, ${aqiA.category || 'Index'}).`;
      }
      notes.push({
        category: 'Air Quality & Atmosphere',
        status: 'comparable',
        text,
      });
    }
  } else if (aqiA.status === 'provider_not_configured' || aqiB.status === 'provider_not_configured') {
    notes.push({
      category: 'Air Quality & Atmosphere',
      status: 'not_configured',
      text: 'Air quality comparison is unavailable because sensor API keys are unconfigured in the backend environment. No estimated or synthetic values are generated.',
    });
  } else if (aqiA.status === 'data_unavailable' || aqiB.status === 'data_unavailable') {
    notes.push({
      category: 'Air Quality & Atmosphere',
      status: 'unavailable',
      text: 'Air quality data is unavailable: no active atmospheric monitoring stations reported readings within range (50 km).',
    });
  } else {
    notes.push({
      category: 'Air Quality & Atmosphere',
      status: 'incomplete',
      text: 'Air quality telemetry encountered an unexpected service error or timeout.',
    });
  }

  return {
    notes,
    disclaimer:
      'This summary is deterministically derived from verified OpenStreetMap civic infrastructure and atmospheric sensors within standard 1.2 km (2.0 km rail) radii. Distances are straight-line geometric (Haversine) calculations, not street travel times. NIVAS does not generate composite scores or infer safety from missing data.',
  };
};

export default function LocalityComparisonView() {
  // Independent Locality A State
  const [localityA, setLocalityA] = useState(() => {
    const saved = safeStorage.getItem('nivas_livability_compare_a');
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
  const [searchQueryA, setSearchQueryA] = useState('');
  const [statusA, setStatusA] = useState({ isSearching: false, searchError: '', reverseError: '' });
  const [dataA, setDataA] = useState(null);
  const [isLoadingA, setIsLoadingA] = useState(false);
  const [errorA, setErrorA] = useState(null);
  const activeRequestRefA = useRef(0);

  // Independent Locality B State
  const [localityB, setLocalityB] = useState(() => {
    const saved = safeStorage.getItem('nivas_livability_compare_b');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (typeof parsed.latitude === 'number' && typeof parsed.longitude === 'number' && parsed.address) {
          return parsed;
        }
      } catch (e) {}
    }
    return {
      latitude: 28.5245,
      longitude: 77.1535,
      address: 'Vasant Kunj, South West Delhi, Delhi',
    };
  });
  const [searchQueryB, setSearchQueryB] = useState('');
  const [statusB, setStatusB] = useState({ isSearching: false, searchError: '', reverseError: '' });
  const [dataB, setDataB] = useState(null);
  const [isLoadingB, setIsLoadingB] = useState(false);
  const [errorB, setErrorB] = useState(null);
  const activeRequestRefB = useRef(0);

  // Persist A and B locations
  useEffect(() => {
    safeStorage.setItem('nivas_livability_compare_a', JSON.stringify(localityA));
  }, [localityA]);

  useEffect(() => {
    safeStorage.setItem('nivas_livability_compare_b', JSON.stringify(localityB));
  }, [localityB]);

  // Fetch telemetry for Locality A
  const fetchTelemetryA = useCallback(
    (lat, lon, addr) => {
      if (typeof lat !== 'number' || typeof lon !== 'number') return;
      const reqId = ++activeRequestRefA.current;
      const controller = new AbortController();

      setIsLoadingA(true);
      setErrorA(null);

      fetchLivabilityLocationData({ latitude: lat, longitude: lon, address: addr }, controller.signal)
        .then((data) => {
          if (activeRequestRefA.current === reqId) {
            setDataA(data);
            setIsLoadingA(false);
            setErrorA(null);
          }
        })
        .catch((err) => {
          if (activeRequestRefA.current === reqId) {
            if (err.name !== 'CanceledError' && err.name !== 'AbortError' && err?.code !== 'ERR_CANCELED') {
              setErrorA(err.message || 'Unable to retrieve telemetry for Locality A');
              setIsLoadingA(false);
            }
          }
        });

      return () => controller.abort();
    },
    []
  );

  // Fetch telemetry for Locality B
  const fetchTelemetryB = useCallback(
    (lat, lon, addr) => {
      if (typeof lat !== 'number' || typeof lon !== 'number') return;
      const reqId = ++activeRequestRefB.current;
      const controller = new AbortController();

      setIsLoadingB(true);
      setErrorB(null);

      fetchLivabilityLocationData({ latitude: lat, longitude: lon, address: addr }, controller.signal)
        .then((data) => {
          if (activeRequestRefB.current === reqId) {
            setDataB(data);
            setIsLoadingB(false);
            setErrorB(null);
          }
        })
        .catch((err) => {
          if (activeRequestRefB.current === reqId) {
            if (err.name !== 'CanceledError' && err.name !== 'AbortError' && err?.code !== 'ERR_CANCELED') {
              setErrorB(err.message || 'Unable to retrieve telemetry for Locality B');
              setIsLoadingB(false);
            }
          }
        });

      return () => controller.abort();
    },
    []
  );

  useEffect(() => {
    const cleanupA = fetchTelemetryA(localityA.latitude, localityA.longitude, localityA.address);
    return () => {
      if (typeof cleanupA === 'function') cleanupA();
    };
  }, [localityA.latitude, localityA.longitude, localityA.address, fetchTelemetryA]);

  useEffect(() => {
    const cleanupB = fetchTelemetryB(localityB.latitude, localityB.longitude, localityB.address);
    return () => {
      if (typeof cleanupB === 'function') cleanupB();
    };
  }, [localityB.latitude, localityB.longitude, localityB.address, fetchTelemetryB]);

  // Handlers for Locality A
  const handleLocationChangeA = useCallback((newLoc) => {
    setLocalityA((prev) => ({
      latitude: newLoc.latitude,
      longitude: newLoc.longitude,
      address: newLoc.address || prev.address || 'Selected Location A',
    }));
  }, []);

  // Handlers for Locality B
  const handleLocationChangeB = useCallback((newLoc) => {
    setLocalityB((prev) => ({
      latitude: newLoc.latitude,
      longitude: newLoc.longitude,
      address: newLoc.address || prev.address || 'Selected Location B',
    }));
  }, []);

  // Compute nearest facilities for each category
  const nearestSchoolA = useMemo(
    () => findNearestFacility(dataA?.infrastructure?.facilities, ['school'], localityA.latitude, localityA.longitude),
    [dataA, localityA]
  );
  const nearestSchoolB = useMemo(
    () => findNearestFacility(dataB?.infrastructure?.facilities, ['school'], localityB.latitude, localityB.longitude),
    [dataB, localityB]
  );

  const nearestHealthA = useMemo(
    () => findNearestFacility(dataA?.infrastructure?.facilities, ['hospital', 'clinic', 'pharmacy'], localityA.latitude, localityA.longitude),
    [dataA, localityA]
  );
  const nearestHealthB = useMemo(
    () => findNearestFacility(dataB?.infrastructure?.facilities, ['hospital', 'clinic', 'pharmacy'], localityB.latitude, localityB.longitude),
    [dataB, localityB]
  );

  const nearestTransitA = useMemo(
    () => findNearestFacility(dataA?.infrastructure?.facilities, ['transit', 'railway'], localityA.latitude, localityA.longitude),
    [dataA, localityA]
  );
  const nearestTransitB = useMemo(
    () => findNearestFacility(dataB?.infrastructure?.facilities, ['transit', 'railway'], localityB.latitude, localityB.longitude),
    [dataB, localityB]
  );

  const nearestEmergencyA = useMemo(
    () => findNearestFacility(dataA?.infrastructure?.facilities, ['police', 'fire'], localityA.latitude, localityA.longitude),
    [dataA, localityA]
  );
  const nearestEmergencyB = useMemo(
    () => findNearestFacility(dataB?.infrastructure?.facilities, ['police', 'fire'], localityB.latitude, localityB.longitude),
    [dataB, localityB]
  );

  // Evidence comparison synthesis
  const summary = useMemo(
    () => generateLocalityEvidenceSummary(localityA, dataA, localityB, dataB),
    [localityA, dataA, localityB, dataB]
  );

  const renderStatusBadge = (status, errorMsg) => {
    if (status === 'active') {
      return (
        <span className="compare-status-badge ready">
          <CheckCircle2 size={11} /> Verified
        </span>
      );
    }
    if (status === 'empty') {
      return (
        <span className="compare-status-badge empty">
          <Info size={11} /> 0 Recorded
        </span>
      );
    }
    if (status === 'provider_not_configured') {
      return (
        <span className="compare-status-badge unconfigured">
          <Info size={11} /> Provider Unconfigured
        </span>
      );
    }
    if (status === 'data_unavailable') {
      return (
        <span className="compare-status-badge unavailable">
          <AlertCircle size={11} /> Data Unavailable
        </span>
      );
    }
    if (status === 'fetch_failed') {
      return (
        <span className="compare-status-badge failed">
          <AlertCircle size={11} /> Fetch Failed
        </span>
      );
    }
    return (
      <span className="compare-status-badge pending">
        <Loader2 size={11} className="spin-icon" /> Pending
      </span>
    );
  };

  return (
    <div className="locality-compare-root" data-testid="locality-comparison-view">
      {/* Overview Banner */}
      <div className="locality-compare-intro-banner">
        <div className="intro-title-wrap">
          <Scale size={20} className="intro-icon" />
          <div>
            <h2 className="intro-title">Evidence-Based Locality Comparison</h2>
            <p className="intro-subtitle">
              Parallel comparative evaluation of verified civic infrastructure, connectivity, and atmospheric telemetry for two independent localities.
            </p>
          </div>
        </div>
        <div className="intro-radius-pill">
          <Info size={12} />
          <span>Standard Search Radius: 1.2 km civic · 2.0 km rail/metro · Haversine Straight-Line Distance</span>
        </div>
      </div>

      {/* Two Independent Locality Selection Pickers */}
      <div className="locality-compare-selection-grid">
        {/* Locality A Selection */}
        <div className="locality-selection-card locality-card-a" data-testid="locality-card-a">
          <div className="selection-card-header">
            <span className="locality-badge locality-badge-a">Locality A</span>
            <div className="selection-coords-badge">
              {localityA.latitude.toFixed(4)}° N, {localityA.longitude.toFixed(4)}° E
            </div>
          </div>

          <h3 className="selection-locality-title" title={localityA.address}>
            {localityA.address || 'Dwarka Sector 12, New Delhi'}
          </h3>

          <div className="locality-picker-wrapper">
            <PropertyLocationPicker
              latitude={localityA.latitude}
              longitude={localityA.longitude}
              location={localityA}
              onLocationChange={handleLocationChangeA}
              searchQuery={searchQueryA}
              onSearchQueryChange={setSearchQueryA}
              onSearchStatusChange={setStatusA}
              searchPlaceholder="Search Locality A (e.g. Hauz Khas, Dwarka)..."
              mapHeight={220}
              initialZoom={14}
            />
          </div>

          <div className="selection-status-row">
            {isLoadingA ? (
              <span className="selection-status-pill loading">
                <Loader2 size={12} className="spin-icon" /> Querying OpenStreetMap...
              </span>
            ) : errorA ? (
              <span className="selection-status-pill error">
                <AlertCircle size={12} /> Telemetry Error
              </span>
            ) : (
              <span className="selection-status-pill ready">
                <CheckCircle2 size={12} /> Telemetry Loaded ({dataA?.infrastructure?.total_facilities || 0} amenities)
              </span>
            )}
            {dataA?.retrieved_at && !isLoadingA && (
              <span className="selection-retrieved-at">
                Retrieved: {new Date(dataA.retrieved_at).toISOString().slice(11, 19)} UTC
              </span>
            )}
            {statusA.reverseError && <span className="selection-notice warning">{statusA.reverseError}</span>}
            {statusA.searchError && <span className="selection-notice error">{statusA.searchError}</span>}
          </div>
        </div>

        {/* Locality B Selection */}
        <div className="locality-selection-card locality-card-b" data-testid="locality-card-b">
          <div className="selection-card-header">
            <span className="locality-badge locality-badge-b">Locality B</span>
            <div className="selection-coords-badge">
              {localityB.latitude.toFixed(4)}° N, {localityB.longitude.toFixed(4)}° E
            </div>
          </div>

          <h3 className="selection-locality-title" title={localityB.address}>
            {localityB.address || 'Vasant Kunj, South West Delhi'}
          </h3>

          <div className="locality-picker-wrapper">
            <PropertyLocationPicker
              latitude={localityB.latitude}
              longitude={localityB.longitude}
              location={localityB}
              onLocationChange={handleLocationChangeB}
              searchQuery={searchQueryB}
              onSearchQueryChange={setSearchQueryB}
              onSearchStatusChange={setStatusB}
              searchPlaceholder="Search Locality B (e.g. Connaught Place, Rohini)..."
              mapHeight={220}
              initialZoom={14}
            />
          </div>

          <div className="selection-status-row">
            {isLoadingB ? (
              <span className="selection-status-pill loading">
                <Loader2 size={12} className="spin-icon" /> Querying OpenStreetMap...
              </span>
            ) : errorB ? (
              <span className="selection-status-pill error">
                <AlertCircle size={12} /> Telemetry Error
              </span>
            ) : (
              <span className="selection-status-pill ready">
                <CheckCircle2 size={12} /> Telemetry Loaded ({dataB?.infrastructure?.total_facilities || 0} amenities)
              </span>
            )}
            {dataB?.retrieved_at && !isLoadingB && (
              <span className="selection-retrieved-at">
                Retrieved: {new Date(dataB.retrieved_at).toISOString().slice(11, 19)} UTC
              </span>
            )}
            {statusB.reverseError && <span className="selection-notice warning">{statusB.reverseError}</span>}
            {statusB.searchError && <span className="selection-notice error">{statusB.searchError}</span>}
          </div>
        </div>
      </div>

      {/* Side-by-Side Evidence Comparison Table */}
      <div className="locality-compare-evidence-section">
        <div className="evidence-section-header">
          <div className="evidence-header-title-wrap">
            <Building2 size={17} />
            <h3 className="evidence-header-title">Side-by-Side Civic Evidence Comparison</h3>
          </div>
          <span className="evidence-header-tag">OpenStreetMap & Atmospheric Telemetry</span>
        </div>

        <div className="compare-table-responsive-wrapper">
          <table className="locality-compare-table" aria-label="Locality Evidence Comparison Table">
            <thead>
              <tr>
                <th className="th-metric">Civic & Environmental Metric</th>
                <th className="th-loc-a">
                  <span className="loc-header-badge a">Locality A</span>
                  <div className="th-loc-name">{localityA.address?.split(',')[0] || 'Locality A'}</div>
                </th>
                <th className="th-loc-b">
                  <span className="loc-header-badge b">Locality B</span>
                  <div className="th-loc-name">{localityB.address?.split(',')[0] || 'Locality B'}</div>
                </th>
              </tr>
            </thead>
            <tbody>
              {/* Row 1: Schools & Education */}
              <tr>
                <td className="metric-cell">
                  <div className="metric-title-group">
                    <GraduationCap size={16} className="metric-icon school" />
                    <div>
                      <div className="metric-title">Schools & Education</div>
                      <div className="metric-desc">Primary & secondary schools within 1.2 km</div>
                    </div>
                  </div>
                </td>
                <td className="data-cell a">
                  {isLoadingA ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      <div className="metric-val-main">
                        {formatCivicMetricValue(
                          dataA?.infrastructure,
                          dataA?.infrastructure?.schools_count,
                          'Mapped School',
                          'Mapped Schools'
                        )}
                      </div>
                      {dataA?.infrastructure?.status === 'active' && nearestSchoolA && (
                        <div className="nearest-place-line" title={nearestSchoolA.name}>
                          Nearest: <strong>{nearestSchoolA.name}</strong> ({nearestSchoolA.formattedDistance})
                        </div>
                      )}
                      <div className="status-wrap">{renderStatusBadge(dataA?.infrastructure?.status)}</div>
                    </>
                  )}
                </td>
                <td className="data-cell b">
                  {isLoadingB ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      <div className="metric-val-main">
                        {formatCivicMetricValue(
                          dataB?.infrastructure,
                          dataB?.infrastructure?.schools_count,
                          'Mapped School',
                          'Mapped Schools'
                        )}
                      </div>
                      {dataB?.infrastructure?.status === 'active' && nearestSchoolB && (
                        <div className="nearest-place-line" title={nearestSchoolB.name}>
                          Nearest: <strong>{nearestSchoolB.name}</strong> ({nearestSchoolB.formattedDistance})
                        </div>
                      )}
                      <div className="status-wrap">{renderStatusBadge(dataB?.infrastructure?.status)}</div>
                    </>
                  )}
                </td>
              </tr>

              {/* Row 2: Healthcare Facilities */}
              <tr>
                <td className="metric-cell">
                  <div className="metric-title-group">
                    <HeartPulse size={16} className="metric-icon healthcare" />
                    <div>
                      <div className="metric-title">Healthcare Facilities</div>
                      <div className="metric-desc">Hospitals, clinics, pharmacies within 1.2 km</div>
                    </div>
                  </div>
                </td>
                <td className="data-cell a">
                  {isLoadingA ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      <div className="metric-val-main">
                        {formatCivicMetricValue(
                          dataA?.infrastructure,
                          (dataA?.infrastructure?.hospitals_count || 0) +
                            (dataA?.infrastructure?.clinics_count || 0) +
                            (dataA?.infrastructure?.pharmacies_count || 0),
                          'Facility',
                          'Total Facilities'
                        )}
                      </div>
                      {dataA?.infrastructure?.status === 'active' && (
                        <div className="breakdown-line">
                          {dataA.infrastructure.hospitals_count} hosp, {dataA.infrastructure.clinics_count} clinics, {dataA.infrastructure.pharmacies_count} pharm
                        </div>
                      )}
                      {dataA?.infrastructure?.status === 'active' && nearestHealthA && (
                        <div className="nearest-place-line" title={nearestHealthA.name}>
                          Nearest: <strong>{nearestHealthA.name}</strong> ({nearestHealthA.formattedDistance})
                        </div>
                      )}
                      <div className="status-wrap">{renderStatusBadge(dataA?.infrastructure?.status)}</div>
                    </>
                  )}
                </td>
                <td className="data-cell b">
                  {isLoadingB ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      <div className="metric-val-main">
                        {formatCivicMetricValue(
                          dataB?.infrastructure,
                          (dataB?.infrastructure?.hospitals_count || 0) +
                            (dataB?.infrastructure?.clinics_count || 0) +
                            (dataB?.infrastructure?.pharmacies_count || 0),
                          'Facility',
                          'Total Facilities'
                        )}
                      </div>
                      {dataB?.infrastructure?.status === 'active' && (
                        <div className="breakdown-line">
                          {dataB.infrastructure.hospitals_count} hosp, {dataB.infrastructure.clinics_count} clinics, {dataB.infrastructure.pharmacies_count} pharm
                        </div>
                      )}
                      {dataB?.infrastructure?.status === 'active' && nearestHealthB && (
                        <div className="nearest-place-line" title={nearestHealthB.name}>
                          Nearest: <strong>{nearestHealthB.name}</strong> ({nearestHealthB.formattedDistance})
                        </div>
                      )}
                      <div className="status-wrap">{renderStatusBadge(dataB?.infrastructure?.status)}</div>
                    </>
                  )}
                </td>
              </tr>

              {/* Row 3: Transit & Commute Access */}
              <tr>
                <td className="metric-cell">
                  <div className="metric-title-group">
                    <Bus size={16} className="metric-icon transit" />
                    <div>
                      <div className="metric-title">Transit & Commute Access</div>
                      <div className="metric-desc">Metro & rail (within 2.0 km), bus stops (1.2 km)</div>
                    </div>
                  </div>
                </td>
                <td className="data-cell a">
                  {isLoadingA ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      <div className="metric-val-main">
                        {formatCivicMetricValue(
                          dataA?.infrastructure,
                          (dataA?.infrastructure?.public_transport_count || 0) +
                            (dataA?.infrastructure?.railway_stations_count || 0),
                          'Transit Stop',
                          'Transit Stops'
                        )}
                      </div>
                      {dataA?.infrastructure?.status === 'active' && (
                        <div className="breakdown-line">
                          {dataA.infrastructure.railway_stations_count} rail/metro, {dataA.infrastructure.public_transport_count} bus stops
                        </div>
                      )}
                      {dataA?.infrastructure?.status === 'active' && nearestTransitA && (
                        <div className="nearest-place-line" title={nearestTransitA.name}>
                          Nearest: <strong>{nearestTransitA.name}</strong> ({nearestTransitA.formattedDistance})
                        </div>
                      )}
                      <div className="status-wrap">{renderStatusBadge(dataA?.infrastructure?.status)}</div>
                    </>
                  )}
                </td>
                <td className="data-cell b">
                  {isLoadingB ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      <div className="metric-val-main">
                        {formatCivicMetricValue(
                          dataB?.infrastructure,
                          (dataB?.infrastructure?.public_transport_count || 0) +
                            (dataB?.infrastructure?.railway_stations_count || 0),
                          'Transit Stop',
                          'Transit Stops'
                        )}
                      </div>
                      {dataB?.infrastructure?.status === 'active' && (
                        <div className="breakdown-line">
                          {dataB.infrastructure.railway_stations_count} rail/metro, {dataB.infrastructure.public_transport_count} bus stops
                        </div>
                      )}
                      {dataB?.infrastructure?.status === 'active' && nearestTransitB && (
                        <div className="nearest-place-line" title={nearestTransitB.name}>
                          Nearest: <strong>{nearestTransitB.name}</strong> ({nearestTransitB.formattedDistance})
                        </div>
                      )}
                      <div className="status-wrap">{renderStatusBadge(dataB?.infrastructure?.status)}</div>
                    </>
                  )}
                </td>
              </tr>

              {/* Row 4: Emergency Services */}
              <tr>
                <td className="metric-cell">
                  <div className="metric-title-group">
                    <ShieldAlert size={16} className="metric-icon emergency" />
                    <div>
                      <div className="metric-title">Emergency Services</div>
                      <div className="metric-desc">Police & fire stations within 1.2 km</div>
                    </div>
                  </div>
                </td>
                <td className="data-cell a">
                  {isLoadingA ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      <div className="metric-val-main">
                        {formatCivicMetricValue(
                          dataA?.infrastructure,
                          (dataA?.infrastructure?.police_stations_count || 0) +
                            (dataA?.infrastructure?.fire_stations_count || 0),
                          'Station',
                          'Stations'
                        )}
                      </div>
                      {dataA?.infrastructure?.status === 'active' && (
                        <div className="breakdown-line">
                          {dataA.infrastructure.police_stations_count} police, {dataA.infrastructure.fire_stations_count} fire
                        </div>
                      )}
                      {dataA?.infrastructure?.status === 'active' && nearestEmergencyA && (
                        <div className="nearest-place-line" title={nearestEmergencyA.name}>
                          Nearest: <strong>{nearestEmergencyA.name}</strong> ({nearestEmergencyA.formattedDistance})
                        </div>
                      )}
                      <div className="status-wrap">{renderStatusBadge(dataA?.infrastructure?.status)}</div>
                    </>
                  )}
                </td>
                <td className="data-cell b">
                  {isLoadingB ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      <div className="metric-val-main">
                        {formatCivicMetricValue(
                          dataB?.infrastructure,
                          (dataB?.infrastructure?.police_stations_count || 0) +
                            (dataB?.infrastructure?.fire_stations_count || 0),
                          'Station',
                          'Stations'
                        )}
                      </div>
                      {dataB?.infrastructure?.status === 'active' && (
                        <div className="breakdown-line">
                          {dataB.infrastructure.police_stations_count} police, {dataB.infrastructure.fire_stations_count} fire
                        </div>
                      )}
                      {dataB?.infrastructure?.status === 'active' && nearestEmergencyB && (
                        <div className="nearest-place-line" title={nearestEmergencyB.name}>
                          Nearest: <strong>{nearestEmergencyB.name}</strong> ({nearestEmergencyB.formattedDistance})
                        </div>
                      )}
                      <div className="status-wrap">{renderStatusBadge(dataB?.infrastructure?.status)}</div>
                    </>
                  )}
                </td>
              </tr>

              {/* Row 5: Major Arterial Roads */}
              <tr>
                <td className="metric-cell">
                  <div className="metric-title-group">
                    <Building2 size={16} className="metric-icon road" />
                    <div>
                      <div className="metric-title">Major Arterial Roads</div>
                      <div className="metric-desc">Primary & secondary thoroughfares in 1.2 km</div>
                    </div>
                  </div>
                </td>
                <td className="data-cell a">
                  {isLoadingA ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      <div className="metric-val-main">
                        {formatCivicMetricValue(
                          dataA?.infrastructure,
                          dataA?.infrastructure?.major_roads_count,
                          'Arterial Road',
                          'Arterial Roads'
                        )}
                      </div>
                      <div className="status-wrap">{renderStatusBadge(dataA?.infrastructure?.status)}</div>
                    </>
                  )}
                </td>
                <td className="data-cell b">
                  {isLoadingB ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      <div className="metric-val-main">
                        {formatCivicMetricValue(
                          dataB?.infrastructure,
                          dataB?.infrastructure?.major_roads_count,
                          'Arterial Road',
                          'Arterial Roads'
                        )}
                      </div>
                      <div className="status-wrap">{renderStatusBadge(dataB?.infrastructure?.status)}</div>
                    </>
                  )}
                </td>
              </tr>

              {/* Row 6: Air Quality & Atmosphere */}
              <tr>
                <td className="metric-cell">
                  <div className="metric-title-group">
                    <Wind size={16} className="metric-icon aqi" />
                    <div>
                      <div className="metric-title">Air Quality (AQI)</div>
                      <div className="metric-desc">Observed sensor readings & category</div>
                    </div>
                  </div>
                </td>
                <td className="data-cell a">
                  {isLoadingA ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      {dataA?.air_quality?.status === 'active' && dataA.air_quality.aqi_value != null ? (
                        <>
                          <div className="metric-val-main">
                            AQI {dataA.air_quality.aqi_value}{' '}
                            <span className="aqi-category-pill">({dataA.air_quality.category || 'Index'})</span>
                          </div>
                          {dataA.air_quality.scale && (
                            <div className="scale-line">Scale: {dataA.air_quality.scale}</div>
                          )}
                          {dataA.air_quality.station_name && (
                            <div className="station-line">Station: {dataA.air_quality.station_name}</div>
                          )}
                          {dataA.air_quality.source && (
                            <div className="provider-line">Source: {dataA.air_quality.source}</div>
                          )}
                          {dataA.retrieved_at && (
                            <div className="timestamp-line">
                              Observed: {new Date(dataA.retrieved_at).toISOString().slice(11, 19)} UTC
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="metric-val-main unconfigured">
                          {dataA?.air_quality?.status === 'provider_not_configured'
                            ? 'Unconfigured Provider'
                            : dataA?.air_quality?.status === 'data_unavailable'
                            ? 'No Nearby Station'
                            : dataA?.air_quality?.status === 'fetch_failed'
                            ? 'Telemetry Failed'
                            : '—'}
                        </div>
                      )}
                      <div className="status-wrap">{renderStatusBadge(dataA?.air_quality?.status)}</div>
                    </>
                  )}
                </td>
                <td className="data-cell b">
                  {isLoadingB ? (
                    <span className="cell-loading"><Loader2 size={12} className="spin-icon" /> Querying...</span>
                  ) : (
                    <>
                      {dataB?.air_quality?.status === 'active' && dataB.air_quality.aqi_value != null ? (
                        <>
                          <div className="metric-val-main">
                            AQI {dataB.air_quality.aqi_value}{' '}
                            <span className="aqi-category-pill">({dataB.air_quality.category || 'Index'})</span>
                          </div>
                          {dataB.air_quality.scale && (
                            <div className="scale-line">Scale: {dataB.air_quality.scale}</div>
                          )}
                          {dataB.air_quality.station_name && (
                            <div className="station-line">Station: {dataB.air_quality.station_name}</div>
                          )}
                          {dataB.air_quality.source && (
                            <div className="provider-line">Source: {dataB.air_quality.source}</div>
                          )}
                          {dataB.retrieved_at && (
                            <div className="timestamp-line">
                              Observed: {new Date(dataB.retrieved_at).toISOString().slice(11, 19)} UTC
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="metric-val-main unconfigured">
                          {dataB?.air_quality?.status === 'provider_not_configured'
                            ? 'Unconfigured Provider'
                            : dataB?.air_quality?.status === 'data_unavailable'
                            ? 'No Nearby Station'
                            : dataB?.air_quality?.status === 'fetch_failed'
                            ? 'Telemetry Failed'
                            : '—'}
                        </div>
                      )}
                      <div className="status-wrap">{renderStatusBadge(dataB?.air_quality?.status)}</div>
                    </>
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Deterministic Evidence Synthesis Card */}
      <div className="locality-compare-summary-card" data-testid="evidence-synthesis-card">
        <div className="summary-card-header">
          <div className="summary-header-title-wrap">
            <Info size={16} />
            <h4 className="summary-header-title">Comparative Evidence Synthesis</h4>
          </div>
          <span className="summary-deterministic-tag">Deterministic · Telemetry-Grounded</span>
        </div>

        <div className="summary-observations-list">
          {summary.notes.map((note, idx) => (
            <div key={idx} className={`summary-observation-item ${note.status}`}>
              <span className="observation-category">{note.category}:</span>
              <span className="observation-text">{note.text}</span>
            </div>
          ))}
        </div>

        <div className="summary-card-footer">
          <ShieldAlert size={13} />
          <span>{summary.disclaimer}</span>
        </div>
      </div>
    </div>
  );
}
