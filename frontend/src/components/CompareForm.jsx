import React, { useState } from 'react';
import { Building2, MapPin, Image as ImageIcon, Scale, AlertTriangle, Info, Sliders, Compass } from 'lucide-react';

const PRESETS = [
  {
    id: 'dwarka',
    label: 'Dwarka Sec 12',
    val: 'Dwarka Sector 12, New Delhi',
    type: 'Apartment',
    locality: 'Dwarka Sector 12',
    city: 'New Delhi',
    lat: 28.5921,
    lon: 77.0460,
    subcity: 'South West Delhi',
    landmark: 'DDA Sports Complex / Metro Blue Line',
  },
  {
    id: 'rohini',
    label: 'Rohini Sec 8',
    val: 'Rohini Sector 8, New Delhi',
    type: 'Apartment',
    locality: 'Rohini Sector 8',
    city: 'New Delhi',
    lat: 28.7041,
    lon: 77.1172,
    subcity: 'North West Delhi',
    landmark: 'Rajiv Gandhi Cancer Institute / Metro Red Line',
  },
  {
    id: 'lajpat',
    label: 'Lajpat Nagar 2',
    val: 'Lajpat Nagar 2, New Delhi',
    type: 'Commercial Space',
    locality: 'Lajpat Nagar 2',
    city: 'New Delhi',
    lat: 28.5677,
    lon: 77.2433,
    subcity: 'South Delhi',
    landmark: 'Central Market / Metro Violet & Pink Lines',
  },
  {
    id: 'cp',
    label: 'Connaught Place',
    val: 'Connaught Place, New Delhi',
    type: 'Commercial Space',
    locality: 'Connaught Place',
    city: 'New Delhi',
    lat: 28.6315,
    lon: 77.2167,
    subcity: 'Central Delhi',
    landmark: 'Rajiv Chowk / Radial Financial Corridor',
  },
];

