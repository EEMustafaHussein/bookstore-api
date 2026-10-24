from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def _normalise_url(url: str) -> str:
    # Hosts such as Neon and Render hand out "postgres://" or "postgresql://" links;
    # point them at the psycopg 3 driver that is installed.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _make_engine(url: str):
    url = _normalise_url(url)
    if not url.startswith("sqlite"):
        # Free databases go to sleep and drop idle connections, so each one is checked before use.
        return create_engine(url, pool_pre_ping=True, pool_recycle=280)

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
