import logging
import re
from typing import Optional
import httpx
from pydantic import BaseModel
from backend.core.config import settings

logger = logging.getLogger("nivas.services.geocoding")

# Pre-compiled regex patterns — compiled once at import time, not per-call
_RE_SECTOR_BLOCK = re.compile(r'\b(sector|block|phase)\s+\d+[a-z]?\b', re.IGNORECASE)
_RE_TRAILING_NUM = re.compile(r'(\b[a-zA-Z]{3,}\b)\s+\d+\b')
_RE_WHITESPACE   = re.compile(r'\s+')
_RE_TRAILING_NUM_SIMPLE = re.compile(r'\s+\d+\b')


class GeocodeResult(BaseModel):
    latitude: float
    longitude: float
    formatted_address: str
    display_name: Optional[str] = None


async def geocode_address(address: str, timeout: float = 5.0) -> Optional[GeocodeResult]:
    """
    Convert an Indian address string into real latitude and longitude coordinates.
    Uses Google Maps API if GOOGLE_MAPS_API_KEY is configured,
    otherwise uses OpenStreetMap Nominatim API with a smart fallback query hierarchy.
    Does not hardcode coordinates.

    Fallback chain (Nominatim only):
    1. Original address
    2. Strip Sector/Block/Phase modifiers and trailing number suffixes
    3. First locality part + city (e.g. "Lajpat Nagar, New Delhi")

    All fallback queries are issued sequentially over a single persistent
    httpx.AsyncClient to reuse the TCP connection.
    """
    if not address or not address.strip():
        return None

    clean_address = address.strip()

    # ── 1. Google Maps Geocoding API (preferred) ──────────────────────────────
    if settings.GOOGLE_MAPS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={
                        "address": clean_address,
                        "components": "country:IN",
                        "key": settings.GOOGLE_MAPS_API_KEY,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "OK" and data.get("results"):
                        res = data["results"][0]
                        loc = res["geometry"]["location"]
                        return GeocodeResult(
                            latitude=float(loc["lat"]),
                            longitude=float(loc["lng"]),
                            formatted_address=res.get("formatted_address", clean_address),
                            display_name=res.get("formatted_address"),
                        )
        except Exception as err:
            logger.warning("Google Maps geocoding failed: %s", str(err))

    # ── 2. Build Nominatim fallback query list (pre-compute all, O(1) each) ──
    queries_to_try: list[str] = [clean_address]

    # Fallback 2a: strip sector/block/phase modifiers + trailing numbers
    simplified = _RE_SECTOR_BLOCK.sub('', clean_address)
    simplified = _RE_TRAILING_NUM.sub(r'\1', simplified)
    simplified = _RE_WHITESPACE.sub(' ', simplified).strip()
    if simplified and simplified.lower() != clean_address.lower() and simplified not in queries_to_try:
        queries_to_try.append(simplified)

    # Fallback 2b: first locality part + city
    parts = [p.strip() for p in clean_address.split(",") if p.strip()]
    if len(parts) >= 2:
        locality = _RE_TRAILING_NUM_SIMPLE.sub('', parts[0]).strip()
        city = parts[-1].strip()
        if locality and city:
            candidate = f"{locality}, {city}"
            if candidate.lower() not in {q.lower() for q in queries_to_try}:
                queries_to_try.append(candidate)

    # ── 3. Nominatim — single persistent client, sequential fallback loop ────
    headers = {"User-Agent": "NIVAS-Property-Inspection/1.0 (contact@nivas.app)"}
    url = "https://nominatim.openstreetmap.org/search"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            for q_text in queries_to_try:
                query = q_text if "india" in q_text.lower() else f"{q_text}, India"
                resp = await client.get(
                    url,
                    params={"q": query, "format": "json", "limit": 1, "countrycodes": "in"},
                    headers=headers,
                )
                if resp.status_code == 200:
                    results = resp.json()
                    if results and isinstance(results, list):
                        item = results[0]
                        logger.info(
                            "Geocoded '%s' → (%.5f, %.5f)",
                            q_text, float(item["lat"]), float(item["lon"]),
                        )
                        return GeocodeResult(
                            latitude=float(item["lat"]),
                            longitude=float(item["lon"]),
                            formatted_address=item.get("display_name", clean_address),
                            display_name=item.get("display_name"),
                        )
                else:
                    logger.warning("Nominatim HTTP %s for query: %s", resp.status_code, query)

    except httpx.TimeoutException:
        logger.warning("Geocoding timed out for address: %s", clean_address)
        return None
    except Exception as err:
        logger.error("Geocoding error for '%s': %s", clean_address, str(err))
        return None

    logger.info("No geocoding result for address: %s", clean_address)
    return None
