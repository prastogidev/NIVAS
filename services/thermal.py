import logging
from typing import Optional
import numpy as np
from scipy.ndimage import median_filter

from backend.models.score import ThermalModuleResult

logger = logging.getLogger("nivas.services.thermal")

# Configurable anomaly detection thresholds
THERMAL_ANOMALY_DEVIATION_THRESHOLD: float = 3.5  # °C deviation from local median
BLUR_LAPLACIAN_THRESHOLD: float = 50.0            # Reused pattern for consistency


def compute_local_median_matrix(arr: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """
    Compute 2D local median temperature matrix using scipy.ndimage.median_filter.
    O(n) vectorized C implementation — replaces the former Python double-loop over all pixels.
    Edge padding via 'nearest' mode preserves full 32×24 matrix dimensions.
    """
    return median_filter(arr.astype(np.float32), size=kernel_size, mode="nearest")


def detect_thermal_anomalies(
    thermal_matrix: np.ndarray,
    deviation_threshold: float = THERMAL_ANOMALY_DEVIATION_THRESHOLD,
    kernel_size: int = 3,
) -> tuple[int, list[dict]]:
    """
    Detect local thermal anomalies by comparing each pixel to its local median.
    A pixel is anomalous if |pixel - local_median| > deviation_threshold.

    Returns:
        anomaly_count: Number of anomalous pixels
        anomaly_details: List of dicts with row, col, temperature, deviation
    """
    local_medians = compute_local_median_matrix(thermal_matrix, kernel_size=kernel_size)
    deviation = np.abs(thermal_matrix - local_medians)

    anomaly_mask = deviation > deviation_threshold
    anomaly_coords = np.argwhere(anomaly_mask)
    anomaly_count = int(anomaly_coords.shape[0])

    # Return up to 10 anomaly detail records (row, col, temperature, deviation)
    details = []
    for r, c in anomaly_coords[:10]:
        details.append({
            "row": int(r),
            "col": int(c),
            "temperature": round(float(thermal_matrix[r, c]), 2),
            "deviation_from_local_median": round(float(deviation[r, c]), 2),
        })

    return anomaly_count, details


async def run_thermal_analysis(image_info=None) -> Optional[ThermalModuleResult]:
    """
    Execute thermal insulation analysis using real sensor or uploaded thermal image.

    Priority chain:
    1. MLX90640 I2C hardware sensor (if connected)
    2. Uploaded thermal image URL (if provided as image_info)
    3. Returns None — never fabricates sensor data

    Anomaly detection uses configurable local-median deviation filter.
    Insulation score is normalized 0–100 based on anomaly density.
    """
    thermal_matrix: Optional[np.ndarray] = None
    sensor_status: str = "Disconnected"

    # ── 1. Try real MLX90640 I2C hardware sensor ──────────────────────────────
    try:
        from backend.hardware.mlx90640 import read_mlx90640_frame
        frame = read_mlx90640_frame()
        if frame is not None:
            thermal_matrix = np.array(frame, dtype=np.float32).reshape(24, 32)
            sensor_status = "MLX90640 I2C — Live Hardware Reading"
            logger.info("MLX90640 hardware frame acquired (24×32)")
    except ImportError:
        logger.debug("MLX90640 hardware driver not importable — skipping hardware path")
    except Exception as hw_err:
        logger.warning("MLX90640 hardware read failed: %s", str(hw_err))

    # ── 2. Try uploaded thermal image (Base64 or URL) ─────────────────────────
    if thermal_matrix is None and image_info:
        thermal_b64 = getattr(image_info, "thermal_base64", None)
        thermal_url = getattr(image_info, "thermal_url", None)

        img_type = getattr(image_info, "image_type", None) or ""
        if not thermal_b64 and not thermal_url and img_type.lower() in ("thermal", "ir", "infrared", "thermal_scan"):
            thermal_b64 = getattr(image_info, "image_base64", None)
            thermal_url = getattr(image_info, "image_url", None)

        if not thermal_b64 and not thermal_url and getattr(image_info, "images", None):
            for item in image_info.images:
                if isinstance(item, dict) and item.get("image_type", "").lower() in ("thermal", "ir", "infrared", "thermal_scan"):
                    thermal_b64 = item.get("image_base64")
                    thermal_url = item.get("image_url")
                    break

        if thermal_b64 or thermal_url:
            try:
                from io import BytesIO
                from PIL import Image
                import base64

                img = None
                if thermal_b64 and str(thermal_b64).strip():
                    b64_data = str(thermal_b64).strip()
                    if "," in b64_data:
                        b64_data = b64_data.split(",", 1)[1]
                    img_bytes = base64.b64decode(b64_data)
                    if len(img_bytes) > 0:
                        img = Image.open(BytesIO(img_bytes)).convert("L").resize((32, 24))
                        sensor_status = "Thermal Image (Upload) — Relative Pixel Gradient Estimation (Not Calibrated Physical Sensor)"
                elif thermal_url and str(thermal_url).strip():
                    import httpx
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(str(thermal_url).strip())
                    if resp.status_code == 200:
                        img = Image.open(BytesIO(resp.content)).convert("L").resize((32, 24))
                        sensor_status = "Thermal Image (URL) — Relative Pixel Gradient Estimation (Not Calibrated Physical Sensor)"

                if img is not None:
                    raw = np.array(img, dtype=np.float32)
                    raw_min, raw_max = raw.min(), raw.max()
                    if raw_max > raw_min:
                        thermal_matrix = 15.0 + (raw - raw_min) / (raw_max - raw_min) * 30.0
                    else:
                        thermal_matrix = np.full((24, 32), 25.0, dtype=np.float32)
                    logger.info("Thermal image loaded and normalized successfully")
            except Exception as img_err:
                logger.warning("Thermal image load failed: %s", str(img_err))

    # ── 3. No real data available ─────────────────────────────────────────────
    if thermal_matrix is None:
        logger.info("Thermal module returning None — no hardware or image source available")
        return ThermalModuleResult(
            sensor_status="Disconnected (null) — No MLX90640 hardware or thermal image provided",
            insulation_score=None,
        )

    # ── 4. Compute statistics & anomalies ────────────────────────────────────
    mean_temp = float(np.mean(thermal_matrix))
    min_temp = float(np.min(thermal_matrix))
    max_temp = float(np.max(thermal_matrix))
    std_temp = float(np.std(thermal_matrix))

    anomaly_count, anomaly_details = detect_thermal_anomalies(
        thermal_matrix,
        deviation_threshold=THERMAL_ANOMALY_DEVIATION_THRESHOLD,
    )

    # ── 5. Insulation score: penalize dense anomaly coverage ──────────────────
    total_pixels = thermal_matrix.size  # 32 × 24 = 768
    anomaly_density = anomaly_count / total_pixels  # [0.0, 1.0]
    # Score drops linearly from 100 → 0 as anomaly density goes from 0 → 40%
    raw_score = max(0.0, 100.0 - (anomaly_density / 0.40) * 100.0)
    insulation_score = round(min(100.0, raw_score), 2)

    logger.info(
        "Thermal analysis: mean=%.1f°C, anomalies=%d/%d pixels, score=%.1f",
        mean_temp, anomaly_count, total_pixels, insulation_score,
    )

    return ThermalModuleResult(
        sensor_status=sensor_status,
        mean_temp=round(mean_temp, 2),
        min_temp=round(min_temp, 2),
        max_temp=round(max_temp, 2),
        std_temp=round(std_temp, 2),
        anomalies_detected_count=anomaly_count,
        anomaly_details=anomaly_details,
        insulation_score=insulation_score,
        thermal_matrix=thermal_matrix.tolist(),
    )
