from pydantic import BaseModel

class CheckoutRequest(BaseModel):
    amount: str
    payment_method_nonce: str