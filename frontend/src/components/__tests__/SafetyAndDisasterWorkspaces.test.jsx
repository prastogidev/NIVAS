import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SafetyIntelligenceView from '../SafetyIntelligenceView';
import DisasterWorkspace from '../DisasterWorkspace';
import App from '../../App';
import * as api from '../../services/api';

// Mock Leaflet
vi.mock('leaflet', () => {
  const mockMap = {
    setView: vi.fn(),
    getZoom: () => 14,
    remove: vi.fn(),
    invalidateSize: vi.fn(),
    on: vi.fn(),
    fitBounds: vi.fn(),
  };

  const mockLayerGroup = {
    addTo: vi.fn(function() { return this; }),
    clearLayers: vi.fn(function() { return this; }),
  };

  return {
    default: {
      map: () => mockMap,
      tileLayer: () => ({ addTo: () => {} }),
      layerGroup: () => mockLayerGroup,
      geoJSON: () => ({ addTo: () => {} }),
      polygon: () => ({ addTo: () => {} }),
      circle: () => ({ addTo: () => {} }),
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
    },
    nearby_police_stations: [
      {
        name: 'Dwarka Sector 23 Police Station',
        latitude: 28.5833,
        longitude: 77.0500,
        distance_km: 1.1,
        address: 'Sector 23, Dwarka, Delhi',
      },
      {
        name: 'Dwarka North Police Station',
        latitude: 28.6050,
        longitude: 77.0400,
        distance_km: 1.5,
        address: 'Sector 16B, Dwarka, Delhi',
      },
    ],
  };

  beforeEach(() => {
    vi.spyOn(api, 'fetchSafetyData').mockResolvedValue(mockSafetyResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders official district name, rates, and clearance statistics correctly', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Dwarka (South-West) Crime Intelligence')).toBeDefined();
    });

    expect(screen.getByText('342.5')).toBeDefined();
    expect(screen.getByText('41.2%')).toBeDefined();
    expect(screen.getAllByText('7,850').length).toBeGreaterThanOrEqual(1);
  });

  it('renders crime categories with truthful numbers and clearance rates', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Theft & Motor Vehicle Theft')).toBeDefined();
    });

    expect(screen.getByText(/4,200 cases/i)).toBeDefined();
    expect(screen.getByText('Violent Crimes (Robbery, Murder, Assault)')).toBeDefined();
  });

  it('renders OSM-verified local police stations', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Dwarka Sector 23 Police Station')).toBeDefined();
    });

    expect(screen.getByText(/1.10? km/i)).toBeDefined();
    expect(screen.getByText('Dwarka North Police Station')).toBeDefined();
    expect(screen.getByText(/1.50? km/i)).toBeDefined();
  });

  it('renders statutory disclosures and official data provenance', async () => {
    render(
      <SafetyIntelligenceView
        location={{ latitude: 28.5921, longitude: 77.0460, address: 'Dwarka Sector 12, Delhi' }}
        onLocationChange={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Safety Data Integrity & Methodology Disclosures/i)
      ).toBeDefined();
    });
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
      hazards: [
        {
          hazard_type: 'earthquake',
          title: 'Earthquake Hazard (Seismic Zone IV)',
          severity: 'high',
          category: 'static_zonal',
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
});
