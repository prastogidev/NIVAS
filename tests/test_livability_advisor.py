import os
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.livability import (
    LivabilityChatRequest,
    LivabilityChatContext,
    LivabilityChatFacilityItem,
)
from backend.services.livability_advisor import (
    generate_grounded_telemetry_reply,
    generate_advisor_response,
    calculate_haversine_distance_km,
    format_distance,
    call_gemini_provider,
    call_openai_provider,
    sanitize_and_validate_ai_reply,
)

client = TestClient(app)


@pytest.fixture
def sample_chat_context():
    return LivabilityChatContext(
        latitude=28.5921,
        longitude=77.0460,
        address="Dwarka Sector 12, South West Delhi, Delhi",
        locality="Dwarka Sector 12",
        search_radius_meters=1200,
        railway_search_radius_meters=2000,
        infrastructure_status="active",
        facilities=[
            LivabilityChatFacilityItem(
                id="h-1",
                name="Venkateshwar Hospital",
                category="hospital",
                category_label="Hospital",
                latitude=28.5891,
                longitude=77.0422,
                distance_km=0.51,
                formatted_distance="510 m",
                source="OpenStreetMap",
            ),
            LivabilityChatFacilityItem(
                id="s-1",
                name="DPS Dwarka",
                category="school",
                category_label="School",
                latitude=28.5912,
                longitude=77.0456,
                distance_km=0.11,
                formatted_distance="110 m",
                source="OpenStreetMap",
            ),
            LivabilityChatFacilityItem(
                id="t-1",
                name="Dwarka Sector 12 Metro Station",
                category="railway",
                category_label="Metro Station",
                latitude=28.5930,
                longitude=77.0470,
                distance_km=0.14,
                formatted_distance="140 m",
                source="OpenStreetMap",
            ),
        ],
        schools_count=1,
        hospitals_count=1,
        clinics_count=0,
        pharmacies_count=0,
        police_stations_count=0,
        fire_stations_count=0,
        public_transport_count=0,
        railway_stations_count=1,
        major_roads_count=2,
        nearby_places=["DPS Dwarka", "Venkateshwar Hospital", "Dwarka Sector 12 Metro"],
        air_quality_status="active",
        aqi_value=165,
        aqi_category="Moderate",
        aqi_station="Dwarka CAAQMS",
        aqi_source="CPCB CAAQMS / OpenWeather",
        environmental_score=60,
        retrieved_at="2026-10-10T12:00:00Z",
        hazards_status="data_not_configured",
        hazards_message="Real-time environmental hazard sensor network not configured for this region",
    )


def test_haversine_distance_math():
    dist = calculate_haversine_distance_km(28.6315, 77.2167, 28.6129, 77.2295)
    assert dist is not None
    assert 2.3 < dist < 2.5
    assert calculate_haversine_distance_km(28.5, 77.0, 28.5, 77.0) == 0.0
    assert calculate_haversine_distance_km(None, 77.0, 28.5, 77.0) is None


def test_format_distance():
    assert format_distance(0.25) == "250 m"
    assert format_distance(1.456) == "1.46 km"
    assert format_distance(None) == "Distance unavailable"


def test_grounded_telemetry_healthcare_inquiry(sample_chat_context):
    reply, sources = generate_grounded_telemetry_reply(
        "What healthcare facilities are nearby?", sample_chat_context
    )
    assert "Venkateshwar Hospital" in reply
    assert "510 m" in reply
    assert "OpenStreetMap" in reply
    assert "OpenStreetMap Overpass API" in sources
    assert "Haversine formula" in reply


def test_grounded_telemetry_transit_inquiry(sample_chat_context):
    reply, sources = generate_grounded_telemetry_reply(
        "How far away is the nearest mapped transit facility?", sample_chat_context
    )
    assert "Dwarka Sector 12 Metro Station" in reply
    assert "140 m" in reply
    assert "Metro Station" in reply
    assert "OpenStreetMap Overpass API" in sources


def test_grounded_telemetry_schools_inquiry(sample_chat_context):
    reply, sources = generate_grounded_telemetry_reply(
        "What schools are nearby?", sample_chat_context
    )
    assert "DPS Dwarka" in reply
    assert "110 m" in reply


