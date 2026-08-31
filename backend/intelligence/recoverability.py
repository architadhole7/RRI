import math
from typing import Any

from backend.ingestion.schemas import Customer, FailureCategory, Payment, PaymentFailure, RecoveryAction
from backend.intelligence.features import FeatureExtractor


class RecoverabilityModel:
    """Predicts recovery probability P(recovery | transaction, action, context)."""

    def __init__(self, use_ml_weights: bool = True):
        self.feature_extractor = FeatureExtractor()
        self.use_ml_weights = use_ml_weights

        # Logistic Regression Weight Vector trained on synthetic patterns
        self.weights = {
            "bias": -1.2,
            "amount_log": -0.05,
            "retry_count": -0.45,
            "is_network": 0.80,
            "is_funds": 0.20,
            "is_expired": -1.50,
            "is_declined": -0.30,
            "is_limit": 0.10,
            "is_temp": 0.50,
            "is_upi": 0.15,
            "is_card": 0.05,
            "is_act_retry_now": 0.25,
            "is_act_retry_later": 0.40,
            "is_act_notify": 0.35,
            "is_act_escalate": 0.10,
            "is_act_stop": -3.00,
            "consent": 0.60,
            "risk_score": -0.80,
            "contact_count": -0.30,
            "succ_rate": 0.50,
        }

    def predict_probability(
        self,
        payment: Payment,
        action: RecoveryAction | str,
        failure: PaymentFailure | None = None,
        customer: Customer | None = None,
    ) -> float:
        if isinstance(action, str):
            action_enum = RecoveryAction(action)
        else:
            action_enum = action

        if action_enum == RecoveryAction.STOP:
            return 0.0

        features = self.feature_extractor.extract_features(payment, action_enum, failure, customer)

        # Baseline Heuristic Mode
        if not self.use_ml_weights:
            return self._heuristic_probability(payment, action_enum, failure, customer)

        # Logistic Sigmoidal Probability Prediction
        z = self.weights["bias"]
        for k, v in features.items():
            if k in self.weights:
                z += self.weights[k] * v

        # Action-category specific interaction boosts
        cat = failure.failure_category if failure else FailureCategory.UNKNOWN
        if cat == FailureCategory.NETWORK_ERROR and action_enum == RecoveryAction.RETRY_NOW:
            z += 2.2
        elif cat == FailureCategory.INSUFFICIENT_FUNDS and action_enum == RecoveryAction.RETRY_LATER:
            z += 1.8
        elif cat == FailureCategory.EXPIRED_PAYMENT_METHOD and action_enum == RecoveryAction.NOTIFY_CUSTOMER:
            if customer and customer.consent_to_contact:
                z += 2.5
        elif cat == FailureCategory.LIMIT_EXCEEDED and action_enum == RecoveryAction.RETRY_LATER:
            z += 1.5
        elif cat == FailureCategory.BANK_DECLINED and action_enum == RecoveryAction.ESCALATE:
            z += 1.2

        # Sigmoid activation function
        prob = 1.0 / (1.0 + math.exp(-z))

        # Clamp prediction to [0.0, 1.0]
        return round(max(0.0, min(1.0, prob)), 4)

    def _heuristic_probability(
        self,
        payment: Payment,
        action: RecoveryAction,
        failure: PaymentFailure | None,
        customer: Customer | None,
    ) -> float:
        cat = failure.failure_category if failure else FailureCategory.UNKNOWN
        if cat == FailureCategory.NETWORK_ERROR:
            return 0.80 if action == RecoveryAction.RETRY_NOW else 0.50
        elif cat == FailureCategory.INSUFFICIENT_FUNDS:
            return 0.65 if action == RecoveryAction.RETRY_LATER else 0.20
        elif cat == FailureCategory.EXPIRED_PAYMENT_METHOD:
            return 0.75 if action == RecoveryAction.NOTIFY_CUSTOMER and customer and customer.consent_to_contact else 0.05
        return 0.25

    def get_feature_importance(self) -> dict[str, float]:
        """Returns normalized feature importances derived from model coefficients."""
        total_mag = sum(abs(v) for k, v in self.weights.items() if k != "bias")
        if total_mag == 0:
            return {}
        return {
            k: round(abs(v) / total_mag, 4)
            for k, v in self.weights.items()
            if k != "bias"
        }

    def evaluate_model(self, y_true: list[int], y_prob: list[float]) -> dict[str, Any]:
        """Evaluates classification metrics & Brier calibration score."""
        n = len(y_true)
        if n == 0:
            return {"brier_score": 0.0, "accuracy": 0.0, "total": 0}

        brier = sum((p - t) ** 2 for p, t in zip(y_prob, y_true)) / n

        # Binary classification at 0.5 threshold
        correct = sum(1 for p, t in zip(y_prob, y_true) if (p >= 0.5) == (t == 1))
        acc = correct / n

        return {
            "total_samples": n,
            "brier_score": round(brier, 4),
            "accuracy": round(acc, 4),
        }
