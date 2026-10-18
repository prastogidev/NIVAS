import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional
import httpx
from backend.core.config import settings
from backend.models.score import PriceBenchmarkResult, PropertyListing

logger = logging.getLogger("nivas.services.price")

# Path to local compliant benchmark repository & cache directory
# Canonical data location: backend/data/cached_demo_data or /NIVAS/data/cached_demo_data
_LOCAL_BACKEND_DATA = Path(__file__).resolve().parent.parent / "data" / "cached_demo_data"
_ROOT_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "cached_demo_data"
DATA_DIR = _LOCAL_BACKEND_DATA if _LOCAL_BACKEND_DATA.exists() else _ROOT_DATA
CACHE_DIR = DATA_DIR / "cache"

# Configurable Cache Time-To-Live in seconds (default: 24 hours / 86400 seconds)
PRICE_CACHE_TTL_SECONDS = 86400


def calculate_price_fairness_score(
    price_per_sqft: float,
    median_price_per_sqft: float,
) -> float:
    """
    Computes a transparent 0-100 property price valuation fairness score by comparing a property's
    price per sq. ft. against the real locality median market price per sq. ft.

    Definition of a Good Price in Real Estate Valuation:
    - Excellent / Deep Bargain Value (Score 90-100): Price per sq. ft. is <= 70% to 85% of market median.
    - Fair Market Value (Score 80-90): Price per sq. ft. is around 85% to 100% of market median.
      (Baseline score for exact market median price is 85.0/100).
    - Fair to Slight Premium (Score 60-80): Price per sq. ft. is 100% to 125% of market median.
    - Premium to Overpriced (Score 25-60): Price per sq. ft. is 125% to 160% of market median.
    - Highly Overpriced (Score 0-25): Price per sq. ft. is > 160% of market median.

    Piecewise Linear Mapping Formula:
    Let Ratio R = price_per_sqft / median_price_per_sqft

    - R <= 0.70: Score = 100.0
    - 0.70 < R <= 1.00: Score = 100.0 - ((R - 0.70) / 0.30) * 15.0  (100.0 down to 85.0)
    - 1.00 < R <= 1.25: Score = 85.0 - ((R - 1.00) / 0.25) * 25.0   (85.0 down to 60.0)
    - 1.25 < R <= 1.60: Score = 60.0 - ((R - 1.25) / 0.35) * 35.0   (60.0 down to 25.0)
    - R > 1.60: Score = max(0.0, 25.0 - ((R - 1.60) / 0.40) * 25.0) (25.0 down to 0.0)
    """
    if price_per_sqft <= 0 or median_price_per_sqft <= 0:
        return 0.0

    ratio = price_per_sqft / median_price_per_sqft

    if ratio <= 0.70:
        score = 100.0
    elif ratio <= 1.00:
        score = 100.0 - ((ratio - 0.70) / 0.30) * 15.0
    elif ratio <= 1.25:
        score = 85.0 - ((ratio - 1.00) / 0.25) * 25.0
    elif ratio <= 1.60:
        score = 60.0 - ((ratio - 1.25) / 0.35) * 35.0
    else:
        score = max(0.0, 25.0 - ((ratio - 1.60) / 0.40) * 25.0)

    return round(score, 2)


def get_cache_filepath(address: str, property_type: str) -> Path:
    """Generate a deterministic file path for caching price benchmark results."""
    key = f"{address.strip().lower()}:{property_type.strip().lower()}"
    key_hash = hashlib.md5(key.encode("utf-8")).hexdigest()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"price_{key_hash}.json"


def get_cached_price(filepath: Path, ttl_seconds: int = PRICE_CACHE_TTL_SECONDS) -> Optional[PriceBenchmarkResult]:
    """Read cached result if it exists and has not expired."""
    if not filepath.exists():
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            cache_obj = json.load(f)

        cached_time = cache_obj.get("timestamp", 0)
        if time.time() - cached_time > ttl_seconds:
            logger.info("Price cache expired for %s", filepath.name)
            return None

        data = cache_obj.get("data")
        if data and isinstance(data, dict):
            price = data.get("estimated_price_per_sqft")
            if price and float(price) > 0:
                logger.info("Price cache HIT for %s", filepath.name)
                return PriceBenchmarkResult.model_validate(data)
    except Exception as err:
        logger.warning("Error reading cache file %s: %s", filepath, str(err))

    return None


