import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.analytics.evaluation import Evaluator
from backend.analytics.reports import ReportGenerator
from backend.ingestion.loaders import load_dataset


def main():
    print("Running Rigorous Baseline vs. RevenueGuard Evaluation...")
    dataset = load_dataset()
    merchants = dataset.get("merchants", {})
    customers = dataset.get("customers", {})
    payments = dataset.get("payments", {})
    failures = dataset.get("failures", {})
    ground_truth = dataset.get("ground_truth", {})

    if not payments:
        print("No payment data found! Running dataset generation...")
        from scripts.generate_dataset import main as gen_main
        gen_main()
        dataset = load_dataset()
        merchants = dataset.get("merchants", {})
        customers = dataset.get("customers", {})
        payments = dataset.get("payments", {})
        failures = dataset.get("failures", {})
        ground_truth = dataset.get("ground_truth", {})

    evaluator = Evaluator(seed=42)
    metrics, rg_outcomes, baseline_outcomes = evaluator.run_evaluation(
        merchants=merchants,
        customers=customers,
        payments=payments,
        failures=failures,
        ground_truth=ground_truth,
    )

    reporter = ReportGenerator()
    json_path, md_path = reporter.generate_reports(metrics)

    print("\n=======================================================")
    print("            EVALUATION RESULTS COMPARISON              ")
    print("=======================================================")
    print(f"Total Transactions Evaluated: {metrics.total_transactions}")
    print(f"Total Revenue at Risk:        INR {metrics.total_at_risk_amount:,.2f}")
    print(f"Fixed Baseline Recovery:      INR {metrics.baseline_recovered_amount:,.2f} ({metrics.baseline_recovery_rate*100:.2f}%)")
    print(f"RevenueGuard AI Recovery:     INR {metrics.total_recovered_amount:,.2f} ({metrics.recovery_rate*100:.2f}%)")
    inc_amt_str = (
        f"-INR {abs(metrics.incremental_recovery_amount):,.2f}"
        if metrics.incremental_recovery_amount < 0
        else f"+INR {metrics.incremental_recovery_amount:,.2f}"
    )
    inc_pct_str = (
        f"{metrics.incremental_recovery_lift_pct:.2f}%"
        if metrics.incremental_recovery_lift_pct < 0
        else f"+{metrics.incremental_recovery_lift_pct:.2f}%"
    )
    print(f"Incremental Revenue Lift:     {inc_amt_str} ({inc_pct_str})")
    print(f"Net Recovered (After Costs):  INR {metrics.net_recovery:,.2f}")
    print(f"Unsafe Actions Blocked:       {metrics.unsafe_actions_blocked}")
    print("=======================================================")
    print(f"JSON Summary: {json_path}")
    print(f"Markdown Report: {md_path}")


if __name__ == "__main__":
    main()
