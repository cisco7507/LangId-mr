# langid_service/tests/conftest.py
import pytest
import threading
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from langid_service.app.main import app, worker_loop
from langid_service.app.database import Base, SessionLocal
from langid_service.app.models.models import Job

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the database tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[SessionLocal] = override_get_db

@pytest.fixture(scope="function")
def db_session():
    """
    Fixture to provide a database session for a test, with cleanup.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def start_worker(db_session):
    """
    Fixture to start the background worker thread for each test function.
    Function scope ensures mocks can be applied before the worker starts.
    """
    # Pass the test db session to the worker loop
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    yield
    # The daemon thread will exit when the main test thread exits.

@pytest.fixture(scope="function")
def client(db_session):
    """
    Fixture to provide a TestClient that uses the same db session as the test.
    """
    def override_get_db_for_client():
        yield db_session

    app.dependency_overrides[SessionLocal] = override_get_db_for_client
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(SessionLocal, None)

@pytest.fixture(autouse=True)
def cleanup_jobs(db_session):
    """
    Fixture to clean up any jobs left in the database after each test.
    """
    yield
    db_session.query(Job).delete()
    db_session.commit()
