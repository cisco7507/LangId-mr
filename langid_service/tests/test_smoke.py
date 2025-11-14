import importlib


def test_import_main_app():
    """Basic smoke test: the FastAPI app module should import without errors."""
    module = importlib.import_module("langid_service.app.main")
    assert hasattr(module, "app"), "FastAPI app instance should exist"
