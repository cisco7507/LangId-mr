import os
import uvicorn

# Import the ASGI app directly so we don't rely on console scripts/shims
from app.main import app

host = os.environ.get("APP_HOST", "0.0.0.0")
port = int(os.environ.get("APP_PORT", "8080"))

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=True,
        # You can also tune workers here if you prefer uvicorn's workers
        # but you already have internal worker processes for jobs.
    )