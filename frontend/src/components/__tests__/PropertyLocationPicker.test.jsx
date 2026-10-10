import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PropertyLocationPicker from '../PropertyLocationPicker';

// Mock Leaflet since jsdom does not support SVG / Canvas layout operations
vi.mock('leaflet', () => {
  const mockMap = {
    setView: () => {},
    getZoom: () => 15,
    remove: () => {},
    invalidateSize: () => {},
    on: () => {},
  };
  const mockMarker = {
    addTo: function() { return this; },
    setLatLng: () => {},
    getLatLng: () => ({ lat: 28.5921, lng: 77.0460 }),
    on: () => {},
  };

  return {
    default: {
      map: () => mockMap,
      tileLayer: () => ({ addTo: () => {} }),
      marker: () => mockMarker,
      divIcon: () => ({}),
    },
  };
});

describe('PropertyLocationPicker Location Search', () => {
  let originalFetch;

  beforeEach(() => {
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.clearAllMocks();
  });

  it('clicking Search does not submit parent form or reload page and calls geocoding', async () => {
    const parentSubmit = vi.fn((e) => e.preventDefault());
    const onLocationChange = vi.fn();

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          lat: '28.5921',
          lon: '77.0460',
          display_name: 'Dwarka Sector 12, South West Delhi, Delhi, India',
        },
      ],
    });

    render(
      <form onSubmit={parentSubmit}>
        <PropertyLocationPicker
          latitude={28.5921}
          longitude={77.0460}
          onLocationChange={onLocationChange}
        />
      </form>
    );

    const input = screen.getByPlaceholderText(/Search address or locality/i);
    const searchBtn = screen.getByRole('button', { name: /Search/i });

    // Ensure search button is type="button" to prevent parent form submission
    expect(searchBtn.getAttribute('type')).toBe('button');

    fireEvent.change(input, { target: { value: 'Dwarka Sector 12' } });
    fireEvent.click(searchBtn);

    // Parent form submission must NOT be called
    expect(parentSubmit).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
      expect(onLocationChange).toHaveBeenCalledWith(
        expect.objectContaining({
          latitude: 28.5921,
          longitude: 77.0460,
          address: 'Dwarka Sector 12, South West Delhi, Delhi, India',
          reverseGeocoded: true,
        })
      );
    });

    // Query remains intact in the input
    expect(input.value).toBe('Dwarka Sector 12');
  });

  it('pressing Enter in search input triggers search without parent form submission or reload', async () => {
    const parentSubmit = vi.fn((e) => e.preventDefault());
    const onLocationChange = vi.fn();

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          lat: '28.6304',
          lon: '77.3725',
          display_name: 'Indirapuram, Ghaziabad, Uttar Pradesh, India',
        },
      ],
    });

    render(
      <form onSubmit={parentSubmit}>
        <PropertyLocationPicker
          latitude={28.5921}
          longitude={77.0460}
          onLocationChange={onLocationChange}
        />
      </form>
    );

    const input = screen.getByPlaceholderText(/Search address or locality/i);

    fireEvent.change(input, { target: { value: 'Indirapuram, Ghaziabad' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    // Parent form submission must NOT be triggered
    expect(parentSubmit).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(onLocationChange).toHaveBeenCalledWith(
        expect.objectContaining({
          latitude: 28.6304,
          longitude: 77.3725,
          address: 'Indirapuram, Ghaziabad, Uttar Pradesh, India',
          reverseGeocoded: true,
        })
      );
    });

    // Query text remains preserved
    expect(input.value).toBe('Indirapuram, Ghaziabad');
  });

  it('shows clear error notice and preserves user query when search yields no results', async () => {
    const parentSubmit = vi.fn((e) => e.preventDefault());
    const onLocationChange = vi.fn();

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [], // No results
    });

    render(
      <form onSubmit={parentSubmit}>
        <PropertyLocationPicker
          latitude={28.5921}
          longitude={77.0460}
          onLocationChange={onLocationChange}
        />
      </form>
    );

    const input = screen.getByPlaceholderText(/Search address or locality/i);
    const searchBtn = screen.getByRole('button', { name: /Search/i });

    fireEvent.change(input, { target: { value: 'Nonexistent Place XYZ 9999' } });
    fireEvent.click(searchBtn);

    expect(parentSubmit).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(screen.getByText(/No matching locations found for "Nonexistent Place XYZ 9999"/i)).toBeTruthy();
    });

    // Location change should not have fired on empty search
    expect(onLocationChange).not.toHaveBeenCalled();
    // User input query is NOT wiped out
    expect(input.value).toBe('Nonexistent Place XYZ 9999');
  });

  it('handles network failure gracefully without wiping user input', async () => {
    const onLocationChange = vi.fn();

    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    render(
      <PropertyLocationPicker
        latitude={28.5921}
        longitude={77.0460}
        onLocationChange={onLocationChange}
      />
    );

    const input = screen.getByPlaceholderText(/Search address or locality/i);
    const searchBtn = screen.getByRole('button', { name: /Search/i });

    fireEvent.change(input, { target: { value: 'Rohini Sector 10' } });
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(screen.getByText(/Location search failed/i)).toBeTruthy();
    });

    expect(onLocationChange).not.toHaveBeenCalled();
    expect(input.value).toBe('Rohini Sector 10');
  });
});
