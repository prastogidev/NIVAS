# NIVAS Feature Inventory & Baseline Audit

*Neighborhood Intelligence & Verification Analytics System*  
Canonical Repository: [https://github.com/prastogidev/NIVAS](https://github.com/prastogidev/NIVAS)  
Production Deployment: [https://nivas-one.vercel.app](https://nivas-one.vercel.app)

---

## 1. Module Inventory & Operational Status

Every feature in NIVAS is audited and classified into one of four states:
- **WORKING**: Fully implemented, verified with automated tests, real data or transparent fallbacks, and production-tested.
- **PARTIALLY WORKING**: Core flow functional, with documented boundary constraints, approximate models, or simulated external feeds.
- **BROKEN**: Implementation defective, failing tests, or non-functional.
- **NOT IMPLEMENTED**: Feature not yet built or wired into the system.

| Module | Feature / Component | Operational Status | Evidence & Data Grounding |
| :--- | :--- | :--- | :--- |
| **Livability & Amenities** | Overpass API Live OSM Fetch | **WORKING** | Queries real OpenStreetMap Overpass servers for 13 amenity categories (schools, hospitals, transit, etc.). Live distance calculations with caching and circuit breaker. |
| **Livability & Amenities** | Air Quality (AQI) Integration | **WORKING** | Real-time Open-Meteo Air Quality API with fallback to historical seasonal baselines when upstream is unavailable. Transparent status tags (`live`, `cached`, `fallback`). |
| **Livability & Amenities** | Livability Index Scoring | **WORKING** | Deterministic composite score (0–100) aggregating transit, health, education, retail, and environmental metrics. |
| **Safety & Crime Intelligence** | Official NCT Delhi Crime Data | **WORKING** | Grounded in official Delhi Police / NCRB statistical compendiums. NCT-wide crime statistics clearly separated from localized estimates. |
| **Safety & Crime Intelligence** | Police District Boundaries | **WORKING** | 15 Delhi police district approximations with explicit spatial disclosures. District per-capita rates suppressed when denominators are incompatible. |
| **Safety & Crime Intelligence** | Multi-Factor Safety Score | **WORKING** | Integrates lighting density, police proximity, transit accessibility, and verified incident benchmarks into safety score (0–100). |
| **Disaster Hazards Workspace** | Flood Risk Assessment | **WORKING** | Grounded in Delhi flood hazard zones (Yamuna floodplain, low-lying depressions, drainage proximity) with explicit elevation models. |
| **Disaster Hazards Workspace** | Seismic & Heat Risk | **WORKING** | Grounded in BIS Seismic Zone IV classification for NCR and urban heat island (UHI) thermal proxies. |
| **Disaster Hazards Workspace** | Live Disaster Feeds | **PARTIALLY WORKING** | IMD radar and live telemetry are marked as currently unavailable with honest status disclosures rather than fabricated live alerts. |
| **Disaster Hazards Workspace** | Location Hazard Comparison | **WORKING** | Cross-locality hazard comparative matrix with explicit evidence tags (`complete`, `partial_evidence`, `incomparable`). |
| **Property Inspection** | Visual Defect Detection | **WORKING** | Computer vision analysis for cracks, dampness/efflorescence, spalling, and surface degradation. |
| **Property Inspection** | Thermal Gradient Simulation | **WORKING** | Simulated infrared temperature gradient analysis detecting insulation voids and moisture anomalies. |
| **Property Inspection** | Multi-Property Comparison | **WORKING** | Side-by-side comparison matrix evaluating structural health, repair cost estimates, and risk index. |
| **Neighborhood AI Advisor** | Multi-Provider Chat Engine | **WORKING** | Supports Google Gemini (via `@google/genai`), Groq, and heuristic fallback. Complete provider status indicators in UI. |
| **Document Intelligence** | PDF / Text Metadata Extraction | **WORKING** | Structured extraction for Sale Deeds, Agreements, Conveyances, Parties, Consideration, Registration details with page citations. |
| **Document Intelligence** | Cross-Document Discrepancy Engine | **WORKING** | Automated diffing across transaction documents flagging mismatches in consideration, plot numbers, party names, and registration dates. |

---

## 2. Integrity and Telemetry Disclosures
1. **Official vs Derived Separation**: All district-level crime estimates in Delhi are explicitly flagged as spatial allocations rather than official station-level micro-counts.
2. **Disaster Data**: Static hazard risk zones are grounded in official CPCB/NDMA/BIS maps; live radar/satellite feeds report honest unavailable states.
3. **No Fabricated Data**: All API fallbacks explicitly disclose data source and state (`fallback_baseline`, `simulated`, or `unavailable`).
4. **Legal Status**: Property inspections and document intelligence are automated decision-support tools and explicitly disclaim legal title opinions or structural engineering guarantees.
