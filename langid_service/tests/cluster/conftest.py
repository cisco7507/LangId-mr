
import pytest
from unittest.mock import MagicMock
from langid_service.cluster import config

@pytest.fixture
def mock_cluster_config(monkeypatch):
    """
    Fixture to mock the cluster configuration.
    Default: node-a (self), node-b (peer)
    """
    mock_conf = MagicMock()
    mock_conf.self_name = "node-a"
    mock_conf.nodes = {
        "node-a": "http://node-a.internal:8080",
        "node-b": "http://node-b.internal:8080"
    }
    mock_conf.health_check_interval_seconds = 1
    mock_conf.internal_request_timeout_seconds = 1

    # Mock the load_cluster_config function to return our mock object
    monkeypatch.setattr(config, "load_cluster_config", lambda: mock_conf)
    
    # Also reset the global _config to ensure fresh load if needed, though we are mocking the function
    config._config = None
    
    return mock_conf

@pytest.fixture(autouse=True)
def mock_db_session(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from langid_service.app.database import Base
    from langid_service.app import main
    # Import models to ensure they are registered in Base.metadata
    from langid_service.app.models import models
    
    from sqlalchemy.pool import StaticPool
    
    # Use in-memory SQLite with StaticPool to share the DB across sessions
    engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    # Use Job.metadata to ensure we have the right metadata
    models.Job.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    monkeypatch.setattr(main, "SessionLocal", SessionLocal)
    
    # Also patch database module to be safe
    from langid_service.app import database
    monkeypatch.setattr(database, "SessionLocal", SessionLocal)
    monkeypatch.setattr(database, "engine", engine)
    
    return SessionLocal