export default function CompareForm({ onSubmit, error }) {
  // Property A State
  const [addressA, setAddressA] = useState('Dwarka Sector 12, New Delhi');
  const [typeA, setTypeA] = useState('Apartment');
  const [imageUrlA, setImageUrlA] = useState('');
  const [imageTypeA, setImageTypeA] = useState('RGB');

  // Property B State
  const [addressB, setAddressB] = useState('Connaught Place, New Delhi');
  const [typeB, setTypeB] = useState('Commercial Space');
  const [imageUrlB, setImageUrlB] = useState('');
  const [imageTypeB, setImageTypeB] = useState('RGB');

  const presetA = PRESETS.find((p) => p.val.toLowerCase() === addressA.trim().toLowerCase());
  const presetB = PRESETS.find((p) => p.val.toLowerCase() === addressB.trim().toLowerCase());

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!addressA.trim() || !addressB.trim()) return;

    const comparePayload = {
      property_a: {
        address: addressA.trim(),
        property_type: typeA,
        image_info: imageUrlA.trim() ? { image_url: imageUrlA.trim(), image_type: imageTypeA } : null
      },
      property_b: {
        address: addressB.trim(),
        property_type: typeB,
        image_info: imageUrlB.trim() ? { image_url: imageUrlB.trim(), image_type: imageTypeB } : null
      }
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

      {/* Preset Pair Selectors */}
      <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '1.25rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Quick Compare Presets:</span>
        <button
          type="button"
          className="btn-secondary-sm"
          onClick={() => {
            setAddressA('Dwarka Sector 12, New Delhi');
            setTypeA('Apartment');
            setAddressB('Lajpat Nagar 2, New Delhi');
            setTypeB('Commercial Space');
          }}
        >
          Dwarka vs Lajpat Nagar
        </button>
        <button
          type="button"
          className="btn-secondary-sm"
          onClick={() => {
            setAddressA('Rohini Sector 8, New Delhi');
            setTypeA('Apartment');
            setAddressB('Lajpat Nagar 2, New Delhi');
            setTypeB('Commercial Space');
          }}
        >
          Rohini vs Lajpat Nagar
        </button>
        <button
          type="button"
          className="btn-secondary-sm"
          onClick={() => {
            setAddressA('Dwarka Sector 12, New Delhi');
            setTypeA('Apartment');
            setAddressB('Rohini Sector 8, New Delhi');
            setTypeB('Apartment');
          }}
        >
          Dwarka vs Rohini
        </button>
      </div>

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

            <div className="form-group">
              <label htmlFor="imageUrlA">
                <ImageIcon size={14} style={{ display: 'inline', marginRight: 4 }} />
                Property Image A URL (Optional)
              </label>
              <input
                id="imageUrlA"
                type="url"
                placeholder="https://example.com/property-a.jpg"
                value={imageUrlA}
                onChange={(e) => setImageUrlA(e.target.value)}
              />
            </div>

            {imageUrlA.trim() && (
              <div className="form-group">
                <label htmlFor="imageTypeA">Image Category A</label>
                <select id="imageTypeA" value={imageTypeA} onChange={(e) => setImageTypeA(e.target.value)}>
                  <option value="RGB">Standard Visual (RGB)</option>
                  <option value="Thermal">Thermal Infrared</option>
                  <option value="Defect">Close-up Defect Scan</option>
                </select>
              </div>
            )}
            {/* Property A Location Map */}
            <div className="compare-map-section">
              <div className="compare-map-header">
                <MapPin size={14} style={{ color: 'var(--ink-deep)' }} />
                <span>Property A Location Map</span>
              </div>
              {presetA ? (
                <div className="compare-map-container">
                  <iframe
                    title={`OpenStreetMap - ${presetA.locality}`}
                    className="location-map-frame"
                    src={`https://www.openstreetmap.org/export/embed.html?bbox=${presetA.lon - 0.009}%2C${presetA.lat - 0.006}%2C${presetA.lon + 0.009}%2C${presetA.lat + 0.006}&layer=mapnik&marker=${presetA.lat}%2C${presetA.lon}`}
                    loading="lazy"
                  />
                  <div className="compare-map-footer">
                    <span>{presetA.locality}, {presetA.city}</span>
                    <span className="compare-coords-tag">{presetA.lat.toFixed(3)}°N, {presetA.lon.toFixed(3)}°E</span>
                  </div>
                </div>
              ) : (
                <div className="compare-map-pending">
                  <Compass size={22} className="pending-icon" />
                  <p className="compare-pending-text">
                    <strong>{addressA.trim() || 'Address A'}</strong>
                  </p>
                  <span className="compare-pending-subtext">Coordinates resolved via Nominatim GIS</span>
                </div>
              )}
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

            <div className="form-group">
              <label htmlFor="imageUrlB">
                <ImageIcon size={14} style={{ display: 'inline', marginRight: 4 }} />
                Property Image B URL (Optional)
              </label>
              <input
                id="imageUrlB"
                type="url"
                placeholder="https://example.com/property-b.jpg"
                value={imageUrlB}
                onChange={(e) => setImageUrlB(e.target.value)}
              />
            </div>

            {imageUrlB.trim() && (
              <div className="form-group">
                <label htmlFor="imageTypeB">Image Category B</label>
                <select id="imageTypeB" value={imageTypeB} onChange={(e) => setImageTypeB(e.target.value)}>
                  <option value="RGB">Standard Visual (RGB)</option>
                  <option value="Thermal">Thermal Infrared</option>
                  <option value="Defect">Close-up Defect Scan</option>
                </select>
              </div>
            )}

            {/* Property B Location Map */}
            <div className="compare-map-section">
              <div className="compare-map-header">
                <MapPin size={14} style={{ color: '#2D2D2D' }} />
                <span>Property B Location Map</span>
              </div>
              {presetB ? (
                <div className="compare-map-container">
                  <iframe
                    title={`OpenStreetMap - ${presetB.locality}`}
                    className="location-map-frame"
                    src={`https://www.openstreetmap.org/export/embed.html?bbox=${presetB.lon - 0.009}%2C${presetB.lat - 0.006}%2C${presetB.lon + 0.009}%2C${presetB.lat + 0.006}&layer=mapnik&marker=${presetB.lat}%2C${presetB.lon}`}
                    loading="lazy"
                  />
                  <div className="compare-map-footer">
                    <span>{presetB.locality}, {presetB.city}</span>
                    <span className="compare-coords-tag">{presetB.lat.toFixed(3)}°N, {presetB.lon.toFixed(3)}°E</span>
                  </div>
                </div>
              ) : (
                <div className="compare-map-pending">
                  <Compass size={22} className="pending-icon" />
                  <p className="compare-pending-text">
                    <strong>{addressB.trim() || 'Address B'}</strong>
                  </p>
                  <span className="compare-pending-subtext">Coordinates resolved via Nominatim GIS</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="info-box">
          <Info size={18} style={{ color: '#8B1E2D', flexShrink: 0, marginTop: 2 }} />
          <div style={{ fontSize: '0.85rem', color: '#2D2D2D' }}>
            <strong>Comparison Rule:</strong> Both properties are evaluated using the identical scoring engine and weights (Location 25%, Price 25%, CV 30%, Thermal 20%). Unprovided images or disconnected hardware are flagged as <code>Disconnected (null)</code> for that property without fabricating numbers.
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
