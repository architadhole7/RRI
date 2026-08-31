from typing import Any
from backend.ingestion.schemas import FailureCategory, Payment, PaymentFailure

FAILURE_CODE_MAPPING = {
    "ERR_NETWORK_TIMEOUT": FailureCategory.NETWORK_ERROR,
    "ERR_GATEWAY_DOWN": FailureCategory.NETWORK_ERROR,
    "ERR_INSUFFICIENT_FUNDS": FailureCategory.INSUFFICIENT_FUNDS,
    "ERR_LOW_BALANCE": FailureCategory.INSUFFICIENT_FUNDS,
    "ERR_CARD_EXPIRED": FailureCategory.EXPIRED_PAYMENT_METHOD,
    "ERR_BANK_DECLINED": FailureCategory.BANK_DECLINED,
    "ERR_SECURITY_BLOCK": FailureCategory.BANK_DECLINED,
    "ERR_DAILY_LIMIT_EXCEEDED": FailureCategory.LIMIT_EXCEEDED,
    "ERR_TEMP_PROCESSING_ISSUE": FailureCategory.TEMPORARY_FAILURE,
}


class FailureDiagnoser:
    """Diagnoses payment failure categories from failure codes and transaction contexts."""

    def diagnose(
        self, failure_code: str | None, payment: Payment | None = None, message: str | None = None
    ) -> tuple[FailureCategory, float]:
        if failure_code and failure_code in FAILURE_CODE_MAPPING:
            return FAILURE_CODE_MAPPING[failure_code], 0.95

        # Heuristic message matching
        if message:
            msg_upper = message.upper()
            if "TIMEOUT" in msg_upper or "GATEWAY" in msg_upper:
                return FailureCategory.NETWORK_ERROR, 0.85
            if "BALANCE" in msg_upper or "FUNDS" in msg_upper:
                return FailureCategory.INSUFFICIENT_FUNDS, 0.85
            if "EXPIRED" in msg_upper:
                return FailureCategory.EXPIRED_PAYMENT_METHOD, 0.90
            if "DECLINED" in msg_upper or "BLOCK" in msg_upper:
                return FailureCategory.BANK_DECLINED, 0.80
            if "LIMIT" in msg_upper:
                return FailureCategory.LIMIT_EXCEEDED, 0.85

        return FailureCategory.UNKNOWN, 0.50

    def evaluate_performance(
        self, failures: list[PaymentFailure], ground_truth_categories: list[FailureCategory]
    ) -> dict[str, Any]:
        """Calculates precision, recall, F1, and accuracy for diagnosis classification."""
        total = len(failures)
        if total == 0:
            return {"accuracy": 0.0, "f1_score": 0.0, "total": 0}

        correct = 0
        cat_stats: dict[str, dict[str, int]] = {}

        for pf, gt_cat in zip(failures, ground_truth_categories):
            pred_cat, _ = self.diagnose(pf.failure_code, message=pf.failure_message)
            if pred_cat == gt_cat:
                correct += 1

            p_str = pred_cat.value
            g_str = gt_cat.value
            if g_str not in cat_stats:
                cat_stats[g_str] = {"tp": 0, "fp": 0, "fn": 0}
            if p_str not in cat_stats:
                cat_stats[p_str] = {"tp": 0, "fp": 0, "fn": 0}

            if pred_cat == gt_cat:
                cat_stats[g_str]["tp"] += 1
            else:
                cat_stats[p_str]["fp"] += 1
                cat_stats[g_str]["fn"] += 1

        accuracy = correct / total

        # Compute macro F1
        f1_scores = []
        for cat, stats in cat_stats.items():
            tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            f1_scores.append(f1)

        macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

        return {
            "total_samples": total,
            "accuracy": round(accuracy, 4),
            "macro_f1": round(macro_f1, 4),
        }
