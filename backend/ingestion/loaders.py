import json
import os
from pathlib import Path
from typing import Any

from backend.ingestion.schemas import Customer, Merchant, Payment, PaymentFailure
from backend.ingestion.validators import validate_customer, validate_payment, validate_payment_failure


def load_dataset(data_dir: str = "data/processed") -> dict[str, Any]:
    """Loads merchants, customers, payments, and failures from JSON files."""
    dir_path = Path(data_dir)
    
    merchants: dict[str, Merchant] = {}
    customers: dict[str, Customer] = {}
    payments: dict[str, Payment] = {}
    failures: dict[str, PaymentFailure] = {}
    ground_truth: dict[str, Any] = {}

    merchants_file = dir_path / "merchants.json"
    if merchants_file.exists():
        with open(merchants_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                m = Merchant(**item)
                merchants[m.merchant_id] = m

    customers_file = dir_path / "customers.json"
    if customers_file.exists():
        with open(customers_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                c = Customer(**item)
                validate_customer(c)
                customers[c.customer_id] = c

    payments_file = dir_path / "payments.json"
    if payments_file.exists():
        with open(payments_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                p = Payment(**item)
                validate_payment(p, customers if customers else None)
                payments[p.payment_id] = p

    failures_file = dir_path / "failures.json"
    if failures_file.exists():
        with open(failures_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                pf = PaymentFailure(**item)
                validate_payment_failure(pf)
                failures[pf.payment_id] = pf

    ground_truth_file = Path("data/ground_truth") / "ground_truth.json"
    if ground_truth_file.exists():
        with open(ground_truth_file, "r", encoding="utf-8") as f:
            ground_truth = json.load(f)

    return {
        "merchants": merchants,
        "customers": customers,
        "payments": payments,
        "failures": failures,
        "ground_truth": ground_truth,
    }


def save_dataset(
    merchants: list[Merchant],
    customers: list[Customer],
    payments: list[Payment],
    failures: list[PaymentFailure],
    ground_truth: dict[str, Any],
    data_dir: str = "data",
) -> None:
    """Saves dataset files to raw, processed, and ground_truth folders."""
    processed_dir = Path(data_dir) / "processed"
    gt_dir = Path(data_dir) / "ground_truth"
    
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(gt_dir, exist_ok=True)

    with open(processed_dir / "merchants.json", "w", encoding="utf-8") as f:
        json.dump([m.model_dump(mode="json") for m in merchants], f, indent=2)

    with open(processed_dir / "customers.json", "w", encoding="utf-8") as f:
        json.dump([c.model_dump(mode="json") for c in customers], f, indent=2)

    with open(processed_dir / "payments.json", "w", encoding="utf-8") as f:
        json.dump([p.model_dump(mode="json") for p in payments], f, indent=2)

    with open(processed_dir / "failures.json", "w", encoding="utf-8") as f:
        json.dump([pf.model_dump(mode="json") for pf in failures], f, indent=2)

    with open(gt_dir / "ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)
