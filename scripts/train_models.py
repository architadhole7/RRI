import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ingestion.loaders import load_dataset
from backend.intelligence.models import save_model
from backend.intelligence.recoverability import RecoverabilityModel
from backend.simulator.recovery import RecoverySimulator


def main():
    print("Loading synthetic dataset for model training...")
    dataset = load_dataset()
    payments = dataset.get("payments", {})
    failures = dataset.get("failures", {})
    customers = dataset.get("customers", {})
    ground_truth = dataset.get("ground_truth", {})

    if not payments:
        print("No payment data found! Running dataset generation first...")
        from scripts.generate_dataset import main as gen_main
        gen_main()
        dataset = load_dataset()
        payments = dataset.get("payments", {})
        failures = dataset.get("failures", {})
        customers = dataset.get("customers", {})
        ground_truth = dataset.get("ground_truth", {})

    print(f"Training recoverability prediction model on {len(payments)} payment contexts...")
    model = RecoverabilityModel()
    simulator = RecoverySimulator(ground_truth=ground_truth, seed=42)

    y_true = []
    y_prob = []

    for p_id, p in list(payments.items())[:2000]:
        cust = customers.get(p.customer_id)
        fail = failures.get(p_id)

        for act in p.failure_code and ["RETRY_NOW", "RETRY_LATER", "NOTIFY_CUSTOMER", "STOP"] or []:
            prob = model.predict_probability(p, act, fail, cust)
            outcome = simulator.simulate_action(p, act, cust, fail)

            y_prob.append(prob)
            y_true.append(1 if outcome.recovered else 0)

    eval_metrics = model.evaluate_model(y_true, y_prob)
    print("Model Training & Calibration Results:")
    print(f"- Samples Evaluated: {eval_metrics['total_samples']}")
    print(f"- Brier Calibration Score: {eval_metrics['brier_score']}")
    print(f"- Classification Accuracy: {eval_metrics['accuracy'] * 100:.2f}%")

    model_path = "data/models/recoverability_model.json"
    save_model(model, save_path=model_path)
    print(f"Model saved to '{model_path}'")


if __name__ == "__main__":
    main()
