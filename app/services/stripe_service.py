"""
Stripe billing integration
"""
import stripe
from app.core.config import settings
from app.models.models import Facility

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_customer(facility: Facility, admin_email: str) -> str:
    customer = stripe.Customer.create(
        name=facility.name,
        email=admin_email,
        metadata={"facility_id": str(facility.id)},
    )
    return customer.id


def create_checkout_session(facility: Facility, customer_id: str, price_id: str) -> str:
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.FRONTEND_BILLING_SUCCESS_URL,
        cancel_url=settings.FRONTEND_BILLING_CANCEL_URL,
        metadata={"facility_id": str(facility.id)},
    )
    return session.url


def create_portal_session(customer_id: str) -> str:
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=settings.FRONTEND_BILLING_PORTAL_RETURN_URL,
    )
    return session.url


def verify_webhook_signature(payload: bytes, sig_header: str):
    return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)


def get_product(product_id: str) -> dict:
    return stripe.Product.retrieve(product_id).to_dict()


def cancel_subscription(subscription_id: str) -> dict:
    """Schedules cancellation at the end of the current billing period."""
    return stripe.Subscription.modify(subscription_id, cancel_at_period_end=True).to_dict()


def renew_subscription(subscription_id: str) -> dict:
    """Undoes a scheduled cancellation, so the subscription auto-renews again."""
    return stripe.Subscription.modify(subscription_id, cancel_at_period_end=False).to_dict()
