import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import L from 'leaflet';
import PropertyLocationPicker from '../PropertyLocationPicker';
import SafetyIntelligenceView from '../SafetyIntelligenceView';
import DisasterWorkspace from '../DisasterWorkspace';
import App from '../../App';
import * as api from '../../services/api';

// Mock Leaflet
vi.mock('leaflet', () => {
  const mockMap = {
    setView: vi.fn(),
    flyTo: vi.fn(),
    panTo: vi.fn(),
    getZoom: () => 14,
    remove: vi.fn(),
    invalidateSize: vi.fn(),
    on: vi.fn(),
    fitBounds: vi.fn(),
    createPane: vi.fn(),
    getPane: vi.fn(),
  };

  const mockLayerGroup = {
    addTo: vi.fn(function() { return this; }),
    clearLayers: vi.fn(function() { return this; }),
  };

  const mockCircle = {
    addTo: vi.fn(function() { return this; }),
    setLatLng: vi.fn(),
    setRadius: vi.fn(),
    redraw: vi.fn(),
    remove: vi.fn(),
  };

  const mockPolygon = {
    addTo: vi.fn(function() { return this; }),
  };

  return {
    default: {
      map: () => mockMap,
      tileLayer: () => ({ addTo: () => {} }),
      layerGroup: () => mockLayerGroup,
      geoJSON: () => ({ addTo: () => {} }),
      polygon: vi.fn(() => mockPolygon),
      circle: vi.fn(() => mockCircle),
      marker: () => ({
        addTo: function() { return this; },
        bindPopup: function() { return this; },
        setLatLng: vi.fn(),
        getLatLng: () => ({ lat: 28.5921, lng: 77.0460 }),
        on: vi.fn(),
      }),
      divIcon: () => ({}),
    },
  };
});

