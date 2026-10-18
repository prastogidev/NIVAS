import base64
import hashlib
import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import numpy as np
from PIL import Image
import httpx
try:
    import torch
    import torch.nn.functional as F
    from backend.cv.model import build_efficientnet_b0, get_eval_transforms, WALL_CONDITION_CLASSES
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    F = None
    build_efficientnet_b0 = None
    get_eval_transforms = None
    WALL_CONDITION_CLASSES = ["clean", "crack", "peeling", "water_damage", "mold"]
    TORCH_AVAILABLE = False

from backend.models.score import ImageInfo, CVModelResult, VisualEvidenceItem

logger = logging.getLogger("nivas.services.cv_model")

_LOCAL_MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "models" / "wall_condition_efficientnet.pth"
_ROOT_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "models" / "wall_condition_efficientnet.pth"
MODEL_WEIGHTS_PATH = _LOCAL_MODEL_PATH if _LOCAL_MODEL_PATH.exists() else _ROOT_MODEL_PATH
BLUR_VARIANCE_THRESHOLD = 50.0  # Images with Laplacian variance below 50.0 are flagged as blurry
VIDEO_SAMPLE_INTERVAL_SECONDS = 2.0


def compute_blur_variance(pil_img: Image.Image) -> float:
    """Compute 2D discrete Laplacian variance of grayscale image to measure sharpness."""
    gray = np.array(pil_img.convert("L"), dtype=np.float32)
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0

    lap = (
        gray[1:-1, 2:] + gray[1:-1, :-2] +
        gray[2:, 1:-1] + gray[:-2, 1:-1] -
        4 * gray[1:-1, 1:-1]
    )
    return float(np.var(lap))


def _image_signature(b64: Optional[str], url: Optional[str]) -> Optional[str]:
    """Generate a unique content signature for image deduplication."""
    if b64 and str(b64).strip():
        data = str(b64).strip()
        if "," in data:
            data = data.split(",", 1)[1]
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    if url and str(url).strip():
        return f"url:{str(url).strip()}"
    return None


async def _load_candidate_image(
    image_base64: Optional[str], image_url: Optional[str]
) -> Tuple[Optional[Image.Image], Optional[str]]:
    """
    Safely load and validate PIL RGB Image from URL or Base64 payload.
    Returns (img, error_message).
    """
    try:
        if image_base64 and str(image_base64).strip():
            b64_data = str(image_base64).strip()
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_data)
            if len(img_bytes) == 0:
                return None, "Corrupted 0-byte Base64 image payload."

            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            img.load()
            return img, None

        if image_url and str(image_url).strip():
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(str(image_url).strip())
                if resp.status_code != 200:
                    return None, f"HTTP {resp.status_code} error downloading property image."

                img_bytes = resp.content
                if len(img_bytes) == 0:
                    return None, "Downloaded 0-byte image file from URL."

                img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                img.load()
                return img, None
    except Exception as err:
        return None, f"Image parsing error ({type(err).__name__}): {str(err)}"

    return None, "No image_url or image_base64 provided."


async def load_and_validate_image(image_info: ImageInfo) -> Tuple[Optional[Image.Image], Optional[str]]:
    """Safely load and validate PIL RGB Image from ImageInfo. Retained for backwards compatibility."""
    if not image_info:
        return None, "No image_info provided."
    return await _load_candidate_image(image_info.image_base64, image_info.image_url)


