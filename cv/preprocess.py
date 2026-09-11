import io
import logging
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
import torch
from torchvision import transforms

logger = logging.getLogger("nivas.cv.preprocess")

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def get_inference_pipeline() -> transforms.Compose:
    """Return standard PyTorch torchvision preprocessing transforms for 224x224 input."""
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def validate_and_load_image(image_path: Path) -> Tuple[bool, Optional[str], Optional[Image.Image]]:
    """
    Validate that an image file exists, is non-zero in size, and can be cleanly opened/verified by PIL.

    Returns:
        (is_valid: bool, error_message: str | None, image: PIL.Image | None)
    """
    if not image_path.exists():
        return False, f"File does not exist: {image_path}", None

    if image_path.stat().st_size == 0:
        return False, f"Corrupted 0-byte file: {image_path.name}", None

    try:
        # Step 1: PIL verification check
        with Image.open(image_path) as img:
            img.verify()

        # Step 2: Re-open file to load image into memory and convert to RGB
        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")
            # Force loading pixel data
            img_rgb.load()

        return True, None, img_rgb

    except Exception as err:
        return False, f"Corrupted or invalid image data ({type(err).__name__}): {str(err)}", None


def preprocess_image_file(image_path: Path) -> Tuple[bool, Optional[str], Optional[torch.Tensor]]:
    """
    Validate and preprocess a raw image file into a normalized (1, 3, 224, 224) PyTorch Tensor.
    """
    valid, err, img = validate_and_load_image(image_path)
    if not valid or img is None:
        return False, err, None

    try:
        pipeline = get_inference_pipeline()
        tensor = pipeline(img).unsqueeze(0)
        return True, None, tensor
    except Exception as err:
        return False, f"Preprocessing transform failed: {str(err)}", None