describe('Safety & Crime Intelligence Workspace Component', () => {
  const mockSafetyResponse = {
    status: 'active',
    official_state_crime: {
      state_ut_name: 'NCT of Delhi',
      reporting_year: 2022,
      total_ipc_cases: 298988,
      crime_rate_per_lakh: 1422.6,
      data_status: 'verified_official',
      is_derived_estimate: false,
    },
    matched_district: {
      district_id: 'south_west',
      district_name: 'Dwarka (South-West)',
      total_ipc_crimes_2022: 7850,
      crime_rate_per_lakh: 342.5,
      clearance_rate_pct: 41.2,
      population_projection_2022: 2291000,
      categories_2022: [
        {
          category_name: 'Theft & Motor Vehicle Theft',
          reported_cases: 4200,
          rate_per_lakh: 183.2,
          pct_of_total: 53.5,
          clearance_pct: 24.5,
        },
        {
          category_name: 'Violent Crimes (Robbery, Murder, Assault)',
          reported_cases: 310,
          rate_per_lakh: 13.5,
          pct_of_total: 3.9,
          clearance_pct: 82.1,
        },
      ],
      historical_trend_ipc: {
        2018: 6950,
        2019: 7200,
        2020: 6800,
        2021: 7450,
        2022: 7850,
      },
      data_source: 'National Crime Records Bureau (NCRB) & Delhi Police',
      boundary_type: 'spatial_approximation_reference',
      boundary_disclaimer:
        'Approximated Police District Jurisdictional Zone. Macro reference geometry for locality mapping; not an official cadastral boundary published by Delhi Police or Survey of India.',
      is_derived_estimate: true,
      state_ut_benchmark: {
        '2018': { total_ipc_cases: 236476, crime_rate_per_lakh: 1215.7, source_table: 'NCRB Crime in India 2018, Table 1A.1' },
        '2019': { total_ipc_cases: 299475, crime_rate_per_lakh: 1518.0, source_table: 'NCRB Crime in India 2019, Table 1A.1' },
        '2020': { total_ipc_cases: 245844, crime_rate_per_lakh: 1228.6, source_table: 'NCRB Crime in India 2020, Table 1A.1' },
        '2021': { total_ipc_cases: 287563, crime_rate_per_lakh: 1410.8, source_table: 'NCRB Crime in India 2021, Table 1A.1' },
        '2022': { total_ipc_cases: 298988, crime_rate_per_lakh: 1422.6, source_table: 'NCRB Crime in India 2022, Table 1A.1' },
      },
      provenance_details: {
        source_agency: 'National Crime Records Bureau (NCRB) & Delhi Police',
        official_table_state_ut: 'NCRB Crime in India Table 1A.1: Cognizable IPC Crimes in States/UTs',
        official_portal_url: 'https://ncrb.gov.in/crime-in-india.html',
        population_methodology:
          'Census of India 2011 surveyed 9 Revenue Districts. Police district populations are derived projections used by Delhi Police.',
      },
    },
    nearby_police_stations: [
      {
        osm_id: 'node_dwk_23',
        name: 'Dwarka Sector 23 Police Station',
        latitude: 28.5833,
        longitude: 77.0500,
        distance_km: 1.1,
        formatted_distance: '1.1 km',
        locality: 'Sector 23, Dwarka',
        is_within_radius: true,
      },
      {
        osm_id: 'node_dwk_north',
        name: 'Dwarka North Police Station',
        latitude: 28.6050,
        longitude: 77.0400,
        distance_km: 1.5,
        formatted_distance: '1.5 km',
        locality: 'Sector 17, Dwarka',
        is_within_radius: false,
      },
    ],
    nearest_police_stations: [
      {
        osm_id: 'node_dwk_23',
        name: 'Dwarka Sector 23 Police Station',
        latitude: 28.5833,
        longitude: 77.0500,
        distance_km: 1.1,
        formatted_distance: '1.1 km',
        locality: 'Sector 23, Dwarka',
        is_within_radius: true,
      },
      {
        osm_id: 'node_dwk_north',
        name: 'Dwarka North Police Station',
        latitude: 28.6050,
        longitude: 77.0400,
        distance_km: 1.5,
        formatted_distance: '1.5 km',
        locality: 'Sector 17, Dwarka',
        is_within_radius: false,
      },
      {
        osm_id: 'node_dwk_south',
        name: 'Dwarka South Police Station',
        latitude: 28.5772,
        longitude: 77.0610,
        distance_km: 2.2,
        formatted_distance: '2.2 km',
        locality: 'Sector 9, Dwarka',
        is_within_radius: false,
      },
    ],
  };

  const mockNationalOverview = {
    status: 'success',
    reporting_year: 2022,
    source_agency: 'National Crime Records Bureau (NCRB)',
    source_title: 'Crime in India 2022, Table 1A.1: Cognizable IPC Crimes in States/UTs',
    source_url: 'https://ncrb.gov.in/crime-in-india.html',
    national_benchmark_rate: 258.1,
    total_all_india_ipc_cases: 3561379,
    classification_method: 'Fixed Statutory Rate Thresholds',
    thresholds: {
      lower: '< 200 crimes per 100k population',
      moderate: '200 to 350 crimes per 100k population (National Benchmark: 258.1)',
      higher: '> 350 crimes per 100k population (High e-FIR portal adoption)',
    },
    color_palette: {
      lower: '#10B981',
      moderate: '#F59E0B',
      higher: '#EF4444',
    },
    coverage_summary: {
      total_states_mapped: 36,
      states_with_statutory_data: 36,
      states_with_subdistrict_polygons: 1,
      coverage_percentage: 100.0,
    },
    geojson: {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            state_code: 'IN-DL',
            state_name: 'NCT of Delhi',
            raw_name: 'Delhi',
            reporting_year: 2022,
            total_ipc_cases: 298988,
            projected_population_lakhs: 210.2,
            crime_rate_per_lakh: 1422.6,
            risk_tier: 'higher',
            tier_label: 'Higher Recorded IPC Rate (> 350 per 100k)',
            color: '#EF4444',
            fill_opacity: 0.38,
            has_district_data: true,
            source_citation: 'NCRB Crime in India 2022, Table 1A.1: IPC Crimes in States/UTs',
            legal_disclosure: 'Statutory State/UT aggregate. Does not measure individual property or street-level crime.',
            e_fir_effect: 'Higher recorded rate heavily reflects 100% digital citizen e-FIR registration for vehicle and property theft rather than localized physical violence.',
          },
          geometry: { type: 'Polygon', coordinates: [[[76.8, 28.4], [77.3, 28.4], [77.3, 28.9], [76.8, 28.9], [76.8, 28.4]]] },
        },
        {
          type: 'Feature',
          properties: {
            state_code: 'IN-MH',
            state_name: 'Maharashtra',
            raw_name: 'Maharashtra',
            reporting_year: 2022,
            total_ipc_cases: 374038,
            projected_population_lakhs: 1257.0,
            crime_rate_per_lakh: 297.6,
            risk_tier: 'moderate',
            tier_label: 'Moderate Recorded IPC Rate (200-350 per 100k)',
            color: '#F59E0B',
            fill_opacity: 0.38,
            has_district_data: false,
            source_citation: 'NCRB Crime in India 2022, Table 1A.1: IPC Crimes in States/UTs',
            legal_disclosure: 'Statutory State/UT aggregate.',
            e_fir_effect: null,
          },
          geometry: { type: 'Polygon', coordinates: [[[72.8, 18.9], [73.5, 18.9], [73.5, 19.5], [72.8, 19.5], [72.8, 18.9]]] },
        },
      ],
    },
    interpretability_guide: [
      { topic: 'Registration Volume vs. Danger', explanation: 'Crime rate measures reported cases, not unmeasured street crime.' },
    ],
  };

  beforeEach(() => {
    vi.spyOn(api, 'fetchSafetyData').mockResolvedValue(mockSafetyResponse);
    vi.spyOn(api, 'fetchNationalSafetyOverview').mockResolvedValue(mockNationalOverview);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders official district name, rates, and clearance statistics correctly', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Dwarka (South-West) Crime Intelligence')).toBeDefined();
    });

    expect(screen.getByText('342.5')).toBeDefined();
    expect(screen.getByText('41.2%')).toBeDefined();
    expect(screen.getAllByText('7,850').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Derived Estimate')).toBeDefined();
  });

  it('renders verified official State/UT benchmark card with NCRB Table 1A.1 data', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('official-state-benchmark')).toBeDefined();
    });

    expect(screen.getByText('Verified Official Benchmark (State/UT Level)')).toBeDefined();
    expect(screen.getByText('298,988')).toBeDefined();
    expect(screen.getByText('1422.6')).toBeDefined();
  });

  it('suppresses district crime rate per 100k when null and displays explanatory footnote', async () => {
    const suppressedMock = {
      ...mockSafetyResponse,
      matched_district: {
        ...mockSafetyResponse.matched_district,
        crime_rate_per_lakh: null,
        rate_unavailable_reason: 'Census population denominators do not align with operational police districts',
      },
    };
    vi.spyOn(api, 'fetchSafetyData').mockResolvedValue(suppressedMock);

    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Dwarka (South-West) Crime Intelligence')).toBeDefined();
    });

    expect(screen.getByText('—')).toBeDefined();
    expect(screen.getByText('Suppressed')).toBeDefined();
    expect(screen.getByText(/Census population denominators do not align/i)).toBeDefined();
  });

  it('renders crime categories with truthful numbers and clearance rates', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Theft & Motor Vehicle Theft')).toBeDefined();
    });

    expect(screen.getByText(/4,200 cases/i)).toBeDefined();
    expect(screen.getByText('Violent Crimes (Robbery, Murder, Assault)')).toBeDefined();
  });

  it('renders Nearest Police Stations Directory with distances, localities, within/outside badges, and actions', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('nearest-police-stations-card')).toBeDefined();
    });

    expect(screen.getByText('Nearest Verified Police Stations Directory')).toBeDefined();
    expect(screen.getByText('Dwarka Sector 23 Police Station')).toBeDefined();
    expect(screen.getByText('Sector 23, Dwarka')).toBeDefined();
    expect(screen.getByText('1.1 km')).toBeDefined();
    expect(screen.getByText('Within 1.2 km')).toBeDefined();

    expect(screen.getByText('Dwarka North Police Station')).toBeDefined();
    expect(screen.getByText('Sector 17, Dwarka')).toBeDefined();
    expect(screen.getByText('1.5 km')).toBeDefined();
    expect(screen.getAllByText('Outside 1.2 km').length).toBeGreaterThanOrEqual(1);

    expect(screen.getByText('Dwarka South Police Station')).toBeDefined();
    expect(screen.getByText('2.2 km')).toBeDefined();

    // Verify Focus on Map and Directions action buttons exist
    const focusButtons = screen.getAllByRole('button', { name: /Focus on Map/i });
    expect(focusButtons.length).toBe(3);
    const directionLinks = screen.getAllByRole('link', { name: /Directions/i });
    expect(directionLinks.length).toBe(3);
  });

  it('renders map view controls with Reset to India view and Zoom to selected district', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('map-view-controls')).toBeDefined();
    });

    const resetBtn = screen.getByTestId('reset-to-india-view-btn');
    expect(resetBtn).toBeDefined();
    expect(resetBtn.textContent).toContain('Reset to India view');

    const zoomDistrictBtn = screen.getByTestId('zoom-to-district-btn');
    expect(zoomDistrictBtn).toBeDefined();
    expect(zoomDistrictBtn.textContent).toContain('Zoom to Dwarka (South-West)');

    // Click Reset to India view
    fireEvent.click(resetBtn);
    expect(resetBtn.classList.contains('active')).toBe(true);

    // Click Zoom to selected district
    fireEvent.click(zoomDistrictBtn);
    expect(zoomDistrictBtn.classList.contains('active')).toBe(true);
  });

  it('displays helpful fallback notice rather than misleading zero when stations are unavailable', async () => {
    const emptyStationsMock = {
      ...mockSafetyResponse,
      nearby_police_stations: [],
      nearest_police_stations: [],
    };
    vi.spyOn(api, 'fetchSafetyData').mockResolvedValue(emptyStationsMock);

    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('stations-fallback-notice')).toBeDefined();
    });

    expect(screen.getByText(/Police facility directory temporarily unavailable/i)).toBeDefined();
    expect(screen.getByText(/dial police control/i)).toBeDefined();
    expect(screen.queryByText(/0 police stations mapped within/i)).toBeNull();
  });

  it('renders statutory disclosures and official data provenance', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Safety Data Integrity & Methodology Disclosures/i)
      ).toBeDefined();
    });
  });

  it('toggles provenance and citations panel and displays legal methodology', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('toggle-provenance-btn')).toBeDefined();
    });

    // Panel is initially hidden
    expect(screen.queryByTestId('provenance-panel')).toBeNull();

    // Click toggle button
    fireEvent.click(screen.getByTestId('toggle-provenance-btn'));

    // Panel should now be visible
    expect(screen.getByTestId('provenance-panel')).toBeDefined();
    expect(screen.getByText(/NCRB Crime in India Table 1A.1/i)).toBeDefined();
    expect(screen.getByText(/Approximated Police District Jurisdictional Zone/i)).toBeDefined();
  });

  it('allows selecting historical years and updates trend focus box', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('year-col-2021')).toBeDefined();
    });

    fireEvent.click(screen.getByTestId('year-col-2021'));
    expect(screen.getByTestId('trend-year-focus')).toBeDefined();
    expect(screen.getByText('7,450 IPC cases')).toBeDefined();
  });

  it('renders map first before official benchmark and crime report cards with clean unobtrusive legend', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('safety-map-panel')).toBeDefined();
    });

    const mapPanel = screen.getByTestId('safety-map-panel');
    const benchmarkCard = screen.getByTestId('official-state-benchmark');
    const metricsGrid = screen.getByTestId('safety-metrics-grid');

    // Verify map is rendered before benchmark and metrics cards in DOM order
    expect(mapPanel.compareDocumentPosition(benchmarkCard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(mapPanel.compareDocumentPosition(metricsGrid) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(benchmarkCard.compareDocumentPosition(metricsGrid) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    // Verify clean unobtrusive legend exists with district boundary and police stations
    const legend = screen.getByTestId('safety-map-legend');
    expect(legend).toBeDefined();
    expect(legend.textContent).toContain('Police District Boundary');
    expect(legend.textContent).toContain('Verified Physical Police Stations');
    expect(legend.textContent).toContain('Selected Search Location');
  });

  it('disables radius circle on safety map while preserving radius circle on default/livability map', async () => {
    L.circle.mockClear();

    // Render SafetyIntelligenceView which has showRadius={false}
    const { unmount } = render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
        radius={1200}
        initialMode="inspect"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('safety-map-panel')).toBeDefined();
    });

    // In SafetyIntelligenceView, L.circle must NOT be called for the radius
    expect(L.circle).not.toHaveBeenCalled();

    unmount();

    // Now render PropertyLocationPicker with default showRadius={true} (used by Livability)
    L.circle.mockClear();
    render(
      <PropertyLocationPicker
        latitude={28.5921}
        longitude={77.0460}
        onLocationChange={vi.fn()}
        radiusCircleMeters={1200}
      />
    );

    // With default showRadius={true}, L.circle MUST be called with radius 1200
    expect(L.circle).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ radius: 1200 })
    );
  });

  it('renders India Safety Overview by default with coverage banner, thematic legend, and state inspection card', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
      />
    );

    // Segmented control exists with India Safety Overview active
    await waitFor(() => {
      expect(screen.getByTestId('safety-mode-bar')).toBeDefined();
    });
    const overviewBtn = screen.getByTestId('mode-overview-btn');
    const inspectBtn = screen.getByTestId('mode-inspect-btn');
    expect(overviewBtn.classList.contains('active')).toBe(true);
    expect(inspectBtn.classList.contains('active')).toBe(false);

    // Mode A container is rendered
    expect(screen.getByTestId('safety-overview-section')).toBeDefined();

    // Coverage banner displays statutory numbers
    const covBanner = screen.getByTestId('safety-coverage-banner');
    expect(covBanner.textContent).toContain('36 of 36 States & UTs');
    expect(covBanner.textContent).toContain('258.1');

    // Thematic legend renders with 3 tiers
    const legend = screen.getByTestId('safety-thematic-legend');
    expect(legend.textContent).toContain('Lower Rate');
    expect(legend.textContent).toContain('< 200 per 100k');
    expect(legend.textContent).toContain('Moderate Rate');
    expect(legend.textContent).toContain('200–350 per 100k');
    expect(legend.textContent).toContain('Higher Recorded');
    expect(legend.textContent).toContain('> 350 per 100k');

    // State inspection card renders NCT of Delhi by default
    await waitFor(() => {
      expect(screen.getByTestId('state-inspection-card')).toBeDefined();
    });
    expect(screen.getByText('NCT of Delhi')).toBeDefined();
    expect(screen.getByText('1422.6')).toBeDefined();
    expect(screen.getByTestId('state-efir-note')).toBeDefined();

    // Toggle interpretability guide
    const toggleGuideBtn = screen.getByTestId('toggle-interpret-guide-btn');
    expect(screen.queryByTestId('interpret-content')).toBeNull();
    fireEvent.click(toggleGuideBtn);
    expect(screen.getByTestId('interpret-content')).toBeDefined();
    expect(screen.getByText(/Registration Volume vs. Street Victimization/i)).toBeDefined();
  });

  it('switches between India Safety Overview and Check My Location seamlessly', async () => {
    const handleLocationChange = vi.fn();
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={handleLocationChange}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('mode-inspect-btn')).toBeDefined();
    });

    // Click Check My Location segmented button
    fireEvent.click(screen.getByTestId('mode-inspect-btn'));

    // Mode B container and local toolbar should appear
    expect(screen.getByTestId('safety-inspect-section')).toBeDefined();
    expect(screen.getByTestId('safety-local-toolbar')).toBeDefined();
    expect(screen.getByTestId('location-evidence-card')).toBeDefined();
    expect(screen.getByText(/Verified District Telemetry Active/i)).toBeDefined();

    // Nearest police stations should be visible in Mode B
    expect(screen.getByTestId('nearest-police-stations-card')).toBeDefined();

    // Click Return to India Overview
    const returnBtn = screen.getByTestId('return-overview-btn');
    fireEvent.click(returnBtn);

    // Returns to Mode A
    expect(screen.getByTestId('safety-overview-section')).toBeDefined();
    expect(screen.queryByTestId('safety-inspect-section')).toBeNull();
  });

  it('switches to inspect mode when clicking Check Local Evidence in State Inspection card', async () => {
    const handleLocationChange = vi.fn();
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={handleLocationChange}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('inspect-state-btn')).toBeDefined();
    });

    fireEvent.click(screen.getByTestId('inspect-state-btn'));

    // Should switch to inspect mode and update location if Delhi
    expect(screen.getByTestId('safety-inspect-section')).toBeDefined();
    expect(handleLocationChange).toHaveBeenCalledWith(
      expect.objectContaining({ latitude: 28.6139, longitude: 77.2090 })
    );
  });
});

