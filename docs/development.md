# NIVAS — Local Development & Contribution Guide

Canonical Repository: [https://github.com/prastogidev/NIVAS](https://github.com/prastogidev/NIVAS)  
Production URL: [https://nivas-one.vercel.app](https://nivas-one.vercel.app)

---

## 1. Prerequisites

Ensure the following tools are installed on your workstation:
- **Node.js**: v18.x or higher (`node -v`, `npm -v`)
- **Python**: v3.10 or higher (`python3 --version`)
- **Git**: v2.30 or higher (`git --version`)

---

## 2. Getting Started & Cloning

NIVAS uses a Git Submodule pattern for its backend service. Always clone with recursive submodule fetching:

```bash
git clone --recurse-submodules https://github.com/prastogidev/NIVAS.git
cd NIVAS
```

If you previously cloned without `--recurse-submodules`, initialize the backend submodule manually:
```bash
git submodule update --init --recursive
```

---

## 3. Backend Setup

The FastAPI backend lives in the `backend/` directory.

```bash
# 1. Enter the backend directory
cd backend

# 2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. (Optional) Configure environment variables
cp .env.example .env

# 5. Start the backend development server
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Verify backend health at: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) or browse interactive docs at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

## 4. Frontend Setup

The React 18 + Vite frontend lives in the `frontend/` directory.

```bash
# In a new terminal tab from repository root:
cd frontend

# 1. Install Node dependencies
npm install

# 2. Start the Vite development server
npm run dev
```

The frontend will be accessible at: [http://localhost:5173](http://localhost:5173). In development mode, Vite proxies `/api` requests to `http://127.0.0.1:8000` via [`vite.config.js`](../frontend/vite.config.js).

---

## 5. Running Tests

Both backend and frontend have comprehensive test suites that must pass before any commit.

### Backend Pytest Suite (144 Tests)
Run from the repository root:
```bash
backend/venv/bin/pytest backend/tests
```
Or from inside `backend/`:
```bash
cd backend
source venv/bin/activate
pytest tests/
```
*Expected: 144 passed.*

### Frontend Vitest Suite (77 Tests)
Run from inside `frontend/`:
```bash
cd frontend
npm test -- --run
```
*Expected: 77 passed.*

### Production Build Verification
Ensure the frontend builds without bundle or syntax errors:
```bash
cd frontend
npm run build
```

---

## 6. Git Contribution Workflow

### Working on the Frontend
1. Ensure you are on the `main` branch: `git checkout main`
2. Make your edits in `frontend/src/`
3. Run tests and build: `cd frontend && npm test -- --run && npm run build`
4. Stage and commit:
   ```bash
   git add frontend/
   git commit -m "feat(frontend): add descriptive summary"
   git push origin main
   ```

### Working on the Backend
1. Navigate into `backend/`: `cd backend`
2. Ensure you are on the `backend` branch: `git checkout backend`
3. Make your edits in `backend/api/`, `backend/services/`, etc.
4. Run tests: `pytest tests/`
5. Commit and push inside `backend/`:
   ```bash
   git add .
   git commit -m "feat(api): add descriptive summary"
   git push origin backend
   ```
6. Return to root and update the submodule pointer:
   ```bash
   cd ..
   git add backend
   git commit -m "chore(backend): bump backend submodule pointer"
   git push origin main
   ```

> [!CAUTION]
> **Never open a Pull Request from `backend` to `main` on GitHub.**
> Follow the guidance in [`docs/repository-structure.md`](./repository-structure.md).
