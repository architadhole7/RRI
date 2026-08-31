from backend.analytics.reports import ReportGenerator
from backend.ingestion.schemas import EvaluationMetrics


def test_report_formatting_negative_and_positive():
    reporter = ReportGenerator()

    # Negative value formatting
    neg_curr = reporter.format_currency_diff(-160775.49)
    neg_pct = reporter.format_pct_diff(-7.28)
    assert neg_curr == "-₹160,775.49"
    assert neg_pct == "-7.28%"
    assert "+" not in neg_curr
    assert "+" not in neg_pct

    # Positive value formatting
    pos_curr = reporter.format_currency_diff(150000.0)
    pos_pct = reporter.format_pct_diff(5.2)
    assert pos_curr == "+₹150,000.00"
    assert pos_pct == "+5.20%"

    # Zero value formatting
    zero_curr = reporter.format_currency_diff(0.0)
    zero_pct = reporter.format_pct_diff(0.0)
    assert zero_curr == "₹0.00"
    assert zero_pct == "0.00%"


def test_report_generator_generates_markdown():
    reporter = ReportGenerator()
    metrics = EvaluationMetrics(
        total_transactions=100,
        total_at_risk_amount=100000.0,
        baseline_recovered_amount=40000.0,
        baseline_recovery_rate=0.40,
        revenueguard_automated_recovered_amount=35000.0,
        revenueguard_human_approved_recovered_amount=15000.0,
        total_recovered_amount=50000.0,
        recovery_rate=0.50,
        incremental_recovery_amount=10000.0,
        incremental_recovery_lift_pct=25.0,
    )
    j_path, m_path = reporter.generate_reports(metrics, output_dir="data/test_reports_out")
    assert j_path.endswith("evaluation_summary.json")
    assert m_path.endswith("evaluation_report.md")
