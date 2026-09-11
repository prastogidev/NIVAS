import React, { useState } from 'react';
import { Building2, MapPin, Image as ImageIcon, Send, AlertTriangle } from 'lucide-react';

export default function PropertyForm({ onSubmit, isLoading, error }) {
  const [address, setAddress] = useState('');
  const [propertyType, setPropertyType] = useState('Apartment');
  const [imageUrl, setImageUrl] = useState('');
  const [imageType, setImageType] = useState('RGB');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!address.trim()) return;

    const payload = {
      address: address.trim(),
      property_type: propertyType,
      image_info: imageUrl.trim() ? {
        image_url: imageUrl.trim(),
        image_type: imageType
      } : null
    };

    onSubmit(payload);
  };

  return (
    <div className="card">
      <div className="card-header">
        <Building2 style={{ color: 'var(--color-primary, #8B1E2D)' }} size={24} />
        <h2>Property Inspection Request</h2>
      </div>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="address">
            <MapPin size={14} style={{ display: 'inline', marginRight: 4 }} />
            Property Address / Locality *
          </label>
          <input
            id="address"
            type="text"
            placeholder="e.g. Dwarka Sector 12, New Delhi"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            required
            disabled={isLoading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="propertyType">Property Type *</label>
          <select
            id="propertyType"
            value={propertyType}
            onChange={(e) => setPropertyType(e.target.value)}
            disabled={isLoading}
          >
            <option value="Apartment">Apartment / Flat</option>
            <option value="Independent House">Independent House</option>
            <option value="Villa">Villa / Builder Floor</option>
            <option value="Commercial Space">Commercial Space</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="imageUrl">
            <ImageIcon size={14} style={{ display: 'inline', marginRight: 4 }} />
            Property Image URL (Optional)
          </label>
          <input
            id="imageUrl"
            type="url"
            placeholder="https://example.com/property-facade.jpg"
            value={imageUrl}
            onChange={(e) => setImageUrl(e.target.value)}
            disabled={isLoading}
          />
        </div>

        {imageUrl.trim() && (
          <div className="form-group">
            <label htmlFor="imageType">Image Category</label>
            <select
              id="imageType"
              value={imageType}
              onChange={(e) => setImageType(e.target.value)}
              disabled={isLoading}
            >
              <option value="RGB">Standard Visual (RGB)</option>
              <option value="Thermal">Thermal Infrared</option>
              <option value="Defect">Close-up Defect Scan</option>
            </select>
          </div>
        )}

        <button type="submit" className="btn-primary" disabled={isLoading || !address.trim()}>
          {isLoading ? (
            <>
              <div className="spinner" />
              <span>Analyzing Property...</span>
            </>
          ) : (
            <>
              <Send size={18} />
              <span>Submit for Inspection Score</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
}
