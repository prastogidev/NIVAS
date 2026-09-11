# NIVAS Wall Condition Dataset Guide

This directory contains the dataset structure for training the NIVAS Computer Vision Wall-Condition Classifier using **EfficientNet-B0** transfer learning.

---

## 1. Class Definitions & Mapping

The model classifies property/wall condition into **5 distinct structural classes**:

| Class Index | Class Name | Description | Example Visual Characteristics |
| :---: | :--- | :--- | :--- |
| `0` | `clean` | Intact, well-maintained wall surfaces | No discoloration, cracks, peeling, or biological growth |
| `1` | `damp` | Water seepage / moisture ingress | Dark moist patches, peeling paint from moisture, efflorescence |
| `2` | `algae` | Moss and green biological growth | Green or yellowish patches on external or damp masonry |
| `3` | `mold` | Black / dark fungal spore infestation | Black, grey, or dark brown spotted colonies, heavy spore clusters |
| `4` | `broken` | Clearly visible physical/property damage | Broken tiles, damaged wall surfaces, shattered/broken fixtures, damaged doors/windows, or other obvious physical defects |

---

## 2. Directory Structure

You can provide images in either of two ways:

### Option A: Raw Images (Automated Train/Val/Test Splitting)
Place raw, unsplit property images into `data/wall_condition_dataset/raw/`:
```text
data/wall_condition_dataset/
├── raw/
│   ├── clean/       <- Put raw clean wall images here
│   ├── damp/        <- Put raw damp wall images here
│   ├── algae/       <- Put raw algae wall images here
│   ├── mold/        <- Put raw mold wall images here
│   └── broken/      <- Put raw broken property/wall images here
```
Then run the automated stratified splitting script:
```bash
PYTHONPATH=. backend/venv/bin/python -m backend.cv.split_dataset --source_dir data/wall_condition_dataset/raw --train_ratio 0.70 --val_ratio 0.15 --test_ratio 0.15
```

### Option B: Pre-Partitioned Splits
Place images directly into the `train`, `val`, and `test` directories:
```text
data/wall_condition_dataset/
├── train/
│   ├── clean/
│   ├── damp/
│   ├── algae/
│   ├── mold/
│   └── broken/
├── val/
│   ├── clean/
│   ├── damp/
│   ├── algae/
│   ├── mold/
│   └── broken/
└── test/
    ├── clean/
    ├── damp/
    ├── algae/
    ├── mold/
    └── broken/
```

---

## 3. Image Requirements & Best Practices

1. **File Formats**: `.jpg`, `.jpeg`, `.png`, `.webp` (must be non-zero bytes and valid RGB images).
2. **Resolution**: Minimum recommended resolution is $224 \times 224$ pixels (images will be resized to $224 \times 224$ for inference/validation and random cropped from $256 \times 256$ for training).
3. **Lighting & Sharpness**:
   - Avoid extreme blur (images with Laplacian variance $< 50.0$ are flagged by the quality gate).
   - Ensure even lighting without extreme lens flare.
4. **No Fabricated / Mock Data**: Only use authentic property wall photos.

---

## 4. Pipeline Execution Workflow

### Step 1: Verify Dataset & Class Balance
Scans all images, validates file decodability, flags corrupted files, and computes class balance:
```bash
PYTHONPATH=. backend/venv/bin/python -m backend.cv.verify_dataset
```

### Step 2: Split Dataset (if using `raw/`)
```bash
PYTHONPATH=. backend/venv/bin/python -m backend.cv.split_dataset --source_dir data/wall_condition_dataset/raw
```

### Step 3: Run Training
Executes transfer learning with data augmentation, backbone freezing, class-weighted cross entropy, early stopping, and multi-class metrics logging:
```bash
PYTHONPATH=. backend/venv/bin/python -m backend.cv.train \
  --data_dir data/wall_condition_dataset \
  --output_model_path data/models/wall_condition_efficientnet.pth \
  --output_metrics_path data/models/wall_condition_val_metrics.json \
  --epochs 15 \
  --batch_size 16 \
  --lr 0.001 \
  --backbone_lr 0.0001 \
  --freeze_backbone_epochs 3 \
  --balance_classes \
  --early_stopping_patience 5
```

### Step 4: Inspect Validation Metrics
The training pipeline automatically outputs a comprehensive JSON evaluation report to `data/models/wall_condition_val_metrics.json` containing:
- Overall Accuracy
- Loss
- Macro Precision, Recall, F1
- Per-class Precision, Recall, F1, True Positives, False Positives, False Negatives, Support
- 5x5 Confusion Matrix

---

## 5. Production Compatibility

The output checkpoint (`data/models/wall_condition_efficientnet.pth`) is 100% compatible with the existing NIVAS production inference service (`backend/services/cv_model.py`). Once trained, restart or reload the backend service and it will automatically detect and load your fine-tuned weights!

> **Note**: This is currently a proof-of-concept dataset. The CV model cannot reliably detect broken property conditions until it has actually been trained and evaluated on real labeled data.
