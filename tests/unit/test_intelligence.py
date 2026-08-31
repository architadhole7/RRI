from datetime import datetime, timezone

from backend.ingestion.schemas import Customer, FailureCategory, Payment, PaymentFailure, RecoveryAction
from backend.intelligence.failure_diagnosis import FailureDiagnoser
from backend.intelligence.features import FeatureExtractor
from backend.intelligence.recoverability import RecoverabilityModel


def test_failure_diagnoser_mappings():
    diagnoser = FailureDiagnoser()
    cat, conf = diagnoser.diagnose("ERR_NETWORK_TIMEOUT")
    assert cat == FailureCategory.NETWORK_ERROR
    assert conf >= 0.90

    cat2, conf2 = diagnoser.diagnose("UNKNOWN_CODE", message="Card expired by bank")
    assert cat2 == FailureCategory.EXPIRED_PAYMENT_METHOD
    assert conf2 >= 0.80


def test_feature_extractor_no_leakage():
    extractor = FeatureExtractor()
    payment = Payment(
        payment_id="pay_feat_1",
        merchant_id="mer_01",
        customer_id="cust_01",
        amount=2000.0,
        currency="INR",
        payment_method="CARD",
        status="FAILED",
        failure_code="ERR_BANK_DECLINED",
        created_at=datetime.now(timezone.utc),
    )
    features = extractor.extract_features(payment, RecoveryAction.RETRY_NOW)
    assert "amount_log" in features
    assert "retry_count" in features
    assert "recovered" not in features  # No future outcome leakage!


def test_recoverability_model_predictions():
    model = RecoverabilityModel()
    payment = Payment(
        payment_id="pay_rec_1",
        merchant_id="mer_01",
        customer_id="cust_01",
        amount=1500.0,
        currency="INR",
        payment_method="UPI",
        status="FAILED",
        failure_code="ERR_NETWORK_TIMEOUT",
        created_at=datetime.now(timezone.utc),
    )
    failure = PaymentFailure(
        payment_id="pay_rec_1",
        failure_code="ERR_NETWORK_TIMEOUT",
        failure_category=FailureCategory.NETWORK_ERROR,
        occurred_at=datetime.now(timezone.utc),
    )
    prob_retry = model.predict_probability(payment, RecoveryAction.RETRY_NOW, failure)
    prob_stop = model.predict_probability(payment, RecoveryAction.STOP, failure)

    assert prob_retry > 0.50
    assert prob_stop == 0.0
