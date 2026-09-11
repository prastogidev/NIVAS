# NIVAS

**NIVAS** is an intelligent property inspection and risk assessment system that combines computer vision, thermal imaging analysis, air quality monitoring, and location-based risk evaluation to provide comprehensive property scoring.

## Overview

NIVAS Backend is a FastAPI-based REST API that provides property defect detection, thermal analysis, air quality assessment, and composite property scoring. The system leverages deep learning models for image processing and integrates with multiple external APIs for real-time data.

## Features

- **🏗️ Building Defect Detection**: Computer vision-based inspection for structural defects
- **🌡️ Thermal Imaging Analysis**: MLX90640 thermal sensor integration for building efficiency assessment
- **🌍 Air Quality Monitoring**: Real-time AQI and pollution data from AQICN and OpenWeather APIs
- **📍 Location-based Risk Assessment**: Geocoding and proximity analysis for risk factors
- **💰 Property Pricing Analysis**: Integration with PropStack API for market value assessment
- **📊 Composite Scoring**: Machine learning-based property risk score generation
- **🔍 Comparative Analysis**: Side-by-side property comparison
- **📋 Automated Reporting**: Generate comprehensive property inspection reports

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast web framework for building APIs
- **Server**: [Uvicorn](https://www.uvicorn.org/) - Lightning-fast ASGI server
- **ML/CV**: TensorFlow/PyTorch for deep learning models
- **Data Processing**: NumPy, Pandas, Scikit-learn
- **Web Scraping**: BeautifulSoup4
- **External APIs**: 
  - OpenWeather (weather data)
  - Google Maps (geocoding)
  - AQICN (air quality data)
  - PropStack (property pricing)

## Project Structure

```
backend/
├── api/                      # API route definitions
│   └── score.py             # Scoring endpoint
├── core/                     # Core configuration
│   └── config.py            # Application settings
├── cv/                       # Computer Vision modules
│   ├── model.py             # CV model architecture
│   ├── preprocess.py        # Image preprocessing
│   ├── train.py             # Model training script
│   ├── split_dataset.py     # Dataset splitting utility
│   └── verify_dataset.py    # Dataset verification
├── hardware/                 # Hardware integration
│   └── mlx90640.py          # Thermal sensor driver
├── models/                   # Pydantic data models
│   ├── __init__.py
│   └── score.py             # Request/response schemas
├── services/                 # Business logic layer
│   ├── air_quality.py       # Air quality assessment
│   ├── aqi.py               # AQI calculations
│   ├── compare.py           # Property comparison
│   ├── cv_model.py          # CV model service
│   ├── geocoding.py         # Location services
│   ├── location.py          # Location risk assessment
│   ├── price.py             # Price analysis
│   ├── report.py            # Report generation
│   ├── scoring.py           # Composite scoring
│   └── thermal.py           # Thermal analysis
├── tests/                    # Test suite
├── utils/                    # Utility functions
├── main.py                   # Application entry point
├── requirements.txt          # Python dependencies
├── .env.example             # Environment template
└── README.md                # This file
```

## Installation

### Prerequisites
- Python 3.8+
- pip or conda
- Virtual environment (recommended)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/prastogidev/SIH_NIVAS.git
   cd SIH_NIVAS
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys:
   # - OPENWEATHER_API_KEY
   # - GOOGLE_MAPS_API_KEY
   # - AQICN_TOKEN
   # - PROPSTACK_API_KEY
   ```

5. **Run the server**
   ```bash
   python main.py
   ```

   The API will be available at `http://localhost:8000`

## API Documentation

### Interactive Documentation
Once the server is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Health Check
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "service": "NIVAS Backend API",
  "version": "1.0.0"
}
```

### Scoring Endpoint
```bash
POST /score
```

Comprehensive property scoring combining:
- Building condition analysis
- Thermal efficiency assessment
- Air quality metrics
- Location risk factors
- Market valuation

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ENVIRONMENT` | `development` or `production` | Yes |
| `LOG_LEVEL` | Logging level (INFO, DEBUG, ERROR) | Yes |
| `OPENWEATHER_API_KEY` | OpenWeather API key | Yes |
| `GOOGLE_MAPS_API_KEY` | Google Maps API key | Yes |
| `AQICN_TOKEN` | AQICN air quality token | Yes |
| `PROPSTACK_API_KEY` | PropStack property data API key | Yes |
| `MODEL_CHECKPOINT_DIR` | Path to model checkpoints | No |
| `DATA_CACHE_DIR` | Cache directory for external data | No |

## Testing

Run the test suite:
```bash
pytest tests/
```

Specific test categories:
```bash
# Air quality relevance tests
pytest tests/test_air_quality_relevance.py

# End-to-end tests
pytest tests/test_e2e_delhi_localities.py

# Location fallback tests
pytest tests/test_location_fallback.py

# Report generation tests
pytest tests/test_report_wording.py
```

## Key Services

### Air Quality Service (`services/air_quality.py`)
Fetches and processes air quality data from multiple sources with fallback mechanisms.

### Thermal Analysis (`services/thermal.py`)
Integrates MLX90640 thermal sensor for building efficiency assessment.

### CV Model Service (`services/cv_model.py`)
Loads and runs deep learning models for defect detection and image classification.

### Scoring Service (`services/scoring.py`)
Combines multiple risk factors into a composite property score.

### Report Generation (`services/report.py`)
Generates comprehensive property inspection reports with findings and recommendations.

## Performance

- **Request Timing**: All responses include `X-Process-Time` header
- **CORS Support**: Configured for cross-origin requests
- **Error Handling**: Global exception handler for robust error responses

## Development

### Adding New Endpoints

1. Create a route in `api/` directory
2. Define request/response models in `models/`
3. Implement business logic in `services/`
4. Include router in `main.py`

### Code Style

- Follow PEP 8 conventions
- Use type hints for all functions
- Document complex functions with docstrings

## Deployment

### Docker (Coming Soon)
```bash
docker build -t nivas-backend .
docker run -p 8000:8000 --env-file .env nivas-backend
```

### Production Considerations
- Set `ENVIRONMENT=production` in `.env`
- Use environment-specific `.env` files
- Configure proper logging and monitoring
- Set up CORS appropriately for your frontend domain
- Use a production ASGI server (e.g., Gunicorn + Uvicorn)

## API Keys & External Services

### Obtaining API Keys

1. **OpenWeather**: https://openweathermap.org/api
2. **Google Maps**: https://cloud.google.com/maps-platform
3. **AQICN**: https://aqicn.org/api/
4. **PropStack**: https://propstack.com/

⚠️ **Never commit `.env` file with real credentials to version control!**

## Troubleshooting

### Port 8000 Already in Use
```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9
# Or use a different port
python main.py --port 8001
```

### Missing API Keys
Ensure all required API keys are set in `.env`. Check logs for specific service failures.

### Model Loading Issues
Verify model checkpoint paths in `MODEL_CHECKPOINT_DIR` and ensure files are present.

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes and commit: `git commit -am 'Add new feature'`
3. Push to branch: `git push origin feature/your-feature`
4. Submit a pull request

## License

This project is part of Smart India Hackathon 2026.

## Support

For issues, questions, or suggestions, please open an issue on GitHub or contact the development team.

---

**Built with ❤️ for Smart India Hackathon 2026**
