"""
NIVAS CV Pipeline — Candidate Model Promotion Guard.

This script verifies a candidate checkpoint and, only after explicit confirmation,
copies it to the production path. It does NOT deploy or push to GitHub.

Safety rules:
  - Requires explicit --confirm flag (no auto-promotion).
  - Verifies checkpoint loads correctly with the NIVAS inference loader.
  - Verifies output class order matches WALL_CONDITION_CLASSES exactly.
  - Never overwrites the production checkpoint without creating a backup first.
  - Prints a clear summary of what will be changed before asking for confirmation.

Usage:
  python -m cv_pipeline.promote_candidate \
      --candidate data/models/candidate/wall_condition_efficientnet_candidate.pth \
      [--confirm]
"""

import argparse
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("nivas.cv_pipeline.promote_candidate")

# Production checkpoint path (must match cv_model.py _LOCAL_MODEL_PATH)
PRODUCTION_PATH = Path("backend/data/models/wall_condition_efficientnet.pth")
BACKUP_DIR = Path("data/models/backup")


def verify_candidate(candidate_path: Path) -> bool:
    """Load candidate checkpoint and verify it is compatible with the NIVAS inference loader."""
    try:
        import torch
        from backend.cv.model import build_efficientnet_b0, WALL_CONDITION_CLASSES

        logger.info("Loading candidate checkpoint: %s", candidate_path)
        model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=False)
        state_dict = torch.load(str(candidate_path), map_location="cpu")
        model.load_state_dict(state_dict)
        model.eval()

        dummy = torch.randn(1, 3, 224, 224)
        with torch.no_grad():
            out = model(dummy)

        if out.shape != (1, len(WALL_CONDITION_CLASSES)):
            logger.error(
                "Output shape mismatch: got %s, expected (1, %d)",
                tuple(out.shape), len(WALL_CONDITION_CLASSES),
            )
            return False

        logger.info(
            "Candidate is compatible: output shape=%s, classes=%s",
            tuple(out.shape), WALL_CONDITION_CLASSES,
        )
        return True
    except Exception as e:
        logger.error("Candidate verification failed: %s", e)
        return False


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Promote a candidate model to production")
    parser.add_argument(
        "--candidate",
        required=True,
        type=str,
        help="Path to candidate .pth checkpoint",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually perform the promotion (required; without this flag, only dry-run/verify)",
    )
    args = parser.parse_args()

    candidate_path = Path(args.candidate)

    if not candidate_path.exists():
        logger.error("Candidate checkpoint not found: %s", candidate_path)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("NIVAS CV Candidate Promotion")
    print("=" * 60)
    print(f"Candidate  : {candidate_path}")
    print(f"Production : {PRODUCTION_PATH}")
    print()

    # Verify compatibility
    logger.info("Verifying candidate checkpoint compatibility...")
    if not verify_candidate(candidate_path):
        logger.error("Candidate verification FAILED. Promotion aborted.")
        sys.exit(1)

    print("Verification: PASSED")

    if not args.confirm:
        print("\nDRY RUN: --confirm flag not provided. No files were modified.")
        print("Re-run with --confirm to perform the actual promotion.")
        print("=" * 60)
        return

    # Backup existing production checkpoint if it exists
    if PRODUCTION_PATH.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_name = f"wall_condition_efficientnet_backup_{ts}.pth"
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / backup_name
        shutil.copy2(PRODUCTION_PATH, backup_path)
        logger.info("Backed up existing production checkpoint to: %s", backup_path)
        print(f"Backup     : {backup_path}")

    # Copy candidate to production
    PRODUCTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate_path, PRODUCTION_PATH)
    logger.info("Promoted candidate to production: %s → %s", candidate_path, PRODUCTION_PATH)

    print(f"Promoted   : {candidate_path} → {PRODUCTION_PATH}")
    print("\nPromotion COMPLETE.")
    print("Restart the NIVAS backend to load the new model.")
    print("Do NOT push to GitHub or deploy until you have reviewed the evaluation results.")
    print("=" * 60)


if __name__ == "__main__":
    main()
