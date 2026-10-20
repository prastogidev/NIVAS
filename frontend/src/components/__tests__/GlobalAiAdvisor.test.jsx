import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
        setLatLng: vi.fn(),
        getLatLng: () => ({ lat: 28.5921, lng: 77.0460 }),
        bindPopup: function() { return this; },
        on: vi.fn(),
      }),
      divIcon: () => ({}),
    },
  };
});

describe('NIVAS Global Floating AI Advisor & Minimized-by-Default Behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    if (typeof window !== 'undefined') {
      window.location.hash = '';
      if (window.localStorage?.clear) {
        window.localStorage.clear();
      }
    }

    vi.spyOn(api, 'fetchLivabilityLocationData').mockResolvedValue({
      location: {
        latitude: 28.5921,
        longitude: 77.0460,
        address: 'Dwarka Sector 12, South West Delhi, Delhi',
      },
      infrastructure: { status: 'active', facilities: [] },
      air_quality: { status: 'active', aqi_value: 120, category: 'Moderate' },
    });
  });

  it('Requirement 1: Opens in minimized circular icon state by default on fresh page load without auto-expanding', async () => {
    render(<App />);

    // Circular floating launcher is present
    const launcher = screen.getByTestId('advisor-launcher-btn');
    expect(launcher).toBeTruthy();
    expect(launcher.getAttribute('aria-label')).toBe('Open NIVAS AI Advisor');

    // Expanded chat panel is NOT open
    expect(screen.queryByTestId('floating-advisor-panel')).toBeNull();
  });

  it('Requirement 2: Floating launcher is persistent across all 4 workspaces with exactly ONE instance', async () => {
    render(<App />);

    // 1. Livability workspace (default)
    expect(screen.getByTestId('advisor-launcher-btn')).toBeTruthy();
    expect(screen.getAllByTestId('advisor-launcher-btn').length).toBe(1);

    // 2. Switch to Disaster & Climate Hazards workspace
    const disasterTab = screen.getByRole('button', { name: /^Disaster Hazards$/i });
    fireEvent.click(disasterTab);
    expect(screen.getByTestId('advisor-launcher-btn')).toBeTruthy();
    expect(screen.getAllByTestId('advisor-launcher-btn').length).toBe(1);

    // 3. Switch to Property Inspection workspace
    const inspectionTab = screen.getByRole('button', { name: /^Property Inspection$/i });
    fireEvent.click(inspectionTab);
    expect(screen.getByTestId('advisor-launcher-btn')).toBeTruthy();
    expect(screen.getAllByTestId('advisor-launcher-btn').length).toBe(1);

    // 4. Switch to Document Intelligence workspace
    const documentsTab = screen.getByRole('button', { name: /^Document Intelligence$/i });
    fireEvent.click(documentsTab);
    expect(screen.getByTestId('advisor-launcher-btn')).toBeTruthy();
    expect(screen.getAllByTestId('advisor-launcher-btn').length).toBe(1);
  });

  it('Requirement 3: Expands into full chat panel on click, and collapses back to circular launcher on minimize', async () => {
    render(<App />);

    const launcher = screen.getByTestId('advisor-launcher-btn');
    expect(screen.queryByTestId('floating-advisor-panel')).toBeNull();

    // Click launcher to expand
    fireEvent.click(launcher);
    expect(screen.getByTestId('floating-advisor-panel')).toBeTruthy();
    expect(screen.getByTestId('chat-panel-title')).toBeTruthy();

    // Click minimize button to collapse
    const minimizeBtn = screen.getByTestId('minimize-advisor-btn');
    fireEvent.click(minimizeBtn);

    // Chat panel closes, circular launcher returns
    expect(screen.queryByTestId('floating-advisor-panel')).toBeNull();
    expect(screen.getByTestId('advisor-launcher-btn')).toBeTruthy();
  });

  it('Requirement 4: Preserves conversation state and messages when navigating between tabs and minimize cycles', async () => {
    vi.spyOn(api, 'sendLivabilityChatMessage').mockResolvedValue({
      reply: 'Dwarka Sector 12 has multiple parks, verified schools, and metro station nearby.',
      sources: ['OpenStreetMap Overpass API'],
      is_ai_generated: false,
      provider_configured: false,
    });

    render(<App />);

    // Open advisor chat
    fireEvent.click(screen.getByTestId('advisor-launcher-btn'));
    expect(screen.getByTestId('floating-advisor-panel')).toBeTruthy();

    // Send a message
    const chatInput = screen.getByPlaceholderText(/Ask about neighborhood livability/i);
    const sendBtn = screen.getByRole('button', { name: /Send message/i });

    fireEvent.change(chatInput, { target: { value: 'How is the transit accessibility here?' } });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(screen.getByText(/Dwarka Sector 12 has multiple parks/i)).toBeTruthy();
    });

    // Minimize advisor
    fireEvent.click(screen.getByTestId('minimize-advisor-btn'));
    expect(screen.queryByTestId('floating-advisor-panel')).toBeNull();

    // Navigate to Disaster workspace
    const disasterTab = screen.getByRole('button', { name: /^Disaster Hazards$/i });
    fireEvent.click(disasterTab);

    // Reopen advisor on Disaster workspace
    fireEvent.click(screen.getByTestId('advisor-launcher-btn'));
    expect(screen.getByTestId('floating-advisor-panel')).toBeTruthy();

    // User message and advisor response are preserved
    expect(screen.getByText('How is the transit accessibility here?')).toBeTruthy();
    expect(screen.getByText(/Dwarka Sector 12 has multiple parks/i)).toBeTruthy();
  });

  it('Requirement 5: Document Intelligence "Open in Neighborhood Advisor" opens the global chat panel with staged files', async () => {
    render(<App />);

    // Navigate to Document Intelligence
    const documentsTab = screen.getByRole('button', { name: /^Document Intelligence$/i });
    fireEvent.click(documentsTab);

    // Initial state: Advisor minimized
    expect(screen.queryByTestId('floating-advisor-panel')).toBeNull();

    // In Document Intelligence tab, click "Open in Neighborhood Advisor"
    const openInChatBtn = screen.getByTestId('doc-bridge-to-chat-btn');
    fireEvent.click(openInChatBtn);

    // Advisor opens with chat panel visible
    await waitFor(() => {
      expect(screen.getByTestId('floating-advisor-panel')).toBeTruthy();
    });
  });
});
