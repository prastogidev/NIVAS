import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LivabilityWorkspace from '../LivabilityWorkspace';
import LocalityComparisonView, {
  findNearestFacility,
  generateLocalityEvidenceSummary,
  formatCivicMetricValue,
} from '../LocalityComparisonView';
import * as api from '../../services/api';
import App from '../../App';

let mapClickHandlers = [];
let markerDragHandlers = [];
let currentMarkerPos = { lat: 28.5921, lng: 77.046 };

// Mock Leaflet
vi.mock('leaflet', () => {
  const mockMap = {
    setView: vi.fn(),
    getZoom: () => 14,
    remove: vi.fn(),
    invalidateSize: vi.fn(),
    on: (evt, cb) => {
      if (evt === 'click') mapClickHandlers.push(cb);
    },
  };

  return {
    default: {
      map: () => mockMap,
      tileLayer: () => ({ addTo: () => {} }),
      marker: (coords) => {
        return {
          coords,
          openPopup: vi.fn(),
          addTo: function () {
            return this;
          },
          setLatLng: vi.fn((ll) => {
            if (Array.isArray(ll)) {
              currentMarkerPos = { lat: ll[0], lng: ll[1] };
            }
          }),
          getLatLng: () => currentMarkerPos,
          bindPopup: vi.fn(),
          on: vi.fn((evt, cb) => {
            if (evt === 'dragend') markerDragHandlers.push(cb);
          }),
        };
      },
      layerGroup: () => ({
        addTo: function () {
          return this;
        },
        clearLayers: vi.fn(),
        addLayer: vi.fn(),
      }),
      DomEvent: {
        stopPropagation: vi.fn(),
      },
      divIcon: () => ({}),
    },
  };
});

const storageMap = new Map();
const mockLocalStorage = {
  getItem: vi.fn((key) => storageMap.get(key) || null),
  setItem: vi.fn((key, value) => {
    storageMap.set(key, String(value));
  }),
  removeItem: vi.fn((key) => {
    storageMap.delete(key);
  }),
  clear: vi.fn(() => {
    storageMap.clear();
  }),
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
});

const mockDataLocalityA = {
  latitude: 28.5921,
  longitude: 77.046,
  address: 'Dwarka Sector 12, South West Delhi, Delhi',
  locality: 'Dwarka Sector 12',
  retrieved_at: '2026-10-10T12:00:00Z',
  infrastructure: {
    status: 'active',
    source: 'OpenStreetMap Overpass API',
    schools_count: 6,
    hospitals_count: 3,
    clinics_count: 2,
    pharmacies_count: 4,
    police_stations_count: 1,
    fire_stations_count: 1,
    public_transport_count: 10,
    railway_stations_count: 2,
    major_roads_count: 5,
    nearby_places: ['Dwarka Sector 12 Metro Station', 'Venkateshwar Hospital'],
    total_facilities: 28,
    facilities: [
      {
        id: 'school-a1',
        name: 'Delhi Public School Dwarka',
        category: 'school',
        category_label: 'School',
        latitude: 28.588,
        longitude: 77.042,
        source: 'OpenStreetMap',
      },
      {
        id: 'hosp-a1',
        name: 'Venkateshwar Hospital',
        category: 'hospital',
        category_label: 'Hospital',
        latitude: 28.5891,
        longitude: 77.0422,
        source: 'OpenStreetMap',
      },
      {
        id: 'transit-a1',
        name: 'Dwarka Sector 12 Metro Station',
        category: 'railway',
        category_label: 'Metro Station',
        latitude: 28.5925,
        longitude: 77.045,
        source: 'OpenStreetMap',
      },
      {
        id: 'police-a1',
        name: 'Dwarka South Police Station',
        category: 'police',
        category_label: 'Police Station',
        latitude: 28.59,
        longitude: 77.041,
        source: 'OpenStreetMap',
      },
    ],
  },
  air_quality: {
    status: 'active',
    source: 'CPCB CAAQMS / OpenWeather',
    scale: '0-500 (US EPA / CPCB)',
    aqi_value: 124.0,
    category: 'Moderate',
    station_name: 'Dwarka Sector 8 CAAQMS',
    environmental_score: 56.0,
  },
  environmental_hazards: {
    status: 'data_not_configured',
    message: 'Sensor network not configured for this region',
  },
};

