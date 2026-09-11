import React, { useState, useRef } from 'react';
import {
  Building2,
  MapPin,
  Camera,
  Film,
  UploadCloud,
  ShieldCheck,
  AlertTriangle,
  X,
  Sliders,
  Flame,
  Compass,
  Plus,
  Trash2,
  Image as ImageIcon,
} from 'lucide-react';

const formatFileSize = (bytes) => {
  if (!bytes || bytes === 0) return '';
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

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

export default function UploadScreen({ onSubmit, error }) {
  const [address, setAddress] = useState('Dwarka Sector 12, New Delhi');
  const [propertyType, setPropertyType] = useState('Apartment');
  const [imageUrl, setImageUrl] = useState('');
  const [images, setImages] = useState([]);
  const [imageError, setImageError] = useState('');
  const [isReadingImage, setIsReadingImage] = useState(false);

  const [videoBase64, setVideoBase64] = useState('');
  const [videoFileName, setVideoFileName] = useState('');
  const [videoType, setVideoType] = useState('');
  const [videoError, setVideoError] = useState('');
  const [isReadingVideo, setIsReadingVideo] = useState(false);

  const [imageType, setImageType] = useState('RGB');

  // Dedicated Thermal Scan State
  const [thermalBase64, setThermalBase64] = useState('');
  const [thermalFileName, setThermalFileName] = useState('');
  const [thermalSize, setThermalSize] = useState(0);
  const [thermalError, setThermalError] = useState('');
  const [isReadingThermal, setIsReadingThermal] = useState(false);

  const [showUrlInput, setShowUrlInput] = useState(false);
  const [urlDraft, setUrlDraft] = useState('');

  const imageInputRef = useRef(null);
  const videoInputRef = useRef(null);
  const thermalInputRef = useRef(null);

  // Match address to a verified preset for real coordinates & map
  const activePreset = PRESETS.find((p) =>
    address.trim().toLowerCase().includes(p.locality.toLowerCase()) ||
    address.trim().toLowerCase() === p.val.toLowerCase()
  );

  const handleImageFileChange = async (event) => {
    const files = Array.from(event.target.files || []);
    setImageError('');

    if (files.length === 0) {
      return;
    }

    const validFiles = [];
    const errorMessages = [];

    for (const file of files) {
      if (!file.type.startsWith('image/')) {
        errorMessages.push(`"${file.name}" is not a valid image file.`);
        continue;
      }
      if (file.size > 8 * 1024 * 1024) {
        errorMessages.push(`"${file.name}" exceeds the 8 MB limit.`);
        continue;
      }
      validFiles.push(file);
    }

    if (errorMessages.length > 0) {
      setImageError(errorMessages.join(' '));
    }

    if (validFiles.length === 0) {
      event.target.value = '';
      return;
    }

    setIsReadingImage(true);

    try {
      const readPromises = validFiles.map((file) => {
        return new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => {
            if (typeof reader.result === 'string') {
              resolve({
                id: `${file.name}-${file.size}-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`,
                base64: reader.result,
                fileName: file.name,
                size: file.size,
                type: 'RGB',
              });
            } else {
              reject(new Error(`Failed to encode image ${file.name}`));
            }
          };
          reader.onerror = () => reject(new Error(`Failed to read image ${file.name}`));
          reader.readAsDataURL(file);
        });
      });

      const loadedImages = await Promise.all(readPromises);

      // Append to existing images without replacing previously selected ones
      setImages((prev) => [...prev, ...loadedImages]);

      // Clear video and remote URL
      setVideoBase64('');
      setVideoFileName('');
      setVideoType('');
      setImageUrl('');
    } catch (err) {
      console.error('Error reading images:', err);
      setImageError('One or more selected images could not be processed.');
    } finally {
      setIsReadingImage(false);
      if (event.target) {
        event.target.value = '';
      }
    }
  };

  const handleThermalFileChange = (event) => {
    const file = event.target.files?.[0];
    setThermalError('');

    if (!file) {
      return;
    }

    if (!file.type.startsWith('image/')) {
      setThermalError('Select a valid radiometric thermal image file (JPEG, PNG, or WebP).');
      event.target.value = '';
      return;
    }

    if (file.size > 8 * 1024 * 1024) {
      setThermalError('Thermal scan images must be 8 MB or smaller.');
      event.target.value = '';
      return;
    }

    const reader = new FileReader();
    setIsReadingThermal(true);
    reader.onload = () => {
      setIsReadingThermal(false);
      if (typeof reader.result !== 'string') {
        setThermalError('The selected thermal scan could not be encoded for analysis.');
        return;
      }
      setThermalBase64(reader.result);
      setThermalFileName(file.name);
      setThermalSize(file.size);
    };
    reader.onerror = () => {
      setIsReadingThermal(false);
      setThermalError('The selected thermal scan could not be read.');
    };
    reader.readAsDataURL(file);
    event.target.value = '';
  };

  const clearThermal = () => {
    setThermalBase64('');
    setThermalFileName('');
    setThermalSize(0);
    setThermalError('');
    if (thermalInputRef.current) thermalInputRef.current.value = '';
  };

  const handleVideoFileChange = (event) => {
    const file = event.target.files?.[0];
    setVideoError('');

    if (!file) {
      return;
    }

    if (!file.type.startsWith('video/')) {
      setVideoError('Select a valid property video file (MP4, WebM, or MOV).');
      event.target.value = '';
      return;
    }

    if (file.size > 30 * 1024 * 1024) {
      setVideoError('Property videos must be 30 MB or smaller.');
      event.target.value = '';
      return;
    }

    const reader = new FileReader();
    setIsReadingVideo(true);
    reader.onload = () => {
      setIsReadingVideo(false);
      if (typeof reader.result !== 'string') {
        setVideoError('The selected video could not be encoded for analysis.');
        return;
      }
      setVideoBase64(reader.result);
      setVideoFileName(file.name);
      setVideoType(file.type);
      setImages([]);
      setImageUrl('');
    };
    reader.onerror = () => {
      setIsReadingVideo(false);
      setVideoError('The selected video could not be read.');
    };
    reader.readAsDataURL(file);
  };

  const handleRemoveImage = (idToRemove) => {
    setImages((prev) => prev.filter((img) => img.id !== idToRemove));
    if (images.length <= 1) {
      setImageError('');
      if (imageInputRef.current) imageInputRef.current.value = '';
    }
  };

  const handleUpdateImageType = (id, newType) => {
    setImages((prev) =>
      prev.map((img) => (img.id === id ? { ...img, type: newType } : img))
    );
  };

  const clearAllImages = () => {
    setImages([]);
    setImageError('');
    if (imageInputRef.current) imageInputRef.current.value = '';
  };

  const clearVideo = () => {
    setVideoBase64('');
    setVideoFileName('');
    setVideoType('');
    setVideoError('');
    if (videoInputRef.current) videoInputRef.current.value = '';
  };

  const clearUrl = () => {
    setImageUrl('');
    setUrlDraft('');
    setShowUrlInput(false);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!address.trim()) return;

    const hasVisualEvidence = Boolean(videoBase64 || images.length > 0 || imageUrl.trim());
    const hasThermal = Boolean(thermalBase64);

    let imageInfoPayload = null;

    if (hasVisualEvidence || hasThermal) {
      imageInfoPayload = {};

      if (videoBase64) {
        imageInfoPayload.video_base64 = videoBase64;
        imageInfoPayload.video_type = videoType;
        imageInfoPayload.file_name = videoFileName || null;
      } else if (images.length > 0) {
        imageInfoPayload.image_base64 = images[0].base64;
        imageInfoPayload.file_name = images[0].fileName;
        imageInfoPayload.image_type = images[0].type || 'RGB';
        imageInfoPayload.images = images.map((img) => ({
          image_base64: img.base64,
          file_name: img.fileName,
          image_type: img.type || 'RGB',
          size: img.size,
        }));
      } else if (imageUrl.trim()) {
        imageInfoPayload.image_url = imageUrl.trim();
        imageInfoPayload.image_type = 'RGB';
        imageInfoPayload.file_name = imageUrl.split('/').pop() || null;
      }

      if (hasThermal) {
        imageInfoPayload.thermal_base64 = thermalBase64;
        imageInfoPayload.thermal_file_name = thermalFileName;
        // If no visual photos were provided, also populate image_base64 as thermal for backward compatibility
        if (!hasVisualEvidence) {
          imageInfoPayload.image_base64 = thermalBase64;
          imageInfoPayload.image_type = 'Thermal';
          imageInfoPayload.file_name = thermalFileName;
        }
      }
    }

    const payload = {
      address: address.trim(),
      property_type: propertyType,
      image_info: imageInfoPayload,
    };

    onSubmit(payload);
  };

  return (
    <div className="analyze-screen">
      {/* Main Heading & Subtitle */}
      <div className="analyze-header">
        <h1 className="analyze-title">Analyze a Property</h1>
        <p className="analyze-subtitle">Assess the property using the evidence you have available.</p>
      </div>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {/* Desktop 2-Column Layout / Mobile Stacked: Property Details & Location */}
        <div className="inspection-grid">
          {/* LEFT COLUMN — PROPERTY DETAILS */}
          <div className="card property-details-card">
            <div className="card-section-header">
              <Building2 size={18} className="section-icon" />
              <h3>Property Details</h3>
            </div>

            <div className="form-group">
              <label htmlFor="address">Property Address / Locality *</label>
              <input
                id="address"
                type="text"
                placeholder="Dwarka Sector 12, New Delhi"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                required
              />
              <div className="preset-container">
                <span className="preset-label">Verified Localities:</span>
                <div className="preset-chips">
                  {PRESETS.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className={`preset-chip ${activePreset?.id === p.id ? 'active' : ''}`}
                      onClick={() => {
                        setAddress(p.val);
                        setPropertyType(p.type);
                      }}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label htmlFor="propertyType">
                <Sliders size={14} style={{ display: 'inline', marginRight: 6 }} />
                Property Type *
              </label>
              <select
                id="propertyType"
                value={propertyType}
                onChange={(e) => setPropertyType(e.target.value)}
              >
                <option value="Apartment">Apartment / Flat</option>
                <option value="Independent House">Independent House</option>
                <option value="Villa">Villa / Builder Floor</option>
                <option value="Commercial Space">Commercial Space</option>
              </select>
            </div>
          </div>

          {/* RIGHT COLUMN — LOCATION */}
          <div className="card property-location-card">
            <div className="card-section-header">
              <MapPin size={18} className="section-icon" />
              <h3>Property Location</h3>
            </div>

            {activePreset ? (
              <div className="location-verified-content">
                <div className="location-meta-row">
                  <div>
                    <span className="location-name">{activePreset.locality}</span>
                    <span className="location-subcity">{activePreset.subcity}, {activePreset.city}</span>
                  </div>
                  <span className="location-coords-badge">
                    {activePreset.lat.toFixed(4)}° N, {activePreset.lon.toFixed(4)}° E
                  </span>
                </div>

                <div className="location-map-wrapper">
                  <iframe
                    title={`OpenStreetMap - ${activePreset.locality}`}
                    className="location-map-frame"
                    src={`https://www.openstreetmap.org/export/embed.html?bbox=${activePreset.lon - 0.009}%2C${activePreset.lat - 0.006}%2C${activePreset.lon + 0.009}%2C${activePreset.lat + 0.006}&layer=mapnik&marker=${activePreset.lat}%2C${activePreset.lon}`}
                    loading="lazy"
                  />
                </div>

                <div className="location-footer-meta">
                  <span className="location-source-tag">OpenStreetMap Nominatim</span>
                  <span className="location-landmark">{activePreset.landmark}</span>
                </div>
              </div>
            ) : (
              <div className="location-pending-content">
                <div className="location-meta-row">
                  <div>
                    <span className="location-name">{address.trim() || 'Custom Address'}</span>
                    <span className="location-subcity">Dynamic GIS Resolution</span>
                  </div>
                  <span className="location-coords-badge location-pending-badge">
                    Pending Analysis
                  </span>
                </div>

                <div className="location-pending-box">
                  <Compass size={28} className="pending-icon" />
                  <p className="pending-title">Live Geocoding Pipeline</p>
                  <p className="pending-desc">
                    OpenStreetMap Nominatim will geocode coordinates and query Overpass API for schools, transit, and emergency infrastructure during analysis.
                  </p>
                </div>

                <div className="location-footer-meta">
                  <span className="location-source-tag">Nominatim & Overpass API</span>
                  <span className="location-landmark">Real-time resolution</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* BELOW — PROPERTY EVIDENCE */}
        <div className="card property-evidence-card">
          <div className="card-section-header">
            <Camera size={18} className="section-icon" />
            <div>
              <h3>Property Evidence</h3>
              <p className="section-subtitle">Add property photos or a walkthrough video for visible condition analysis.</p>
            </div>
          </div>

          <div className="evidence-body">
            <input
              type="file"
              ref={imageInputRef}
              accept="image/jpeg,image/png,image/webp"
              multiple
              style={{ display: 'none' }}
              onChange={handleImageFileChange}
            />
            <input
              type="file"
              ref={videoInputRef}
              accept="video/mp4,video/webm,video/quicktime"
              style={{ display: 'none' }}
              onChange={handleVideoFileChange}
            />

            {/* Multiple Images Preview Gallery */}
            {images.length > 0 ? (
              <div className="evidence-multi-container">
                <div className="evidence-multi-toolbar">
                  <div className="evidence-multi-heading">
                    <span className="evidence-count-badge">
                      <ImageIcon size={14} />
                      {images.length} {images.length === 1 ? 'Photo' : 'Photos'} Selected
                    </span>
                    <span className="evidence-multi-hint">
                      All photos will be included in the inspection request.
                    </span>
                  </div>
                  <div className="evidence-multi-actions">
                    <button
                      type="button"
                      className="btn-add-more-photos"
                      onClick={() => imageInputRef.current?.click()}
                      title="Add additional property photos"
                    >
                      <Plus size={14} />
                      <span>Add More Photos</span>
                    </button>
                    <button
                      type="button"
                      className="btn-clear-all-photos"
                      onClick={clearAllImages}
                      title="Clear all photos"
                    >
                      <Trash2 size={13} />
                      <span>Clear All</span>
                    </button>
                  </div>
                </div>

                <div className="evidence-thumbnails-grid">
                  {images.map((img, idx) => (
                    <div key={img.id} className="evidence-thumbnail-item">
                      <div className="evidence-thumbnail-img-wrap">
                        <img src={img.base64} alt={img.fileName} className="evidence-thumbnail-preview" />
                        <span className="evidence-item-index">#{idx + 1}</span>
                        <button
                          type="button"
                          className="btn-remove-thumb"
                          onClick={() => handleRemoveImage(img.id)}
                          title={`Remove ${img.fileName}`}
                          aria-label={`Remove photo ${idx + 1}`}
                        >
                          <X size={13} />
                        </button>
                      </div>
                      <div className="evidence-item-details">
                        <div className="evidence-item-name-row">
                          <span className="evidence-item-name" title={img.fileName}>{img.fileName}</span>
                        </div>
                        <div className="evidence-item-meta-row">
                          <span className="evidence-item-size">{formatFileSize(img.size)}</span>
                          <div className="evidence-item-cat-picker">
                            <select
                              value={img.type || imageType}
                              onChange={(e) => handleUpdateImageType(img.id, e.target.value)}
                              aria-label={`Category for ${img.fileName}`}
                            >
                              <option value="RGB">Visual (RGB)</option>
                              <option value="Defect">Defect</option>
                            </select>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}

                  {/* Add more button tile in grid */}
                  <button
                    type="button"
                    className="evidence-add-tile"
                    onClick={() => imageInputRef.current?.click()}
                    title="Select more photos"
                  >
                    <div className="evidence-add-tile-icon">
                      <Plus size={20} />
                    </div>
                    <span className="evidence-add-tile-label">Add Photos</span>
                    <span className="evidence-add-tile-hint">Select files to append</span>
                  </button>
                </div>
              </div>
            ) : videoBase64 ? (
              <div className="evidence-preview-card">
                <div className="evidence-video-thumb">
                  <Film size={26} />
                </div>
                <div className="evidence-info">
                  <span className="evidence-filename">{videoFileName || 'walkthrough-video.mp4'}</span>
                  <span className="evidence-meta">Walkthrough Video · Samples ~1 frame every 2s for condition analysis</span>
                </div>
                <button type="button" className="btn-remove-evidence" onClick={clearVideo} title="Remove video">
                  <X size={16} />
                </button>
              </div>
            ) : imageUrl.trim() ? (
              <div className="evidence-preview-card">
                <img
                  src={imageUrl}
                  alt="Property URL thumbnail"
                  className="evidence-thumb"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }}
                />
                <div className="evidence-info">
                  <span className="evidence-filename">{imageUrl}</span>
                  <span className="evidence-meta">Remote URL evidence</span>
                  <div className="evidence-cat-picker">
                    <label>Category:</label>
                    <select value={imageType} onChange={(e) => setImageType(e.target.value)}>
                      <option value="RGB">Standard Visual (RGB)</option>
                      <option value="Defect">Close-up Structural Defect</option>
                    </select>
                  </div>
                </div>
                <button type="button" className="btn-remove-evidence" onClick={clearUrl} title="Remove URL">
                  <X size={16} />
                </button>
              </div>
            ) : (
              <div className="upload-dropzone">
                <div className="upload-dropzone-inner">
                  <UploadCloud size={32} className="upload-icon" />
                  <h4>Add Property Photos or Walkthrough Video</h4>
                  <p className="upload-hint">
                    Add property photos for visible condition analysis. You can select multiple images from different rooms, walls, or angles.
                  </p>

                  <div className="upload-actions">
                    <button
                      type="button"
                      className="btn-upload-choice"
                      onClick={() => imageInputRef.current?.click()}
                    >
                      <Camera size={15} />
                      <span>Add Property Photos</span>
                    </button>
                    <button
                      type="button"
                      className="btn-upload-choice"
                      onClick={() => videoInputRef.current?.click()}
                    >
                      <Film size={15} />
                      <span>Upload Video</span>
                    </button>
                  </div>

                  <div className="upload-multi-note">
                    <span className="upload-multi-pill">Multiple photos supported</span>
                    <span>You can select multiple images at once or add more later.</span>
                  </div>

                  <div className="upload-url-toggle">
                    {!showUrlInput ? (
                      <button
                        type="button"
                        className="btn-link"
                        onClick={() => setShowUrlInput(true)}
                      >
                        or provide an image URL
                      </button>
                    ) : (
                      <div className="url-input-row">
                        <input
                          type="url"
                          placeholder="https://example.com/property-facade.jpg"
                          value={urlDraft}
                          onChange={(e) => setUrlDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault();
                              if (urlDraft.trim()) {
                                setImageUrl(urlDraft.trim());
                                setShowUrlInput(false);
                              }
                            }
                          }}
                        />
                        <button
                          type="button"
                          className="btn-secondary-sm"
                          onClick={() => {
                            if (urlDraft.trim()) {
                              setImageUrl(urlDraft.trim());
                              setShowUrlInput(false);
                            }
                          }}
                        >
                          Attach
                        </button>
                        <button
                          type="button"
                          className="btn-link"
                          onClick={() => setShowUrlInput(false)}
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>

                  <span className="upload-limits">
                    Supported formats: JPEG, PNG, WebP (up to 8 MB each) · MP4, WebM, MOV (up to 30 MB)
                  </span>
                </div>
              </div>
            )}

            {imageError && <div className="field-error">{imageError}</div>}
            {videoError && <div className="field-error">{videoError}</div>}
          </div>
        </div>

        {/* BELOW UPLOAD: Thermal Scan (Optional) */}
        <div className="card thermal-scan-card">
          <div className="thermal-card-inner">
            <div className="thermal-info">
              <div className="thermal-title-row">
                <Flame size={18} className="section-icon" />
                <span className="thermal-title">Thermal Scan</span>
                <span className="badge-optional">Optional</span>
              </div>
              <p className="thermal-subtitle">
                Connect thermal sensor or provide thermal scan data when available.
              </p>
            </div>

            <div className="thermal-status-panel">
              <div className="thermal-status-row">
                <span className="thermal-status-label">Status:</span>
                <span className={`thermal-status-pill ${thermalBase64 ? 'status-provided' : 'status-not-provided'}`}>
                  {thermalBase64 ? 'Thermal scan provided' : 'Not provided'}
                </span>
              </div>

              {thermalBase64 ? (
                <div className="thermal-preview-card">
                  <div className="thermal-preview-thumb-wrap">
                    <img src={thermalBase64} alt="Thermal radiometric scan preview" className="thermal-preview-thumb" />
                    <span className="thermal-preview-badge">IR Scan</span>
                  </div>
                  <div className="thermal-preview-meta">
                    <span className="thermal-preview-name" title={thermalFileName}>{thermalFileName}</span>
                    <span className="thermal-preview-desc">
                      {formatFileSize(thermalSize)} · Radiometric IR scan · Ready for thermal insulation analysis
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn-remove-thumb"
                    onClick={clearThermal}
                    title="Remove thermal scan"
                  >
                    <X size={13} />
                  </button>
                </div>
              ) : (
                <div className="thermal-upload-box">
                  <p className="thermal-upload-note">
                    Thermal analysis evaluates building envelope insulation, draft leaks, and temperature variance using radiometric thermal images (FLIR / IR camera) or an MLX90640 I2C sensor. Normal visual photographs are not thermal data.
                  </p>
                  <div className="thermal-action-row">
                    <button
                      type="button"
                      className="btn-secondary-sm btn-thermal-upload"
                      onClick={() => thermalInputRef.current?.click()}
                    >
                      <UploadCloud size={14} />
                      <span>Upload Thermal Scan</span>
                    </button>
                    <span className="thermal-unavail-note">
                      If omitted, Thermal remains <em>Unavailable (null)</em> without scoring penalty.
                    </span>
                  </div>
                </div>
              )}

              <input
                type="file"
                ref={thermalInputRef}
                accept="image/jpeg,image/png,image/webp"
                style={{ display: 'none' }}
                onChange={handleThermalFileChange}
              />

              {thermalError && <div className="field-error">{thermalError}</div>}
            </div>
          </div>
        </div>

        {/* PRIMARY BUTTON: Analyze Property */}
        <div className="analyze-submit-section">
          <button
            type="submit"
            className="btn-primary btn-analyze-large"
            disabled={!address.trim() || isReadingImage || isReadingVideo || isReadingThermal}
          >
            {isReadingImage || isReadingVideo || isReadingThermal ? (
              <>
                <div className="spinner" />
                <span>Reading Evidence...</span>
              </>
            ) : (
              <>
                <ShieldCheck size={18} />
                <span>Analyze Property</span>
              </>
            )}
          </button>
          <p className="analyze-disclaimer">
            Real-time multi-criteria scoring evaluates active modules. Missing inputs remain explicitly null without synthetic fabrication.
          </p>
        </div>
      </form>
    </div>
  );
}
