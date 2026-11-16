import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.core.security import get_or_create_app_token
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.monitoring import MonitoringManagerService


@pytest.fixture
async def async_client(tmp_path):
    MonitoringManagerService().stop_all()
    db_file = tmp_path / "test_api.db"
    test_engine = create_engine(f"sqlite:///{db_file}")

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    import backend.app.db.models  # Ensure all ORM models are registered in Base.metadata
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    from backend.app.db import session as session_module
    orig_session_local = session_module.SessionLocal
    session_module.SessionLocal = TestingSession

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    app_token = get_or_create_app_token()
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"X-App-Token": app_token},
        ) as client:
            yield client
    finally:
        MonitoringManagerService().stop_all()
        app.dependency_overrides.pop(get_db, None)
        session_module.SessionLocal = orig_session_local
        test_engine.dispose()


@pytest.fixture
def db_session(tmp_path):
    import backend.app.db.models
    db_file = tmp_path / "test_sync.db"
    test_engine = create_engine(f"sqlite:///{db_file}")

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    from backend.app.db import session as session_module
    orig_session_local = session_module.SessionLocal
    session_module.SessionLocal = TestingSession

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.pop(get_db, None)
        session_module.SessionLocal = orig_session_local
        test_engine.dispose()

