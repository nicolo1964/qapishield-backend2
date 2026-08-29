"""
Subscription billing endpoints (Stripe)
"""
import logging
from datetime import datetime, timezone
from typing import List
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_role
from app.models.models import AuditActionType, Facility, Subscription, SubscriptionPlan, SubscriptionStatus, User, UserRole
from app.schemas.schemas import (
    CheckoutSessionRequest, CheckoutSessionResponse, PortalSessionResponse,
    PlanResponse, BillingStatusResponse, MessageResponse,
)
from app.services.stripe_service import (
    create_customer, create_checkout_session, create_portal_session,
    verify_webhook_signature, get_product, cancel_subscription, renew_subscription,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_or_create_subscription(db: Session, facility_id: int) -> Subscription:
    subscription = db.query(Subscription).filter(Subscription.facility_id == facility_id).first()
    if not subscription:
        subscription = Subscription(facility_id=facility_id, status=SubscriptionStatus.PENDING_PAYMENT)
        db.add(subscription)
        db.flush()
    return subscription


def _to_datetime(unix_ts) -> datetime:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc) if unix_ts else None


@router.get("/plans", response_model=List[PlanResponse])
async def list_plans(db: Session = Depends(get_db)):
    """
    Active subscription plans, synced from Stripe via webhook. Public — the
    frontend needs this before a facility has even logged in to pick a plan.
    """
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.active == True).all()


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def start_checkout(
    body: CheckoutSessionRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, action_type=AuditActionType.CREATE, resource_type="billing")),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Checkout session for the caller's facility to start/resume payment.
    """
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == body.plan_id, SubscriptionPlan.active == True
    ).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    facility = current_user.facility

    if not facility.stripe_customer_id:
        facility.stripe_customer_id = create_customer(facility, current_user.email)
        db.commit()
        db.refresh(facility)

    subscription = _get_or_create_subscription(db, facility.id)
    subscription.plan_id = plan.id
    db.commit()

    checkout_url = create_checkout_session(facility, facility.stripe_customer_id, plan.stripe_price_id)
    return {"checkout_url": checkout_url}


@router.post("/portal-session", response_model=PortalSessionResponse)
async def start_portal_session(
    current_user: User = Depends(require_role(UserRole.ADMIN, action_type=AuditActionType.CREATE, resource_type="billing")),
):
    """
    Create a Stripe Billing Portal session so the facility admin can view their
    plan, update their payment method, or cancel.
    """
    facility = current_user.facility
    if not facility.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found for this facility yet — start checkout first."
        )
    portal_url = create_portal_session(facility.stripe_customer_id)
    return {"portal_url": portal_url}


@router.post("/cancel-subscription", response_model=MessageResponse)
async def cancel(
    current_user: User = Depends(require_role(UserRole.ADMIN, action_type=AuditActionType.UPDATE, resource_type="billing")),
    db: Session = Depends(get_db),
):
    """
    Schedules cancellation at the end of the current billing period — access
    continues until then (not an immediate cutoff). Status updates for real
    once Stripe's customer.subscription.updated/deleted webhook fires.
    """
    subscription = current_user.facility.subscription
    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active subscription to cancel")

    cancel_subscription(subscription.stripe_subscription_id)
    subscription.cancel_at_period_end = True
    db.commit()
    return {"message": "Subscription will cancel at the end of the current billing period"}


@router.post("/renew-subscription", response_model=MessageResponse)
async def renew(
    current_user: User = Depends(require_role(UserRole.ADMIN, action_type=AuditActionType.UPDATE, resource_type="billing")),
    db: Session = Depends(get_db),
):
    """
    Undoes a scheduled cancellation, so the subscription auto-renews again.
    """
    subscription = current_user.facility.subscription
    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No subscription to renew")

    renew_subscription(subscription.stripe_subscription_id)
    subscription.cancel_at_period_end = False
    db.commit()
    return {"message": "Subscription will renew automatically"}


@router.get("/status", response_model=BillingStatusResponse)
async def get_billing_status(current_user: User = Depends(get_current_user)):
    """
    Current facility's full subscription + plan details. Available to any
    authenticated user in the facility, not just Admin, so staff can see if
    access is blocked. `subscription` is null if checkout was never started.
    """
    return {"subscription": current_user.facility.subscription}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook receiver. Not authenticated via JWT — every request is
    verified via Stripe's own signature before anything is trusted.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = verify_webhook_signature(payload, sig_header)
    except (stripe.error.SignatureVerificationError, ValueError) as exc:
        logger.error("Stripe webhook signature verification failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature") from exc

    event_type = event["type"]
    # Stripe's event data objects no longer behave like plain dicts in recent
    # SDK versions (.get() falls through to __getattr__ and raises) — convert
    # to a real dict up front so every .get() below works as expected.
    data = event["data"]["object"].to_dict()

    if event_type in ("price.created", "price.updated"):
        product = get_product(data["product"])
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.stripe_price_id == data["id"]).first()
        if not plan:
            plan = SubscriptionPlan(stripe_price_id=data["id"])
            db.add(plan)
        plan.stripe_product_id = product["id"]
        plan.name = product.get("name", "")
        plan.description = product.get("description")
        plan.amount = data.get("unit_amount") or 0
        plan.currency = data.get("currency", "")
        plan.interval = (data.get("recurring") or {}).get("interval", "")
        plan.active = bool(data.get("active")) and bool(product.get("active"))
        db.commit()

    elif event_type == "product.updated":
        product_active = bool(data.get("active"))
        plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.stripe_product_id == data["id"]).all()
        for plan in plans:
            plan.name = data.get("name", plan.name)
            plan.description = data.get("description")
            if not product_active:
                plan.active = False
        db.commit()

    elif event_type == "checkout.session.completed":
        facility_id = (data.get("metadata") or {}).get("facility_id")
        facility = db.query(Facility).filter(Facility.id == int(facility_id)).first() if facility_id else None
        if facility:
            subscription = _get_or_create_subscription(db, facility.id)
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.stripe_subscription_id = data.get("subscription")
            db.commit()

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        facility = db.query(Facility).filter(Facility.stripe_customer_id == customer_id).first()
        if facility and facility.subscription:
            facility.subscription.status = SubscriptionStatus.SUSPENDED
            db.commit()

    elif event_type == "invoice.payment_succeeded":
        customer_id = data.get("customer")
        facility = db.query(Facility).filter(Facility.stripe_customer_id == customer_id).first()
        if facility and facility.subscription:
            facility.subscription.status = SubscriptionStatus.ACTIVE
            db.commit()

    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        # Stripe's own subscription status is the authoritative source of
        # truth — catches transitions invoice events alone can miss.
        customer_id = data.get("customer")
        stripe_status = data.get("status")
        facility = db.query(Facility).filter(Facility.stripe_customer_id == customer_id).first()
        if facility:
            subscription = _get_or_create_subscription(db, facility.id)
            if stripe_status in ("active", "trialing"):
                subscription.status = SubscriptionStatus.ACTIVE
            elif stripe_status in ("past_due", "unpaid", "canceled", "incomplete_expired"):
                subscription.status = SubscriptionStatus.SUSPENDED
            subscription.stripe_subscription_id = data.get("id")
            items = (data.get("items") or {}).get("data", [])
            first_item = items[0] if items else {}
            subscription.current_period_start = _to_datetime(first_item.get("current_period_start"))
            subscription.current_period_end = _to_datetime(first_item.get("current_period_end"))
            subscription.cancel_at_period_end = bool(data.get("cancel_at_period_end"))
            db.commit()

    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        facility = db.query(Facility).filter(Facility.stripe_customer_id == customer_id).first()
        if facility and facility.subscription:
            facility.subscription.status = SubscriptionStatus.SUSPENDED
            db.commit()

    return {"received": True}