def _extract_image_candidates(image_info: ImageInfo) -> List[Dict[str, Any]]:
    """
    Extract individual image candidates from ImageInfo while deduplicating
    and excluding thermal payloads. Preserves original upload order.
    """
    candidates: List[Dict[str, Any]] = []
    seen_signatures = set()

    thermal_b64_sig = _image_signature(getattr(image_info, "thermal_base64", None), None)
    thermal_url_sig = _image_signature(None, getattr(image_info, "thermal_url", None))

    def _is_thermal(img_type: Optional[str], sig: Optional[str]) -> bool:
        if img_type and str(img_type).strip().lower() in ("thermal", "ir", "infrared", "thermal_scan"):
            return True
        if sig and (sig == thermal_b64_sig or sig == thermal_url_sig):
            return True
        return False

    # 1. Process items from image_info.images list first if present
    raw_images = getattr(image_info, "images", None)
    if raw_images and isinstance(raw_images, list):
        for item in raw_images:
            b64 = item.get("image_base64") if isinstance(item, dict) else getattr(item, "image_base64", None)
            url = item.get("image_url") if isinstance(item, dict) else getattr(item, "image_url", None)
            file_name = item.get("file_name") if isinstance(item, dict) else getattr(item, "file_name", None)
            img_type = item.get("image_type") if isinstance(item, dict) else getattr(item, "image_type", None)

            sig = _image_signature(b64, url)
            if not sig:
                continue

            if _is_thermal(img_type, sig):
                logger.debug("Skipping thermal image from RGB CV candidate list: %s", file_name)
                continue

            if sig in seen_signatures:
                continue

            seen_signatures.add(sig)
            candidates.append({
                "image_base64": b64,
                "image_url": url,
                "file_name": file_name,
                "image_type": img_type or "RGB",
            })

    # 2. Check primary image_base64 / image_url (for legacy or single image requests)
    primary_b64 = getattr(image_info, "image_base64", None)
    primary_url = getattr(image_info, "image_url", None)
    primary_file_name = getattr(image_info, "file_name", None)
    primary_type = getattr(image_info, "image_type", None)

    primary_sig = _image_signature(primary_b64, primary_url)
    if primary_sig and not _is_thermal(primary_type, primary_sig):
        if primary_sig not in seen_signatures:
            seen_signatures.add(primary_sig)
            candidates.append({
                "image_base64": primary_b64,
                "image_url": primary_url,
                "file_name": primary_file_name,
                "image_type": primary_type or "RGB",
            })

    return candidates


def _result_from_probabilities(probabilities: List[float]) -> CVModelResult:
    """Apply the existing image-CV class, defect, and scoring rules to averaged probabilities."""
    probability_by_class = {
        class_name: probability
        for class_name, probability in zip(WALL_CONDITION_CLASSES, probabilities)
    }
    top_index = int(np.argmax(probabilities))
    defects = [
        defect
        for defect in ("damp", "algae", "mold", "broken")
        if probability_by_class.get(defect, 0.0) >= 0.25
    ]
    defect_coverage = round(min(1.0, sum(probability_by_class.get(defect, 0.0) for defect in defects)), 3)
    structural_score = (
        100.0 * probability_by_class.get("clean", 0.0)
        + 70.0 * probability_by_class.get("damp", 0.0)
        + 50.0 * probability_by_class.get("algae", 0.0)
        + 30.0 * probability_by_class.get("mold", 0.0)
        + 20.0 * probability_by_class.get("broken", 0.0)
    )
    return CVModelResult(
        predicted_class=WALL_CONDITION_CLASSES[top_index],
        confidence=round(float(probabilities[top_index]), 4),
        defects_detected=defects or ["none"],
        defect_coverage_ratio=defect_coverage,
        structural_score=round(max(0.0, min(100.0, structural_score)), 2),
        is_blurry=False,
    )


