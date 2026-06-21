import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session_factory, init_db
from app.models import User
from app.services.auth_service import AuthService

MIN_PASSWORD_LENGTH = 8


def reset_password(session: Session, new_password: str) -> None:
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"New password must be at least {MIN_PASSWORD_LENGTH} characters long"
        )

    service = AuthService(session)
    users = session.scalars(select(User)).all()
    if len(users) != 1:
        raise ValueError("Reset password requires exactly one local user")
    user = users[0]
    service.change_password(user, new_password)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset the local application password")
    parser.add_argument("--password", required=True, help="New password for the local user")
    args = parser.parse_args()

    init_db()
    session = get_session_factory()()
    try:
        reset_password(session, args.password)
        print("password reset complete")
    finally:
        session.close()


if __name__ == "__main__":
    main()