const mockDataLocalityB = {
  latitude: 28.5245,
  longitude: 77.1535,
  address: 'Vasant Kunj, South West Delhi, Delhi',
  locality: 'Vasant Kunj',
  retrieved_at: '2026-10-10T12:00:00Z',
  infrastructure: {
    status: 'active',
    source: 'OpenStreetMap Overpass API',
    schools_count: 3,
    hospitals_count: 1,
    clinics_count: 1,
    pharmacies_count: 2,
    police_stations_count: 1,
    fire_stations_count: 0,
    public_transport_count: 4,
    railway_stations_count: 0,
    major_roads_count: 3,
    nearby_places: ['Fortis Hospital Vasant Kunj'],
    total_facilities: 11,
    facilities: [
      {
        id: 'school-b1',
        name: 'Vasant Valley School',
        category: 'school',
        category_label: 'School',
        latitude: 28.528,
        longitude: 77.156,
        source: 'OpenStreetMap',
      },
      {
        id: 'hosp-b1',
        name: 'Fortis Hospital Vasant Kunj',
        category: 'hospital',
        category_label: 'Hospital',
        latitude: 28.521,
        longitude: 77.151,
        source: 'OpenStreetMap',
      },
      {
        id: 'transit-b1',
        name: 'Vasant Kunj Bus Terminal',
        category: 'transit',
        category_label: 'Bus Station',
        latitude: 28.523,
        longitude: 77.152,
        source: 'OpenStreetMap',
      },
      {
        id: 'police-b1',
        name: 'Vasant Kunj South Police Station',
        category: 'police',
        category_label: 'Police Station',
        latitude: 28.522,
        longitude: 77.15,
        source: 'OpenStreetMap',
      },
    ],
  },
  air_quality: {
    status: 'active',
    source: 'CPCB CAAQMS / OpenWeather',
    scale: '0-500 (US EPA / CPCB)',
    aqi_value: 168.0,
    category: 'Unhealthy for Sensitive Groups',
    station_name: 'Vasant Kunj Institutional Area CAAQMS',
    environmental_score: 42.0,
  },
  environmental_hazards: {
    status: 'data_not_configured',
    message: 'Sensor network not configured for this region',
  },
};