def test_grounded_telemetry_air_quality_inquiry(sample_chat_context):
    reply, sources = generate_grounded_telemetry_reply(
        "What does the available air-quality data tell us?", sample_chat_context
    )
    assert "AQI Reading: 165" in reply
    assert "Moderate" in reply
    assert "Dwarka CAAQMS" in reply
    assert any("OpenWeather" in s or "CPCB" in s for s in sources)


def test_grounded_telemetry_missing_data_inquiry(sample_chat_context):
    reply, sources = generate_grounded_telemetry_reply(
        "What information is missing for this locality?", sample_chat_context
    )
    assert "Coverage Limitations" in reply
    assert "Search Radius Boundary" in reply
    assert "Real-time environmental hazard sensors are currently unconfigured" in reply
    assert "Missing data or unmapped nodes must NEVER be interpreted as confirmation of safety" in reply


def test_grounded_telemetry_empty_facilities():
    empty_ctx = LivabilityChatContext(
        latitude=28.5921,
        longitude=77.0460,
        address="Rural Outskirts",
        infrastructure_status="empty",
        facilities=[],
        schools_count=0,
        hospitals_count=0,
        clinics_count=0,
        pharmacies_count=0,
        police_stations_count=0,
        fire_stations_count=0,
        public_transport_count=0,
        railway_stations_count=0,
        major_roads_count=0,
        air_quality_status="provider_not_configured",
        hazards_status="data_not_configured",
        hazards_message="Hazard sensors not configured",
    )
    reply, _ = generate_grounded_telemetry_reply(
        "What healthcare facilities are nearby?", empty_ctx
    )
    assert "0 healthcare facilities" in reply
    assert "OpenStreetMap" in reply
    assert "does not guarantee that none exist" in reply

    aqi_reply, _ = generate_grounded_telemetry_reply(
        "What does air quality tell us?", empty_ctx
    )
    assert "Air quality telemetry is currently unconfigured" in aqi_reply
    assert "NIVAS does not synthesize or fabricate estimated air pollution numbers" in aqi_reply


@pytest.mark.asyncio
async def test_unconfigured_ai_provider_reporting(sample_chat_context):
    with patch.dict(os.environ, {}, clear=True):
        req = LivabilityChatRequest(
            query="What healthcare facilities are nearby?",
            latitude=28.5921,
            longitude=77.0460,
            address="Dwarka Sector 12",
            context=sample_chat_context,
        )
        res = await generate_advisor_response(req)
        assert res.provider_configured is False
        assert res.is_ai_generated is False
        assert "[AI Provider Not Configured]" in res.reply
        assert "Real AI model generation is unavailable" in res.reply
        assert "Venkateshwar Hospital" in res.reply
        assert "OpenStreetMap Overpass API" in res.sources


@pytest.mark.asyncio
async def test_configured_gemini_provider_call(sample_chat_context):
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test_fake_gemini_key"}):
        with patch(
            "backend.services.livability_advisor.call_gemini_provider",
            new_callable=AsyncMock,
        ) as mock_gemini:
            mock_gemini.return_value = (
                "Based on OpenStreetMap, Venkateshwar Hospital is located approximately 510 m away."
            )
            req = LivabilityChatRequest(
                query="What healthcare facilities are nearby?",
                latitude=28.5921,
                longitude=77.0460,
                address="Dwarka Sector 12",
                context=sample_chat_context,
            )
            res = await generate_advisor_response(req)
            assert res.provider_configured is True
            assert res.provider_name == "gemini"
            assert res.is_ai_generated is True
            assert "Venkateshwar Hospital" in res.reply


