from backend.analytics.evaluation import Evaluator
from backend.analytics.reports import ReportGenerator
from backend.simulator.synthetic_data import SyntheticDataGenerator


def test_evaluation_pipeline_runs_correctly():
    gen = SyntheticDataGenerator(seed=42)
    merchants, customers, payments, failures, ground_truth = gen.generate(
        num_merchants=2, num_customers=50, num_transactions=100
    )

    merchants_dict = {m.merchant_id: m for m in merchants}
    customers_dict = {c.customer_id: c for c in customers}
    payments_dict = {p.payment_id: p for p in payments}
    failures_dict = {f.payment_id: f for f in failures}

    evaluator = Evaluator(seed=42)
    metrics, rg_outcomes, baseline_outcomes = evaluator.run_evaluation(
        merchants=merchants_dict,
        customers=customers_dict,
        payments=payments_dict,
        failures=failures_dict,
        ground_truth=ground_truth,
    )

    assert metrics.total_transactions == 100
    assert metrics.total_at_risk_amount > 0.0
    assert metrics.total_recovered_amount >= 0.0
    assert metrics.baseline_recovered_amount >= 0.0

    reporter = ReportGenerator()
    j_path, m_path = reporter.generate_reports(metrics, output_dir="data/test_eval_output")
    assert "evaluation_summary.json" in j_path
    assert "evaluation_report.md" in m_path
