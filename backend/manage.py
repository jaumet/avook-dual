"""Lightweight management helpers for local development."""
from __future__ import annotations

import argparse
import sys

from sqlalchemy.exc import IntegrityError

from backend.catalog import CatalogConfigError, get_packages, normalize_package_ids
from backend.database import SessionLocal
from backend.models import User, UserPackage


def _valid_package_ids() -> set[str]:
    try:
        return {pkg.get("id") for pkg in get_packages() if pkg.get("id")}
    except CatalogConfigError as exc:  # pragma: no cover - runtime validation
        raise SystemExit(f"Invalid catalog configuration: {exc}") from exc


def create_user(
    email: str,
    full_access: bool,
    is_active: bool,
    package_ids: list[str] | None = None,
) -> User:
    email_norm = email.strip().lower()
    requested_packages = normalize_package_ids(package_ids or [])
    valid_packages = _valid_package_ids()
    invalid = sorted(pkg for pkg in requested_packages if pkg not in valid_packages)
    if invalid:
        raise SystemExit("Unknown package ids: " + ", ".join(invalid))

    with SessionLocal() as session:
        user = session.query(User).filter(User.email == email_norm).first()
        if user:
            user.full_access = full_access or user.full_access
            user.is_active = is_active
        else:
            user = User(email=email_norm, full_access=full_access, is_active=is_active)
            session.add(user)

        existing = set(user.packages)
        for package_id in requested_packages:
            if package_id not in existing:
                user.package_links.append(UserPackage(package_id=package_id))

        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise SystemExit(f"Failed to upsert user {email_norm}: {exc}") from exc
        session.refresh(user)
        return user


def list_users() -> list[User]:
    with SessionLocal() as session:
        return session.query(User).order_by(User.id.asc()).all()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audiovook backend management utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_cmd = subparsers.add_parser("create-user", help="Create or update a user")
    create_cmd.add_argument("email", help="Email address")
    create_cmd.add_argument(
        "--full-access", action="store_true", help="Grant subscriber access to the user"
    )
    create_cmd.add_argument(
        "--inactive", action="store_true", help="Create the user but mark it as inactive"
    )
    create_cmd.add_argument(
        "--package",
        action="append",
        default=[],
        help="Package ID to assign (repeat to grant multiple packages)",
    )

    subparsers.add_parser("list-users", help="Print existing users")

    args = parser.parse_args(argv)

    if args.command == "create-user":
        user = create_user(args.email, args.full_access, not args.inactive, args.package)
        packages = ",".join(user.packages) or "-"
        print(
            f"User #{user.id} · {user.email} · full_access={user.full_access} · is_active={user.is_active} · packages={packages}"
        )
        return 0
    if args.command == "list-users":
        for user in list_users():
            packages = ",".join(user.packages) or "-"
            print(
                f"User #{user.id} · {user.email} · full_access={user.full_access} · is_active={user.is_active} · packages={packages}"
            )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
