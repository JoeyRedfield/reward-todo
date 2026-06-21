from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {
            "future": True,
            "connect_args": {"check_same_thread": False},
        }
    return {"future": True}


_engine = None
_session_factory = None


def get_engine():
    global _engine
    settings = get_settings()
    if _engine is None or str(_engine.url) != settings.database_url:
        _engine = create_engine(
            settings.database_url,
            **_engine_kwargs(settings.database_url),
        )
    return _engine


def get_session_factory():
    global _session_factory
    engine = get_engine()
    if _session_factory is None or _session_factory.kw["bind"] is not engine:
        _session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
    return _session_factory


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
