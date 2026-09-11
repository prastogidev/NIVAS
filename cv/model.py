import torch
import torch.nn as nn
from torchvision import models
from torchvision.transforms import transforms
from typing import List

WALL_CONDITION_CLASSES: List[str] = ["clean", "damp", "algae", "mold"]


def get_eval_transforms() -> transforms.Compose:
    """Standard ImageNet preprocessing pipeline for 224x224 EfficientNet-B0 inference."""
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ),
    ])


def build_efficientnet_b0(num_classes: int = 4, pretrained: bool = True) -> nn.Module:
    """
    Build EfficientNet-B0 transfer learning architecture for wall-condition classification.
    Replaces the final classifier linear layer with num_classes outputs (clean, damp, algae, mold).
    """
    if pretrained:
        try:
            weights = models.EfficientNet_B0_Weights.DEFAULT
            model = models.efficientnet_b0(weights=weights)
        except Exception:
            model = models.efficientnet_b0(weights=None)
    else:
        model = models.efficientnet_b0(weights=None)

    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)
    return model