async def run_cv_analysis(image_info: Optional[ImageInfo]) -> Optional[CVModelResult]:
    """
    Run Computer Vision Wall-Condition Analysis (EfficientNet-B0 Transfer Learning).

    Classes: clean, damp, algae, mold, broken.

    Supports:
    - Multi-image RGB inspection: performs independent inference on each image,
      records individual visual evidence, and aggregates probability distributions.
    - Video-based CV analysis: sampled frame aggregation via run_video_cv_analysis.
    - Single image analysis: 100% backward compatible.

    Safeguards:
    1. Missing Image: Returns None if no image is provided.
    2. Invalid/Corrupted Image: Logs warning, skips corrupt image, continues with remaining valid images.
    3. Blurry Image: Skips blurry frames from score aggregation; flags is_blurry=True if all images are blurry.
    4. Thermal Filtering: Excludes thermal images from RGB CV pipeline.
    5. Deduplication: Ensures images are not evaluated multiple times.
    """
    if not image_info:
        logger.info("No image_info provided in request. Returning None.")
        return None

    if not TORCH_AVAILABLE:
        logger.info("PyTorch is not available in the current serverless runtime environment. Returning None for CV analysis.")
        return None

    if image_info.video_url or image_info.video_base64:
        return await run_video_cv_analysis(image_info)

    candidates = _extract_image_candidates(image_info)
    if not candidates:
        logger.info("No valid RGB property image candidates found. Returning None.")
        return None

    # Load model weights once for all candidates
    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
        if MODEL_WEIGHTS_PATH.exists():
            model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=False)
            state_dict = torch.load(MODEL_WEIGHTS_PATH, map_location=device)
            model.load_state_dict(state_dict)
            logger.info("Loaded fine-tuned EfficientNet-B0 checkpoint from %s", MODEL_WEIGHTS_PATH)
        else:
            model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=True)
            logger.info("Using pretrained EfficientNet-B0 transfer learning architecture for wall inference")

        model.to(device)
        model.eval()
        transform = get_eval_transforms()
    except Exception as model_err:
        logger.error("Failed to initialize EfficientNet-B0 model: %s", str(model_err))
        return None

    valid_probabilities: List[List[float]] = []
    evidence_items: List[VisualEvidenceItem] = []
    blurry_count = 0

    for candidate in candidates:
        file_name = candidate.get("file_name")
        b64 = candidate.get("image_base64")
        url = candidate.get("image_url")

        img, err_msg = await _load_candidate_image(b64, url)
        if img is None:
            logger.warning("Invalid property image candidate '%s': %s", file_name or "unknown", err_msg)
            continue

        blur_var = compute_blur_variance(img)
        if blur_var < BLUR_VARIANCE_THRESHOLD:
            logger.warning(
                "Property image '%s' is too blurry for defect classification (blur_variance=%.2f < %.2f).",
                file_name or "unknown", blur_var, BLUR_VARIANCE_THRESHOLD
            )
            blurry_count += 1
            continue

        try:
            input_tensor = transform(img).unsqueeze(0).to(device)
            with torch.no_grad():
                outputs = model(input_tensor)
                probs = F.softmax(outputs, dim=1).squeeze(0).cpu().tolist()

            top_idx = int(np.argmax(probs))
            top_class = WALL_CONDITION_CLASSES[top_idx]
            confidence = round(float(probs[top_idx]), 4)

            evidence_item = VisualEvidenceItem(
                file_name=file_name,
                image_url=url,
                image_base64=b64,
                predicted_class=top_class,
                confidence=confidence,
                is_video_frame=False
            )
            evidence_items.append(evidence_item)
            valid_probabilities.append(probs)
        except Exception as inf_err:
            logger.error("Inference failed for image '%s': %s", file_name or "unknown", str(inf_err))
            continue

    if not valid_probabilities:
        if blurry_count > 0:
            logger.warning("All provided property images (%d) were too blurry for CV analysis.", blurry_count)
            return CVModelResult(
                predicted_class="unclear_blurry",
                confidence=None,
                defects_detected=["blurry_image_warning"],
                defect_coverage_ratio=None,
                structural_score=None,
                is_blurry=True,
            )
        logger.warning("No valid images could be evaluated for CV analysis.")
        return None

    # Aggregate probabilities across all valid analyzed images
    averaged_probabilities = np.mean(np.asarray(valid_probabilities), axis=0).tolist()
    result = _result_from_probabilities(averaged_probabilities)
    result.visual_evidence = evidence_items
    return result


