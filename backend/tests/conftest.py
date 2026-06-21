import os
import sys
from pathlib import Path
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

backend_root = Path(__file__).resolve().parents[1]
backend_root_path = str(backend_root)
if backend_root_path not in sys.path:
    sys.path.insert(0, backend_root_path)

site_packages_root = backend_root / ".venv" / "lib"
site_packages_dirs = sorted(site_packages_root.glob("python*/site-packages"))
if not site_packages_dirs and (backend_root / ".venv").exists():
    raise RuntimeError(
        "Could not locate site-packages under backend/.venv/lib/python*/site-packages"
    )
for site_packages_dir in site_packages_dirs:
    site_packages_path = str(site_packages_dir)
    if site_packages_path not in sys.path:
        sys.path.insert(0, site_packages_path)

os.environ.setdefault("AUTH_INITIAL_USERNAME", "reward")
os.environ.setdefault("AUTH_INITIAL_PASSWORD", "super-secret")
os.environ.setdefault("AUTH_COOKIE_SECURE", "false")
os.environ.setdefault("TESTING", "true")

from app.config import get_settings
from app.database import Base
from app.dependencies import get_db_session
from app.main import create_app


@pytest.fixture()
def db_session(tmp_path: pytest.TempPathFactory) -> Generator[Session, None, None]:
    database_path = tmp_path / "reward_todo_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{database_path}"
    os.environ["READONLY_TOKEN"] = "readonly-test-token"
    get_settings.cache_clear()

    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        get_settings.cache_clear()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
