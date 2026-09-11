"""
NIVAS Computer Vision Evaluation Metrics Module.

Calculates multi-class classification metrics:
- Overall Accuracy
- Confusion Matrix (C x C)
- Per-class Precision, Recall, F1-score, and Support
- Macro-averaged Precision, Recall, and F1-score

Uses pure PyTorch / NumPy computation with no fabricated metrics.
"""

from typing import List, Dict, Any, Optional
import numpy as np


def compute_classification_metrics(
    y_true: List[int],
    y_pred: List[int],
    class_names: List[str],
    loss: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Computes rigorous classification metrics for multi-class classification.

    Args:
        y_true: List of ground-truth integer class indices.
        y_pred: List of predicted integer class indices.
        class_names: Ordered list of class labels (e.g. ['clean', 'damp', 'algae', 'mold']).
        loss: Optional average loss value for the evaluation batch/split.

    Returns:
        Structured dictionary with accuracy, macro metrics, per-class metrics, and confusion matrix.
    """
    num_classes = len(class_names)
    total_samples = len(y_true)

    if total_samples == 0:
        return {
            "loss": loss,
            "overall_accuracy": 0.0,
            "total_samples": 0,
            "macro_avg": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "per_class": {cls: {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0} for cls in class_names},
            "confusion_matrix": [[0] * num_classes for _ in range(num_classes)],
            "confusion_matrix_labels": class_names,
        }

    # Build Confusion Matrix: rows = actual class, cols = predicted class
    cm = [[0] * num_classes for _ in range(num_classes)]
    for true_label, pred_label in zip(y_true, y_pred):
        if 0 <= true_label < num_classes and 0 <= pred_label < num_classes:
            cm[true_label][pred_label] += 1

    # Overall Accuracy
    correct = sum(cm[i][i] for i in range(num_classes))
    overall_accuracy = round(correct / total_samples, 4)

    # Per-Class Metrics
    per_class_metrics: Dict[str, Dict[str, Any]] = {}
    precisions: List[float] = []
    recalls: List[float] = []
    f1s: List[float] = []

    for i, cls_name in enumerate(class_names):
        tp = cm[i][i]
        fp = sum(cm[r][i] for r in range(num_classes) if r != i)
        fn = sum(cm[i][c] for c in range(num_classes) if c != i)
        tn = total_samples - (tp + fp + fn)
        support = sum(cm[i][c] for c in range(num_classes))

        # Precision = TP / (TP + FP)
        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        # Recall = TP / (TP + FN)
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        # F1 = 2 * (P * R) / (P + R)
        if (precision + recall) > 0:
            f1 = round(2 * (precision * recall) / (precision + recall), 4)
        else:
            f1 = 0.0

        per_class_metrics[cls_name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
        }

        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)

    macro_precision = round(float(np.mean(precisions)), 4)
    macro_recall = round(float(np.mean(recalls)), 4)
    macro_f1 = round(float(np.mean(f1s)), 4)

    result: Dict[str, Any] = {
        "loss": round(loss, 4) if loss is not None else None,
        "overall_accuracy": overall_accuracy,
        "total_samples": total_samples,
        "macro_avg": {
            "precision": macro_precision,
            "recall": macro_recall,
            "f1": macro_f1,
        },
        "per_class": per_class_metrics,
        "confusion_matrix": cm,
        "confusion_matrix_labels": class_names,
    }

    return result
