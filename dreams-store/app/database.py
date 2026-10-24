from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def _make_engine(url: str):
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)

    kwargs = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite://", "sqlite:///:memory:"):
        kwargs["poolclass"] = StaticPool
    sqlite_engine = create_engine(url, **kwargs)

    @event.listens_for(sqlite_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return sqlite_engine


engine = _make_engine(settings.database_url)


def create_db_and_tables():
    # Importing the models registers every table on SQLModel.metadata.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


MAX_ID = 2**31 - 1


def get_by_id(session: Session, model, ident: int | str | None):
    """Looks a row up by id, treating anything that is not a sensible id as missing."""
    if isinstance(ident, str):
        ident = int(ident) if ident.isdigit() and len(ident) <= 10 else None
    if ident is None or not 0 < ident <= MAX_ID:
        return None
    return session.get(model, ident)
