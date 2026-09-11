import base64
import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np
from PIL import Image
import httpx
import torch
import torch.nn.functional as F

from backend.models.score import ImageInfo, CVModelResult, VisualEvidenceItem
from backend.cv.model import build_efficientnet_b0, get_eval_transforms, WALL_CONDITION_CLASSES

logger = logging.getLogger("nivas.services.cv_model")

MODEL_WEIGHTS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "models" / "wall_condition_efficientnet.pth"
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


async def load_and_validate_image(image_info: ImageInfo) -> Tuple[Optional[Image.Image], Optional[str]]:
    """
    Safely load and validate PIL RGB Image from URL or Base64 payload.
    Returns (img, error_message).
    """
    try:
        if image_info.image_base64 and image_info.image_base64.strip():
            b64_data = image_info.image_base64.strip()
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_data)
            if len(img_bytes) == 0:
                return None, "Corrupted 0-byte Base64 image payload."

            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            img.load()
            return img, None

        if image_info.image_url and image_info.image_url.strip():
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(image_info.image_url.strip())
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


async def run_cv_analysis(image_info: Optional[ImageInfo]) -> Optional[CVModelResult]:
    """
    Run Computer Vision Wall-Condition Analysis (EfficientNet-B0 Transfer Learning).

    Classes: clean, damp, algae, mold, broken.

    Safeguards:
    1. Missing Image: Returns None if no image is provided.
    2. Invalid/Corrupted Image: Logs warning and returns None cleanly.
    3. Blurry Image: Flags is_blurry=True and returns None score to prevent inaccurate scoring.
    4. Missing Model Weights: Returns None without fabricating fake predictions or metrics.
    """
    if image_info and (image_info.video_url or image_info.video_base64):
        return await run_video_cv_analysis(image_info)

    if not image_info or (not image_info.image_url and not image_info.image_base64):
        logger.info("No property image provided in request. Returning None.")
        return None

    # Step 1: Safe image loading & validation
    img, err_msg = await load_and_validate_image(image_info)
    if img is None:
        logger.warning("Invalid property wall image: %s", err_msg)
        return None

    # Step 2: Blurry image quality check
    blur_var = compute_blur_variance(img)
    if blur_var < BLUR_VARIANCE_THRESHOLD:
        logger.warning(
            "Property image is too blurry for accurate defect classification (blur_variance=%.2f < %.2f).",
            blur_var, BLUR_VARIANCE_THRESHOLD
        )
        return CVModelResult(
            predicted_class="unclear_blurry",
            confidence=None,
            defects_detected=["blurry_image_warning"],
            defect_coverage_ratio=None,
            structural_score=None,
            is_blurry=True,
        )

    # Step 3 & 4: Model loading & inference
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
        input_tensor = transform(img).unsqueeze(0).to(device)

        with torch.no_grad():
            outputs = model(input_tensor)
            probs = F.softmax(outputs, dim=1).squeeze(0).cpu().tolist()

        prob_dict = {cls_name: prob for cls_name, prob in zip(WALL_CONDITION_CLASSES, probs)}

        # Predicted class & confidence
        top_idx = int(np.argmax(probs))
        top_class = WALL_CONDITION_CLASSES[top_idx]
        confidence = round(float(probs[top_idx]), 4)

        # Defect detection threshold (>= 25% probability)
        detected_defects: List[str] = []
        defect_prob_sum = 0.0
        for defect_cls in ["damp", "algae", "mold", "broken"]:
            if prob_dict.get(defect_cls, 0.0) >= 0.25:
                detected_defects.append(defect_cls)
                defect_prob_sum += prob_dict[defect_cls]

        defect_coverage_ratio = round(min(1.0, defect_prob_sum), 3)

        # Transparent 0-100 normalized condition score
        # Weights reflect severity: clean=100, damp=70, algae=50, mold=30, broken=20
        # broken (20.0) is the most severe — direct physical/structural damage
        clean_p = prob_dict.get("clean", 1.0)
        damp_p = prob_dict.get("damp", 0.0)
        algae_p = prob_dict.get("algae", 0.0)
        mold_p = prob_dict.get("mold", 0.0)
        broken_p = prob_dict.get("broken", 0.0)

        structural_score = 100.0 * clean_p + 70.0 * damp_p + 50.0 * algae_p + 30.0 * mold_p + 20.0 * broken_p
        structural_score = round(max(0.0, min(100.0, structural_score)), 2)

        # Build visual evidence item from the actual analyzed image
        evidence_item = VisualEvidenceItem(
            file_name=image_info.file_name,
            image_url=image_info.image_url,
            image_base64=image_info.image_base64,
            predicted_class=top_class,
            confidence=confidence,
            is_video_frame=False
        )

        return CVModelResult(
            predicted_class=top_class,
            confidence=confidence,
            defects_detected=detected_defects if detected_defects else ["none"],
            defect_coverage_ratio=defect_coverage_ratio,
            structural_score=structural_score,
            is_blurry=False,
            visual_evidence=[evidence_item]
        )
    except Exception as err:
        logger.error("Error executing EfficientNet-B0 CV model inference: %s", str(err))
        return None


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


async def run_video_cv_analysis(image_info: ImageInfo) -> Optional[CVModelResult]:
    """Sample a property video every ~2 seconds and aggregate valid frame predictions.

    This is deliberately frame-based rather than a temporal neural-network model.
    A video produces a result only when the existing checkpoint successfully
    classifies at least one non-blurry decoded frame.
    """
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
