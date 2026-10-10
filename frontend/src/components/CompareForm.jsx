import React, { useState } from 'react';
import { Building2, MapPin, Scale, AlertTriangle, Info, Sliders, Compass } from 'lucide-react';

import PropertyLocationPicker from './PropertyLocationPicker';

export default function CompareForm({ onSubmit, error }) {
  // Property A State
  const [addressA, setAddressA] = useState('Dwarka Sector 12, New Delhi');
  const [typeA, setTypeA] = useState('Apartment');
  const [latA, setLatA] = useState(28.5921);
  const [lonA, setLonA] = useState(77.0460);

  // Property B State
  const [addressB, setAddressB] = useState('Connaught Place, New Delhi');
  const [typeB, setTypeB] = useState('Commercial Space');
  const [latB, setLatB] = useState(28.6315);
  const [lonB, setLonB] = useState(77.2167);

  const handleLocationChangeA = ({ latitude, longitude, address, reverseGeocoded }) => {
    setLatA(latitude);
    setLonA(longitude);
    if (reverseGeocoded && address) {
      setAddressA(address);
    }
  };

  const handleLocationChangeB = ({ latitude, longitude, address, reverseGeocoded }) => {
    setLatB(latitude);
    setLonB(longitude);
    if (reverseGeocoded && address) {
      setAddressB(address);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!addressA.trim() || !addressB.trim()) return;

    const comparePayload = {
      property_a: {
        address: addressA.trim(),
        property_type: typeA,
      },
      property_b: {
        address: addressB.trim(),
        property_type: typeB,
      },
    };

    onSubmit(comparePayload);
  };

  return (
    <div className="card upload-card">
      <div className="card-header">
        <Scale style={{ color: 'var(--ink-deep)' }} size={28} />
        <div>
          <h2>Dual Property Comparison Engine</h2>
          <p className="card-subtitle">Submit two real property locations to run parallel risk, pricing, visual defect, and thermal evaluation</p>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="compare-grid">
          {/* Property A Column */}
          <div className="compare-column">
            <div className="column-header column-header-a">
              <span className="prop-badge prop-badge-a">Property A</span>
              <h3>Primary Property</h3>
            </div>

            <div className="form-group">
              <label htmlFor="addressA">
                <MapPin size={14} style={{ display: 'inline', marginRight: 4 }} />
                Address / Locality A *
              </label>
              <input
                id="addressA"
                type="text"
                placeholder="e.g. Dwarka Sector 12, New Delhi"
                value={addressA}
                onChange={(e) => setAddressA(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="typeA">
                <Sliders size={14} style={{ display: 'inline', marginRight: 4 }} />
                Property Type A *
              </label>
              <select id="typeA" value={typeA} onChange={(e) => setTypeA(e.target.value)}>
                <option value="Apartment">Apartment / Flat</option>
                <option value="Independent House">Independent House</option>
                <option value="Villa">Villa / Builder Floor</option>
                <option value="Commercial Space">Commercial Space</option>
              </select>
            </div>

            {/* Property A Location Map */}
            <div className="compare-map-section">
              <div className="compare-map-header">
                <MapPin size={14} style={{ color: 'var(--ink-deep)' }} />
                <span>Property A Location Map</span>
              </div>
              <div className="compare-map-container" style={{ padding: '0.65rem' }}>
                <PropertyLocationPicker
                  latitude={latA}
                  longitude={lonA}
                  onLocationChange={handleLocationChangeA}
                  mapHeight={240}
                />
                <div className="compare-map-footer" style={{ marginTop: '0.5rem' }}>
                  <span className="compare-location-tag">{addressA.trim() || 'Selected Location A'}</span>
                  <span className="compare-coords-tag">{latA.toFixed(4)}°N, {lonA.toFixed(4)}°E</span>
                </div>
              </div>
            </div>
          </div>

          {/* Property B Column */}
          <div className="compare-column">
            <div className="column-header column-header-b">
              <span className="prop-badge prop-badge-b">Property B</span>
              <h3>Comparison Property</h3>
            </div>

            <div className="form-group">
              <label htmlFor="addressB">
                <MapPin size={14} style={{ display: 'inline', marginRight: 4 }} />
                Address / Locality B *
              </label>
              <input
                id="addressB"
                type="text"
                placeholder="e.g. Connaught Place, New Delhi"
                value={addressB}
                onChange={(e) => setAddressB(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="typeB">
                <Sliders size={14} style={{ display: 'inline', marginRight: 4 }} />
                Property Type B *
              </label>
              <select id="typeB" value={typeB} onChange={(e) => setTypeB(e.target.value)}>
                <option value="Apartment">Apartment / Flat</option>
                <option value="Independent House">Independent House</option>
                <option value="Villa">Villa / Builder Floor</option>
                <option value="Commercial Space">Commercial Space</option>
              </select>
            </div>

            {/* Property B Location Map */}
            <div className="compare-map-section">
              <div className="compare-map-header">
                <MapPin size={14} style={{ color: '#2D2D2D' }} />
                <span>Property B Location Map</span>
              </div>
              <div className="compare-map-container" style={{ padding: '0.65rem' }}>
                <PropertyLocationPicker
                  latitude={latB}
                  longitude={lonB}
                  onLocationChange={handleLocationChangeB}
                  mapHeight={240}
                />
                <div className="compare-map-footer" style={{ marginTop: '0.5rem' }}>
                  <span className="compare-location-tag">{addressB.trim() || 'Selected Location B'}</span>
                  <span className="compare-coords-tag">{latB.toFixed(4)}°N, {lonB.toFixed(4)}°E</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="info-box">
          <Info size={18} style={{ color: '#8B1E2D', flexShrink: 0, marginTop: 2 }} />
          <div style={{ fontSize: '0.85rem', color: '#2D2D2D' }}>
            <strong>Comparison Rule:</strong> Both properties are evaluated using the identical scoring engine and weights (Location 25%, Price 25%, CV 30%, Thermal 20%). Disconnected modules or unassessed inputs are flagged as <code>Not assessed</code> for that property without fabricating numbers.
          </div>
        </div>

        <button type="submit" className="btn-primary" disabled={!addressA.trim() || !addressB.trim()} style={{ marginTop: '1.5rem' }}>
          <Scale size={18} />
          <span>Launch Dual Property Comparison</span>
        </button>
      </form>
    </div>
  );
}
