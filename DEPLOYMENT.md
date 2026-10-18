# NIVAS — Vercel Multi-Service Deployment Guide

> [!NOTE]
> **Documentation Library**: This guide is mirrored and maintained in the centralized documentation suite at [`docs/deployment.md`](./docs/deployment.md). For architecture and repository structure, see [`docs/architecture.md`](./docs/architecture.md) and [`docs/repository-structure.md`](./docs/repository-structure.md).

**Canonical GitHub Repository:** [https://github.com/prastogidev/NIVAS](https://github.com/prastogidev/NIVAS)  
**Project Name:** NIVAS (Neighborhood Intelligence & Verification Analytics System)

---

## 1. Multi-Service Architecture Overview

NIVAS deploys to Vercel as a unified project using official **Vercel Services** (Beta) syntax in [`vercel.json`](file:///Users/piyushrastogi/NIVAS/vercel.json). Both frontend and backend are maintained within this repository and deployed together on a shared domain.

```
                  ┌────────────────────────────────────────┐
                  │          Vercel Edge Network           │
                  │        https://<project>.vercel.app     │
                  └──────────────────┬─────────────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           │                                                   │
  Path: /api/* or /health                              Path: /* (All other routes)
           │                                                   │
           ▼                                                   ▼
┌───────────────────────┐                           ┌─────────────────────┐
│    Backend Service    │                           │  Frontend Service   │
│ root: backend/        │                           │ root: frontend/     │
│ framework: fastapi    │                           │ framework: vite     │
│ entrypoint: main:app  │                           │ output: dist        │
└───────────────────────┘                           └─────────────────────┘
```

### Services & Ingress Routing

| Service | Root Directory | Framework | Entrypoint | Output Dir | Routes Handled |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`frontend`** | `frontend/` | `vite` | N/A | `dist` | `/*` (Static assets, SPA index.html fallback) |
| **`backend`** | `backend/` | `fastapi` | `main:app` | N/A | `/api/(.*)`, `/health` (REST API & diagnostics) |

### Service Bindings
- **Declared Bindings:** None.
- **Rationale:** The frontend is a client-side React SPA executing in the browser; it accesses FastAPI over public HTTPS same-origin rewrites (`/api/*`). The backend is self-contained and does not call any secondary internal Vercel services.

---

## 2. Environment Variables Configuration

Configure the following variables in the **Vercel Dashboard > Project Settings > Environment Variables**:

| Variable Name | Required | Default Fallback if Unset | Purpose |
| :--- | :---: | :--- | :--- |
| `GEMINI_API_KEY` | Optional | Rule-based advisor tagged `[AI Provider Not Configured]` | Google Gemini generative livability analysis |
| `OPENAI_API_KEY` | Optional | Gemini or rule-based fallback | Secondary generative advisor fallback |
| `OPENWEATHER_API_KEY` | Optional | AQICN token or `provider_not_configured` | Real-time Delhi Air Pollution telemetry |
| `AQICN_TOKEN` | Optional | `provider_not_configured` | Alternative air quality station telemetry |
| `PROPSTACK_API_KEY` | Optional | Delhi MCD circle rate categories & local benchmark cache | Commercial property valuation benchmark |
| `DATA_GOV_IN_API_KEY` | Optional | Local official historical crime baseline | OGD India automated synchronization |
| `VITE_API_BASE_URL` | Optional | `""` (current origin via Vercel rewrites) | Custom API domain override for the frontend |

> **Security Note:** Never commit `.env` or credentials to git. All keys must be stored in Vercel project environment variables.

---

## 3. Local Development & Simulation

Run the local development environment using either native dev servers or the Vercel CLI simulator:

### Option A: Native Dev Servers
```bash
# Terminal 1: FastAPI Backend
backend/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Terminal 2: React Frontend (proxies /api and /health to 127.0.0.1:8000)
cd frontend && npm run dev -- --port 3000
```

### Option B: Local Vercel Multi-Service Simulation
```bash
# Simulates full Vercel Services multi-service routing on port 4000
npx vercel dev -L --listen 127.0.0.1:4000 --yes
```

---

## 4. Deployment Procedure

### Prerequisites
1. Install Vercel CLI: `npm install -g vercel` (or use `npx vercel`).
2. Log in to Vercel account:
   ```bash
   npx vercel login
   ```
3. Link the repository:
   ```bash
   npx vercel link
   ```

### Step 1: Preview Deployment
```bash
npx vercel
```
- Verify the build logs in the Vercel Dashboard.
- Run smoke tests against the generated preview URL:
  - `curl -sI https://<preview-url>/health`
  - `curl -sI https://<preview-url>/`
  - `curl -s "https://<preview-url>/api/disaster/hazard-data?latitude=28.5921&longitude=77.046"`

### Step 2: Production Deployment
```bash
npx vercel --prod
```

---

## 5. Known Limitations & Troubleshooting

1. **PyTorch & Serverless Limits:**
   - Standard Vercel Serverless Functions enforce a 250MB uncompressed bundle limit.
   - PyTorch (`torch`) exceeds 800MB uncompressed. To ensure compatibility with standard serverless deployment, `cv_model.py` uses graceful import detection (`TORCH_AVAILABLE`).
   - When running in a standard serverless environment without PyTorch installed, computer vision inspection returns `None` for image defects, and NIVAS transparently discloses provisional composite scores with exact coverage percentages.
   - For full deep-learning image defect inference in production, configure the backend service with `"runtime": "container"` using a Dockerfile.
2. **Read-Only Serverless Filesystem:**
   - Vercel Serverless Functions execute on a read-only filesystem except for `/tmp`.
   - The price benchmark module utilizes local bundled static datasets under `backend/data/cached_demo_data/` and graceful fallback when runtime cache files cannot be persisted.
3. **External API Timeouts:**
   - Overpass OpenStreetMap mirrors and external government endpoints may occasionally experience network throttling. NIVAS includes built-in multi-mirror failover and explicit unavailable disclosures.
