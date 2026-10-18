# NIVAS — Vercel Multi-Service Deployment Guide

Canonical Repository: [https://github.com/prastogidev/NIVAS](https://github.com/prastogidev/NIVAS)  
Production URL: [https://nivas-one.vercel.app](https://nivas-one.vercel.app)

---

## 1. Architecture & Deployment Model

NIVAS deploys to Vercel as a single project using official **Vercel Services** architecture declared in [`vercel.json`](../vercel.json):

```
                   ┌────────────────────────────────────────┐
                   │          Vercel Edge Network           │
                   │        https://nivas-one.vercel.app    │
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

---

## 2. Environment Variables Matrix

All external API integrations are designed with deterministic fallbacks when API keys are not supplied. Set these in **Vercel Project Settings > Environment Variables**:

| Variable Name | Required | Default Fallback if Unset | Purpose |
| :--- | :---: | :--- | :--- |
| `GEMINI_API_KEY` | Optional | Rule-based advisor tagged `[AI Provider Not Configured]` | Google Gemini generative livability analysis |
| `OPENAI_API_KEY` | Optional | Gemini or rule-based fallback | Secondary generative advisor fallback |
| `OPENWEATHER_API_KEY` | Optional | Open-Meteo or fallback baseline | Real-time Delhi air pollution telemetry |
| `AQICN_TOKEN` | Optional | Open-Meteo or fallback baseline | Alternative air quality station telemetry |
| `PROPSTACK_API_KEY` | Optional | Delhi MCD circle rate categories & local benchmark cache | Commercial property valuation benchmark |
| `DATA_GOV_IN_API_KEY` | Optional | Local official historical crime baseline | OGD India automated synchronization |
| `VITE_API_BASE_URL` | Optional | `""` (current origin via Vercel rewrites) | Custom API domain override for the frontend |

> [!SECURITY]
> **Zero Secret Leaks**: Never commit `.env` or `.env.local` files to Git. All secrets must be securely configured within the Vercel Dashboard or injected during secure CI runners.

---

## 3. Deployment Workflow

### Step 1: Pre-Deployment Verification
Before triggering a deployment, always verify local tests and build:
```bash
# Backend pytest suite (144 tests)
backend/venv/bin/pytest backend/tests

# Frontend vitest suite (77 tests)
cd frontend && npm test -- --run

# Frontend production bundle build
npm run build
cd ..
```

### Step 2: Deploying to Preview
Deploy a preview environment to validate changes in isolation before touching production:
```bash
npx vercel
```
This generates a unique preview URL (e.g. `https://nivas-xyz-sukoon14.vercel.app`).

### Step 3: Verifying the Preview Deployment
Test endpoints against the preview URL:
```bash
# Health check endpoint
curl -s -o /dev/null -w "%{http_code}\n" https://<preview-url>/health

# Livability location telemetry
curl -s -X POST https://<preview-url>/api/livability/location-data \
  -H "Content-Type: application/json" \
  -d '{"latitude": 28.5921, "longitude": 77.0460, "radius": 1200}'

# Safety intelligence
curl -s "https://<preview-url>/api/safety/delhi-crime-data?lat=28.5921&lng=77.0460"
```

### Step 4: Deploying to Production
> [!IMPORTANT]
> Deploy to production only after user approval and verified preview tests.

```bash
npx vercel --prod
```
The production deployment will automatically update the canonical production alias:
[https://nivas-one.vercel.app](https://nivas-one.vercel.app)

---

## 4. Handling Deployment Protection

When Vercel **Deployment Protection** (Password Protection, SSO, or Vercel Authentication) is enabled for Preview deployments:
- Direct `curl` requests without credentials will return HTTP `401 Unauthorized` or redirect to Vercel SSO.
- To test preview deployments with protection enabled:
  1. Use the Vercel Protection Bypass Header or automation token securely:
     ```bash
     curl -H "x-vercel-protection-bypass: <TOKEN>" https://<preview-url>/health
     ```
  2. Or test through an authenticated browser session where you are logged in to the Vercel team.
  3. Never log or output secret protection tokens in public terminal outputs or reports.
