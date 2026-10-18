import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LivabilityWorkspace, {
  calculateHaversineDistanceKm,
  formatFacilityDistance,
} from '../LivabilityWorkspace';
import App from '../../App';
import * as api from '../../services/api';

let mapClickHandlers = [];
let markerDragHandlers = [];
let currentMarkerPos = { lat: 28.5921, lng: 77.0460 };
let createdMarkers = [];
let mockStopPropagation = vi.fn();

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
      marker: (coords, options) => {
        const markerObj = {
          coords,
          options,
          clickHandlers: [],
          popupContent: null,
          openPopup: vi.fn(function() { return this; }),
          addTo: function() { return this; },
          setLatLng: vi.fn((ll) => {
            if (Array.isArray(ll)) {
              currentMarkerPos = { lat: ll[0], lng: ll[1] };
            } else if (ll && typeof ll.lat === 'number') {
              currentMarkerPos = { lat: ll.lat, lng: ll.lng };
            }
          }),
          getLatLng: () => currentMarkerPos,
          bindPopup: vi.fn(function(content) {
            markerObj.popupContent = content;
            return this;
          }),
          on: vi.fn((evt, cb) => {
            if (evt === 'dragend') markerDragHandlers.push(cb);
            if (evt === 'click') markerObj.clickHandlers.push(cb);
          }),
        };
        createdMarkers.push(markerObj);
        return markerObj;
      },
      layerGroup: () => {
        const layers = [];
        return {
          addTo: function() { return this; },
          clearLayers: function() { layers.length = 0; },
          addLayer: function(l) { layers.push(l); },
        };
      },
      circle: (coords, options) => {
        const circleObj = {
          coords,
          options,
          radius: options?.radius || 1200,
          addTo: function() { return this; },
          setLatLng: vi.fn(function(ll) { this.coords = ll; return this; }),
          setRadius: vi.fn(function(r) { this.radius = r; return this; }),
          remove: vi.fn(),
        };
        return circleObj;
      },
      DomEvent: {
        stopPropagation: (...args) => mockStopPropagation(...args),
      },
      divIcon: () => ({}),
    },
  };
});

const storageMap = new Map();
const mockLocalStorage = {
  getItem: vi.fn((key) => storageMap.get(key) || null),
  setItem: vi.fn((key, value) => { storageMap.set(key, String(value)); }),
  removeItem: vi.fn((key) => { storageMap.delete(key); }),
  clear: vi.fn(() => { storageMap.clear(); }),
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
});