async def _load_video_bytes(image_info: ImageInfo) -> Tuple[Optional[bytes], Optional[str]]:
    """Load an uploaded video without treating its contents as a prediction."""
    try:
        if image_info.video_base64 and image_info.video_base64.strip():
            encoded = image_info.video_base64.strip()
            if "," in encoded:
                encoded = encoded.split(",", 1)[1]
            content = base64.b64decode(encoded)
            return (content, None) if content else (None, "Corrupted 0-byte Base64 video payload.")

        if image_info.video_url and image_info.video_url.strip():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(image_info.video_url.strip())
            if response.status_code != 200:
                return None, f"HTTP {response.status_code} error downloading property video."
            return (response.content, None) if response.content else (None, "Downloaded 0-byte video file.")
    except Exception as err:
        return None, f"Video parsing error ({type(err).__name__}): {str(err)}"

    return None, "No video_url or video_base64 provided."



async def run_video_cv_analysis(image_info: ImageInfo) -> Optional[CVModelResult]:
    """Sample a property video every ~2 seconds and aggregate valid frame predictions.

    This is deliberately frame-based rather than a temporal neural-network model.
    A video produces a result only when the existing checkpoint successfully
    classifies at least one non-blurry decoded frame.
    """
    if not TORCH_AVAILABLE:
        logger.info("PyTorch is not available in the current serverless runtime environment. Returning None for video CV.")
        return None

    if not MODEL_WEIGHTS_PATH.exists():
        logger.info("Trained model checkpoint '%s' not found. Returning None for video CV.", MODEL_WEIGHTS_PATH)
        return None

    try:
        import cv2
    except ImportError:
        logger.warning("OpenCV is not installed; returning None for video CV.")
        return None

    video_bytes, error_message = await _load_video_bytes(image_info)
    if video_bytes is None:
        logger.warning("Invalid property video: %s", error_message)
        return None

    suffix = ".mp4"
    if image_info.video_type and "webm" in image_info.video_type.lower():
        suffix = ".webm"
    elif image_info.video_type and "quicktime" in image_info.video_type.lower():
        suffix = ".mov"

    temporary_path = None
    capture = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary_file:
            temporary_file.write(video_bytes)
            temporary_path = temporary_file.name

        capture = cv2.VideoCapture(temporary_path)
        if not capture.isOpened():
            logger.warning("OpenCV could not decode the uploaded property video.")
            return None

        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_interval = max(1, round(fps * VIDEO_SAMPLE_INTERVAL_SECONDS)) if fps > 0 else 1
        device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
        if MODEL_WEIGHTS_PATH.exists():
            model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=False)
            model.load_state_dict(torch.load(MODEL_WEIGHTS_PATH, map_location=device))
        else:
            model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=True)
        model.to(device)
        model.eval()
        transform = get_eval_transforms()

        frame_index = 0
        valid_probabilities: List[List[float]] = []
        while True:
            success, frame = capture.read()
            if not success:
                break
            if frame_index % frame_interval == 0:
                frame_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if compute_blur_variance(frame_image) >= BLUR_VARIANCE_THRESHOLD:
                    with torch.no_grad():
                        output = model(transform(frame_image).unsqueeze(0).to(device))
                        valid_probabilities.append(F.softmax(output, dim=1).squeeze(0).cpu().tolist())
            frame_index += 1

        if not valid_probabilities:
            logger.warning("No valid non-blurry frames were available for property video CV analysis.")
            return CVModelResult(
                predicted_class="unclear_blurry",
                confidence=None,
                defects_detected=["blurry_or_invalid_video_frames"],
                defect_coverage_ratio=None,
                structural_score=None,
                is_blurry=True,
            )

        averaged_probabilities = np.mean(np.asarray(valid_probabilities), axis=0).tolist()
        return _result_from_probabilities(averaged_probabilities)
    except Exception as err:
        logger.error("Error executing frame-based video CV analysis: %s", str(err))
        return None
    finally:
        if capture is not None:
            capture.release()
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
