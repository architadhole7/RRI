import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ingestion.loaders import save_dataset
from backend.simulator.synthetic_data import SyntheticDataGenerator


def main():
    parser = argparse.ArgumentParser(description="Generate reproducible synthetic payment dataset for RevenueGuard.")
    parser.add_argument("--merchants", type=int, default=5, help="Number of merchants")
    parser.add_argument("--customers", type=int, default=1000, help="Number of customers")
    parser.add_argument("--transactions", type=int, default=5000, help="Number of failed transactions")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--data-dir", type=str, default="data", help="Target output directory")

    args = parser.parse_args()

    print(f"Generating synthetic ecosystem (Customers: {args.customers}, Transactions: {args.transactions}, Seed: {args.seed})...")
    generator = SyntheticDataGenerator(seed=args.seed)
    merchants, customers, payments, failures, ground_truth = generator.generate(
        num_merchants=args.merchants,
        num_customers=args.customers,
        num_transactions=args.transactions,
    )

    save_dataset(
        merchants=merchants,
        customers=customers,
        payments=payments,
        failures=failures,
        ground_truth=ground_truth,
        data_dir=args.data_dir,
    )

    print(f"Dataset generation complete!")
    print(f"- Merchants: {len(merchants)}")
    print(f"- Customers: {len(customers)}")
    print(f"- Payments: {len(payments)}")
    print(f"- Failures: {len(failures)}")
    print(f"- Ground Truth Records: {len(ground_truth)}")
    print(f"- Files saved to '{args.data_dir}/processed/' and '{args.data_dir}/ground_truth/'")


if __name__ == "__main__":
    main()
