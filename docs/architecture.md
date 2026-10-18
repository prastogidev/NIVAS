# NIVAS — System Architecture & Data Flow

Canonical Repository: [https://github.com/prastogidev/NIVAS](https://github.com/prastogidev/NIVAS)  
Production URL: [https://nivas-one.vercel.app](https://nivas-one.vercel.app)

---

## 1. High-Level Architecture Overview

NIVAS (*Neighborhood Intelligence & Verification Analytics System*) is an evidence-grounded urban analytics and property due-diligence platform. The application is architected around **two decoupled tiers** deployed via **Vercel Services**:

```
                              ┌──────────────────────────────────────────────┐
                              │            Client Web Browser                │
                              │       React 18 + Vite (Tailwind / CSS)       │
                              └──────────────────────┬───────────────────────┘
                                                     │
                                                     ▼
                              ┌──────────────────────────────────────────────┐
                              │             Vercel Edge Ingress              │
                              │           https://nivas-one.vercel.app       │
                              └──────────────┬────────────────┬──────────────┘
                                             │                │
                        Path: /api/*, /health│                │Path: /* (SPA routes)
                                             ▼                ▼
                             ┌───────────────────┐  ┌───────────────────┐
                             │  FastAPI Backend  │  │ Frontend Web App  │
                             │  (Python 3.10+)   │  │ (Vite Static SPA) │
                             └─────────┬─────────┘  └───────────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐
│ OpenStreetMap Mirrors │  │  Environmental Feeds  │  │ Local Verified Assets │
│ Overpass API (4 nodes)│  │ Open-Meteo / AQICN /  │  │ Delhi GeoJSON Hazard, │
│ Nominatim Geocoding   │  │ OpenWeather Air API   │  │ Crime Baseline, Rates │
└───────────────────────┘  └───────────────────────┘  └───────────────────────┘
```

---

## 2. Vercel Multi-Service Routing

The deployment configuration is declared in [`vercel.json`](../vercel.json):

```json
{
  "version": 2,
  "services": {
    "frontend": {
      "path": "frontend"
    },
    "backend": {
      "path": "backend"
    }
  },
  "routes": [
    { "src": "/api/(.*)", "dest": "backend" },
    { "src": "/health", "dest": "backend" },
    { "src": "/(.*)", "dest": "frontend" }
  ]
}
```

### Ingress Separation
- **`/api/*` & `/health`**: Routed directly to the FastAPI application inside `backend/main.py`.
- **`/*`**: Routed to the Vite static SPA (`frontend/dist`), serving `index.html` with client-side history fallback.
- **Service Bindings**: None required. The frontend is a client-side browser SPA calling public same-origin HTTPS endpoints (`/api/*`). The backend does not call secondary internal Vercel microservices.

---

## 3. Core Workspaces & Data Flows

### Workspace 1: Neighborhood Livability Intelligence
- **Spatial Pinpointing**: Leaflet-based interactive map with Nominatim forward/reverse geocoding.
- **Civic Infrastructure Telemetry**: Queries 4 Overpass API mirrors concurrently (`asyncio.as_completed`) for 13 civic categories (schools, hospitals, public transit, emergency services, roads) within configurable radii (500m – 3000m).
- **Network Resilience**: Circuit-breaker pattern isolates temporary mirror network outages (`status: fetch_failed`) from confirmed zero amenities (`status: empty`).
- **Environmental Context**: Live PM2.5, PM10, and AQI from Open-Meteo Air Quality API with fallback to seasonal Delhi baselines.
- **Neighborhood AI Advisor**: Context-grounded conversational assistant powered by Google Gemini (via `@google/genai`), Groq, or deterministic rule-based analysis.

### Workspace 2: Safety & Crime Intelligence
- **Boundary Precision**: Ray-casting point-in-polygon resolution across 15 official Delhi Police District GeoJSON approximations.
- **Grounded Compendiums**: NCRB and Delhi Police statistical data benchmarks.
- **Integrity Disclosures**: District-level spatial allocations are explicitly distinguished from station-level micro-counts.
- **Composite Safety Index**: Multi-factor model integrating street lighting density, emergency service proximity, transit accessibility, and localized benchmarks.

### Workspace 3: Disaster & Environmental Hazards
- **Hazard Zoning**: GeoJSON hazard layer mapping Yamuna floodplains, low-lying alluvial depressions, and BIS Seismic Zone IV classifications for the National Capital Region.
- **Thermal Proxies**: Urban Heat Island (UHI) temperature anomaly estimations.
- **Truthful Telemetry**: Real-time Doppler radar and satellite feeds report honest unavailable states when live external feeds are offline.

### Workspace 4: Property Inspection & Risk Scoring
- **Computer Vision Defect Classification**: PyTorch EfficientNet-B0 model trained to detect structural defects (cracks, dampness/efflorescence, spalling, algae, clean walls) with blur detection and multi-image aggregation.
- **Thermal Gradient Analysis**: MLX90640 32x24 sensor driver and 2D spatial median anomaly detection for insulation voids and moisture pockets.
- **Valuation Fairness**: Mathematical benchmarking comparing asking prices against Delhi MCD circle rate categories (A through H) with TTL caching.
- **Normalized Composite Score**: Dynamically re-normalizes weights (CV 30%, Thermal 20%, Location 25%, Price 25%) when specific telemetry modules are omitted, marking results as provisional when coverage is incomplete.

### Workspace 5: Document Intelligence
- **Contract & Deed Extraction**: Fast regex and layout-aware parser extracting party entities, consideration amounts, property identifiers, and registration metadata from Sale Deeds and Agreements.
- **Discrepancy Engine**: Cross-document verification engine that flags mismatches in purchase amounts, plot dimensions, or grantor/grantee names across transaction chains.
- **Integrity Disclaimer**: Clearly states that extraction is a decision-support heuristic, not a legal title guarantee.

---

## 4. Git Submodule Service Pattern

To satisfy Vercel Services requirements without duplicating code or creating multiple independent GitHub projects:
1. Root repository (`main` branch) contains the project root, configuration files, frontend application, and documentation.
2. The `backend` folder is mounted as a Git submodule tracking the `backend` branch of the same repository.
3. This guarantees that `backend` can be developed, tested, and version-tagged independently while retaining a single GitHub repository URL.
