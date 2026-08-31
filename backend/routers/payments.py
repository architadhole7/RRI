import logging
from fastapi import APIRouter, HTTPException, status
from backend.ingestion.loaders import load_dataset
from backend.ingestion.schemas import Payment
from backend.ingestion.validators import validate_payment

logger = logging.getLogger("revenueguard")

router = APIRouter(prefix="/payments", tags=["Payments"])

# In-memory payment repository
payments_db: dict[str, Payment] = {}


@router.post("", response_model=Payment, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=Payment, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_payment(payment: Payment):
    logger.info("Ingesting payment request: %s", payment.payment_id)
    try:
        validate_payment(payment)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    payments_db[payment.payment_id] = payment
    return payment


@router.get("", response_model=list[Payment])
@router.get("/", response_model=list[Payment], include_in_schema=False)
def list_payments():
    if not payments_db:
        dataset = load_dataset()
        for p in dataset.get("payments", {}).values():
            payments_db[p.payment_id] = p
    return list(payments_db.values())[:100]


@router.get("/{payment_id}", response_model=Payment)
def get_payment(payment_id: str):
    if payment_id not in payments_db:
        # Check dataset if not in memory
        dataset = load_dataset()
        if payment_id in dataset.get("payments", {}):
            payments_db[payment_id] = dataset["payments"][payment_id]
            return payments_db[payment_id]

        logger.warning("Payment ID '%s' not found", payment_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID '{payment_id}' not found",
        )
    return payments_db[payment_id]
