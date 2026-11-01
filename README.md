# NIVAS Backend API Service

FastAPI-powered REST backend providing property defect inspection, civic walkability analytics, disaster hazard exposure, safety intelligence, and legal document due diligence.

---

## Architecture & Responsibilities

The backend service runs as a stateless, serverless-ready FastAPI application. It is organized into specialized domain routers and service modules:

```
backend/
├── main.py                     # App factory, CORS, exception handlers, /health
├── requirements.txt            # Serverless production dependencies
├── requirements-ml.txt         # Optional GPU/training dependencies (PyTorch)
├── api/                        # API route controllers
│   ├── score.py                # POST /api/score, POST /api/score/compare
│   ├── livability.py           # GET /api/livability/location-data, POST /chat
│   ├── disaster.py             # GET /api/disaster/hazard-data, POST /compare
│   └── documents.py            # POST /api/documents/analyze, POST /compare
├── core/
│   └── config.py               # Pydantic Settings, environment variables
├── models/                     # Strongly-typed Pydantic schemas
│   ├── score.py
│   ├── livability.py
│   ├── safety.py
│   ├── disaster.py
│   └── documents.py
├── services/                   # Algorithmic & external API integrations
│   ├── air_quality.py          # OpenWeather + WAQI AQI pipeline
│   ├── weather.py              # OpenWeather current meteorological conditions
│   ├── location.py             # OpenStreetMap Overpass (4 mirrors) + Geocoding
│   ├── livability_advisor.py   # Gemini 3.5 Flash / OpenAI / Telemetry fallback
│   ├── crime_data.py           # NCRB 2022 Table 1A.1 + Delhi Police GeoJSON
│   ├── disaster.py             # 8 official statutory GIS hazard layers
│   ├── document_analysis.py    # PDF text/OCR extraction & discrepancy engine
│   ├── cv_model.py             # EfficientNet-B0 inference & blur validation
│   ├── thermal.py              # MLX90640 radiometric spatial median filter
│   └── price.py                # MCD circle rates & benchmark price analytics
├── cv/                         # Computer Vision training & architecture
│   ├── model.py                # EfficientNet-B0 model builder
│   └── train.py                # Class-weighted PyTorch training harness
├── data/                       # Official static datasets & GeoJSON layers
└── tests/                      # 192 automated unit and integration tests
```

---

## API Endpoints Summary

| Endpoint | Method | Domain | Description |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | System | Health check returning service status and version |
| `/api/score` | `POST` | Property | Composite property score (0–100), CV inspection, thermal status |
| `/api/score/compare` | `POST` | Property | Side-by-side comparative property inspection score |
| `/api/livability/location-data` | `GET`/`POST` | Livability | Verified OSM infrastructure, ambient weather, and real-time AQI |
| `/api/livability/chat` | `POST` | Advisor | Grounded conversational Q&A via Gemini 3.5 Flash or rule fallback |
| `/api/livability/safety-data` | `GET` | Safety | Delhi Police operational district incident stats & station catalog |
| `/api/livability/national-safety-overview` | `GET` | Safety | 36 states/UTs NCRB 2022 Table 1A.1 safety choropleth data |
| `/api/disaster/hazard-data` | `GET` | Disaster | Multi-hazard spatial risk evaluation across 8 statutory layers |
| `/api/disaster/compare` | `POST` | Disaster | Comparative hazard exposure matrix for two locations |
| `/api/documents/analyze` | `POST` | Documents | Multipart PDF/TXT legal entity extraction & page citations |
| `/api/documents/sample-documents` | `GET` | Documents | Synthetic demonstration legal instruments with provenance notes |
| `/api/documents/compare` | `POST` | Documents | Cross-document discrepancy detection across transaction drafts |

---

## Environment Variables

All secrets are loaded via `backend/core/config.py`. Never hardcode keys or commit `.env` files:

* `GEMINI_API_KEY`: Google Gemini API key (primary conversational AI provider)
* `GEMINI_MODEL`: Model name (defaults to `gemini-3.5-flash`)
* `OPENAI_API_KEY`: OpenAI API key (optional secondary provider)
* `OPENWEATHER_API_KEY`: OpenWeather API key (ambient weather & air pollution)
* `AQICN_TOKEN` / `AQICN_API_KEY`: WAQI / AQICN token (air quality station monitoring)
* `PROPSTACK_API_KEY`: Propstack API key (optional commercial property pricing)

---

## Local Development & Testing

```bash
# 1. Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Run test suite (192 passing tests)
pytest tests/ -q --tb=short

# 3. Start local development server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.
