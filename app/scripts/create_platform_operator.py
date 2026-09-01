"""
One-time management command to create (or rotate) a platform-operator
credential. This intentionally has NO HTTP surface at all -- the only way
to create an operator is to run this directly against the production
database (e.g. via `render ssh` / the Render shell), which keeps the
attack surface for "who can become a platform operator" at zero over the
network.

Usage (run in the backend's own environment, where DATABASE_URL is set):

    python -m app.scripts.create_platform_operator "Deborah - Sales Ops"

    # to rotate/replace an existing operator's key instead of creating a
    # new operator row:
    python -m app.scripts.create_platform_operator "Deborah - Sales Ops" --rotate 3

The raw operator key is printed to stdout exactly once and is never
stored anywhere (only its SHA-256 hash is persisted). Copy it immediately
into your own password manager / secrets tool -- it cannot be recovered
later, only rotated (which invalidates the old key).
"""
import argparse
import hashlib
import secrets
import sys

from app.core.database import SessionLocal
from app.models.models import PlatformOperator


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Human-readable label for this operator, e.g. 'Deborah - Sales Ops'")
    parser.add_argument(
        "--rotate", type=int, metavar="OPERATOR_ID", default=None,
        help="Rotate the key for an existing operator id instead of creating a new operator",
    )
    parser.add_argument(
        "--deactivate", type=int, metavar="OPERATOR_ID", default=None,
        help="Deactivate an existing operator id (e.g. offboarding) and exit",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.deactivate is not None:
            operator = db.query(PlatformOperator).filter(PlatformOperator.id == args.deactivate).first()
            if not operator:
                print(f"No operator with id {args.deactivate}", file=sys.stderr)
                sys.exit(1)
            operator.is_active = False
            db.commit()
            print(f"Operator {operator.id} ({operator.name}) deactivated.")
            return

        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        if args.rotate is not None:
            operator = db.query(PlatformOperator).filter(PlatformOperator.id == args.rotate).first()
            if not operator:
                print(f"No operator with id {args.rotate}", file=sys.stderr)
                sys.exit(1)
            operator.key_hash = key_hash
            operator.is_active = True
            db.commit()
        else:
            operator = PlatformOperator(name=args.name, key_hash=key_hash, is_active=True)
            db.add(operator)
            db.commit()
            db.refresh(operator)

        print("=" * 72)
        print(f"Operator id:   {operator.id}")
        print(f"Operator name: {operator.name}")
        print("Operator key (copy now -- shown only this once):")
        print(f"  {raw_key}")
        print("=" * 72)
        print("Send these two values to the operator's own secrets manager, never")
        print("via chat/email. The provisioning endpoint expects:")
        print(f"  X-Operator-Id: {operator.id}")
        print("  X-Operator-Key: <the key above>")
    finally:
        db.close()


if __name__ == "__main__":
    main()
