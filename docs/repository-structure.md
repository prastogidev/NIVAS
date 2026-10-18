# NIVAS — Repository Structure & Git Workflow Guide

Canonical Repository: [https://github.com/prastogidev/NIVAS](https://github.com/prastogidev/NIVAS)  
Production URL: [https://nivas-one.vercel.app](https://nivas-one.vercel.app)

---

## 1. Architectural Overview & Branch Topology

NIVAS utilizes a **multi-service Git Submodule architecture** hosted within a single GitHub repository (`prastogidev/NIVAS`). The repository contains two distinct, intentional branches with divergent tree layouts:

```
GitHub Remote: https://github.com/prastogidev/NIVAS.git
│
├── branch: main (Default Branch)
│   ├── vercel.json                  # Vercel multi-service routing definition
│   ├── docs/                        # Centralized documentation
│   ├── frontend/                    # React 18 + Vite SPA client
│   │   ├── src/
│   │   ├── package.json
│   │   └── vite.config.js
│   ├── .gitmodules                  # Declares backend submodule
│   └── backend @ 95a630e            # Git submodule pointer (mode 160000) -> branch 'backend'
│
└── branch: backend (Service Branch)
    ├── main.py                      # FastAPI application entrypoint
    ├── requirements.txt             # Backend Python dependencies
    ├── api/                         # FastAPI route modules (livability, disaster, documents, score)
    ├── services/                    # Business logic & telemetry engines
    ├── models/                      # Pydantic schemas & data models
    ├── data/                        # Static geojson boundaries, crime baselines, and benchmarks
    └── tests/                       # 144 unit and integration tests
```

---

## 2. The GitHub "Compare & pull request" Banner

### Why GitHub Displays This Banner
Whenever commits are pushed to the `backend` branch, GitHub displays a notification banner on the repository homepage:
> **backend had recent pushes less than a minute ago — [Compare & pull request]**

This is **normal, automated GitHub platform behavior**. GitHub assumes every non-default branch is a temporary feature branch intended to be merged back into `main`.

> [!WARNING]
> **DO NOT CLICK "Compare & pull request" OR MERGE `backend` INTO `main`.**
> Merging the `backend` branch directly into `main` will corrupt the repository layout, create severe file conflicts, and break Vercel deployments.

### Concrete Consequences of Merging `backend` into `main`
If a pull request from `backend` into `main` is merged:
1. **Directory Tree Clobbering**: The root files of `backend` (`main.py`, `requirements.txt`, `api/`, `services/`, `models/`, `data/`) would be dumped into the root directory of `main`.
2. **Submodule Pointer Invalidation**: The Git submodule link at `backend/` would not be updated correctly; instead, root files would duplicate or conflict with submodule contents.
3. **Vercel Multi-Service Breakage**: In [`vercel.json`](../vercel.json), Vercel specifies:
   ```json
   "services": {
     "frontend": { "path": "frontend" },
     "backend": { "path": "backend" }
   }
   ```
   Vercel requires the FastAPI service source code to live exclusively inside the `backend/` directory. Scattering files into the repository root breaks build discovery and deployment routing.
4. **Git Tree Divergence**: Root and backend histories have different root trees. Forcing a merge creates confusing commit graphs and phantom merge conflicts.

### How to Resolve and Dismiss the Banner
- **Dismiss in Browser**: Click the **`X`** on the right side of the banner to dismiss it.
- **Ignore the Prompt**: Treat the `backend` branch as an independent branch dedicated to serving the `backend/` submodule.
- **Branch Protection**: You can configure a Branch Protection Rule on GitHub (`Settings > Branches`) to require pull requests with specific reviews before merging to `main`, preventing accidental one-click merges.
- **Vercel Preview Protection**: Vercel's Ignored Build Step is configured to cancel builds automatically on the `backend` branch (`if [ "$VERCEL_GIT_COMMIT_REF" = "backend" ] || [ ! -f vercel.json ]; then exit 0; else exit 1; fi`), preventing routine submodule pushes from generating failed preview deployments. See [`docs/deployment.md`](./deployment.md).

---

## 3. Directory Layout Reference

| Path | Purpose | Tracked On |
| :--- | :--- | :--- |
| `vercel.json` | Vercel multi-service routing (`/api/*` -> backend, `/*` -> frontend) | `main` |
| `.gitmodules` | Maps the `backend/` folder to `origin/backend` | `main` |
| `.gitignore` | Ignores `.env*`, `node_modules/`, `venv/`, `.vercel/`, cache files | `main` |
| `docs/` | Comprehensive architectural, development, and deployment documentation | `main` |
| `frontend/` | React SPA source code, components, tests, and build assets | `main` |
| `backend/` | Git submodule checkout of the FastAPI backend application | Pointer in `main`, code in `backend` |

---

## 4. Standard Contribution Workflows

### Scenario A: Modifying Frontend Code
Frontend files live directly in the `main` branch under `frontend/`.
```bash
git checkout main
git pull origin main

# Edit frontend files in frontend/src/
cd frontend
npm test -- --run
npm run build
cd ..

git add frontend/
git commit -m "feat(frontend): add feature description"
git push origin main
```

### Scenario B: Modifying Backend Code
Backend files live in the submodule under `backend/` (branch `backend`).
```bash
# Navigate to backend submodule
cd backend
git checkout backend
git pull origin backend

# Make changes, run backend tests
venv/bin/pytest tests/

# Commit and push within the submodule
git add api/ services/ tests/
git commit -m "feat(backend): implement endpoint"
git push origin backend

# Step back to root repository and update submodule pointer
cd ..
git add backend
git commit -m "chore(backend): bump backend submodule pointer"
git push origin main
```

### Scenario C: Cloning Fresh Repository
Always clone with submodule initialization:
```bash
git clone --recurse-submodules https://github.com/prastogidev/NIVAS.git
cd NIVAS
```
If cloned without `--recurse-submodules`:
```bash
git submodule update --init --recursive
```