describe('LivabilityWorkspace Shell & State Isolation', () => {
  let originalFetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    mapClickHandlers = [];
    markerDragHandlers = [];
    currentMarkerPos = { lat: 28.5921, lng: 77.0460 };
    createdMarkers = [];
    mockStopPropagation = vi.fn();
    window.localStorage.clear();
    window.location.hash = '';
  });

  afterEach(() => {
    global.fetch = originalFetch;
    window.localStorage.clear();
    window.location.hash = '';
    vi.clearAllMocks();
  });

  it('renders the responsive two-column layout with AI chat panel and map panel', () => {
    render(<LivabilityWorkspace />);

    // Header check
    expect(screen.getByText(/Neighborhood Livability Intelligence/i)).toBeTruthy();

    // Left Column: AI Recommendation Chat Panel with Logo
    const headerLogo = screen.getByAltText('Neighborhood AI Advisor logo');
    expect(headerLogo).toBeTruthy();
    expect(headerLogo.getAttribute('src')).toBe('/neighborhood-ai-logo.svg');
    expect(headerLogo.getAttribute('width')).toBe('52');
    expect(headerLogo.getAttribute('height')).toBe('52');

    expect(screen.getByRole('heading', { name: /Neighborhood AI Advisor/i })).toBeTruthy();
    expect(screen.getByText(/Interactive Preview/i)).toBeTruthy();
    expect(screen.getByText(/AI Discovery/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/Ask about neighborhood livability/i)).toBeTruthy();

    // Chat Message Avatar Logo
    const msgAvatars = screen.getAllByAltText('Neighborhood AI Advisor');
    expect(msgAvatars.length).toBeGreaterThanOrEqual(1);
    expect(msgAvatars[0].getAttribute('src')).toBe('/neighborhood-ai-logo.svg');
    expect(msgAvatars[0].getAttribute('width')).toBe('36');
    expect(msgAvatars[0].getAttribute('height')).toBe('36');

    // Right Column: Locality Explorer Map Panel
    expect(screen.getByText(/Regional Locality Explorer/i)).toBeTruthy();
    expect(screen.getByText(/Active Pinpoint:/i)).toBeTruthy();
    expect(screen.getByText(/28.5921° N, 77.0460° E/i)).toBeTruthy();
    expect(screen.getByText(/Selected Exploration Focus/i)).toBeTruthy();
    expect(screen.getByText(/Dwarka Sector 12, South West Delhi, Delhi/i)).toBeTruthy();
  });

  it('allows clicking a suggested prompt to populate the chat input', () => {
    render(<LivabilityWorkspace />);

    const promptBtn = screen.getByRole('button', {
      name: /Neighborhoods in South Delhi with best metro connectivity/i,
    });
    fireEvent.click(promptBtn);

    const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
    expect(chatInput.value).toBe('Neighborhoods in South Delhi with best metro connectivity');
  });

  it('handles sending a message with grounded advisor response and uses logo for assistant replies', async () => {
    vi.spyOn(api, 'sendLivabilityChatMessage').mockResolvedValue({
      reply: 'Verified healthcare facilities near Dwarka Sector 12: Venkateshwar Hospital at 510 m.',
      sources: ['OpenStreetMap Overpass API'],
      provider_configured: false,
      is_ai_generated: false,
      latitude: 28.5921,
      longitude: 77.0460,
    });

    render(<LivabilityWorkspace />);

    const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
    const sendBtn = screen.getByRole('button', { name: /Send message/i });

    fireEvent.change(chatInput, { target: { value: 'Best areas near green parks' } });
    fireEvent.click(sendBtn);

    // User message should appear
    expect(screen.getByText('Best areas near green parks')).toBeTruthy();
    // Input should be reset
    expect(chatInput.value).toBe('');

    await waitFor(() => {
      expect(screen.getByText(/Venkateshwar Hospital at 510 m/i)).toBeTruthy();
      expect(screen.getAllByText(/OpenStreetMap Overpass API/i).length).toBeGreaterThanOrEqual(1);
    });

    // Both initial and reply assistant messages should have the logo avatar
    const msgAvatars = screen.getAllByAltText('Neighborhood AI Advisor');
    expect(msgAvatars.length).toBe(2);
    expect(msgAvatars[1].getAttribute('src')).toBe('/neighborhood-ai-logo.svg');
  });

  it('allows searching for a locality and updates coordinate indicator and selected-locality card', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          lat: '28.5494',
          lon: '77.2001',
          display_name: 'Hauz Khas, South Delhi, Delhi, India',
        },
      ],
    });

    render(<LivabilityWorkspace />);

    const searchInput = screen.getByPlaceholderText(
      /Search neighborhood or locality \(e\.g\. Hauz Khas, Vasant Kunj, Rohini\)\.\.\./i
    );
    const searchBtn = screen.getByRole('button', { name: /Search/i });

    fireEvent.change(searchInput, { target: { value: 'Hauz Khas' } });
    expect(searchInput.value).toBe('Hauz Khas');

    fireEvent.click(searchBtn);

    await waitFor(() => {
      // Coordinate indicator should update to Hauz Khas coords
      expect(screen.getByText(/28.5494° N, 77.2001° E/i)).toBeTruthy();
      // Locality card should update
      expect(screen.getByText('Hauz Khas, South Delhi, Delhi, India')).toBeTruthy();
    });
  });

  it('updates coordinates and locality card on map click and reverse geocoding', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        display_name: 'Vasant Kunj, South West Delhi, Delhi, 110070, India',
        address: {
          suburb: 'Vasant Kunj',
          city: 'South West Delhi',
          state: 'Delhi',
          postcode: '110070',
        },
      }),
    });

    render(<LivabilityWorkspace />);

    // Simulate map click event handler registered on Leaflet map
    expect(mapClickHandlers.length).toBeGreaterThan(0);
    const clickHandler = mapClickHandlers[0];
    clickHandler({ latlng: { lat: 28.5245, lng: 77.1535 } });

    await waitFor(() => {
      expect(screen.getByText(/28.5245° N, 77.1535° E/i)).toBeTruthy();
      expect(screen.getAllByText(/Vasant Kunj/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('updates coordinates and locality card on marker dragend and reverse geocoding', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        display_name: 'Connaught Place, New Delhi, Delhi, India',
        address: {
          suburb: 'Connaught Place',
          city: 'New Delhi',
          state: 'Delhi',
        },
      }),
    });

    render(<LivabilityWorkspace />);

    expect(markerDragHandlers.length).toBeGreaterThan(0);
    const dragHandler = markerDragHandlers[0];
    currentMarkerPos = { lat: 28.6315, lng: 77.2167 };
    dragHandler();

    await waitFor(() => {
      expect(screen.getByText(/28.6315° N, 77.2167° E/i)).toBeTruthy();
      expect(screen.getAllByText(/Connaught Place/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('guarantees complete state isolation: Livability location changes never overwrite Single Inspection or Property Compare', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          lat: '28.5494',
          lon: '77.2001',
          display_name: 'Hauz Khas, South Delhi, Delhi, India',
        },
      ],
    });

    render(<App />);

    // 1. Opens in Livability by default
    expect(screen.getByText(/Regional Locality Explorer/i)).toBeTruthy();
    const livabilitySearchInput = screen.getByPlaceholderText(
      /Search neighborhood or locality \(e\.g\. Hauz Khas, Vasant Kunj, Rohini\)\.\.\./i
    );
    const searchBtn = screen.getByRole('button', { name: /Search/i });

    // Change location in Livability to Hauz Khas
    fireEvent.change(livabilitySearchInput, { target: { value: 'Hauz Khas' } });
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(screen.getByText('Hauz Khas, South Delhi, Delhi, India')).toBeTruthy();
      expect(screen.getByText(/28.5494° N, 77.2001° E/i)).toBeTruthy();
    });

    // 2. Switch to Property Inspection
    const inspectionTab = screen.getByRole('button', { name: /Property Inspection/i });
    fireEvent.click(inspectionTab);

    // Verify Single Inspection address was NOT overwritten by Livability's Hauz Khas
    expect(screen.getByDisplayValue('Dwarka Sector 12, New Delhi')).toBeTruthy();

    // 3. Switch to Property Compare mode
    const compareModeBtn = screen.getByRole('button', { name: /Property Compare/i });
    fireEvent.click(compareModeBtn);

    // Verify Compare Form retains its independent Property A and Property B addresses
    expect(screen.getByDisplayValue('Dwarka Sector 12, New Delhi')).toBeTruthy();
    expect(screen.getByDisplayValue('Connaught Place, New Delhi')).toBeTruthy();

    // 4. Switch back to Livability: Livability retains its chosen location
    const livabilityTab = screen.getByRole('button', { name: /Livability/i });
    fireEvent.click(livabilityTab);
    expect(screen.getByText('Hauz Khas, South Delhi, Delhi, India')).toBeTruthy();
    expect(screen.getByText(/28.5494° N, 77.2001° E/i)).toBeTruthy();
  });

  it('allows pressing Enter in search input to search without page reload', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          lat: '28.7041',
          lon: '77.1025',
          display_name: 'Rohini, North West Delhi, Delhi, India',
        },
      ],
    });

    render(<LivabilityWorkspace />);

    const searchInput = screen.getByPlaceholderText(
      /Search neighborhood or locality \(e\.g\. Hauz Khas, Vasant Kunj, Rohini\)\.\.\./i
    );

    fireEvent.change(searchInput, { target: { value: 'Rohini Sector 10' } });
    fireEvent.keyDown(searchInput, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText(/28.7041° N, 77.1025° E/i)).toBeTruthy();
      expect(screen.getByText('Rohini, North West Delhi, Delhi, India')).toBeTruthy();
    });
  });

  it('preserves selected coordinates and shows status note when reverse geocoding fails', async () => {
    // Reverse geocode rejects
    global.fetch = vi.fn().mockRejectedValue(new Error('Reverse geocode timeout'));

    render(<LivabilityWorkspace />);

    expect(mapClickHandlers.length).toBeGreaterThan(0);
    const clickHandler = mapClickHandlers[0];
    clickHandler({ latlng: { lat: 28.5355, lng: 77.3910 } });

    await waitFor(() => {
      // Coordinates are updated and preserved despite reverse geocoding failure
      expect(screen.getByText(/28.5355° N, 77.3910° E/i)).toBeTruthy();
      expect(screen.getByText(/Coords Preserved/i)).toBeTruthy();
      expect(screen.getAllByText(/Reverse geocoding service unavailable\. Selected coordinates are preserved\./i).length).toBeGreaterThan(0);
    });
  });

  it('preserves user query and does not corrupt marker/coordinates when search fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [], // No results
    });

    render(<LivabilityWorkspace />);

    const searchInput = screen.getByPlaceholderText(
      /Search neighborhood or locality \(e\.g\. Hauz Khas, Vasant Kunj, Rohini\)\.\.\./i
    );
    const searchBtn = screen.getByRole('button', { name: /Search/i });

    fireEvent.change(searchInput, { target: { value: 'Nonexistent Place ABC 12345' } });
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(screen.getAllByText(/No matching locations found for "Nonexistent Place ABC 12345"/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Search Error/i)).toBeTruthy();
    });

    // Query text remains preserved in the input
    expect(searchInput.value).toBe('Nonexistent Place ABC 12345');
    // Default coordinates remain preserved
    expect(screen.getByText(/28.5921° N, 77.0460° E/i)).toBeTruthy();
  });

  it('restores the last selected Livability location from localStorage after reload', () => {
    // Seed localStorage with a saved Livability location
    const savedLoc = {
      latitude: 28.4595,
      longitude: 77.0266,
      address: 'Cyber City, Gurugram, Haryana, India',
    };
    window.localStorage.setItem('nivas_livability_location', JSON.stringify(savedLoc));
    window.localStorage.setItem('nivas_app_section', 'livability');

    render(<App />);

    // Active pinpoint and selected-locality card should reflect the restored location
    expect(screen.getByText(/28.4595° N, 77.0266° E/i)).toBeTruthy();
    expect(screen.getByText('Cyber City, Gurugram, Haryana, India')).toBeTruthy();
  });

  it('guarantees complete bidirectional isolation: modifying Single Inspection or Compare does not affect Livability', async () => {
    render(<App />);

    // 1. In Livability by default
    expect(screen.getByText(/Regional Locality Explorer/i)).toBeTruthy();
    expect(screen.getByText(/Dwarka Sector 12, South West Delhi, Delhi/i)).toBeTruthy();

    // 2. Switch to Property Inspection (Single Inspection)
    const inspectionTab = screen.getByRole('button', { name: /Property Inspection/i });
    fireEvent.click(inspectionTab);

    // Modify Single Inspection address
    const singleAddressInput = screen.getByDisplayValue('Dwarka Sector 12, New Delhi');
    fireEvent.change(singleAddressInput, { target: { value: 'Indirapuram, Ghaziabad' } });
    expect(singleAddressInput.value).toBe('Indirapuram, Ghaziabad');

    // 3. Switch to Property Compare mode
    const compareModeBtn = screen.getByRole('button', { name: /Property Compare/i });
    fireEvent.click(compareModeBtn);

    // Modify Property A and Property B in Compare Form
    const propAInput = screen.getByDisplayValue('Dwarka Sector 12, New Delhi');
    fireEvent.change(propAInput, { target: { value: 'Saket, New Delhi' } });
    expect(propAInput.value).toBe('Saket, New Delhi');

    const propBInput = screen.getByDisplayValue('Connaught Place, New Delhi');
    fireEvent.change(propBInput, { target: { value: 'Noida Sector 18, Uttar Pradesh' } });
    expect(propBInput.value).toBe('Noida Sector 18, Uttar Pradesh');

    // 4. Switch back to Livability: Livability remains untouched
    const livabilityTab = screen.getByRole('button', { name: /Livability/i });
    fireEvent.click(livabilityTab);

    expect(screen.getByText(/Dwarka Sector 12, South West Delhi, Delhi/i)).toBeTruthy();
    expect(screen.getByText(/28.5921° N, 77.0460° E/i)).toBeTruthy();
  });

  it('persists active tab across reloads and defaults to livability on initial opening', () => {
    // 1. Initial fresh open: defaults to livability
    const { unmount } = render(<App />);
    expect(screen.getByText(/Neighborhood Livability Intelligence/i)).toBeTruthy();

    // Switch to Property Inspection
    const inspectionTab = screen.getByRole('button', { name: /Property Inspection/i });
    fireEvent.click(inspectionTab);
    expect(screen.getByText(/Inspection Workflow Mode/i)).toBeTruthy();

    // Verify localStorage was updated
    expect(window.localStorage.getItem('nivas_app_section')).toBe('inspection');

    // Unmount (simulating page close/refresh)
    unmount();

    // Re-mount (simulating reload)
    const { unmount: unmount2 } = render(<App />);
    // Should stay on Property Inspection
    expect(screen.getByText(/Inspection Workflow Mode/i)).toBeTruthy();

    // Switch back to Livability
    const livabilityTab = screen.getByRole('button', { name: /Livability/i });
    fireEvent.click(livabilityTab);
    expect(screen.getByText(/Neighborhood Livability Intelligence/i)).toBeTruthy();
    expect(window.localStorage.getItem('nivas_app_section')).toBe('livability');

    unmount2();

    // Re-mount again (simulating reload on Livability)
    render(<App />);
    expect(screen.getByText(/Neighborhood Livability Intelligence/i)).toBeTruthy();
  });
});

