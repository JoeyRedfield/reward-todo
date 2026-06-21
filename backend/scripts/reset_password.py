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


def reset_password(session: Session, new_password: str) -> None:
    service = AuthService(session)
    user = session.scalar(select(User))
    if user is None:
        raise ValueError("Initial user does not exist")
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
