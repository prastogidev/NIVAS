#!/usr/bin/env python3
"""Verify all required imports for NIVAS backend"""
import sys

print("=" * 70)
print("NIVAS BACKEND - DEPENDENCY IMPORT VERIFICATION")
print("=" * 70)
print(f"\nPython Version: {sys.version}")
print(f"Python Executable: {sys.executable}\n")

# Define required packages
REQUIRED_IMPORTS = {
    "Core": [
        ("typing", "Python typing utilities"),
        ("asyncio", "Async support"),
        ("logging", "Logging"),
    ],
    "Web Framework": [
        ("fastapi", "FastAPI framework"),
        ("uvicorn", "ASGI server"),
        ("pydantic", "Data validation"),
        ("httpx", "HTTP client"),
    ],
    "Data Science": [
        ("numpy", "Numerical computing"),
        ("scipy", "Scientific computing"),
        ("PIL", "Image processing"),
    ],
    "Deep Learning": [
        ("torch", "PyTorch"),
        ("torchvision", "PyTorch vision"),
    ],
    "Testing": [
        ("pytest", "Testing framework"),
        ("pytest_asyncio", "Async pytest support"),
    ],
}

failed = []
passed = []

for category, packages in REQUIRED_IMPORTS.items():
    print(f"\n[{category}]")
    for package_name, description in packages:
        try:
            mod = __import__(package_name)
            version = getattr(mod, "__version__", "unknown")
            status = "✅"
            print(f"  {status} {package_name:20} (v{version:15}) - {description}")
            passed.append(package_name)
        except ImportError as e:
            status = "❌"
            print(f"  {status} {package_name:20} (MISSING)           - {description}")
            failed.append((package_name, str(e)))

# Try importing backend modules
print(f"\n[Backend Modules]")
backend_modules = [
    ("backend.models.score", "Score models"),
    ("backend.services.scoring", "Scoring service"),
    ("backend.services.location", "Location service"),
    ("backend.services.cv_model", "CV model service"),
    ("backend.services.thermal", "Thermal service"),
    ("backend.api.score", "Score API"),
]

for module_name, description in backend_modules:
    try:
        __import__(module_name)
        status = "✅"
        print(f"  {status} {module_name:40} - {description}")
    except Exception as e:
        status = "❌"
        print(f"  {status} {module_name:40} - {description}")
        print(f"     Error: {e}")
        failed.append((module_name, str(e)))

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"✅ Passed: {len(passed)}")
print(f"❌ Failed: {len(failed)}")

if failed:
    print("\nFailed imports:")
    for name, error in failed:
        print(f"  - {name}: {error}")
    sys.exit(1)
else:
    print("\n🎉 All dependencies imported successfully!")
    sys.exit(0)