describe('NIVAS Step 5.1: Evidence-Based Locality Comparison', () => {
  let originalFetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    mapClickHandlers = [];
    markerDragHandlers = [];
    currentMarkerPos = { lat: 28.5921, lng: 77.046 };
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it('correctly calculates nearest facility using findNearestFacility helper', () => {
    const facilities = mockDataLocalityA.infrastructure.facilities;
    const nearestSchool = findNearestFacility(facilities, ['school'], 28.5921, 77.046);
    expect(nearestSchool).toBeTruthy();
    expect(nearestSchool.name).toBe('Delhi Public School Dwarka');
    expect(nearestSchool.distanceKm).toBeGreaterThan(0);
    expect(nearestSchool.formattedDistance).toMatch(/m|km/);

    // Empty list
    expect(findNearestFacility([], ['school'], 28.5921, 77.046)).toBeNull();
    // Non-existent category
    expect(findNearestFacility(facilities, ['nonexistent'], 28.5921, 77.046)).toBeNull();
  });

  it('deterministically generates factual comparison synthesis without fabricating scores', () => {
    const locA = { address: 'Dwarka Sector 12, Delhi' };
    const locB = { address: 'Vasant Kunj, Delhi' };

    const summary = generateLocalityEvidenceSummary(locA, mockDataLocalityA, locB, mockDataLocalityB);
    expect(summary.notes.length).toBeGreaterThanOrEqual(4);

    // Schools comparison
    const schoolNote = summary.notes.find((n) => n.category === 'Schools & Education');
    expect(schoolNote.text).toContain('Dwarka Sector 12 has more mapped schools (6) than Vasant Kunj (3)');

    // Transit comparison: Dwarka has rail/metro, Vasant Kunj has 0
    const transitNote = summary.notes.find((n) => n.category === 'Transit & Commute Access');
    expect(transitNote.text).toContain('immediate rail/metro station access (2 stations within 2.0 km)');

    // Air quality comparison
    const aqiNote = summary.notes.find((n) => n.category === 'Air Quality & Atmosphere');
    expect(aqiNote.text).toContain('Dwarka Sector 12 reported lower AQI (124');

    // Disclaimer guarantees no composite score or safety assumption
    expect(summary.disclaimer).toContain('NIVAS does not generate composite scores');
  });

  it('handles unconfigured or failed telemetry honestly in evidence synthesis', () => {
    const locA = { address: 'Dwarka Sector 12, Delhi' };
    const locB = { address: 'Vasant Kunj, Delhi' };

    const unconfiguredLocB = {
      ...mockDataLocalityB,
      infrastructure: { status: 'fetch_failed' },
      air_quality: { status: 'provider_not_configured' },
    };

    const summary = generateLocalityEvidenceSummary(locA, mockDataLocalityA, locB, unconfiguredLocB);
    const schoolNote = summary.notes.find((n) => n.category === 'Schools & Education');
    expect(schoolNote.status).toBe('incomplete');
    expect(schoolNote.text).toContain('OpenStreetMap query failed');

    const aqiNote = summary.notes.find((n) => n.category === 'Air Quality & Atmosphere');
    expect(aqiNote.status).toBe('not_configured');
    expect(aqiNote.text).toContain('sensor API keys are unconfigured');
  });

  it('renders LocalityComparisonView with independent selectors, side-by-side evidence, and synthesis card', async () => {
    vi.spyOn(api, 'fetchLivabilityLocationData').mockImplementation(async (params) => {
      if (params.latitude === 28.5921) {
        return mockDataLocalityA;
      }
      return mockDataLocalityB;
    });

    render(<LocalityComparisonView />);

    // Header & Search Radius label
    expect(screen.getByText(/Evidence-Based Locality Comparison/i)).toBeTruthy();
    expect(screen.getByText(/Standard Search Radius: 1.2 km civic · 2.0 km rail\/metro/i)).toBeTruthy();

    // Locality A and Locality B selection cards
    expect(screen.getByTestId('locality-card-a')).toBeTruthy();
    expect(screen.getByTestId('locality-card-b')).toBeTruthy();
    expect(screen.getAllByText(/Locality A/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Locality B/i).length).toBeGreaterThan(0);

    // Side-by-side evidence table headers
    await waitFor(() => {
      expect(screen.getByText('Side-by-Side Civic Evidence Comparison')).toBeTruthy();
      expect(screen.getByText('Schools & Education')).toBeTruthy();
      expect(screen.getByText('Healthcare Facilities')).toBeTruthy();
      expect(screen.getByText('Transit & Commute Access')).toBeTruthy();
      expect(screen.getByText('Emergency Services')).toBeTruthy();
      expect(screen.getByText('Major Arterial Roads')).toBeTruthy();
      expect(screen.getByText(/Air Quality \(AQI\)/i)).toBeTruthy();
    });

    // Metric counts rendered
    expect(screen.getByText('6 Mapped Schools')).toBeTruthy();
    expect(screen.getByText('3 Mapped Schools')).toBeTruthy();
    expect(screen.getByText('9 Total Facilities')).toBeTruthy(); // 3 hosp + 2 clinic + 4 pharm
    expect(screen.getByText('12 Transit Stops')).toBeTruthy(); // 10 bus + 2 metro

    // Comparative Evidence Synthesis card rendered
    expect(screen.getByTestId('evidence-synthesis-card')).toBeTruthy();
    expect(screen.getByText('Comparative Evidence Synthesis')).toBeTruthy();
  });

  it('allows switching views in LivabilityWorkspace and preserves isolation', async () => {
    vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockDataLocalityA);

    render(<LivabilityWorkspace />);

    // Defaults to Explore Neighborhood
    expect(screen.getByRole('heading', { name: /Neighborhood AI Advisor/i })).toBeTruthy();
    expect(screen.getByText(/Regional Locality Explorer/i)).toBeTruthy();

    // Switch to Compare Localities
    const compareTab = screen.getByRole('tab', { name: /Compare Localities/i });
    fireEvent.click(compareTab);

    // Now renders Locality Comparison View
    expect(screen.getByTestId('locality-comparison-view')).toBeTruthy();
    expect(screen.getByText(/Side-by-Side Civic Evidence Comparison/i)).toBeTruthy();

    // Switch back to Explore Neighborhood
    const exploreTab = screen.getByRole('tab', { name: /Explore Neighborhood/i });
    fireEvent.click(exploreTab);

    // AI Advisor & Map are restored
    expect(screen.getByRole('heading', { name: /Neighborhood AI Advisor/i })).toBeTruthy();
    expect(screen.getByText(/Regional Locality Explorer/i)).toBeTruthy();
  });

  it('guarantees state isolation: changes in Compare Localities never overwrite Single Inspection, Property Compare, or exploration pin', async () => {
    vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockDataLocalityA);

    render(<App />);

    // 1. Opens in Livability by default
    expect(screen.getByText(/Neighborhood Livability Intelligence/i)).toBeTruthy();

    // Switch to Compare Localities view
    const compareTab = screen.getByRole('tab', { name: /Compare Localities/i });
    fireEvent.click(compareTab);
    expect(screen.getByTestId('locality-comparison-view')).toBeTruthy();

    // 2. Switch to Property Inspection tab
    const inspectionTab = screen.getByRole('button', { name: /Property Inspection/i });
    fireEvent.click(inspectionTab);

    // Verify Single Inspection form retained its address
    expect(screen.getByDisplayValue('Dwarka Sector 12, New Delhi')).toBeTruthy();

    // 3. Switch to Property Compare mode
    const compareModeBtn = screen.getByRole('button', { name: /Property Compare/i });
    fireEvent.click(compareModeBtn);

    // Verify Compare Form retains its independent Property A and Property B addresses
    expect(screen.getByDisplayValue('Dwarka Sector 12, New Delhi')).toBeTruthy();
    expect(screen.getByDisplayValue('Connaught Place, New Delhi')).toBeTruthy();

    // 4. Switch back to Livability: Livability remains intact
    const livabilityTab = screen.getByRole('button', { name: /Livability/i });
    fireEvent.click(livabilityTab);
    expect(screen.getByText(/Neighborhood Livability Intelligence/i)).toBeTruthy();
  });

  it('formatCivicMetricValue helper handles active, empty, and failed telemetry without zero-inference', () => {
    // Null or undefined
    expect(formatCivicMetricValue(null, 5, 'Mapped School', 'Mapped Schools')).toBe('—');

    // Telemetry fetch failed or data unavailable must NEVER be converted to zero
    expect(formatCivicMetricValue({ status: 'fetch_failed' }, 0, 'Mapped School', 'Mapped Schools')).toBe('—');
    expect(formatCivicMetricValue({ status: 'data_unavailable' }, 0, 'Facility', 'Total Facilities')).toBe('—');

    // Confirmed empty query within search radius
    expect(formatCivicMetricValue({ status: 'empty' }, 0, 'Mapped School', 'Mapped Schools')).toBe('0 Mapped Schools');

    // Active counts
    expect(formatCivicMetricValue({ status: 'active' }, 1, 'Mapped School', 'Mapped Schools')).toBe('1 Mapped School');
    expect(formatCivicMetricValue({ status: 'active' }, 5, 'Mapped School', 'Mapped Schools')).toBe('5 Mapped Schools');
  });

  it('findNearestFacility filters out invalid coordinates, NaNs, and empty names', () => {
    const mixedFacilities = [
      { name: '', category: 'school', latitude: 28.59, longitude: 77.04 },
      { name: '   ', category: 'school', latitude: 28.59, longitude: 77.04 },
      { name: 'Invalid Lat', category: 'school', latitude: NaN, longitude: 77.04 },
      { name: 'Invalid Lon', category: 'school', latitude: 28.59, longitude: 'invalid' },
      { name: 'Valid School', category: 'school', latitude: 28.592, longitude: 77.046 },
    ];

    const nearest = findNearestFacility(mixedFacilities, ['school'], 28.5921, 77.046);
    expect(nearest).toBeTruthy();
    expect(nearest.name).toBe('Valid School');

    // User coordinate NaNs
    expect(findNearestFacility(mixedFacilities, ['school'], NaN, 77.046)).toBeNull();
  });

  it('handles AQI scale differences and road thoroughfares in deterministic summary', () => {
    const locA = { address: 'Dwarka Sector 12, Delhi' };
    const locB = { address: 'Vasant Kunj, Delhi' };

    const dataWithDiffScalesA = {
      ...mockDataLocalityA,
      air_quality: {
        status: 'active',
        aqi_value: 124,
        scale: 'US-EPA (1-500)',
        category: 'Unhealthy for Sensitive Groups',
        station_name: 'Dwarka Station',
      },
    };

    const dataWithDiffScalesB = {
      ...mockDataLocalityB,
      air_quality: {
        status: 'active',
        aqi_value: 4,
        scale: 'OpenWeather (1-5)',
        category: 'Poor',
        station_name: 'Vasant Kunj Station',
      },
    };

    const summary = generateLocalityEvidenceSummary(locA, dataWithDiffScalesA, locB, dataWithDiffScalesB);
    const aqiNote = summary.notes.find((n) => n.category === 'Air Quality & Atmosphere');
    expect(aqiNote.status).toBe('incomplete');
    expect(aqiNote.text).toContain('use different measurement scales (US-EPA (1-500) vs OpenWeather (1-5))');

    // Major Arterial Roads comparison
    const roadNote = summary.notes.find((n) => n.category === 'Major Arterial Roads');
    expect(roadNote).toBeTruthy();
    expect(roadNote.status).toBe('comparable');
    expect(roadNote.text).toContain('Dwarka Sector 12 has more mapped arterial thoroughfares (5) within 1.2 km vs Vasant Kunj (3)');
  });

  it('renders honest status badges, timestamps, and scales in LocalityComparisonView', async () => {
    const customDataA = {
      ...mockDataLocalityA,
      retrieved_at: '2026-10-10T14:30:00Z',
      air_quality: {
        status: 'active',
        aqi_value: 95,
        scale: 'US-EPA (1-500)',
        category: 'Moderate',
        station_name: 'Dwarka Sector 8 Station',
        source: 'Central Pollution Control Board',
      },
    };

    const emptyDataB = {
      ...mockDataLocalityB,
      retrieved_at: '2026-10-10T14:30:00Z',
      infrastructure: {
        ...mockDataLocalityB.infrastructure,
        status: 'empty',
        schools_count: 0,
        total_facilities: 0,
      },
      air_quality: {
        status: 'data_unavailable',
        error_message: 'No stations reporting in radius',
      },
    };

    vi.spyOn(api, 'fetchLivabilityLocationData').mockImplementation(async (params) => {
      if (params.latitude === 28.5921) {
        return customDataA;
      }
      return emptyDataB;
    });

    render(<LocalityComparisonView />);

    await waitFor(() => {
      // Scale and timestamp rendering
      expect(screen.getByText(/Scale: US-EPA \(1-500\)/i)).toBeTruthy();
      expect(screen.getByText(/Station: Dwarka Sector 8 Station/i)).toBeTruthy();
      expect(screen.getAllByText(/Observed: 14:30:00 UTC/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Retrieved: 14:30:00 UTC/i).length).toBeGreaterThan(0);

      // Unconfigured or unavailable AQI label
      expect(screen.getByText('No Nearby Station')).toBeTruthy();

      // Status badges
      expect(screen.getAllByText(/0 Recorded/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Data Unavailable/i).length).toBeGreaterThan(0);
    });
  });
});

