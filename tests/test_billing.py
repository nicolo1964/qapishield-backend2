"""
Stripe billing error-mapping tests: verifies every _call_stripe-wrapped
Stripe SDK call maps CardError/InvalidRequestError/StripeError to the safe,
generic HTTP responses defined in app.services.stripe_service, and that the
webhook route's own signature-verification failure path stays safe too.
"""
from unittest.mock import MagicMock

import pytest
import stripe

from app.models.models import SubscriptionPlan
from app.services.stripe_service import _SAFE_MESSAGE
from tests.conftest import auth_headers


@pytest.fixture
def active_plan(db_session):
    plan = SubscriptionPlan(
        stripe_product_id="prod_test123",
        stripe_price_id="price_test123",
        name="Test Plan",
        amount=2999,
        currency="usd",
        interval="month",
        active=True,
    )
    db_session.add(plan)
    db_session.flush()
    return plan


@pytest.fixture
def facility_with_customer(facility, db_session):
    facility.stripe_customer_id = "cus_test123"
    db_session.commit()
    return facility


@pytest.fixture
def subscription_with_stripe_id(active_subscription, db_session):
    active_subscription.stripe_subscription_id = "sub_test123"
    db_session.commit()
    return active_subscription


STRIPE_ERROR_CASES = [
    pytest.param(
        lambda: stripe.error.CardError("Your card was declined.", None, "card_declined"),
        402,
        id="card_error_402",
    ),
    pytest.param(
        lambda: stripe.error.InvalidRequestError("Invalid parameter.", "price"),
        400,
        id="invalid_request_error_400",
    ),
    pytest.param(
        lambda: stripe.error.StripeError("Stripe had an internal issue."),
        502,
        id="generic_stripe_error_502",
    ),
]


def _assert_safe_response(response, expected_status):
    assert response.status_code == expected_status
    assert response.json() == {"detail": _SAFE_MESSAGE}
    text = response.text
    for leaked in ("cus_", "sub_", "price_", "prod_", "sk_", "card_declined", "Traceback"):
        assert leaked not in text


# --- checkout-session --------------------------------------------------

@pytest.mark.parametrize("make_error,expected_status", STRIPE_ERROR_CASES)
def test_checkout_session_create_checkout_error_maps_to_safe_response(
    client, admin_user, facility_with_customer, active_plan, monkeypatch, make_error, expected_status
):
    monkeypatch.setattr(stripe.checkout.Session, "create", MagicMock(side_effect=make_error()))
    response = client.post(
        "/api/v1/billing/checkout-session",
        json={"plan_id": active_plan.id},
        headers=auth_headers(admin_user),
    )
    _assert_safe_response(response, expected_status)


@pytest.mark.parametrize("make_error,expected_status", STRIPE_ERROR_CASES)
def test_checkout_session_create_customer_error_maps_to_safe_response(
    client, admin_user, active_plan, monkeypatch, make_error, expected_status
):
    monkeypatch.setattr(stripe.Customer, "create", MagicMock(side_effect=make_error()))
    response = client.post(
        "/api/v1/billing/checkout-session",
        json={"plan_id": active_plan.id},
        headers=auth_headers(admin_user),
    )
    _assert_safe_response(response, expected_status)


# --- portal-session ------------------------------------------------------

@pytest.mark.parametrize("make_error,expected_status", STRIPE_ERROR_CASES)
def test_portal_session_error_maps_to_safe_response(
    client, admin_user, facility_with_customer, monkeypatch, make_error, expected_status
):
    monkeypatch.setattr(stripe.billing_portal.Session, "create", MagicMock(side_effect=make_error()))
    response = client.post("/api/v1/billing/portal-session", headers=auth_headers(admin_user))
    _assert_safe_response(response, expected_status)


# --- cancel / renew subscription ------------------------------------------

@pytest.mark.parametrize("make_error,expected_status", STRIPE_ERROR_CASES)
def test_cancel_subscription_error_maps_to_safe_response(
    client, admin_user, subscription_with_stripe_id, monkeypatch, make_error, expected_status
):
    monkeypatch.setattr(stripe.Subscription, "modify", MagicMock(side_effect=make_error()))
    response = client.post("/api/v1/billing/cancel-subscription", headers=auth_headers(admin_user))
    _assert_safe_response(response, expected_status)


@pytest.mark.parametrize("make_error,expected_status", STRIPE_ERROR_CASES)
def test_renew_subscription_error_maps_to_safe_response(
    client, admin_user, subscription_with_stripe_id, monkeypatch, make_error, expected_status
):
    monkeypatch.setattr(stripe.Subscription, "modify", MagicMock(side_effect=make_error()))
    response = client.post("/api/v1/billing/renew-subscription", headers=auth_headers(admin_user))
    _assert_safe_response(response, expected_status)


# --- webhook: product lookup + signature verification ---------------------

class _FakeStripeObject(dict):
    def to_dict(self):
        return dict(self)


def _fake_price_event():
    return {
        "type": "price.created",
        "data": {
            "object": _FakeStripeObject({
                "id": "price_test123",
                "product": "prod_test123",
                "unit_amount": 2999,
                "currency": "usd",
                "recurring": {"interval": "month"},
                "active": True,
            })
        },
    }


@pytest.mark.parametrize("make_error,expected_status", STRIPE_ERROR_CASES)
def test_webhook_product_lookup_error_maps_to_safe_response(
    client, monkeypatch, make_error, expected_status
):
    monkeypatch.setattr(
        "app.api.v1.billing.verify_webhook_signature",
        lambda payload, sig_header: _fake_price_event(),
    )
    monkeypatch.setattr(stripe.Product, "retrieve", MagicMock(side_effect=make_error()))

    response = client.post(
        "/api/v1/billing/webhook",
        content=b'{"type": "price.created"}',
        headers={"stripe-signature": "t=1,v1=irrelevant"},
    )
    _assert_safe_response(response, expected_status)


def test_webhook_invalid_signature_returns_safe_400(client, monkeypatch):
    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        MagicMock(side_effect=stripe.error.SignatureVerificationError(
            "Unable to verify signature", "t=1,v1=bad_sig"
        )),
    )
    response = client.post(
        "/api/v1/billing/webhook",
        content=b'{"type": "price.created"}',
        headers={"stripe-signature": "t=1,v1=bad_sig"},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid webhook signature"}
    assert "bad_sig" not in response.text
    assert "sig_header" not in response.text
