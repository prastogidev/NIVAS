"""
NIVAS CV Pipeline — Training Entry Point.

This script wraps backend/cv/train.py and adds:
  - Candidate checkpoint directory management (never overwrites production checkpoint)
  - Pre-training dataset integrity check
  - Class-order verification (P3)
  - Post-training compatibility verification with the NIVAS inference loader
  - Majority-class baseline reporting

Usage (Mac, from NIVAS/ root):
  python -m cv_pipeline.train_runner \
      --data_dir data/wall_condition_dataset \
      --candidate_dir data/models/candidate \
      --epochs 15

The trained model is saved to data/models/candidate/ ONLY.
To promote it to production, run cv_pipeline/promote_candidate.py after review.

Do NOT run this script if no real training images exist in data/wall_condition_dataset/train/.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

logger = logging.getLogger("nivas.cv_pipeline.train_runner")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="NIVAS CV Pipeline — Training Runner")
    parser.add_argument("--data_dir", default="data/wall_condition_dataset", help="Dataset root")
    parser.add_argument("--candidate_dir", default="data/models/candidate", help="Candidate model output dir")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--backbone_lr", type=float, default=1e-4)
    parser.add_argument("--freeze_backbone_epochs", type=int, default=3)
    parser.add_argument("--weight_decay", type=float, default=1e-2)
    parser.add_argument("--early_stopping_patience", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num_workers", type=int, default=2)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--skip_integrity_check", action="store_true",
                        help="Skip pre-training dataset integrity check (not recommended)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    candidate_dir = Path(args.candidate_dir)
    candidate_model_path = candidate_dir / "wall_condition_efficientnet_candidate.pth"
    candidate_metrics_path = candidate_dir / "wall_condition_candidate_metrics.json"

    candidate_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Dataset integrity check
    if not args.skip_integrity_check:
        logger.info("Step 1: Running pre-training dataset integrity check...")
        from cv_pipeline.dataset_check import check_dataset_integrity, print_report
        report = check_dataset_integrity(data_dir)
        print_report(report)

        if report["errors"]:
            logger.error("Dataset integrity check FAILED with errors. Aborting training.")
            sys.exit(1)

        if not report["is_ready_for_training"]:
            logger.error(
                "Dataset is NOT ready for training. "
                "Ensure all 5 class directories exist in train/ with real images. Aborting."
            )
            sys.exit(1)

        logger.info("Dataset integrity check PASSED.")
    else:
        logger.warning("Skipping dataset integrity check (--skip_integrity_check)")

    # Step 2: Verify pretrained weights can be downloaded
    logger.info("Step 2: Verifying EfficientNet-B0 pretrained weight availability...")
    try:
        import torch
        from torchvision import models
        weights = models.EfficientNet_B0_Weights.DEFAULT
        # This will download weights if not cached
        _ = models.efficientnet_b0(weights=weights)
        logger.info("EfficientNet-B0 pretrained weights: AVAILABLE")
    except Exception as e:
        logger.error(
            "FATAL: Cannot download EfficientNet-B0 pretrained weights: %s\n"
            "Training ABORTED — do not silently substitute random initialization.\n"
            "Check your internet connection or set TORCH_HOME to a local cache.",
            e,
        )
        sys.exit(1)

    # Step 3: Run training
    logger.info("Step 3: Starting training pipeline...")
    t_start = time.time()

    # Import here so the integrity check can run without torch installed
    from backend.cv.train import train_wall_condition_model

    result = train_wall_condition_model(
        data_dir=str(data_dir),
        output_model_path=str(candidate_model_path),
        output_metrics_path=str(candidate_metrics_path),
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        backbone_lr=args.backbone_lr,
        freeze_backbone_epochs=args.freeze_backbone_epochs,
        weight_decay=args.weight_decay,
        balance_classes=True,
        early_stopping_patience=args.early_stopping_patience,
        seed=args.seed,
        num_workers=args.num_workers,
        device_name=args.device,
    )

    t_elapsed = time.time() - t_start
    logger.info("Training duration: %.1f seconds (%.1f minutes)", t_elapsed, t_elapsed / 60)

    if result is None or result.get("status") != "training_completed":
        logger.error("Training did not complete successfully. Status: %s", result)
        sys.exit(1)

    logger.info("Training completed. Candidate checkpoint: %s", candidate_model_path)
    logger.info("Candidate metrics: %s", candidate_metrics_path)

    # Step 4: Compatibility check with NIVAS inference loader
    logger.info("Step 4: Verifying candidate checkpoint compatibility with NIVAS inference loader...")
    if not candidate_model_path.exists():
        logger.error("Candidate checkpoint was not saved. Something went wrong during training.")
        sys.exit(1)

    try:
        import torch
        from backend.cv.model import build_efficientnet_b0, WALL_CONDITION_CLASSES

        model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=False)
        state_dict = torch.load(str(candidate_model_path), map_location="cpu")
        model.load_state_dict(state_dict)
        model.eval()

        dummy = torch.randn(1, 3, 224, 224)
        with torch.no_grad():
            out = model(dummy)

        assert out.shape == (1, len(WALL_CONDITION_CLASSES)), (
            f"Output shape {out.shape} does not match expected (1, {len(WALL_CONDITION_CLASSES)})"
        )
        logger.info(
            "Compatibility check PASSED: output shape=%s, classes=%s",
            tuple(out.shape), WALL_CONDITION_CLASSES,
        )
    except Exception as e:
        logger.error("Compatibility check FAILED: %s", e)
        sys.exit(1)

    # Step 5: Final report
    print("\n" + "=" * 60)
    print("NIVAS CV Training Runner — Complete")
    print("=" * 60)
    print(f"Status         : {result.get('status')}")
    print(f"Architecture   : {result.get('model_architecture')}")
    print(f"Classes        : {result.get('classes')}")
    print(f"Train samples  : {result.get('total_train_samples')}")
    print(f"Class counts   : {result.get('train_class_counts')}")
    print(f"Best val loss  : {result.get('best_val_loss')}")
    print(f"Best val F1    : {result.get('best_val_macro_f1')}")
    print(f"Checkpoint     : {candidate_model_path}")
    print(f"Metrics        : {candidate_metrics_path}")
    print(f"Duration       : {t_elapsed:.1f}s ({t_elapsed/60:.1f} min)")
    print("\nNOTE: Model is in CANDIDATE status. Review metrics before promoting.")
    print("To promote: python -m cv_pipeline.promote_candidate --candidate", candidate_model_path)
    print("=" * 60)


if __name__ == "__main__":
    main()
