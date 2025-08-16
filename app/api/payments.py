from fastapi import APIRouter, HTTPException
from app.services.payment_service import PaymentService

router = APIRouter()

@router.get("/token")
def get_client_token():
    return {"client_token": PaymentService.generate_client_token()}

@router.post("/checkout")
def checkout(amount: str, payment_method_nonce: str):
    result = PaymentService.process_payment(amount, payment_method_nonce)
    if result.is_success:
        return {"transaction_id": result.transaction.id}
    else:
        raise HTTPException(status_code=400, detail=result.message)
