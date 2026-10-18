import os
import sys
import time
import types

# Ensure the 'backend' package namespace is available regardless of whether Python
# is started from the repository root (e.g. pytest, local dev) or from within the
# backend directory itself (e.g. Vercel Functions service root).
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if "backend" not in sys.modules:
    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [current_dir]
    backend_pkg.__file__ = os.path.join(current_dir, "__init__.py")
    sys.modules["backend"] = backend_pkg

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.api.score import router as score_router
from backend.api.livability import router as livability_router
from backend.api.disaster import router as disaster_router
from backend.api.documents import router as documents_router

app = FastAPI(
    title="NIVAS Property Inspection & Scoring API",
    description="Backend API for building defect inspection, thermal analysis, location risk, and composite property scoring.",
    version="1.0.0",
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing & performance header middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.6f}s"
    return response


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred.", "error": str(exc)},
    )


# Register API routes
app.include_router(score_router)
app.include_router(livability_router)
app.include_router(disaster_router)
app.include_router(documents_router)


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "service": "NIVAS Backend API",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)