describe('Livability Location Data Foundation', () => {
  let originalFetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    mapClickHandlers = [];
    markerDragHandlers = [];
    currentMarkerPos = { lat: 28.5921, lng: 77.0460 };
    createdMarkers = [];
    mockStopPropagation = vi.fn();
    window.localStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders loading indicators during data fetch and succeeds with active infrastructure & AQI data', async () => {
    const mockData = {
      latitude: 28.5921,
      longitude: 77.0460,
      address: 'Dwarka Sector 12, South West Delhi, Delhi',
      locality: 'Dwarka Sector 12',
      retrieved_at: '2026-10-10T12:00:00Z',
      infrastructure: {
        status: 'active',
        source: 'OpenStreetMap Overpass API',
        schools_count: 8,
        hospitals_count: 4,
        clinics_count: 2,
        pharmacies_count: 5,
        police_stations_count: 1,
        fire_stations_count: 1,
        public_transport_count: 12,
        railway_stations_count: 2,
        major_roads_count: 7,
        nearby_places: ['Dwarka Sector 12 Metro Station', 'City Centre Mall', 'Venkateshwar Hospital'],
        total_facilities: 35,
      },
      air_quality: {
        status: 'active',
        source: 'AQICN WAQI API',
        scale: '0-500 (US EPA / CPCB)',
        aqi_value: 128.0,
        category: 'Moderate',
        station_name: 'Dwarka Sector 8 Station',
        environmental_score: 55.0,
      },
      environmental_hazards: {
        status: 'data_not_configured',
        message: 'Real-time environmental hazard sensor network not configured for this region',
      },
    };

    const fetchSpy = vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockData);

    render(<LivabilityWorkspace />);

    // Initial check: header exists
    expect(screen.getByText(/Verified Location Data Foundation/i)).toBeTruthy();

    // Await data resolution
    await waitFor(() => {
      expect(screen.getByText('Verified Telemetry')).toBeTruthy();
    });

    // Infrastructure metrics rendered
    expect(screen.getByText('Civic Infrastructure')).toBeTruthy();
    expect(screen.getByText('8')).toBeTruthy(); // Schools
    expect(screen.getByText('11')).toBeTruthy(); // Healthcare: 4 + 2 + 5 = 11
    expect(screen.getByText('14')).toBeTruthy(); // Transit & Metro: 12 + 2 = 14
    expect(screen.getByText('7')).toBeTruthy(); // Arterial Roads

    // Mapped landmarks
    expect(screen.getByText('Dwarka Sector 12 Metro Station')).toBeTruthy();
    expect(screen.getByText('City Centre Mall')).toBeTruthy();

    // Air Quality
    expect(screen.getByText('128')).toBeTruthy();
    expect(screen.getByText('AQI (Moderate)')).toBeTruthy();
    expect(screen.getByText(/Monitoring Station: Dwarka Sector 8 Station/i)).toBeTruthy();
    expect(screen.getByText(/Hazards: Real-time environmental hazard sensor network not configured/i)).toBeTruthy();
  });

  it('renders transparent messaging when air quality provider is not configured without fabricating numbers', async () => {
    const mockData = {
      latitude: 28.5921,
      longitude: 77.0460,
      address: 'Dwarka Sector 12, South West Delhi, Delhi',
      locality: 'Dwarka Sector 12',
      retrieved_at: '2026-10-10T12:00:00Z',
      infrastructure: {
        status: 'active',
        source: 'OpenStreetMap Overpass API',
        schools_count: 2,
        hospitals_count: 1,
        clinics_count: 0,
        pharmacies_count: 1,
        police_stations_count: 0,
        fire_stations_count: 0,
        public_transport_count: 3,
        railway_stations_count: 0,
        major_roads_count: 2,
        nearby_places: ['Local Park'],
        total_facilities: 9,
      },
      air_quality: {
        status: 'provider_not_configured',
        source: null,
        aqi_value: null,
        error_message: 'Air quality API key is not configured in backend environment.',
      },
      environmental_hazards: {
        status: 'data_not_configured',
        message: 'Sensor network not configured',
      },
    };

    vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockData);

    render(<LivabilityWorkspace />);

    await waitFor(() => {
      expect(
        screen.getByText(/Air quality API key \(OpenWeather or AQICN\) is not configured in backend environment/i)
      ).toBeTruthy();
    });

    // Zero fake numbers for AQI
    expect(screen.queryByText('AQI (Good)')).toBeNull();
    expect(screen.queryByText('AQI (Moderate)')).toBeNull();
  });

  it('distinguishes zero recorded facilities from fetch errors', async () => {
    const mockData = {
      latitude: 28.0,
      longitude: 77.0,
      address: 'Remote Area',
      locality: 'Remote Area',
      retrieved_at: '2026-10-10T12:00:00Z',
      infrastructure: {
        status: 'empty',
        source: 'OpenStreetMap Overpass API',
        schools_count: 0,
        hospitals_count: 0,
        clinics_count: 0,
        pharmacies_count: 0,
        police_stations_count: 0,
        fire_stations_count: 0,
        public_transport_count: 0,
        railway_stations_count: 0,
        major_roads_count: 0,
        nearby_places: [],
        total_facilities: 0,
      },
      air_quality: {
        status: 'data_unavailable',
        error_message: 'No active atmospheric monitoring stations within range (50 km).',
      },
      environmental_hazards: {
        status: 'data_not_configured',
        message: 'Sensor network not configured',
      },
    };

    vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockData);

    render(<LivabilityWorkspace />);

    await waitFor(() => {
      expect(
        screen.getByText(/0 civic amenities recorded within search radius in OpenStreetMap/i)
      ).toBeTruthy();
      expect(
        screen.getByText(/No active atmospheric monitoring stations within range \(50 km\)/i)
      ).toBeTruthy();
    });
  });

  it('handles network failure gracefully without resetting coordinates or crashing the map', async () => {
    vi.spyOn(api, 'fetchLivabilityLocationData').mockRejectedValue(new Error('Network connection timeout'));

    render(<LivabilityWorkspace />);

    await waitFor(() => {
      expect(screen.getByText('Sync Error')).toBeTruthy();
      expect(screen.getByText(/Network connection timeout — Coordinates and map navigation remain active/i)).toBeTruthy();
    });

    // Coordinates and locality card remain fully visible and intact
    expect(screen.getByText(/28.5921° N, 77.0460° E/i)).toBeTruthy();
    expect(screen.getByText(/Dwarka Sector 12, South West Delhi, Delhi/i)).toBeTruthy();
  });

  it('discards stale out-of-order responses when coordinates change rapidly (race condition prevention)', async () => {
    let resolveFirst;
    const firstPromise = new Promise((resolve) => {
      resolveFirst = resolve;
    });

    let resolveSecond;
    const secondPromise = new Promise((resolve) => {
      resolveSecond = resolve;
    });

    const fetchSpy = vi.spyOn(api, 'fetchLivabilityLocationData')
      .mockImplementationOnce(() => firstPromise)
      .mockImplementationOnce(() => secondPromise);

    const { rerender } = render(
      <LivabilityWorkspace
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Location A' }}
      />
    );

    // Rapid change to Location B before Location A resolves
    rerender(
      <LivabilityWorkspace
        location={{ latitude: 28.7041, longitude: 77.1025, address: 'Location B' }}
      />
    );

    // Location B resolves first
    resolveSecond({
      latitude: 28.7041,
      longitude: 77.1025,
      address: 'Location B',
      locality: 'Location B',
      retrieved_at: '2026-10-10T12:00:02Z',
      infrastructure: {
        status: 'active',
        source: 'OpenStreetMap Overpass API',
        schools_count: 99,
        hospitals_count: 0,
        clinics_count: 0,
        pharmacies_count: 0,
        police_stations_count: 0,
        fire_stations_count: 0,
        public_transport_count: 0,
        railway_stations_count: 0,
        major_roads_count: 0,
        nearby_places: ['Location B Landmark'],
        total_facilities: 99,
      },
      air_quality: { status: 'provider_not_configured' },
      environmental_hazards: { status: 'data_not_configured', message: 'None' },
    });

    await waitFor(() => {
      expect(screen.getByText('99')).toBeTruthy();
      expect(screen.getByText('Location B Landmark')).toBeTruthy();
    });

    // Now Location A (stale) resolves afterwards
    resolveFirst({
      latitude: 28.5921,
      longitude: 77.0460,
      address: 'Location A',
      locality: 'Location A',
      retrieved_at: '2026-10-10T12:00:01Z',
      infrastructure: {
        status: 'active',
        source: 'OpenStreetMap Overpass API',
        schools_count: 11,
        hospitals_count: 0,
        clinics_count: 0,
        pharmacies_count: 0,
        police_stations_count: 0,
        fire_stations_count: 0,
        public_transport_count: 0,
        railway_stations_count: 0,
        major_roads_count: 0,
        nearby_places: ['Stale Location A Landmark'],
        total_facilities: 11,
      },
      air_quality: { status: 'provider_not_configured' },
      environmental_hazards: { status: 'data_not_configured', message: 'None' },
    });

    // Wait a brief tick to ensure Location A's resolution is processed
    await new Promise((r) => setTimeout(r, 50));

    // Stale Location A data must NOT overwrite Location B data!
    expect(screen.getByText('99')).toBeTruthy();
    expect(screen.getByText('Location B Landmark')).toBeTruthy();
    expect(screen.queryByText('Stale Location A Landmark')).toBeNull();
  });

  it('renders verified infrastructure markers using actual provider coordinates and displays legend', async () => {
    const mockData = {
      latitude: 28.5921,
      longitude: 77.0460,
      address: 'Dwarka Sector 12, South West Delhi, Delhi',
      locality: 'Dwarka Sector 12',
      retrieved_at: '2026-10-10T12:00:00Z',
      infrastructure: {
        status: 'active',
        source: 'OpenStreetMap Overpass API',
        schools_count: 1,
        hospitals_count: 1,
        clinics_count: 0,
        pharmacies_count: 0,
        police_stations_count: 0,
        fire_stations_count: 0,
        public_transport_count: 0,
        railway_stations_count: 1,
        major_roads_count: 0,
        nearby_places: ['DPS Dwarka', 'Venkateshwar Hospital', 'Dwarka Sec 12 Metro'],
        total_facilities: 3,
        facilities: [
          {
            id: '101',
            name: 'DPS Dwarka',
            category: 'school',
            category_label: 'School',
            latitude: 28.591234,
            longitude: 77.045678,
            source: 'OpenStreetMap',
          },
          {
            id: '202',
            name: 'Venkateshwar Hospital',
            category: 'hospital',
            category_label: 'Hospital',
            latitude: 28.589101,
            longitude: 77.042233,
            source: 'OpenStreetMap',
          },
          {
            id: '303',
            name: 'Dwarka Sec 12 Metro',
            category: 'railway',
            category_label: 'Metro Station',
            latitude: 28.592200,
            longitude: 77.046100,
            source: 'OpenStreetMap',
          },
        ],
      },
      air_quality: {
        status: 'active',
        source: 'AQICN WAQI API',
        aqi_value: 135.0,
        category: 'Unhealthy for Sensitive Groups',
        station_name: 'Dwarka Sector 8 Station',
      },
      environmental_hazards: {
        status: 'data_not_configured',
        message: 'Sensor network not configured',
      },
    };

    vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockData);

    render(<LivabilityWorkspace />);

    await waitFor(() => {
      expect(screen.getByText(/Verified Map Insights Legend/i)).toBeTruthy();
      expect(screen.getByText(/3 places shown/i)).toBeTruthy();
    });

    // Check legend items
    expect(screen.getByText('Schools (1)')).toBeTruthy();
    expect(screen.getByText('Healthcare (1)')).toBeTruthy();
    expect(screen.getByText('Transit & Metro (1)')).toBeTruthy();

    // Verify overlay markers created with exact provider coordinates
    const schoolMarker = createdMarkers.find(
      (m) => m.coords && m.coords[0] === 28.591234 && m.coords[1] === 77.045678
    );
    expect(schoolMarker).toBeTruthy();
    expect(schoolMarker.popupContent).toContain('DPS Dwarka');
    expect(schoolMarker.popupContent).toContain('OpenStreetMap');

    const hospitalMarker = createdMarkers.find(
      (m) => m.coords && m.coords[0] === 28.589101 && m.coords[1] === 77.042233
    );
    expect(hospitalMarker).toBeTruthy();
    expect(hospitalMarker.popupContent).toContain('Venkateshwar Hospital');

    // Verify air quality retrieval timestamp
    expect(screen.getByText(/Telemetry Retrieved: 12:00:00 UTC/i)).toBeTruthy();
  });

  it('clicking an infrastructure place marker does NOT change the exploration pin coordinates', async () => {
    const mockData = {
      latitude: 28.5921,
      longitude: 77.0460,
      address: 'Dwarka Sector 12, South West Delhi, Delhi',
      locality: 'Dwarka Sector 12',
      retrieved_at: '2026-10-10T12:00:00Z',
      infrastructure: {
        status: 'active',
        source: 'OpenStreetMap Overpass API',
        schools_count: 1,
        hospitals_count: 0,
        clinics_count: 0,
        pharmacies_count: 0,
        police_stations_count: 0,
        fire_stations_count: 0,
        public_transport_count: 0,
        railway_stations_count: 0,
        major_roads_count: 0,
        nearby_places: ['DPS Dwarka'],
        total_facilities: 1,
        facilities: [
          {
            id: '101',
            name: 'DPS Dwarka',
            category: 'school',
            category_label: 'School',
            latitude: 28.591234,
            longitude: 77.045678,
            source: 'OpenStreetMap',
          },
        ],
      },
      air_quality: { status: 'provider_not_configured' },
      environmental_hazards: { status: 'data_not_configured', message: 'None' },
    };

    vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockData);

    render(<LivabilityWorkspace />);

    await waitFor(() => {
      expect(screen.getByText(/Schools \(1\)/i)).toBeTruthy();
    });

    const schoolMarker = createdMarkers.find(
      (m) => m.coords && m.coords[0] === 28.591234
    );
    expect(schoolMarker).toBeTruthy();
    expect(schoolMarker.clickHandlers.length).toBeGreaterThanOrEqual(1);

    // Simulate clicking the school marker
    const stopPropagationMock = vi.fn();
    schoolMarker.clickHandlers[0]({
      originalEvent: { stopPropagation: stopPropagationMock },
    });

    // stopPropagation was called
    expect(mockStopPropagation).toHaveBeenCalled();

    // Exploration pin coordinates remain Dwarka Sector 12 (NOT overwritten by school coords)
    expect(screen.getByText(/28.5921° N, 77.0460° E/i)).toBeTruthy();
    expect(screen.getByText(/Dwarka Sector 12, South West Delhi, Delhi/i)).toBeTruthy();
  });

  it('allows filtering categories in legend to reduce visual clutter', async () => {
    const mockData = {
      latitude: 28.5921,
      longitude: 77.0460,
      address: 'Dwarka Sector 12, South West Delhi, Delhi',
      locality: 'Dwarka Sector 12',
      retrieved_at: '2026-10-10T12:00:00Z',
      infrastructure: {
        status: 'active',
        source: 'OpenStreetMap Overpass API',
        schools_count: 1,
        hospitals_count: 1,
        clinics_count: 0,
        pharmacies_count: 0,
        police_stations_count: 0,
        fire_stations_count: 0,
        public_transport_count: 0,
        railway_stations_count: 0,
        major_roads_count: 0,
        nearby_places: ['DPS Dwarka', 'Venkateshwar Hospital'],
        total_facilities: 2,
        facilities: [
          {
            id: '101',
            name: 'DPS Dwarka',
            category: 'school',
            category_label: 'School',
            latitude: 28.591234,
            longitude: 77.045678,
            source: 'OpenStreetMap',
          },
          {
            id: '202',
            name: 'Venkateshwar Hospital',
            category: 'hospital',
            category_label: 'Hospital',
            latitude: 28.589101,
            longitude: 77.042233,
            source: 'OpenStreetMap',
          },
        ],
      },
      air_quality: { status: 'provider_not_configured' },
      environmental_hazards: { status: 'data_not_configured', message: 'None' },
    };

    vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockData);

    render(<LivabilityWorkspace />);

    await waitFor(() => {
      expect(screen.getByText(/2 places shown/i)).toBeTruthy();
    });

    // Click "Schools (1)" filter button
    const schoolBtn = screen.getByRole('button', { name: /Schools \(1\)/i });
    fireEvent.click(schoolBtn);

    // Subtitle updates to 1 place shown
    expect(screen.getByText(/1 place shown/i)).toBeTruthy();

    // Click "All (2)" filter button
    const allBtn = screen.getByRole('button', { name: /All \(2\)/i });
    fireEvent.click(allBtn);

    // Restores 2 places shown
    expect(screen.getByText(/2 places shown/i)).toBeTruthy();
  });

  describe('Step 3.3: Neighborhood Context, Proximity Evidence, and Disclosures', () => {
    it('accurately computes Haversine distances and handles edge cases', () => {
      // Distance between Connaught Place (28.6315, 77.2167) and India Gate (28.6129, 77.2295)
      const dist = calculateHaversineDistanceKm(28.6315, 77.2167, 28.6129, 77.2295);
      expect(dist).toBeGreaterThan(2.3);
      expect(dist).toBeLessThan(2.5);

      // Same coordinate returns 0
      expect(calculateHaversineDistanceKm(28.5921, 77.0460, 28.5921, 77.0460)).toBe(0);

      // Missing or invalid coordinates return null
      expect(calculateHaversineDistanceKm(null, 77.0460, 28.5921, 77.0460)).toBeNull();
      expect(calculateHaversineDistanceKm(28.5921, undefined, 28.5921, 77.0460)).toBeNull();
      expect(calculateHaversineDistanceKm(NaN, 77.0460, 28.5921, 77.0460)).toBeNull();
      expect(calculateHaversineDistanceKm('28.5', 77.0460, 28.5921, 77.0460)).toBeNull();
    });

    it('formats facility distance cleanly into meters and kilometers', () => {
      expect(formatFacilityDistance(0.35)).toBe('350 m');
      expect(formatFacilityDistance(0.08)).toBe('80 m');
      expect(formatFacilityDistance(1.2)).toBe('1.20 km');
      expect(formatFacilityDistance(2.456)).toBe('2.46 km');
      expect(formatFacilityDistance(null)).toBe('Distance unavailable');
      expect(formatFacilityDistance(undefined)).toBe('Distance unavailable');
      expect(formatFacilityDistance(NaN)).toBe('Distance unavailable');
    });

    it('renders the facility evidence directory grouped by category with search radius and distance', async () => {
      const mockData = {
        latitude: 28.5921,
        longitude: 77.0460,
        address: 'Dwarka Sector 12, South West Delhi, Delhi',
        locality: 'Dwarka Sector 12',
        retrieved_at: '2026-10-10T12:00:00Z',
        infrastructure: {
          status: 'active',
          source: 'OpenStreetMap Overpass API',
          search_radius_meters: 1200,
          railway_search_radius_meters: 2000,
          schools_count: 1,
          hospitals_count: 1,
          clinics_count: 0,
          pharmacies_count: 0,
          police_stations_count: 0,
          fire_stations_count: 0,
          public_transport_count: 0,
          railway_stations_count: 1,
          major_roads_count: 0,
          nearby_places: ['DPS Dwarka', 'Venkateshwar Hospital', 'Dwarka Sector 12 Metro'],
          total_facilities: 3,
          facilities: [
            {
              id: 'fac-1',
              name: 'DPS Dwarka',
              category: 'school',
              category_label: 'School',
              latitude: 28.5912,
              longitude: 77.0456,
              source: 'OpenStreetMap',
            },
            {
              id: 'fac-2',
              name: 'Venkateshwar Hospital',
              category: 'hospital',
              category_label: 'Hospital',
              latitude: 28.5891,
              longitude: 77.0422,
              source: 'OpenStreetMap',
            },
            {
              id: 'fac-3',
              name: 'Dwarka Sector 12 Metro Station',
              category: 'railway',
              category_label: 'Metro Station',
              latitude: 28.5930,
              longitude: 77.0470,
              source: 'OpenStreetMap',
            },
          ],
        },
        air_quality: {
          status: 'active',
          source: 'CPCB CAAQMS / OpenWeather',
          aqi_value: 172,
          category: 'Moderate',
          station_name: 'Dwarka Sector 8 Station',
          environmental_score: 58,
        },
        environmental_hazards: { status: 'data_not_configured', message: 'No flood risk sensors configured' },
      };

      vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockData);

      render(<LivabilityWorkspace />);

      await waitFor(() => {
        expect(screen.getByText(/Verified Nearby Facilities & Proximity Evidence/i)).toBeTruthy();
      });

      // Search radius disclosure visible
      expect(screen.getByText(/Civic amenities within 1.2 km \(2.0 km for rail\/metro\) of selected pin/i)).toBeTruthy();

      // Check category groups
      expect(screen.getByTestId('facility-group-school')).toBeTruthy();
      expect(screen.getByTestId('facility-group-healthcare')).toBeTruthy();
      expect(screen.getByTestId('facility-group-transit')).toBeTruthy();

      // Facility items rendered with names and calculated distances
      expect(screen.getAllByText('DPS Dwarka').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Venkateshwar Hospital').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Dwarka Sector 12 Metro Station')).toBeTruthy();

      // Data provenance & disclosures section present
      expect(screen.getByText(/Data Provenance & Calculation Methodology/i)).toBeTruthy();
      expect(screen.getByText(/OpenStreetMap \(OSM\) via Overpass API/i)).toBeTruthy();
      expect(screen.getAllByText(/Haversine formula/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Zero Inference \/ Risk Disclaimer:/i)).toBeTruthy();
    });

    it('selecting a facility in directory opens its marker popup without moving exploration pin', async () => {
      const mockData = {
        latitude: 28.5921,
        longitude: 77.0460,
        address: 'Dwarka Sector 12, South West Delhi, Delhi',
        locality: 'Dwarka Sector 12',
        retrieved_at: '2026-10-10T12:00:00Z',
        infrastructure: {
          status: 'active',
          source: 'OpenStreetMap Overpass API',
          search_radius_meters: 1200,
          railway_search_radius_meters: 2000,
          schools_count: 1,
          hospitals_count: 0,
          clinics_count: 0,
          pharmacies_count: 0,
          police_stations_count: 0,
          fire_stations_count: 0,
          public_transport_count: 0,
          railway_stations_count: 0,
          major_roads_count: 0,
          nearby_places: ['DPS Dwarka'],
          total_facilities: 1,
          facilities: [
            {
              id: 'fac-99',
              name: 'DPS Dwarka',
              category: 'school',
              category_label: 'School',
              latitude: 28.591234,
              longitude: 77.045678,
              source: 'OpenStreetMap',
            },
          ],
        },
        air_quality: { status: 'provider_not_configured' },
        environmental_hazards: { status: 'data_not_configured', message: 'None' },
      };

      vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockData);

      render(<LivabilityWorkspace />);

      await waitFor(() => {
        expect(screen.getByTestId('facility-card-fac-99')).toBeTruthy();
      });

      const matchingMarkers = createdMarkers.filter(
        (m) => m.coords && m.coords[0] === 28.591234
      );
      const facilityMarker = matchingMarkers[matchingMarkers.length - 1];
      expect(facilityMarker).toBeTruthy();

      // Click "View Marker" button for DPS Dwarka
      const viewBtn = screen.getByRole('button', { name: /View DPS Dwarka on map/i });
      fireEvent.click(viewBtn);

      // Marker openPopup was called
      await waitFor(() => {
        expect(facilityMarker.openPopup).toHaveBeenCalled();
      });

      // Exploration coordinates remain unchanged (NOT moved to DPS coords)
      expect(screen.getByText(/28.5921° N, 77.0460° E/i)).toBeTruthy();
      expect(screen.getByText(/Dwarka Sector 12, South West Delhi, Delhi/i)).toBeTruthy();
    });

    it('displays distinct empty and failed telemetry states', async () => {
      const mockEmptyData = {
        latitude: 28.5921,
        longitude: 77.0460,
        address: 'Remote Farm, Outskirts',
        locality: 'Outskirts',
        retrieved_at: '2026-10-10T12:00:00Z',
        infrastructure: {
          status: 'empty',
          source: 'OpenStreetMap Overpass API',
          search_radius_meters: 1200,
          railway_search_radius_meters: 2000,
          schools_count: 0,
          hospitals_count: 0,
          clinics_count: 0,
          pharmacies_count: 0,
          police_stations_count: 0,
          fire_stations_count: 0,
          public_transport_count: 0,
          railway_stations_count: 0,
          major_roads_count: 0,
          nearby_places: [],
          total_facilities: 0,
          facilities: [],
        },
        air_quality: { status: 'provider_not_configured' },
        environmental_hazards: { status: 'data_not_configured', message: 'Sensor network not configured' },
      };

      vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockEmptyData);

      render(<LivabilityWorkspace />);

      await waitFor(() => {
        expect(screen.getByText(/0 civic amenities recorded within search radius in OpenStreetMap/i)).toBeTruthy();
      });

      // Clear empty state notice in directory
      expect(screen.getByText(/No mapped civic amenities found within search radius/i)).toBeTruthy();
    });
  });

  describe('Step 4.1: Grounded Neighborhood AI Advisor with Real Location Telemetry', () => {
    it('answers user questions using grounded location telemetry and displays sources and provenance tag', async () => {
      const mockChatReply = {
        reply: 'Verified healthcare facilities within 1.2 km of Dwarka Sector 12: Venkateshwar Hospital at ~510 m away.',
        sources: ['OpenStreetMap Overpass API'],
        provider_configured: false,
        is_ai_generated: false,
        latitude: 28.5921,
        longitude: 77.0460,
        address: 'Dwarka Sector 12, South West Delhi, Delhi',
        retrieved_at: '2026-10-10T12:00:00Z',
      };

      const sendChatSpy = vi.spyOn(api, 'sendLivabilityChatMessage').mockResolvedValue(mockChatReply);

      render(<LivabilityWorkspace />);

      const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
      const sendBtn = screen.getByRole('button', { name: /Send message/i });

      fireEvent.change(chatInput, { target: { value: 'What healthcare facilities are nearby?' } });
      fireEvent.click(sendBtn);

      expect(sendChatSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          query: 'What healthcare facilities are nearby?',
          latitude: 28.5921,
          longitude: 77.0460,
        }),
        expect.anything()
      );

      await waitFor(() => {
        expect(screen.getByText(/Venkateshwar Hospital at ~510 m away/i)).toBeTruthy();
        expect(screen.getAllByText(/OpenStreetMap Overpass API/i).length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText(/Telemetry Grounded \(AI Unconfigured\)/i).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('honestly reports unconfigured AI provider without simulating fake model answers', async () => {
      const mockUnconfiguredReply = {
        reply: '[AI Provider Not Configured] No generative AI provider (GEMINI_API_KEY or OPENAI_API_KEY) is configured in backend environment. Real AI model generation is unavailable.\n\nVerified location telemetry: Nearest mapped transit stop is Dwarka Sector 12 Metro (~140 m).',
        sources: ['OpenStreetMap Overpass API'],
        provider_configured: false,
        provider_name: null,
        is_ai_generated: false,
        latitude: 28.5921,
        longitude: 77.0460,
        address: 'Dwarka Sector 12',
        retrieved_at: '2026-10-10T12:00:00Z',
      };

      vi.spyOn(api, 'sendLivabilityChatMessage').mockResolvedValue(mockUnconfiguredReply);

      render(<LivabilityWorkspace />);

      const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
      const sendBtn = screen.getByRole('button', { name: /Send message/i });

      fireEvent.change(chatInput, { target: { value: 'How far away is the nearest mapped transit facility?' } });
      fireEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByText(/AI Provider Not Configured/i)).toBeTruthy();
        expect(screen.getByText(/Real AI model generation is unavailable/i)).toBeTruthy();
        expect(screen.getByText(/Dwarka Sector 12 Metro/i)).toBeTruthy();
        expect(screen.getAllByText(/Telemetry Grounded \(AI Unconfigured\)/i).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('handles missing telemetry and empty facilities honestly', async () => {
      const mockMissingReply = {
        reply: 'There are 0 healthcare facilities mapped within 1.2 km of Outskirts in OpenStreetMap. Unmapped nodes do not confirm absence of facilities.',
        sources: ['OpenStreetMap Overpass API'],
        provider_configured: false,
        is_ai_generated: false,
        latitude: 28.5921,
        longitude: 77.0460,
        address: 'Outskirts',
        retrieved_at: '2026-10-10T12:00:00Z',
      };

      vi.spyOn(api, 'sendLivabilityChatMessage').mockResolvedValue(mockMissingReply);

      render(<LivabilityWorkspace />);

      const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
      const sendBtn = screen.getByRole('button', { name: /Send message/i });

      fireEvent.change(chatInput, { target: { value: 'What information is missing for this locality?' } });
      fireEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByText(/0 healthcare facilities mapped within 1.2 km/i)).toBeTruthy();
        expect(screen.getByText(/Unmapped nodes do not confirm absence of facilities/i)).toBeTruthy();
      });
    });

    it('handles backend failures gracefully with error bubble without breaking the map', async () => {
      vi.spyOn(api, 'sendLivabilityChatMessage').mockRejectedValue(new Error('Backend connection refused'));

      render(<LivabilityWorkspace />);

      const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
      const sendBtn = screen.getByRole('button', { name: /Send message/i });

      fireEvent.change(chatInput, { target: { value: 'What infrastructure is available?' } });
      fireEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByText(/Unable to retrieve advisor response: Backend connection refused/i)).toBeTruthy();
      });

      // Coordinates and map navigation remain active
      expect(screen.getByText(/28.5921° N, 77.0460° E/i)).toBeTruthy();
    });

    it('validates input and disables submission for empty or whitespace-only queries', () => {
      const sendSpy = vi.spyOn(api, 'sendLivabilityChatMessage');

      render(<LivabilityWorkspace />);

      const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
      const sendBtn = screen.getByRole('button', { name: /Send message/i });

      // Button is initially disabled when input is empty
      expect(sendBtn.hasAttribute('disabled')).toBe(true);

      // Whitespace only
      fireEvent.change(chatInput, { target: { value: '   ' } });
      expect(sendBtn.hasAttribute('disabled')).toBe(true);

      fireEvent.click(sendBtn);
      expect(sendSpy).not.toHaveBeenCalled();
    });

    it('aborts pending chat request and displays location switch notice when selected location changes', async () => {
      let capturedSignal;
      vi.spyOn(api, 'sendLivabilityChatMessage').mockImplementation(({ query }, signal) => {
        capturedSignal = signal;
        return new Promise((resolve) => {
          // Artificial delay
          setTimeout(() => {
            resolve({
              reply: 'Stale Dwarka reply',
              sources: [],
              provider_configured: false,
              is_ai_generated: false,
            });
          }, 300);
        });
      });

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          display_name: 'Vasant Kunj, South West Delhi, Delhi, India',
          address: { suburb: 'Vasant Kunj' },
        }),
      });

      render(<LivabilityWorkspace />);

      const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
      const sendBtn = screen.getByRole('button', { name: /Send message/i });

      fireEvent.change(chatInput, { target: { value: 'What schools are nearby?' } });
      fireEvent.click(sendBtn);

      // Loading row appears
      expect(screen.getByTestId('chat-loading-row')).toBeTruthy();

      // Location changes via map click while request is in flight
      const clickHandler = mapClickHandlers[0];
      clickHandler({ latlng: { lat: 28.5245, lng: 77.1535 } });

      // Signal was aborted once location change processed
      await waitFor(() => {
        expect(capturedSignal?.aborted).toBe(true);
      });

      // System notice for location update appears in chat
      await waitFor(() => {
        expect(screen.getByTestId('chat-system-notice')).toBeTruthy();
      });

      // Stale response is NOT displayed
      expect(screen.queryByText('Stale Dwarka reply')).toBeNull();
    });

    it('minimizes floating chat panel to launcher and preserves conversation state when reopened', async () => {
      render(<LivabilityWorkspace />);

      // Initially open
      expect(screen.getByTestId('floating-advisor-panel')).toBeTruthy();
      expect(screen.getByText(/Welcome to the NIVAS Neighborhood AI Advisor/i)).toBeTruthy();

      // Minimize the advisor panel
      const minimizeBtn = screen.getByTestId('minimize-advisor-btn');
      fireEvent.click(minimizeBtn);

      // Panel is closed, launcher button is visible in bottom-right
      expect(screen.queryByTestId('floating-advisor-panel')).toBeNull();
      const launcherBtn = screen.getByTestId('advisor-launcher-btn');
      expect(launcherBtn).toBeTruthy();
      expect(screen.getByText(/Neighborhood AI Advisor/i)).toBeTruthy();

      // Click launcher to reopen
      fireEvent.click(launcherBtn);

      // Panel is restored with conversation history completely preserved
      expect(screen.getByTestId('floating-advisor-panel')).toBeTruthy();
      expect(screen.getByText(/Welcome to the NIVAS Neighborhood AI Advisor/i)).toBeTruthy();
    });

    it('allows retrying telemetry fetch when provider request fails', async () => {
      let callCount = 0;
      vi.spyOn(api, 'fetchLivabilityLocationData').mockImplementation(async () => {
        callCount++;
        if (callCount === 1) {
          return {
            latitude: 28.5921,
            longitude: 77.0460,
            address: 'Dwarka Sector 12, Delhi',
            infrastructure: {
              status: 'fetch_failed',
              error_message: 'Overpass API mirrors were unreachable or timed out.',
              total_facilities: 0,
              facilities: [],
            },
            air_quality: { status: 'provider_not_configured' },
          };
        }
        return {
          latitude: 28.5921,
          longitude: 77.0460,
          address: 'Dwarka Sector 12, Delhi',
          infrastructure: {
            status: 'active',
            schools_count: 3,
            hospitals_count: 2,
            clinics_count: 1,
            pharmacies_count: 0,
            police_stations_count: 1,
            fire_stations_count: 0,
            public_transport_count: 4,
            railway_stations_count: 1,
            major_roads_count: 5,
            total_facilities: 17,
            facilities: [
              {
                id: 'fac-1',
                name: 'Delhi Public School',
                category: 'school',
                category_label: 'School',
                latitude: 28.5912,
                longitude: 77.0456,
              },
            ],
          },
          air_quality: { status: 'provider_not_configured' },
        };
      });

      render(<LivabilityWorkspace />);

      // Verify fetch_failed state and retry button appear
      await waitFor(() => {
        expect(screen.getByTestId('retry-telemetry-btn')).toBeTruthy();
      });

      // Click retry
      fireEvent.click(screen.getByTestId('retry-telemetry-btn'));

      // Verify second call succeeds and shows active facilities
      await waitFor(() => {
        expect(callCount).toBe(2);
        expect(screen.getByText('Delhi Public School')).toBeTruthy();
      });
    });
  });

  describe('NIVAS: Floating Neighborhood AI Advisor Conversation Area & Layout Reliability', () => {
    it('floating advisor opens with welcome message visible and telemetry disclosures displayed', () => {
      render(<LivabilityWorkspace />);

      const panel = screen.getByTestId('floating-advisor-panel');
      expect(panel).toBeTruthy();
      expect(panel.classList.contains('floating-advisor-panel')).toBe(true);

      const welcomeMsg = screen.getByText(/Welcome to the NIVAS Neighborhood AI Advisor/i);
      expect(welcomeMsg).toBeTruthy();

      // Verified sources badge and telemetry provenance tag are visible
      expect(screen.getByText(/OpenStreetMap Overpass API/i)).toBeTruthy();
      expect(screen.getByText(/Telemetry Grounded \(AI Unconfigured\)/i)).toBeTruthy();

      // Scroll container exists with appropriate accessibility role
      const scrollContainer = screen.getByRole('log');
      expect(scrollContainer.classList.contains('chat-messages-scroll')).toBe(true);
    });

    it('renders user message and Advisor response in chronological order with accessible input', async () => {
      const mockReply = {
        reply: 'Verified 4 transit stations within 1.2 km of the selected pin.',
        sources: ['OpenStreetMap Overpass API'],
        is_ai_generated: false,
        provider_configured: false,
      };

      vi.spyOn(api, 'sendLivabilityChatMessage').mockResolvedValue(mockReply);

      render(<LivabilityWorkspace />);

      const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
      const sendBtn = screen.getByRole('button', { name: /Send message/i });

      // User types and submits message
      fireEvent.change(chatInput, { target: { value: 'How is metro connectivity here?' } });
      expect(chatInput.value).toBe('How is metro connectivity here?');
      fireEvent.click(sendBtn);

      // User message rendered in conversation
      expect(screen.getByText('How is metro connectivity here?')).toBeTruthy();

      // Input cleared for next question
      expect(chatInput.value).toBe('');

      // Advisor response appears after resolution
      await waitFor(() => {
        expect(screen.getByText(/Verified 4 transit stations within 1.2 km/i)).toBeTruthy();
      });

      // Both welcome message, user query, and advisor response are present in order
      const bubbles = document.querySelectorAll('.chat-bubble-text');
      expect(bubbles.length).toBe(3);
      expect(bubbles[0].textContent).toContain('Welcome to the NIVAS Neighborhood AI Advisor');
      expect(bubbles[1].textContent).toBe('How is metro connectivity here?');
      expect(bubbles[2].textContent).toContain('Verified 4 transit stations within 1.2 km');
    });

    it('preserves multi-turn conversation history across minimize and reopen', async () => {
      const mockReply1 = {
        reply: '3 schools identified: DPS Dwarka, Mount Carmel, Bal Bhavan.',
        sources: ['OpenStreetMap Overpass API'],
        is_ai_generated: false,
        provider_configured: false,
      };

      vi.spyOn(api, 'sendLivabilityChatMessage').mockResolvedValue(mockReply1);

      render(<LivabilityWorkspace />);

      const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
      const sendBtn = screen.getByRole('button', { name: /Send message/i });

      fireEvent.change(chatInput, { target: { value: 'List nearby schools' } });
      fireEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByText(/3 schools identified: DPS Dwarka/i)).toBeTruthy();
      });

      // Minimize the floating panel
      const minimizeBtn = screen.getByTestId('minimize-advisor-btn');
      fireEvent.click(minimizeBtn);

      expect(screen.queryByTestId('floating-advisor-panel')).toBeNull();

      // Launcher button is visible
      const launcherBtn = screen.getByTestId('advisor-launcher-btn');
      expect(launcherBtn).toBeTruthy();

      // Reopen the panel
      fireEvent.click(launcherBtn);

      expect(screen.getByTestId('floating-advisor-panel')).toBeTruthy();

      // Conversation history is completely intact
      expect(screen.getByText(/Welcome to the NIVAS Neighborhood AI Advisor/i)).toBeTruthy();
      expect(screen.getByText('List nearby schools')).toBeTruthy();
      expect(screen.getByText(/3 schools identified: DPS Dwarka/i)).toBeTruthy();
    });

    it('renders provider unconfigured and error states without producing blank conversation', async () => {
      vi.spyOn(api, 'sendLivabilityChatMessage').mockRejectedValue(new Error('Gateway timeout'));

      render(<LivabilityWorkspace />);

      const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
      const sendBtn = screen.getByRole('button', { name: /Send message/i });

      fireEvent.change(chatInput, { target: { value: 'Is this area flood prone?' } });
      fireEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByText(/Unable to retrieve advisor response: Gateway timeout/i)).toBeTruthy();
      });

      // Error bubble is styled with error class and conversation remains scrollable
      const errorBubble = document.querySelector('.bubble-error');
      expect(errorBubble).toBeTruthy();
      expect(screen.getByText(/Welcome to the NIVAS Neighborhood AI Advisor/i)).toBeTruthy();
      expect(screen.getByText('Is this area flood prone?')).toBeTruthy();
    });
  });

  describe('NIVAS: Dynamic Search Radius Slider & Interactive Circle', () => {
    it('defaults to 1.2 km (1200 m) search radius with clear display', () => {
      render(<LivabilityWorkspace />);

      const slider = screen.getByTestId('search-radius-slider');
      expect(slider).toBeTruthy();
      expect(slider.value).toBe('1200');

      const radiusValue = screen.getByTestId('radius-display-value');
      expect(radiusValue.textContent).toBe('1.2 km');
    });

    it('updates radius display immediately when slider is moved', () => {
      render(<LivabilityWorkspace />);

      const slider = screen.getByTestId('search-radius-slider');
      expect(slider.getAttribute('min')).toBe('0');
      expect(slider.getAttribute('max')).toBe('10000');

      fireEvent.change(slider, { target: { value: '2500' } });

      const radiusValue = screen.getByTestId('radius-display-value');
      expect(radiusValue.textContent).toBe('2.5 km');
      expect(slider.value).toBe('2500');

      // Adjust to 500m
      fireEvent.change(slider, { target: { value: '500' } });
      expect(radiusValue.textContent).toBe('500 m');
      expect(slider.value).toBe('500');

      // Adjust to 0m (pinpoint-only zero state)
      fireEvent.change(slider, { target: { value: '0' } });
      expect(radiusValue.textContent).toBe('0 m');
      expect(slider.value).toBe('0');
      expect(screen.getByText(/0 amenities \(Pinpoint only\)/i)).toBeTruthy();
      expect(screen.getByText(/Search radius set to 0 m \(pinpoint only\)/i)).toBeTruthy();

      // Adjust to 10,000m (10 km maximum)
      fireEvent.change(slider, { target: { value: '10000' } });
      expect(radiusValue.textContent).toBe('10 km');
      expect(slider.value).toBe('10000');
    });

    it('filters facilities accurately according to the selected radius', async () => {
      // Mock 3 facilities with known distances from (28.5921, 77.0460)
      // 1. Close: 0.3 km away (inside 500m)
      // 2. Medium: 1.0 km away (inside 1.2km, outside 500m)
      // 3. Far: 2.2 km away (outside 1.2km, inside 2.5km)
      const mockFacilities = [
        {
          id: 'fac-1',
          name: 'Close Clinic',
          category: 'clinic',
          category_label: 'Clinic',
          latitude: 28.5940, // ~250m north
          longitude: 77.0460,
          source: 'OpenStreetMap',
        },
        {
          id: 'fac-2',
          name: 'Midway School',
          category: 'school',
          category_label: 'School',
          latitude: 28.6010, // ~1km north
          longitude: 77.0460,
          source: 'OpenStreetMap',
        },
        {
          id: 'fac-3',
          name: 'Distant Hospital',
          category: 'hospital',
          category_label: 'Hospital',
          latitude: 28.6120, // ~2.2km north
          longitude: 77.0460,
          source: 'OpenStreetMap',
        },
      ];

      vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue({
        latitude: 28.5921,
        longitude: 77.0460,
        address: 'Dwarka Sector 12',
        retrieved_at: '2026-10-18T12:00:00Z',
        infrastructure: {
          status: 'active',
          source: 'OpenStreetMap Overpass API',
          facilities: mockFacilities,
          schools_count: 1,
          hospitals_count: 1,
          clinics_count: 1,
          pharmacies_count: 0,
          police_stations_count: 0,
          fire_stations_count: 0,
          public_transport_count: 0,
          railway_stations_count: 0,
          major_roads_count: 0,
          total_facilities: 3,
        },
        air_quality: { status: 'provider_not_configured' },
        environmental_hazards: { status: 'data_not_configured', message: 'None' },
      });

      render(<LivabilityWorkspace />);

      // At default 1.2 km: Close Clinic and Midway School are visible (2 amenities)
      await waitFor(() => {
        expect(screen.getByText('Close Clinic')).toBeTruthy();
        expect(screen.getByText('Midway School')).toBeTruthy();
        expect(screen.queryByText('Distant Hospital')).toBeNull();
      });

      // Move slider down to 500m: Only Close Clinic remains
      const slider = screen.getByTestId('search-radius-slider');
      fireEvent.change(slider, { target: { value: '500' } });

      await waitFor(() => {
        expect(screen.getByText('Close Clinic')).toBeTruthy();
        expect(screen.queryByText('Midway School')).toBeNull();
        expect(screen.queryByText('Distant Hospital')).toBeNull();
      });

      // Move slider up to 3000m (3km): All 3 are within radius
      fireEvent.change(slider, { target: { value: '3000' } });

      await waitFor(() => {
        expect(screen.getByText('Close Clinic')).toBeTruthy();
        expect(screen.getByText('Midway School')).toBeTruthy();
        expect(screen.getByText('Distant Hospital')).toBeTruthy();
      });
    });

    it('deterministically filters facilities across 0m, 250m, 1.2km, 3km, 6km, and 10km radii and ensures badge, categories, and directory agree', async () => {
      // Deterministic dataset around (28.5921, 77.0460)
      // 1. fac_200m: ~0.20 km (inside 250m)
      // 2. fac_800m: ~0.80 km (inside 1.2km)
      // 3. fac_2km: ~2.00 km (inside 3km)
      // 4. fac_5km: ~5.00 km (inside 6km)
      // 5. fac_8km: ~8.00 km (inside 10km)
      // 6. fac_12km: ~12.00 km (outside 10km)
      const mockMultiRadiusFacilities = [
        {
          id: 'fac-200m',
          name: 'Primary Health Center',
          category: 'clinic',
          category_label: 'Clinic',
          latitude: 28.5939,
          longitude: 77.0460,
          source: 'OpenStreetMap',
        },
        {
          id: 'fac-800m',
          name: 'Sector Model School',
          category: 'school',
          category_label: 'School',
          latitude: 28.5993,
          longitude: 77.0460,
          source: 'OpenStreetMap',
        },
        {
          id: 'fac-2km',
          name: 'Metro Transit Hub',
          category: 'transit',
          category_label: 'Bus Station',
          latitude: 28.6101,
          longitude: 77.0460,
          source: 'OpenStreetMap',
        },
        {
          id: 'fac-5km',
          name: 'Sub-District Hospital',
          category: 'hospital',
          category_label: 'Hospital',
          latitude: 28.6371,
          longitude: 77.0460,
          source: 'OpenStreetMap',
        },
        {
          id: 'fac-8km',
          name: 'Regional Highway Corridor',
          category: 'road',
          category_label: 'Major Road (Primary)',
          latitude: 28.6641,
          longitude: 77.0460,
          source: 'OpenStreetMap',
        },
        {
          id: 'fac-12km',
          name: 'Remote Boundary Station',
          category: 'police',
          category_label: 'Police Station',
          latitude: 28.7001,
          longitude: 77.0460,
          source: 'OpenStreetMap',
        },
      ];

      vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue({
        latitude: 28.5921,
        longitude: 77.0460,
        address: 'Dwarka Sector 12',
        retrieved_at: '2026-10-18T12:00:00Z',
        infrastructure: {
          status: 'active',
          source: 'OpenStreetMap Overpass API',
          facilities: mockMultiRadiusFacilities,
          schools_count: 1,
          hospitals_count: 1,
          clinics_count: 1,
          pharmacies_count: 0,
          police_stations_count: 1,
          fire_stations_count: 0,
          public_transport_count: 1,
          railway_stations_count: 0,
          major_roads_count: 1,
          total_facilities: 6,
        },
        air_quality: { status: 'provider_not_configured' },
        environmental_hazards: { status: 'data_not_configured', message: 'None' },
      });

      render(<LivabilityWorkspace />);

      const slider = screen.getByTestId('search-radius-slider');
      const badge = () => screen.getByTestId('search-radius-slider').closest('.livability-radius-control-bar').querySelector('.radius-control-badge');

      // 1. Default (1200 m / 1.2 km): contains fac-200m and fac-800m = 2 amenities
      await waitFor(() => {
        expect(screen.getByText('Primary Health Center')).toBeTruthy();
        expect(screen.getByText('Sector Model School')).toBeTruthy();
        expect(screen.queryByText('Metro Transit Hub')).toBeNull();
        expect(screen.queryByText('Sub-District Hospital')).toBeNull();
        expect(screen.queryByText('Regional Highway Corridor')).toBeNull();
        expect(screen.queryByText('Remote Boundary Station')).toBeNull();
        expect(badge().textContent).toContain('2 amenities within circle');
      });

      // 2. Radius 0 m (Pinpoint-only zero state): exactly 0 amenities
      fireEvent.change(slider, { target: { value: '0' } });
      await waitFor(() => {
        expect(badge().textContent).toContain('0 amenities (Pinpoint only)');
        expect(screen.queryByText('Primary Health Center')).toBeNull();
        expect(screen.queryByText('Sector Model School')).toBeNull();
        expect(screen.getAllByText(/Search radius set to 0 m \(pinpoint only\)/i).length).toBeGreaterThanOrEqual(1);
      });

      // 3. Radius 250 m: contains only fac-200m = 1 amenity
      fireEvent.change(slider, { target: { value: '250' } });
      await waitFor(() => {
        expect(badge().textContent).toContain('1 amenity within circle');
        expect(screen.getByText('Primary Health Center')).toBeTruthy();
        expect(screen.queryByText('Sector Model School')).toBeNull();
      });

      // 4. Radius 3000 m (3 km): contains fac-200m, fac-800m, fac-2km = 3 amenities
      fireEvent.change(slider, { target: { value: '3000' } });
      await waitFor(() => {
        expect(badge().textContent).toContain('3 amenities within circle');
        expect(screen.getByText('Primary Health Center')).toBeTruthy();
        expect(screen.getByText('Sector Model School')).toBeTruthy();
        expect(screen.getByText('Metro Transit Hub')).toBeTruthy();
        expect(screen.queryByText('Sub-District Hospital')).toBeNull();
      });

      // 5. Radius 6000 m (6 km): contains fac-200m, fac-800m, fac-2km, fac-5km = 4 amenities
      fireEvent.change(slider, { target: { value: '6000' } });
      await waitFor(() => {
        expect(badge().textContent).toContain('4 amenities within circle');
        expect(screen.getByText('Primary Health Center')).toBeTruthy();
        expect(screen.getByText('Sector Model School')).toBeTruthy();
        expect(screen.getByText('Metro Transit Hub')).toBeTruthy();
        expect(screen.getByText('Sub-District Hospital')).toBeTruthy();
        expect(screen.queryByText('Regional Highway Corridor')).toBeNull();
      });

      // 6. Radius 10000 m (10 km): contains all 5 within 10km, fac-12km is EXCLUDED
      fireEvent.change(slider, { target: { value: '10000' } });
      await waitFor(() => {
        expect(badge().textContent).toContain('5 amenities within circle');
        expect(screen.getByText('Primary Health Center')).toBeTruthy();
        expect(screen.getByText('Sector Model School')).toBeTruthy();
        expect(screen.getByText('Metro Transit Hub')).toBeTruthy();
        expect(screen.getByText('Sub-District Hospital')).toBeTruthy();
        expect(screen.getByText('Regional Highway Corridor')).toBeTruthy();
        expect(screen.queryByText('Remote Boundary Station')).toBeNull();
      });

      // Moving radius does NOT change the active exploration pin
      expect(screen.getByText(/28.5921° N, 77.0460° E/i)).toBeTruthy();
    });

    it('invalidates previous location facilities and resets counter when exploration pin changes', async () => {
      const mockDwarkaFacilities = [
        {
          id: 'dwarka-fac-1',
          name: 'Dwarka Health Center',
          category: 'clinic',
          latitude: 28.5939,
          longitude: 77.0460,
          source: 'OpenStreetMap',
        },
      ];

      vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue({
        latitude: 28.5921,
        longitude: 77.0460,
        address: 'Dwarka Sector 12',
        retrieved_at: '2026-10-18T12:00:00Z',
        infrastructure: {
          status: 'active',
          source: 'OpenStreetMap Overpass API',
          facilities: mockDwarkaFacilities,
          schools_count: 0,
          hospitals_count: 0,
          clinics_count: 1,
          pharmacies_count: 0,
          police_stations_count: 0,
          fire_stations_count: 0,
          public_transport_count: 0,
          railway_stations_count: 0,
          major_roads_count: 0,
          total_facilities: 1,
        },
        air_quality: { status: 'provider_not_configured' },
        environmental_hazards: { status: 'data_not_configured', message: 'None' },
      });

      render(<LivabilityWorkspace />);

      await waitFor(() => {
        expect(screen.getByText('Dwarka Health Center')).toBeTruthy();
      });

      // Perform a search to move pin to Shadipur
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            lat: '28.6517',
            lon: '77.1583',
            display_name: 'Shadipur, New Delhi, Delhi, India',
          },
        ],
      });

      const searchInput = screen.getByPlaceholderText(
        /Search neighborhood or locality \(e\.g\. Hauz Khas, Vasant Kunj, Rohini\)\.\.\./i
      );
      const searchBtn = screen.getByRole('button', { name: /Search/i });

      fireEvent.change(searchInput, { target: { value: 'Shadipur' } });
      fireEvent.click(searchBtn);

      // Previous location facilities must be invalidated immediately
      await waitFor(() => {
        expect(screen.queryByText('Dwarka Health Center')).toBeNull();
        expect(screen.getByText(/28.6517° N, 77.1583° E/i)).toBeTruthy();
      });
    });
  });

  describe('NIVAS: Road Category Infrastructure Reliability & Filter Integrity', () => {
    it('renders verified road features with truthful count, subcard metrics, and allows category filtering', async () => {
      const mockData = {
        latitude: 28.6517,
        longitude: 77.1583,
        address: 'Shadipur, New Delhi',
        locality: 'Shadipur',
        retrieved_at: '2026-10-18T12:00:00Z',
        infrastructure: {
          status: 'active',
          source: 'OpenStreetMap Overpass API',
          schools_count: 1,
          hospitals_count: 0,
          clinics_count: 0,
          pharmacies_count: 0,
          police_stations_count: 0,
          fire_stations_count: 0,
          public_transport_count: 0,
          railway_stations_count: 0,
          major_roads_count: 2,
          total_facilities: 3,
          facilities: [
            {
              id: 'road-1',
              name: 'Patel Road',
              category: 'road',
              category_label: 'Major Road (Secondary)',
              latitude: 28.6520,
              longitude: 77.1590,
              source: 'OpenStreetMap',
            },
            {
              id: 'road-2',
              name: 'Pusa Road',
              category: 'road',
              category_label: 'Major Road (Primary)',
              latitude: 28.6535,
              longitude: 77.1605,
              source: 'OpenStreetMap',
            },
            {
              id: 'school-1',
              name: 'Shadipur Model School',
              category: 'school',
              category_label: 'School',
              latitude: 28.6522,
              longitude: 77.1580,
              source: 'OpenStreetMap',
            },
          ],
        },
        air_quality: { status: 'provider_not_configured' },
        environmental_hazards: { status: 'data_not_configured', message: 'None' },
      };

      vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockData);

      render(<LivabilityWorkspace location={{ latitude: 28.6517, longitude: 77.1583, address: 'Shadipur, New Delhi' }} />);

      await waitFor(() => {
        expect(screen.getByText('Patel Road')).toBeTruthy();
        expect(screen.getByText('Pusa Road')).toBeTruthy();
      });

      // Legend shows truthful road count: Roads (2)
      const roadLegendBtn = screen.getByTestId('legend-filter-road');
      expect(roadLegendBtn.textContent).toContain('Roads (2)');

      // Civic Infrastructure subcard shows Arterial Roads: 2
      const roadsPill = screen.getByTestId('metric-pill-roads');
      expect(roadsPill.textContent).toContain('2');
      expect(roadsPill.textContent).toContain('Arterial Roads');

      // Clarification in subcard footer: infrastructure evidence, not walkability/safety score
      expect(screen.getByText(/Mapped roads indicate regional transit connectivity evidence, not walkability or safety ratings/i)).toBeTruthy();

      // Category filtering: clicking Roads filter isolates road markers
      fireEvent.click(roadLegendBtn);
      expect(roadLegendBtn.classList.contains('active')).toBe(true);
      expect(screen.getByText(/2 places shown/i)).toBeTruthy();

      // Clicking again resets category filter to all
      fireEvent.click(roadLegendBtn);
      expect(roadLegendBtn.classList.contains('active')).toBe(false);
      expect(screen.getByText(/3 places shown/i)).toBeTruthy();
    });

    it('displays explicit unavailable state when infrastructure fetch fails', async () => {
      const mockFailedData = {
        latitude: 28.6517,
        longitude: 77.1583,
        address: 'Shadipur, New Delhi',
        infrastructure: {
          status: 'fetch_failed',
          error_message: 'OpenStreetMap Overpass API mirrors were unreachable or timed out',
          schools_count: 0,
          major_roads_count: 0,
          facilities: [],
        },
        air_quality: { status: 'provider_not_configured' },
        environmental_hazards: { status: 'data_not_configured', message: 'None' },
      };

      vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockFailedData);

      render(<LivabilityWorkspace location={{ latitude: 28.6517, longitude: 77.1583, address: 'Shadipur, New Delhi' }} />);

      await waitFor(() => {
        expect(screen.getByTestId('legend-filter-road').textContent).toContain('Roads (Unavailable)');
      });

      expect(screen.getAllByText(/Overpass API mirrors were unreachable or timed out/i).length).toBeGreaterThanOrEqual(1);
    });

    it('distinguishes confirmed zero road results from failure', async () => {
      const mockEmptyData = {
        latitude: 28.6517,
        longitude: 77.1583,
        address: 'Shadipur, New Delhi',
        infrastructure: {
          status: 'empty',
          schools_count: 0,
          major_roads_count: 0,
          total_facilities: 0,
          facilities: [],
        },
        air_quality: { status: 'provider_not_configured' },
        environmental_hazards: { status: 'data_not_configured', message: 'None' },
      };

      vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue(mockEmptyData);

      render(<LivabilityWorkspace location={{ latitude: 28.6517, longitude: 77.1583, address: 'Shadipur, New Delhi' }} />);

      await waitFor(() => {
        expect(screen.getByTestId('legend-filter-road').textContent).toContain('Roads (0)');
      });

      expect(screen.getByText(/0 civic amenities recorded within search radius in OpenStreetMap/i)).toBeTruthy();
    });
  });
});

