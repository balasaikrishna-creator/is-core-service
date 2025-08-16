import braintree
from app.core.config import settings

gateway = braintree.BraintreeGateway(
    braintree.Configuration(
        braintree.Environment.Sandbox,  # Use Sandbox for dev, switch to Production for live
        merchant_id=settings.BRAINTREE_MERCHANT_ID,
        public_key=settings.BRAINTREE_PUBLIC_KEY,
        private_key=settings.BRAINTREE_PRIVATE_KEY
    )
)

class PaymentService:
    @staticmethod
    def generate_client_token():
        return gateway.client_token.generate()

    @staticmethod
    def process_payment(amount, payment_method_nonce):
        """
        amount: str ("10.00")
        payment_method_nonce: str (from client)
        """
        result = gateway.transaction.sale({
            "amount": amount,
            "payment_method_nonce": payment_method_nonce,
            "options": {"submit_for_settlement": True}
        })
        return result
