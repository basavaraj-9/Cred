"""Local operator bootstrap; passwords are read without echo and never passed as arguments."""

import argparse
from getpass import getpass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_engine
from app.models.user import User
from app.runtime.security import PASSWORDS, POLICY, security_event


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--role", choices=sorted(POLICY["roles"]), required=True)
    args = parser.parse_args()
    password = getpass("New password (at least 12 characters): ")
    if len(password) < 12 or password != getpass("Repeat password: "):
        raise SystemExit("Password validation failed")
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("Database is not configured")
    with Session(get_engine(settings.database_url)) as session:
        user = session.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            user = User(email=args.email.strip().lower(), token_version=0)
            session.add(user)
        else:
            user.token_version += 1
        user.password_hash = PASSWORDS.hash(password)
        user.reviewer_role = args.role
        user.account_status, user.is_active = "ACTIVE", True
        session.flush()
        security_event(session, "ADMIN_ACCOUNT_PROVISIONED", "local-operator", user.id)
    print("Account provisioned; any previous tokens have been revoked.")


if __name__ == "__main__":
    main()
