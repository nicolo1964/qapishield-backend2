"""
Stripe billing integration
"""
import logging
import stripe
from fastapi import HTTPException, status
from app.core.config import settings
from app.models.models import Facility

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

_SAFE_MESSAGE = "Unable to process billing request. Please try again or contact support."


def _call_stripe(operation: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except stripe.error.CardError as exc:
        logger.error("Stripe CardError during %s: %s", operation, exc)
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=_SAFE_MESSAGE) from exc
    except stripe.error.InvalidRequestError as exc:
        logger.error("Stripe InvalidRequestError during %s: %s", operation, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_SAFE_MESSAGE) from exc
    except stripe.error.StripeError as exc:
        logger.error("Stripe error during %s: %s: %s", operation, type(exc).__name__, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=_SAFE_MESSAGE) from exc


def create_customer(facility: Facility, admin_email: str) -> str:
    customer = _call_stripe(
        "create_customer", stripe.Customer.create,
        name=facility.name,
        email=admin_email,
        metadata={"facility_id": str(facility.id)},
    )
    return customer.id


def create_checkout_session(facility: Facility, customer_id: str, price_id: str) -> str:
    session = _call_stripe(
        "create_checkout_session", stripe.checkout.Session.create,
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.FRONTEND_BILLING_SUCCESS_URL,
        cancel_url=settings.FRONTEND_BILLING_CANCEL_URL,
        metadata={"facility_id": str(facility.id)},
    )
    return session.url


def create_portal_session(customer_id: str) -> str:
    session = _call_stripe(
        "create_portal_session", stripe.billing_portal.Session.create,
        customer=customer_id,
        return_url=settings.FRONTEND_BILLING_PORTAL_RETURN_URL,
    )
    return session.url


def verify_webhook_signature(payload: bytes, sig_header: str):
    return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)


def get_product(product_id: str) -> dict:
    return _call_stripe("get_product", stripe.Product.retrieve, product_id).to_dict()


def cancel_subscription(subscription_id: str) -> dict:
    """Schedules cancellation at the end of the current billing period."""
    return _call_stripe(
        "cancel_subscription", stripe.Subscription.modify, subscription_id, cancel_at_period_end=True
    ).to_dict()


def renew_subscription(subscription_id: str) -> dict:
    """Undoes a scheduled cancellation, so the subscription auto-renews again."""
    return _call_stripe(
        "renew_subscription", stripe.Subscription.modify, subscription_id, cancel_at_period_end=False
    ).to_dict()