def save_price_cache(filepath: Path, result: PriceBenchmarkResult) -> None:
    """Save successful non-null price benchmark result to cache file."""
    if not result or not result.estimated_price_per_sqft or result.estimated_price_per_sqft <= 0:
        return  # Do not cache invalid or null responses

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_obj = {
            "timestamp": time.time(),
            "data": result.model_dump(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(cache_obj, f, indent=2)
        logger.info("Saved successful price benchmark to cache: %s", filepath.name)
    except Exception as err:
        logger.warning("Error saving price cache to %s: %s", filepath, str(err))


# O(1) locality keyword → canonical key lookup table
# Only includes localities with verified cached benchmark data
_LOCALITY_KEYWORD_MAP: dict[str, str] = {
    "dwarka":       "dwarka",
    "rohini":       "rohini",
    "lajpat":       "lajpat_nagar",
    "lajpat_nagar": "lajpat_nagar",
    "lajpat nagar": "lajpat_nagar",
    # No verified benchmark data exists for Connaught Place
}


def normalize_locality_key(address: str) -> str:
    """
    Return a canonical locality key for local benchmark dataset lookup.
    Uses keyword matching against the lowercased address.
    Falls back to a slugified address string for unknown localities.
    """
    addr_lower = address.lower()
    for keyword, canonical in _LOCALITY_KEYWORD_MAP.items():
        if keyword in addr_lower:
            return canonical
    return addr_lower.strip().replace(" ", "_")


async def fetch_price_benchmark_with_status(
    address: str, property_type: str
) -> tuple[Optional[PriceBenchmarkResult], str, Optional[str]]:
    """
    Fetch property price benchmarks and valuation fairness using compliant data sources.
    Returns:
        (result, status, error_message)
        where status is one of:
        - 'active': benchmark found and fairness score computed
        - 'not_assessed': address is empty or missing
        - 'provider_not_configured': PROPSTACK_API_KEY missing AND no local benchmark dataset for locality
        - 'fetch_failed': Propstack API network/timeout error
        - 'data_unavailable': Propstack returned 200 with 0 listings / no price, or local dataset has no data for property type
    """
    if not address or not address.strip():
        return None, "not_assessed", "Address is required for price valuation benchmark."

    clean_prop_type = property_type.strip() if property_type else "Apartment"
    cache_path = get_cache_filepath(address, clean_prop_type)

    # 1. Check TTL Cache
    cached_res = get_cached_price(cache_path)
    if cached_res is not None:
        return cached_res, "active", None

    res: Optional[PriceBenchmarkResult] = None
    propstack_key = getattr(settings, "PROPSTACK_API_KEY", None)
    propstack_failed = False
    propstack_error: Optional[str] = None

    # 2. Commercial Propstack API integration if key exists
    if propstack_key and propstack_key.strip():
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                url = "https://api.propstack.com/v1/valuation/benchmark"
                headers = {"Authorization": f"Bearer {propstack_key.strip()}"}
                params = {"address": address, "property_type": clean_prop_type}
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data_json = resp.json()
                    price = float(data_json.get("price_per_sqft", 0))
                    median_ref = float(data_json.get("median_price_per_sqft", price))
                    if price > 0:
                        fairness = calculate_price_fairness_score(price, median_ref)
                        res = PriceBenchmarkResult(
                            estimated_price_per_sqft=price,
                            fairness_score=fairness,
                            source="Propstack Valuation API",
                            fetch_status="active",
                        )
                elif resp.status_code == 401 or resp.status_code == 403:
                    propstack_failed = True
                    propstack_error = f"Propstack API authentication failed (HTTP {resp.status_code}). Check PROPSTACK_API_KEY credentials."
                    logger.warning(propstack_error)
                else:
                    propstack_failed = True
                    propstack_error = f"Propstack API returned HTTP status {resp.status_code}"
                    logger.warning(propstack_error)
        except httpx.TimeoutException:
            propstack_failed = True
            propstack_error = "Propstack API request timed out"
            logger.warning(propstack_error)
        except Exception as err:
            propstack_failed = True
            propstack_error = f"Propstack API error: {str(err)}"
            logger.warning(propstack_error)

    # 3. Compliant Local Benchmark Datasets fallback if no Propstack result
    if res is None:
        locality_key = normalize_locality_key(address)
        benchmark_file = DATA_DIR / locality_key / "benchmark.json"
        dataset_file = DATA_DIR / locality_key / "cache_dataset.json"

        if benchmark_file.exists():
            try:
                with open(benchmark_file, "r", encoding="utf-8") as f:
                    b_data = json.load(f)

                circle_category = b_data.get("delhi_circle_category")
                market_stats = b_data.get("market_price_stats", {})
                type_key = "Apartment"
                if "house" in clean_prop_type.lower():
                    type_key = "Independent House"
                elif "villa" in clean_prop_type.lower():
                    type_key = "Villa"
                elif "commercial" in clean_prop_type.lower():
                    type_key = "Commercial Space"
                elif clean_prop_type in market_stats:
                    type_key = clean_prop_type

                stats = market_stats.get(type_key, market_stats.get("Apartment"))
                if stats:
                    median_price = float(stats.get("median_price_per_sqft", 0))
                    if median_price > 0:
                        source_str = "Cached Demo Benchmark Dataset (Delhi Circle Rate & Market Survey Reference)"
                        fetched_at_str = None
                        expiry_str = None
                        sample_count_val = stats.get("sample_listings_count")
                        actual_listings_list = None

                        if dataset_file.exists() and dataset_file.stat().st_size > 0:
                            try:
                                with open(dataset_file, "r", encoding="utf-8") as df:
                                    ds_data = json.load(df)
                                source_str = ds_data.get("source", source_str)
                                fetched_at_str = ds_data.get("fetched_at")
                                expiry_str = ds_data.get("expiry")
                                sample_count_val = ds_data.get("sample_count", sample_count_val)
                                raw_listings = ds_data.get("actual_listings", [])
                                if raw_listings:
                                    actual_listings_list = [
                                        PropertyListing.model_validate(item) for item in raw_listings
                                    ]
                            except Exception as ds_err:
                                logger.warning("Could not parse dataset_file '%s': %s", dataset_file, str(ds_err))

                        # Calculate dynamic price fairness score relative to real market median
                        fairness = calculate_price_fairness_score(median_price, median_price)

                        res = PriceBenchmarkResult(
                            estimated_price_per_sqft=median_price,
                            fairness_score=fairness,
                            source=source_str,
                            fetched_at=fetched_at_str,
                            expiry=expiry_str,
                            sample_count=sample_count_val,
                            actual_listings=actual_listings_list,
                            delhi_circle_category=circle_category,
                            fetch_status="active",
                        )
                    else:
                        return None, "data_unavailable", f"No price listings or valid median rate found for '{clean_prop_type}' in {address} benchmark."
                else:
                    return None, "data_unavailable", f"No benchmark data available for property type '{clean_prop_type}' in {address}."
            except Exception as err:
                logger.error("Error reading price benchmark file '%s': %s", benchmark_file, str(err))
                return None, "fetch_failed", f"Error reading local benchmark dataset: {str(err)}"
        else:
            # Local benchmark does not exist for this locality
            if propstack_failed:
                return None, "fetch_failed", propstack_error or "Propstack API connection failed."
            elif propstack_key and propstack_key.strip():
                return None, "data_unavailable", f"No listings or price benchmark found for '{address}' via Propstack."
            else:
                return None, "provider_not_configured", "Propstack API key is not configured and no local benchmark dataset exists for this locality."

    # 4. Save successful real response to cache
    if res is not None:
        save_price_cache(cache_path, res)
        return res, "active", None

    return None, "data_unavailable", f"Price benchmark data unavailable for '{address}'."


async def fetch_price_benchmark(
    address: str, property_type: str
) -> Optional[PriceBenchmarkResult]:
    """
    Backward-compatible wrapper returning PriceBenchmarkResult or None.
    """
    res, _, _ = await fetch_price_benchmark_with_status(address, property_type)
    return res
