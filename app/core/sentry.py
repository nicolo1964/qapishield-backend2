"""
Sentry error monitoring setup
"""
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from app.core.config import settings


def init_sentry() -> None:
    if not settings.SENTRY_DSN:
        return

    # Report every 4xx/5xx, not just unhandled 5xx (the SDK's default) — an
    # explicit ask to see 401s/403s/etc., not only crashes.
    failed_status_codes = {*range(400, 599)}

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[
            StarletteIntegration(failed_request_status_codes=failed_status_codes),
            FastApiIntegration(failed_request_status_codes=failed_status_codes),
        ],
        send_default_pii=False,
    )