def test_api_chat_endpoint_valid_request(sample_chat_context):
    with patch.dict(os.environ, {}, clear=True):
        payload = {
            "query": "What infrastructure is available in this area?",
            "latitude": 28.5921,
            "longitude": 77.0460,
            "address": "Dwarka Sector 12, South West Delhi, Delhi",
            "context": sample_chat_context.model_dump(),
        }
        resp = client.post("/api/livability/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert data["provider_configured"] is False
        assert data["is_ai_generated"] is False
        assert "[AI Provider Not Configured]" in data["reply"]
        assert "OpenStreetMap Overpass API" in data["sources"]


def test_api_chat_endpoint_validation_errors():
    # Empty query
    resp = client.post(
        "/api/livability/chat",
        json={"query": "   ", "latitude": 28.5921, "longitude": 77.0460},
    )
    assert resp.status_code == 422

    # Latitude out of bounds
    resp = client.post(
        "/api/livability/chat",
        json={"query": "What is nearby?", "latitude": 99.5921, "longitude": 77.0460},
    )
    assert resp.status_code == 422

    # Excessive query length (> 500 characters)
    long_query = "A" * 501
    resp = client.post(
        "/api/livability/chat",
        json={"query": long_query, "latitude": 28.5921, "longitude": 77.0460},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_configured_openai_provider_call(sample_chat_context):
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test_fake_openai_key"}, clear=True):
        with patch(
            "backend.services.livability_advisor.call_openai_provider",
            new_callable=AsyncMock,
        ) as mock_openai:
            mock_openai.return_value = (
                "Verified transit access includes Dwarka Sector 12 Metro Station."
            )
            req = LivabilityChatRequest(
                query="How is metro connectivity?",
                latitude=28.5921,
                longitude=77.0460,
                address="Dwarka Sector 12",
                context=sample_chat_context,
            )
            res = await generate_advisor_response(req)
            assert res.provider_configured is True
            assert res.provider_name == "openai"
            assert res.is_ai_generated is True
            assert "Dwarka Sector 12 Metro Station" in res.reply


@pytest.mark.asyncio
async def test_call_gemini_provider_uses_header_not_url(sample_chat_context):
    """Confirm Gemini API key is passed strictly via x-goog-api-key header and never in the URL."""
    captured_request = {}

    class MockHttpxResponse:
        status_code = 200
        def json(self):
            return {
                "candidates": [
                    {"content": {"parts": [{"text": "Gemini response text"}]}}
                ]
            }

    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, url, headers=None, json=None):
            captured_request["url"] = url
            captured_request["headers"] = headers
            return MockHttpxResponse()

    with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
        result = await call_gemini_provider(
            "What hospitals are near?", sample_chat_context, "secret_gemini_key_123"
        )
        assert result == "Gemini response text"
        assert "secret_gemini_key_123" not in captured_request["url"]
        assert "?key=" not in captured_request["url"]
        assert captured_request["headers"].get("x-goog-api-key") == "secret_gemini_key_123"


@pytest.mark.asyncio
async def test_call_openai_provider_structure(sample_chat_context):
    """Confirm OpenAI API key is passed via Authorization Bearer header."""
    captured_request = {}

    class MockHttpxResponse:
        status_code = 200
        def json(self):
            return {
                "choices": [
                    {"message": {"content": "OpenAI grounded reply"}}
                ]
            }

    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, url, headers=None, json=None):
            captured_request["url"] = url
            captured_request["headers"] = headers
            captured_request["json"] = json
            return MockHttpxResponse()

    with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
        result = await call_openai_provider(
            "What schools are nearby?", sample_chat_context, "secret_openai_key_456"
        )
        assert result == "OpenAI grounded reply"
        assert captured_request["headers"].get("Authorization") == "Bearer secret_openai_key_456"
        assert captured_request["json"]["model"] == "gpt-4o-mini"
        assert "STRICT GROUNDING RULES" in captured_request["json"]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_provider_timeout_and_error_fallback(sample_chat_context):
    """If a configured provider returns None (timeout, quota, upstream error), fall back cleanly."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test_fake_gemini_key"}, clear=True):
        with patch(
            "backend.services.livability_advisor.call_gemini_provider",
            new_callable=AsyncMock,
        ) as mock_gemini:
            mock_gemini.return_value = None  # Provider failed
            req = LivabilityChatRequest(
                query="What healthcare facilities are nearby?",
                latitude=28.5921,
                longitude=77.0460,
                address="Dwarka Sector 12",
                context=sample_chat_context,
            )
            res = await generate_advisor_response(req)
            assert res.provider_configured is True
            assert res.provider_name == "gemini"
            assert res.is_ai_generated is False
            assert "[AI Provider Fallback]" in res.reply
            assert "did not return a response" in res.reply
            assert "Venkateshwar Hospital" in res.reply


def test_sanitize_and_validate_ai_reply_guardrails(sample_chat_context):
    # 1. Normal grounded reply is untouched
    clean_reply = "Verified schools: Delhi Public School at 420 m."
    assert sanitize_and_validate_ai_reply(clean_reply, sample_chat_context) == clean_reply

    # 2. Speculative composite livability score triggers integrity note
    speculative_reply = "Based on amenities, I calculate a composite livability score of 88/100."
    sanitized = sanitize_and_validate_ai_reply(speculative_reply, sample_chat_context)
    assert "[Integrity Note: NIVAS does not calculate composite livability or safety scores." in sanitized

    # 3. Unwarranted safety claim triggers safety caution
    safety_reply = "This area has 0 reported crime incidents and is guaranteed safe for families."
    sanitized_safety = sanitize_and_validate_ai_reply(safety_reply, sample_chat_context)
    assert "[Safety Caution: NIVAS does not maintain real-time crime or police incident sensors." in sanitized_safety


def test_greeting_handling_does_not_dump_telemetry(sample_chat_context):
    """Greetings should receive a concise, helpful response without dumping the entire telemetry report."""
    for greeting in ["hi", "hello", "Hello!", "hey there", "how are you?", "good morning"]:
        reply, sources = generate_grounded_telemetry_reply(greeting, sample_chat_context)
        assert "Hello! I am your NIVAS Neighborhood AI Advisor" in reply
        # Verify it does not dump the full infrastructure list or counts
        assert "Schools: 1" not in reply
        assert "Arterial Roads: 2" not in reply
        assert "Venkateshwar Hospital" not in reply


def test_inquiry_when_telemetry_fetch_failed(sample_chat_context):
    """When infrastructure query failed, inquiries must disclose the error and never claim 0 facilities as confirmed facts."""
    sample_chat_context.infrastructure_status = "fetch_failed"
    sample_chat_context.facilities = []
    sample_chat_context.schools_count = 0
    sample_chat_context.hospitals_count = 0

    reply, _ = generate_grounded_telemetry_reply("What healthcare facilities are nearby?", sample_chat_context)
    assert "currently unavailable" in reply
    assert "timeout or network failure" in reply
    assert "No synthetic healthcare facilities" in reply

    general_reply, _ = generate_grounded_telemetry_reply("What infrastructure is available in this area?", sample_chat_context)
    assert "Telemetry is currently unavailable" in general_reply
    assert "timed out or encountered a network error" in general_reply
    assert "No synthetic amenity data can be reported" in general_reply


def test_relocation_inquiry_handling(sample_chat_context):
    """Relocation and comparison questions should provide evidence-based contrast guidance without declaring subjective winners."""
    for query in [
        "Should I relocate to this neighborhood?",
        "How do I compare this property with another area?",
        "Is it a good decision to buy here compared to elsewhere?",
    ]:
        reply, sources = generate_grounded_telemetry_reply(query, sample_chat_context)
        assert "Relocation & Comparative Evaluation Guidelines" in reply
        assert "NIVAS provides objective, evidence-based contrasts" in reply
        assert "Relocation Candidate Compare" in reply
        assert "missing telemetry for one candidate location must NEVER be interpreted as confirmation of lower risk" in reply
        assert "NIVAS Comparative Telemetry Framework" in sources


def test_safety_inquiry_separation_in_advisor(sample_chat_context):
    """Safety inquiry must clearly separate verified official State/UT baseline from derived district allocation."""
    reply, sources = generate_grounded_telemetry_reply("What are the crime rates and is it safe here?", sample_chat_context)
    assert "Verified Official State/UT Crime Baseline (NCRB 2022 Table 1A.1)" in reply
    assert "298,988 total reported IPC crimes" in reply
    assert "1422.6 per 100k residents" in reply
    assert "District Allocation (Derived Estimate)" in reply
    assert "per-capita rate suppressed" in reply
    assert "Delhi Police / NCRB Official Statistics" in sources

