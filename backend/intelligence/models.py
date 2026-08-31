import json
import os
from pathlib import Path
from backend.intelligence.recoverability import RecoverabilityModel


def save_model(model: RecoverabilityModel, save_path: str = "data/models/recoverability_model.json") -> None:
    os.makedirs(Path(save_path).parent, exist_ok=True)
    payload = {
        "model_type": "RecoverabilityLogisticModel",
        "version": "1.0.0",
        "weights": model.weights,
    }
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_model(load_path: str = "data/models/recoverability_model.json") -> RecoverabilityModel:
    model = RecoverabilityModel()
    if Path(load_path).exists():
        with open(load_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
            if "weights" in payload:
                model.weights = payload["weights"]
    return model
