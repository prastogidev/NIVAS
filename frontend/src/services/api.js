import axios from 'axios';

// In production on Vercel and local dev with Vite proxy, use relative path ('') so requests
// map to the same origin (/api/* and /health). VITE_API_BASE_URL can override when needed.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined
  ? import.meta.env.VITE_API_BASE_URL
  : '';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

export const submitPropertyScore = async (payload) => {
  const response = await apiClient.post('/api/score', payload);
  return response.data;
};

export const compareProperties = async (comparePayload) => {
  const response = await apiClient.post('/api/score/compare', comparePayload);
  return response.data;
};

export const checkHealth = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};

export const fetchLivabilityLocationData = async ({ latitude, longitude, address, radius }, signal) => {
  const params = { latitude, longitude };
  if (address) params.address = address;
  if (typeof radius === 'number') params.radius = radius;
  const response = await apiClient.get('/api/livability/location-data', {
    params,
    signal,
  });
  return response.data;
};

export const sendLivabilityChatMessage = async (
  { query, latitude, longitude, address, context },
  signal
) => {
  const payload = { query, latitude, longitude };
  if (address) payload.address = address;
  if (context) payload.context = context;
  const response = await apiClient.post('/api/livability/chat', payload, {
    signal,
  });
  return response.data;
};

export const fetchSafetyData = async ({ latitude, longitude, address, radius }, signal) => {
  const params = { latitude, longitude };
  if (address) params.address = address;
  if (typeof radius === 'number') params.radius = radius;
  const response = await apiClient.get('/api/livability/safety-data', {
    params,
    signal,
  });
  return response.data;
};

export const fetchNationalSafetyOverview = async (signal) => {
  const response = await apiClient.get('/api/livability/national-safety-overview', { signal });
  return response.data;
};


export const fetchDisasterLayers = async (signal) => {
  const response = await apiClient.get('/api/disaster/layers', { signal });
  return response.data;
};

export const fetchDisasterLayerGeometry = async (layerId, signal) => {
  const response = await apiClient.get('/api/disaster/layer-geometry', {
    params: { layer_id: layerId },
    signal,
  });
  return response.data;
};

export const fetchDisasterHazardData = async ({ latitude, longitude, address }, signal) => {
  const params = { latitude, longitude };
  if (address) params.address = address;
  const response = await apiClient.get('/api/disaster/hazard-data', {
    params,
    signal,
  });
  return response.data;
};

export const compareDisasterLocations = async ({ location_a, location_b }, signal) => {
  const response = await apiClient.post(
    '/api/disaster/compare',
    { location_a, location_b },
    { signal }
  );
  return response.data;
};

export const analyzeDocuments = async (files, signal) => {
  const formData = new FormData();
  Array.from(files).forEach((file) => {
    formData.append('files', file);
  });
  const response = await apiClient.post('/api/documents/analyze', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    signal,
  });
  return response.data;
};

export const fetchSampleDocuments = async (signal) => {
  const response = await apiClient.get('/api/documents/sample-documents', { signal });
  return response.data;
};

export const compareExtractedDocuments = async (docs, signal) => {
  const response = await apiClient.post('/api/documents/compare', docs, { signal });
  return response.data;
};

