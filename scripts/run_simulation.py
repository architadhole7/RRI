import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.ingestion.loaders import load_dataset
from backend.orchestrator.executor import ActionExecutor
from backend.simulator.recovery import RecoverySimulator


def main():
    print("Running RevenueGuard recovery simulation...")
    dataset = load_dataset()
    payments = dataset.get("payments", {})
    failures = dataset.get("failures", {})
    customers = dataset.get("customers", {})
    ground_truth = dataset.get("ground_truth", {})

    if not payments:
        print("No payment data found! Generating dataset first...")
        from scripts.generate_dataset import main as gen_main
        gen_main()
        dataset = load_dataset()
        payments = dataset.get("payments", {})
        failures = dataset.get("failures", {})
        customers = dataset.get("customers", {})
        ground_truth = dataset.get("ground_truth", {})

    simulator = RecoverySimulator(ground_truth=ground_truth, seed=42)
    executor = ActionExecutor(simulator=simulator)

    executed_count = 0
    recovered_count = 0
    total_recovered_amount = 0.0

    print(f"Simulating orchestrator execution over {len(payments)} failed payments...")
    for p_id, p in payments.items():
        cust = customers.get(p.customer_id)
        fail = failures.get(p_id)

        res = executor.process_failed_payment(p, fail, cust)
        executed_count += 1

        outcome = res.get("outcome")
        if outcome and outcome.get("recovered"):
            recovered_count += 1
            total_recovered_amount += outcome.get("recovered_amount", 0.0)

    rec_rate = (recovered_count / executed_count * 100.0) if executed_count > 0 else 0.0
    print("\nSimulation Complete!")
    print(f"- Total Payments Processed: {executed_count}")
    print(f"- Payments Successfully Recovered: {recovered_count} ({rec_rate:.2f}%)")
    print(f"- Total Recovered Revenue: INR {total_recovered_amount:,.2f}")


if __name__ == "__main__":
    main()