describe('Disaster Hazards Workspace Component', () => {
  beforeEach(() => {
    vi.spyOn(api, 'fetchDisasterHazardData').mockResolvedValue({
      status: 'active',
      latitude: 28.5921,
      longitude: 77.0460,
      address: 'Dwarka Sector 12, Delhi',
      locality_name: 'Dwarka Sector 12',
      live_alerts_available: false,
      live_alerts_status: 'unavailable',
      hazards: [
        {
          hazard_type: 'earthquake',
          title: 'Earthquake Hazard (Seismic Zone IV)',
          severity: 'high',
          category: 'static_zonal',
          evidence_type: 'static_zonal',
          data_freshness: 'static_standard',
          geographic_resolution: 'regional_statutory_standard',
          description:
            'Entire NCT of Delhi falls within Bureau of Indian Standards (BIS IS 1893:2016) Seismic Zone IV.',
          mitigation_notes: 'Ensure ductile detailing complying with IS 13920:2016.',
          source_agency: 'BIS IS 1893:2016 & NDMA Guidelines',
          source_url: 'https://bis.gov.in',
          is_applicable: true,
          parameters: { zone_factor: 0.24 },
        },
        {
          hazard_type: 'flood',
          title: 'Yamuna Floodplain Corridor',
          severity: 'low',
          category: 'historical_vulnerability',
          evidence_type: 'historical_and_zonal',
          data_freshness: 'historical_compendium',
          geographic_resolution: 'macro_riverbed_corridor',
          description:
            'Location is outside the active riverbed and protected behind ring bunds and master drainage channels.',
          mitigation_notes: 'Maintain storm water culvert clearance.',
          source_agency: 'Delhi Master Plan 2021 (O-Zone) & Central Water Commission (CWC)',
          source_url: 'https://cwc.gov.in',
          is_applicable: false,
          parameters: {},
        },
      ],
      disclaimers: [
        'Official Hazard Mapping Baseline: All hazard classifications are derived from statutory standards.',
      ],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches and displays official hazard items for the given location', async () => {
    render(
      <DisasterWorkspace
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Earthquake Hazard (Seismic Zone IV)')).toBeDefined();
    });

    expect(screen.getByText('HIGH EXPOSURE')).toBeDefined();
    expect(screen.getByText('Yamuna Floodplain Corridor')).toBeDefined();
    expect(screen.getByText('LOW EXPOSURE')).toBeDefined();
    expect(screen.getByText('Locality Hazard Evidence')).toBeDefined();
    expect(screen.getByText('Relocation Candidate Compare')).toBeDefined();

    // Verify live alerts banner and evidence badges
    expect(screen.getByTestId('disaster-live-alerts-banner')).toBeDefined();
    expect(screen.getByTestId('hazard-evidence-earthquake')).toBeDefined();
  });

  it('opens and executes relocation comparison between two localities', async () => {
    vi.spyOn(api, 'compareDisasterLocations').mockResolvedValue({
      status: 'active',
      location_a: {
        locality_name: 'Dwarka Sector 12',
        latitude: 28.5921,
        longitude: 77.0460,
      },
      location_b: {
        locality_name: 'Yamuna Bazar, Civil Lines',
        latitude: 28.7041,
        longitude: 77.2300,
      },
      comparison_verdict: 'Side-by-side contrast complete across statutory seismic standards and floodplain proximity.',
      comparative_analysis: [
        {
          title: 'Yamuna Floodplain Corridor',
          location_a_verdict: 'Outside Floodplain',
          location_b_verdict: 'Inside Active Floodplain / Yamuna Lowland',
          summary:
            'Location A is safely outside the Yamuna riverbed corridor, whereas Location B is situated directly within the low-lying alluvial floodplain.',
        },
      ],
      disclaimers: ['Comparison grounded in official BIS and CWC zoning data.'],
    });

    render(
      <DisasterWorkspace
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
      />
    );

    const compareTab = screen.getByTestId('tab-disaster-compare');
    fireEvent.click(compareTab);

    await waitFor(() => {
      expect(screen.getByText('Side-by-Side Hazard Exposure Evidence')).toBeDefined();
      expect(screen.getByText('Inside Active Floodplain / Yamuna Lowland')).toBeDefined();
      expect(screen.getByTestId('compare-verdict-card')).toBeDefined();
    });
  });

  it('renders alert when comparison has partial evidence', async () => {
    vi.spyOn(api, 'compareDisasterLocations').mockResolvedValue({
      status: 'partial_evidence',
      location_a: {
        locality_name: 'Dwarka Sector 12',
        latitude: 28.5921,
        longitude: 77.0460,
      },
      location_b: {
        locality_name: 'Mumbai, Maharashtra',
        latitude: 19.0760,
        longitude: 72.8777,
      },
      comparative_analysis: [],
      comparison_verdict:
        'Partial comparison only. Grounded hazard telemetry is available for Dwarka Sector 12, but Mumbai lacks valid coverage. Missing data cannot be ranked as safer.',
      disclaimers: ['Candidate location has no verified hazard coverage.'],
    });

    render(
      <DisasterWorkspace
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
      />
    );

    const compareTab = screen.getByTestId('tab-disaster-compare');
    fireEvent.click(compareTab);

    await waitFor(() => {
      expect(screen.getByTestId('compare-status-alert')).toBeDefined();
      expect(screen.getByText(/Partial Evidence Available/i)).toBeDefined();
      expect(screen.getByText(/Missing data cannot be ranked as safer/i)).toBeDefined();
    });
  });
});

describe('Top-Level Three-Way Navigation & URL Hash Integration', () => {
  beforeEach(() => {
    vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue({
      location: { latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12' },
      facilities: [],
      categories: {},
      summary: 'Mocked Livability Data',
    });
    vi.spyOn(api, 'fetchDisasterHazardData').mockResolvedValue({
      status: 'active',
      latitude: 28.5921,
      longitude: 77.0460,
      locality_name: 'Dwarka Sector 12',
      hazards: [],
      disclaimers: [],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.location.hash = '';
  });

  it('switches between Livability, Disaster Hazards, and Property Inspection', async () => {
    render(<App />);

    // Initial state is livability
    expect(screen.getByText('Livability')).toBeDefined();
    expect(screen.getByText('Disaster Hazards')).toBeDefined();
    expect(screen.getByText('Property Inspection')).toBeDefined();

    // Click Disaster Hazards
    const disasterBtn = screen.getByRole('button', { name: /Disaster Hazards/i });
    fireEvent.click(disasterBtn);

    await waitFor(() => {
      expect(window.location.hash).toBe('#disaster');
      expect(screen.getByText('Disaster & Climate Hazard Workspace')).toBeDefined();
    });

    // Click Property Inspection
    const inspectionBtn = screen.getByRole('button', { name: /Property Inspection/i });
    fireEvent.click(inspectionBtn);

    await waitFor(() => {
      expect(window.location.hash).toBe('#inspection');
      expect(screen.getByText('Inspection Workflow Mode')).toBeDefined();
    });

    // Switch back to Livability
    const livabilityBtn = screen.getByRole('button', { name: /Livability/i });
    fireEvent.click(livabilityBtn);

    await waitFor(() => {
      expect(window.location.hash).toBe('#livability');
    });
  });

  describe('GIS Hazard Zoning Explorer Redesign & All-India Coverage', () => {
    it('renders cleanly organized map controls, without top-right checkboxes, and supports layer toggles & reset', async () => {
      render(
        <DisasterWorkspace
          location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('disaster-hazard-map-panel')).toBeDefined();
      });

      // 1. Verify checkboxes do not appear in the top-right header row
      const mapHeader = screen.getByTestId('disaster-map-header');
      expect(mapHeader.querySelector('.disaster-layer-controls')).toBeNull();
      expect(mapHeader.querySelector('input[type="checkbox"]')).toBeNull();

      // 2. Address/locality search field is rendered
      const searchInput = screen.getByRole('textbox', { name: /search/i });
      expect(searchInput).toBeDefined();

      // 3. Compact, collapsible Map Layers panel
      const togglePanelBtn = screen.getByTestId('toggle-layers-panel-btn');
      expect(togglePanelBtn).toBeDefined();
      expect(togglePanelBtn.getAttribute('aria-expanded')).toBe('true');

      // 4. Initial active count badge (6 of 8 default layers active)
      const activeCountBadge = screen.getByTestId('layers-active-count');
      expect(activeCountBadge.textContent).toContain('6 of 8 Active');

      // Reset button should initially be disabled because default state is active
      const resetBtn = screen.getByTestId('reset-layers-btn');
      expect(resetBtn.hasAttribute('disabled')).toBe(true);

      // 5. Layer toggles exist with clear categories
      const floodToggle = screen.getByTestId('layer-toggle-flood');
      const waterlogToggle = screen.getByTestId('layer-toggle-waterlog');
      expect(floodToggle).toBeDefined();
      expect(waterlogToggle).toBeDefined();
      expect(floodToggle.checked).toBe(true);
      expect(waterlogToggle.checked).toBe(true);

      // Verify category labels
      expect(screen.getByText('Riverine Inundation')).toBeDefined();
      expect(screen.getByText('Surface Drainage')).toBeDefined();
      expect(screen.getByText('Major River Flood Basins & Floodplains')).toBeDefined();
      expect(screen.getByText('Chronic Monsoon Waterlogging Hotspots')).toBeDefined();

      // 6. Toggle Flood layer off
      fireEvent.click(floodToggle);
      expect(floodToggle.checked).toBe(false);
      expect(activeCountBadge.textContent).toContain('5 of 8 Active');
      expect(resetBtn.hasAttribute('disabled')).toBe(false);

      // Toggle Waterlog layer off
      fireEvent.click(waterlogToggle);
      expect(waterlogToggle.checked).toBe(false);
      expect(activeCountBadge.textContent).toContain('4 of 8 Active');

      // 7. Click Reset to Default action
      fireEvent.click(resetBtn);
      expect(floodToggle.checked).toBe(true);
      expect(waterlogToggle.checked).toBe(true);
      expect(activeCountBadge.textContent).toContain('6 of 8 Active');
      expect(resetBtn.hasAttribute('disabled')).toBe(true);

      // 8. Test collapse and expand behavior
      fireEvent.click(togglePanelBtn);
      expect(togglePanelBtn.getAttribute('aria-expanded')).toBe('false');
      // Body should be collapsed (not in DOM)
      expect(screen.queryByTestId('layer-toggle-flood')).toBeNull();

      // Click again to expand
      fireEvent.click(togglePanelBtn);
      expect(togglePanelBtn.getAttribute('aria-expanded')).toBe('true');
      expect(screen.getByTestId('layer-toggle-flood')).toBeDefined();
    });

    it('supports switching between India Hazard Overview and Check My Location with local actions', async () => {
      render(
        <DisasterWorkspace
          location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('disaster-assessment-card')).toBeDefined();
      });

      // Switch to India Hazard Overview
      const overviewBtn = screen.getByTestId('mode-india-overview-btn');
      fireEvent.click(overviewBtn);

      await waitFor(() => {
        expect(screen.getByTestId('disaster-overview-section')).toBeDefined();
        expect(screen.getByTestId('disaster-national-banner')).toBeDefined();
        expect(screen.getByText(/Statutory All-India Coverage/i)).toBeDefined();
      });

      // Switch back to Check My Location
      const checkLocBtn = screen.getByTestId('mode-check-location-btn');
      fireEvent.click(checkLocBtn);

      await waitFor(() => {
        expect(screen.getByTestId('disaster-assessment-card')).toBeDefined();
        expect(screen.getByTestId('disaster-local-actions-toolbar')).toBeDefined();
        expect(screen.getByTestId('action-use-my-location')).toBeDefined();
        expect(screen.getByTestId('action-reset-location')).toBeDefined();
      });
    });
  });
});

