import base64
import io
import logging
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np
from PIL import Image
import httpx
import torch
import torch.nn.functional as F

from backend.models.score import ImageInfo, CVModelResult
from backend.cv.model import build_efficientnet_b0, get_eval_transforms, WALL_CONDITION_CLASSES

logger = logging.getLogger("nivas.services.cv_model")

MODEL_WEIGHTS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "models" / "wall_condition_efficientnet.pth"
BLUR_VARIANCE_THRESHOLD = 50.0  # Images with Laplacian variance below 50.0 are flagged as blurry


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

    Classes: clean, damp, algae, mold.

    Safeguards:
    1. Missing Image: Returns None if no image is provided.
    2. Invalid/Corrupted Image: Logs warning and returns None cleanly.
    3. Blurry Image: Flags is_blurry=True and returns None score to prevent inaccurate scoring.
    4. Missing Model Weights: Returns None without fabricating fake predictions or metrics.
    """
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

    # Step 3: Model checkpoint verification
    if not MODEL_WEIGHTS_PATH.exists():
        logger.info(
            "Trained model checkpoint '%s' not found. "
            "Returning None to avoid generating fake predictions.",
            MODEL_WEIGHTS_PATH,
        )
        return None

    # Step 4: Model Inference
    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
        model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=False)
        state_dict = torch.load(MODEL_WEIGHTS_PATH, map_location=device)
        model.load_state_dict(state_dict)
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
        for defect_cls in ["damp", "algae", "mold"]:
            if prob_dict.get(defect_cls, 0.0) >= 0.25:
                detected_defects.append(defect_cls)
                defect_prob_sum += prob_dict[defect_cls]

        defect_coverage_ratio = round(min(1.0, defect_prob_sum), 3)

        # Transparent 0-100 normalized condition score
        clean_p = prob_dict.get("clean", 1.0)
        damp_p = prob_dict.get("damp", 0.0)
        algae_p = prob_dict.get("algae", 0.0)
        mold_p = prob_dict.get("mold", 0.0)

        structural_score = 100.0 * clean_p + 70.0 * damp_p + 50.0 * algae_p + 30.0 * mold_p
        structural_score = round(max(0.0, min(100.0, structural_score)), 2)

        return CVModelResult(
            predicted_class=top_class,
            confidence=confidence,
            defects_detected=detected_defects if detected_defects else ["none"],
            defect_coverage_ratio=defect_coverage_ratio,
            structural_score=structural_score,
            is_blurry=False,
        )
    except Exception as err:
        logger.error("Error executing EfficientNet-B0 CV model inference: %s", str(err))
        return None
