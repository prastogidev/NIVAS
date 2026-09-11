"""
NIVAS Computer Vision Model Training Pipeline.

Trains a property-condition classifier using EfficientNet-B0 transfer learning.
Target classes: clean, damp, algae, mold, broken.

Features:
- Validates real datasets (fails safely if no real images exist without fabricating weights)
- Preprocessing and data augmentation (standard 224x224 ImageNet normalization)
- Configurable transfer learning (freezing backbone, custom learning rates)
- Class imbalance handling via inverse-frequency weighted Cross-Entropy loss
- Comprehensive validation metrics: loss, accuracy, precision, recall, F1 (macro & per-class), and confusion matrix
- Checkpoint output fully compatible with the NIVAS inference service
"""

import os
import json
import random
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
from torchvision.transforms import transforms

from backend.cv.model import build_efficientnet_b0, WALL_CONDITION_CLASSES
from backend.cv.preprocess import validate_and_load_image
from backend.cv.metrics import compute_classification_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nivas.cv.train")


def set_seed(seed: int = 42) -> None:
    """Set random seed for reproducibility across random, numpy, and torch."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def get_train_transforms() -> transforms.Compose:
    """Data augmentation and normalization pipeline for training."""
    return transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomResizedCrop(224, scale=(0.8, 1.0)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


def get_val_transforms() -> transforms.Compose:
    """Standard ImageNet evaluation transforms for validation and testing."""
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


def verify_real_dataset_exists(data_dir: Path) -> Tuple[int, Dict[str, int]]:
    """
    Scans the training directory to verify that real, valid image files exist.
    Does NOT count empty folders, hidden files, or corrupted zero-byte files.

    Returns:
        (total_valid_count, class_counts_dict)
    """
    train_path = data_dir / "train"
    if not train_path.exists():
        return 0, {}

    valid_count = 0
    class_counts: Dict[str, int] = {}

    for cls in WALL_CONDITION_CLASSES:
        cls_path = train_path / cls
        count = 0
        if cls_path.exists():
            for f in cls_path.glob("*"):
                if f.is_file() and not f.name.startswith("."):
                    is_valid, _, _ = validate_and_load_image(f)
                    if is_valid:
                        count += 1
        class_counts[cls] = count
        valid_count += count

    return valid_count, class_counts


def compute_class_weights(class_counts: Dict[str, int], device: torch.device) -> Optional[torch.Tensor]:
    """
    Calculates balanced class weights inversely proportional to class frequencies:
    w_c = N_total / (num_classes * N_c)
    """
    total = sum(class_counts.values())
    num_classes = len(WALL_CONDITION_CLASSES)
    if total == 0:
        return None

    weights = []
    for cls in WALL_CONDITION_CLASSES:
        count = class_counts.get(cls, 0)
        if count > 0:
            w = total / (num_classes * count)
        else:
            w = 1.0
        weights.append(w)

    weights_tensor = torch.tensor(weights, dtype=torch.float32, device=device)
    # Normalize so mean weight is 1.0
    weights_tensor = weights_tensor / weights_tensor.mean()
    return weights_tensor


def evaluate_model(
    model: nn.Module,
    data_loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Dict[str, Any]:
    """
    Evaluates model on validation/test split and calculates comprehensive metrics:
    accuracy, precision, recall, f1 (macro & per-class), and confusion matrix.
    """
    model.eval()
    total_loss = 0.0
    y_true: List[int] = []
    y_pred: List[int] = []

    with torch.no_grad():
        for images, labels in data_loader:
            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)
            loss = criterion(outputs, labels)
            total_loss += loss.item() * images.size(0)

            _, preds = torch.max(outputs, 1)
            y_true.extend(labels.cpu().tolist())
            y_pred.extend(preds.cpu().tolist())

    total_samples = len(y_true)
    avg_loss = (total_loss / total_samples) if total_samples > 0 else 0.0

    return compute_classification_metrics(
        y_true=y_true,
        y_pred=y_pred,
        class_names=WALL_CONDITION_CLASSES,
        loss=avg_loss,
    )


def train_wall_condition_model(
    data_dir: str = "data/wall_condition_dataset",
    output_model_path: str = "data/models/wall_condition_efficientnet.pth",
    output_metrics_path: str = "data/models/wall_condition_val_metrics.json",
    epochs: int = 15,
    batch_size: int = 16,
    lr: float = 1e-3,
    backbone_lr: float = 1e-4,
    freeze_backbone_epochs: int = 3,
    weight_decay: float = 1e-2,
    balance_classes: bool = True,
    early_stopping_patience: int = 5,
    seed: int = 42,
    num_workers: int = 2,
    device_name: str = "auto",
) -> Optional[Dict[str, Any]]:
    """
    Trains EfficientNet-B0 transfer learning model ONLY when real dataset images exist.
    Saves trained PyTorch weights and validation metrics.
    Does NOT fabricate accuracy numbers, fake model weights, or placeholder images.
    """
    set_seed(seed)
    data_path = Path(data_dir)
    out_model_path = Path(output_model_path)
    out_metrics_path = Path(output_metrics_path)

    out_model_path.parent.mkdir(parents=True, exist_ok=True)
    out_metrics_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Strict Dataset Verification Check
    total_train_valid, train_class_counts = verify_real_dataset_exists(data_path)
    logger.info("Dataset Verification: Found %d valid image files in %s/train", total_train_valid, data_dir)
    for cls, cnt in train_class_counts.items():
        logger.info("  - Class '%s': %d images", cls, cnt)

    if total_train_valid == 0:
        logger.warning(
            "Dataset directory '%s/train' contains 0 valid images. "
            "Training CANCELLED. Real dataset images must be placed in the class folders before training.",
            data_dir,
        )
        cancelled_report = {
            "status": "cancelled_no_dataset",
            "message": "Training aborted because no valid real wall-condition images exist in the training dataset directory.",
            "dataset_directory": str(data_dir),
            "class_counts": train_class_counts,
            "required_classes": WALL_CONDITION_CLASSES,
            "valid_samples_count": 0,
            "final_val_accuracy": None,
            "final_val_loss": None,
            "metrics_by_epoch": [],
        }
        with open(out_metrics_path, "w", encoding="utf-8") as f:
            json.dump(cancelled_report, f, indent=2)
        logger.info("Saved status report to: %s", out_metrics_path)
        return cancelled_report

    # 2. Select Computing Device
    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    else:
        device = torch.device(device_name)
    logger.info("Training EfficientNet-B0 on compute device: %s", device)

    # 3. Prepare Data Loaders
    train_path = data_path / "train"
    val_path = data_path / "val"

    train_dataset = ImageFolder(str(train_path), transform=get_train_transforms())
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=(device.type == "cuda"),
    )

    val_loader = None
    if val_path.exists():
        val_dataset = ImageFolder(str(val_path), transform=get_val_transforms())
        if len(val_dataset) > 0:
            val_loader = DataLoader(
                val_dataset,
                batch_size=batch_size,
                shuffle=False,
                num_workers=num_workers,
            )

    # 4. Configure Class Imbalance Handling
    if balance_classes:
        class_weights = compute_class_weights(train_class_counts, device)
        criterion = nn.CrossEntropyLoss(weight=class_weights)
        logger.info("Class-weighted CrossEntropyLoss enabled with weights: %s", class_weights.cpu().tolist() if class_weights is not None else None)
    else:
        criterion = nn.CrossEntropyLoss()

    # 5. Build Model & Fine-Tuning Strategy
    model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=True)
    model = model.to(device)

    # Freeze backbone if freeze_backbone_epochs > 0
    if freeze_backbone_epochs > 0:
        for param in model.features.parameters():
            param.requires_grad = False
        logger.info("Frozen EfficientNet-B0 backbone for the first %d epochs.", freeze_backbone_epochs)

    # Optimizer with parameter groups for classifier and backbone
    classifier_params = list(model.classifier.parameters())
    backbone_params = list(model.features.parameters())

    optimizer = torch.optim.AdamW([
        {"params": classifier_params, "lr": lr},
        {"params": backbone_params, "lr": backbone_lr if freeze_backbone_epochs == 0 else 0.0},
    ], weight_decay=weight_decay)

    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    best_val_f1 = 0.0
    epochs_no_improve = 0
    metrics_history: List[Dict[str, Any]] = []

    # 6. Training & Validation Loop
    logger.info("Starting training loop (%d epochs, batch_size=%d)...", epochs, batch_size)

    for epoch in range(epochs):
        # Unfreeze backbone after freeze_backbone_epochs
        if epoch == freeze_backbone_epochs and freeze_backbone_epochs > 0:
            logger.info("Unfreezing EfficientNet-B0 backbone for fine-tuning at epoch %d.", epoch + 1)
            for param in model.features.parameters():
                param.requires_grad = True
            optimizer.param_groups[1]["lr"] = backbone_lr

        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()

            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            _, preds = torch.max(outputs, 1)
            correct += torch.sum(preds == labels.data).item()
            total += labels.size(0)

        scheduler.step()
        train_epoch_loss = round(running_loss / total, 4) if total > 0 else 0.0
        train_epoch_acc = round(correct / total, 4) if total > 0 else 0.0

        epoch_record: Dict[str, Any] = {
            "epoch": epoch + 1,
            "train_loss": train_epoch_loss,
            "train_accuracy": train_epoch_acc,
        }

        if val_loader:
            val_metrics = evaluate_model(model, val_loader, criterion, device)
            epoch_record["val"] = val_metrics
            val_loss = val_metrics["loss"]
            val_acc = val_metrics["overall_accuracy"]
            val_f1 = val_metrics["macro_avg"]["f1"]

            logger.info(
                "Epoch [%d/%d] - Train Loss: %.4f, Train Acc: %.4f | Val Loss: %.4f, Val Acc: %.4f, Val Macro F1: %.4f",
                epoch + 1, epochs, train_epoch_loss, train_epoch_acc, val_loss, val_acc, val_f1
            )

            # Checkpoint saving on best validation loss
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_val_f1 = val_f1
                epochs_no_improve = 0
                torch.save(model.state_dict(), str(out_model_path))
                logger.info("Saved new best model checkpoint to %s (Val Loss: %.4f, Val F1: %.4f)", out_model_path, val_loss, val_f1)
            else:
                epochs_no_improve += 1
                if epochs_no_improve >= early_stopping_patience:
                    logger.info("Early stopping triggered after %d epochs without improvement.", epochs_no_improve)
                    metrics_history.append(epoch_record)
                    break
        else:
            logger.info("Epoch [%d/%d] - Train Loss: %.4f, Train Acc: %.4f", epoch + 1, epochs, train_epoch_loss, train_epoch_acc)
            # If no validation set, save model based on training loss
            if train_epoch_loss < best_val_loss:
                best_val_loss = train_epoch_loss
                torch.save(model.state_dict(), str(out_model_path))

        metrics_history.append(epoch_record)

    # 7. Final Metrics Output
    final_summary = {
        "status": "training_completed",
        "model_architecture": "EfficientNet-B0 Transfer Learning",
        "classes": WALL_CONDITION_CLASSES,
        "total_train_samples": total_train_valid,
        "train_class_counts": train_class_counts,
        "hyperparameters": {
            "epochs": epochs,
            "batch_size": batch_size,
            "lr": lr,
            "backbone_lr": backbone_lr,
            "freeze_backbone_epochs": freeze_backbone_epochs,
            "weight_decay": weight_decay,
            "balance_classes": balance_classes,
            "early_stopping_patience": early_stopping_patience,
            "seed": seed,
        },
        "best_val_loss": best_val_loss if best_val_loss != float("inf") else None,
        "best_val_macro_f1": best_val_f1 if best_val_f1 > 0 else None,
        "saved_checkpoint": str(out_model_path),
        "history": metrics_history,
    }

    with open(out_metrics_path, "w", encoding="utf-8") as f:
        json.dump(final_summary, f, indent=2)

    logger.info("Training complete. Model checkpoint saved to '%s', metrics to '%s'.", out_model_path, out_metrics_path)
    return final_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train NIVAS EfficientNet-B0 Wall Condition Model")
    parser.add_argument("--data_dir", type=str, default="data/wall_condition_dataset", help="Path to dataset directory")
    parser.add_argument("--output_model_path", type=str, default="data/models/wall_condition_efficientnet.pth", help="Path to save trained weights")
    parser.add_argument("--output_metrics_path", type=str, default="data/models/wall_condition_val_metrics.json", help="Path to save metrics JSON")
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=16, help="Training batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate for classifier head")
    parser.add_argument("--backbone_lr", type=float, default=1e-4, help="Learning rate for backbone")
    parser.add_argument("--freeze_backbone_epochs", type=int, default=3, help="Epochs to freeze backbone before fine-tuning")
    parser.add_argument("--weight_decay", type=float, default=1e-2, help="Weight decay for AdamW")
    parser.add_argument("--balance_classes", action="store_true", default=True, help="Enable class-weighted loss")
    parser.add_argument("--early_stopping_patience", type=int, default=5, help="Patience for early stopping")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--num_workers", type=int, default=2, help="DataLoader workers")
    parser.add_argument("--device", type=str, default="auto", help="Compute device ('cuda', 'mps', 'cpu', 'auto')")

    args = parser.parse_args()

    train_wall_condition_model(
        data_dir=args.data_dir,
        output_model_path=args.output_model_path,
        output_metrics_path=args.output_metrics_path,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        backbone_lr=args.backbone_lr,
        freeze_backbone_epochs=args.freeze_backbone_epochs,
        weight_decay=args.weight_decay,
        balance_classes=args.balance_classes,
        early_stopping_patience=args.early_stopping_patience,
        seed=args.seed,
        num_workers=args.num_workers,
        device_name=args.device,
    )
