import json
from pathlib import Path
from typing import Any
from fastapi import APIRouter
from backend.analytics.evaluation import Evaluator
from backend.ingestion.loaders import load_dataset
from backend.ingestion.schemas import PolicyConfig

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
def get_analytics_summary() -> dict[str, Any]:
    eval_file = Path("data/evaluation/evaluation_summary.json")
    if eval_file.exists():
        with open(eval_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fallback run evaluation if summary does not exist
    dataset = load_dataset()
    if dataset.get("payments"):
        evaluator = Evaluator(seed=42)
        metrics, _, _ = evaluator.run_evaluation(
            merchants=dataset["merchants"],
            customers=dataset["customers"],
            payments=dataset["payments"],
            failures=dataset["failures"],
            ground_truth=dataset["ground_truth"],
        )
        return metrics.model_dump(mode="json")

    return {
        "status": "no_data",
        "message": "Run dataset generation and evaluation first.",
    }


@router.post("/simulate-policy")
def simulate_policy_adjustment(config: PolicyConfig) -> dict[str, Any]:
    """Runs actual evaluation logic against existing dataset with specified policy configuration."""
    dataset = load_dataset()
    payments = dataset.get("payments", {})
    if not payments:
        return {"status": "error", "message": "No dataset found for simulation."}

    evaluator = Evaluator(seed=42, policy_config=config)
    metrics, _, _ = evaluator.run_evaluation(
        merchants=dataset.get("merchants", {}),
        customers=dataset.get("customers", {}),
        payments=payments,
        failures=dataset.get("failures", {}),
        ground_truth=dataset.get("ground_truth", {}),
    )

    return metrics.model_dump(mode="json")
