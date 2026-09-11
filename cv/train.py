import os
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
from torchvision.transforms import transforms

from backend.cv.model import build_efficientnet_b0, WALL_CONDITION_CLASSES
from backend.cv.preprocess import validate_and_load_image

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("nivas.cv.train")


def get_train_transforms() -> transforms.Compose:
    """Augmentation transforms for training wall-condition classifier."""
    return transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomResizedCrop(224, scale=(0.8, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


def get_val_transforms() -> transforms.Compose:
    """Standard evaluation transforms for validation dataset."""
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


def verify_real_dataset_exists(data_dir: Path) -> Tuple_Count:
    """
    Scans the training split directory to verify that real, valid image files exist.
    Does NOT count empty folders, hidden files, or corrupted zero-byte files.
    """
    train_path = data_dir / "train"
    if not train_path.exists():
        return 0, {}

    valid_count = 0
    class_counts = {}

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


def calculate_val_metrics(
    model: nn.Module,
    val_loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Dict[str, Any]:
    """Calculate validation loss, overall accuracy, and class-level accuracy."""
    model.eval()
    val_loss = 0.0
    correct = 0
    total = 0

    class_correct = {cls: 0 for cls in WALL_CONDITION_CLASSES}
    class_total = {cls: 0 for cls in WALL_CONDITION_CLASSES}

    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            val_loss += loss.item() * images.size(0)

            _, preds = torch.max(outputs, 1)
            correct += torch.sum(preds == labels).item()
            total += labels.size(0)

            for p, l in zip(preds, labels):
                cls_name = WALL_CONDITION_CLASSES[l.item()]
                class_total[cls_name] += 1
                if p == l:
                    class_correct[cls_name] += 1

    avg_loss = round(val_loss / total, 4) if total > 0 else 0.0
    accuracy = round(correct / total, 4) if total > 0 else 0.0

    class_accuracy = {}
    for cls in WALL_CONDITION_CLASSES:
        tot = class_total[cls]
        class_accuracy[cls] = round(class_correct[cls] / tot, 4) if tot > 0 else None

    return {
        "val_loss": avg_loss,
        "val_accuracy": accuracy,
        "class_accuracy": class_accuracy,
        "total_val_samples": total,
    }


def train_wall_condition_model(
    data_dir: str,
    output_model_path: str,
    output_metrics_path: str,
    epochs: int = 10,
    batch_size: int = 16,
    lr: float = 1e-3,
) -> Optional[Dict[str, Any]]:
    """
    Train EfficientNet-B0 transfer learning model ONLY if a real dataset exists.
    Saves trained PyTorch weights and validation metrics.
    Does NOT fabricate accuracy numbers or fake model weights.
    """
    data_path = Path(data_dir)
    models_dir = Path(output_model_path).parent
    models_dir.mkdir(parents=True, exist_ok=True)

    # 1. Strict Dataset Verification
    total_valid, class_counts = verify_real_dataset_exists(data_path)
    logger.info("Dataset Verification: Found %d valid real image files in %s/train", total_valid, data_dir)

    if total_valid == 0:
        logger.warning(
            "Dataset directory '%s/train' contains 0 valid images. "
            "Training CANCELLED. Cannot train EfficientNet-B0 model without a real dataset.",
            data_dir,
        )
        cancelled_metrics = {
            "status": "cancelled_no_dataset",
            "message": "Training skipped because no valid real wall-condition images exist in dataset directory.",
            "valid_samples_count": 0,
            "final_val_accuracy": None,
            "final_val_loss": None,
            "metrics_by_epoch": [],
        }
        with open(output_metrics_path, "w", encoding="utf-8") as f:
            json.dump(cancelled_metrics, f, indent=2)
        logger.info("Saved status report to: %s", output_metrics_path)
        return cancelled_metrics

    # 2. Setup Device & Data Loaders
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    logger.info("Training EfficientNet-B0 on device: %s", device)

    train_path = data_path / "train"
    val_path = data_path / "val"

    train_dataset = ImageFolder(str(train_path), transform=get_train_transforms())
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=2)

    val_loader = None
    if val_path.exists():
        val_dataset = ImageFolder(str(val_path), transform=get_val_transforms())
        if len(val_dataset) > 0:
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    # 3. Build Model & Optimizer
    model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=True)
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_loss = float("inf")
    metrics_history = []

    # 4. Training & Evaluation Loop
    for epoch in range(epochs):
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
        epoch_train_loss = round(running_loss / total, 4) if total > 0 else 0.0
        epoch_train_acc = round(correct / total, 4) if total > 0 else 0.0

        epoch_metrics = {
            "epoch": epoch + 1,
            "train_loss": epoch_train_loss,
            "train_accuracy": epoch_train_acc,
        }

        if val_loader:
            val_res = calculate_val_metrics(model, val_loader, criterion, device)
            epoch_metrics.update(val_res)
            logger.info(
                "Epoch [%d/%d] - Train Loss: %.4f, Train Acc: %.4f | Val Loss: %.4f, Val Acc: %.4f",
                epoch + 1, epochs, epoch_train_loss, epoch_train_acc, val_res["val_loss"], val_res["val_accuracy"]
            )
        else:
            logger.info(
                "Epoch [%d/%d] - Train Loss: %.4f, Train Acc: %.4f",
                epoch + 1, epochs, epoch_train_loss, epoch_train_acc
            )

        metrics_history.append(epoch_metrics)

        if epoch_train_loss < best_loss:
            best_loss = epoch_train_loss
            torch.save(model.state_dict(), output_model_path)
            logger.info("Saved best model checkpoint to %s", output_model_path)

    # 5. Save Final Validation Metrics
    final_metrics = {
        "status": "training_completed",
        "total_train_samples": total_valid,
        "epochs": epochs,
        "final_train_loss": metrics_history[-1]["train_loss"],
        "final_train_accuracy": metrics_history[-1]["train_accuracy"],
        "final_val_loss": metrics_history[-1].get("val_loss"),
        "final_val_accuracy": metrics_history[-1].get("val_accuracy"),
        "metrics_by_epoch": metrics_history,
    }

    with open(output_metrics_path, "w", encoding="utf-8") as f:
        json.dump(final_metrics, f, indent=2)

    logger.info("Training complete. Model saved to '%s', metrics to '%s'.", output_model_path, output_metrics_path)
    return final_metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train EfficientNet-B0 Wall Condition Model")
    parser.add_argument("--data_dir", type=str, default="data/wall_condition_dataset")
    parser.add_argument("--output_model_path", type=str, default="data/models/wall_condition_efficientnet.pth")
    parser.add_argument("--output_metrics_path", type=str, default="data/models/wall_condition_val_metrics.json")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()

    train_wall_condition_model(
        data_dir=args.data_dir,
        output_model_path=args.output_model_path,
        output_metrics_path=args.output_metrics_path,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
    )
