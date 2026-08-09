import logging
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine
from app.routers import auth, playlist

load_dotenv()

# DEBUG defaults to false: an unset variable in production used to enable
# development behaviour, including a wildcard CORS origin.
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# At DEBUG these libraries log full request bodies and every header, which
# buries the application's own output and puts API keys in the log file.
for noisy in ("httpx", "httpcore", "openai", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Aelyra API",
    description="AI-Powered Spotify Playlist Generator",
    version="1.0.0",
)

# Schema is owned by Alembic (`alembic upgrade head`). Calling create_all here
# as well left fresh databases with tables but no alembic_version row, so the
# next migration would try to recreate them.

# Never combine a wildcard origin with credentialed requests: browsers reject
# the pair outright, and it would expose the API to any site if they did not.
default_origins = "http://localhost:3000,http://127.0.0.1:3000"
allowed_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", default_origins).split(",") if o.strip()]

if "*" in allowed_origins:
    logger.warning("CORS_ORIGINS contains '*'; dropping it because allow_credentials is enabled")
    allowed_origins = [o for o in allowed_origins if o != "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(playlist.router, prefix="/api")
app.include_router(auth.router, prefix="/api/spotify")


@app.get("/")
async def root():
    return {"message": "Aelyra API - AI-Powered Spotify Playlist Generator"}


@app.get("/health")
async def health_check():
    """Report on the dependencies a deploy can actually get wrong.

    A health check that always returns healthy lets a broken instance pass its
    own load balancer check, so this one touches the database and confirms the
    credentials the app needs are present.
    """
    checks = {
        "database": False,
        "spotify_configured": bool(os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
    }

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.error(f"Health check database probe failed: {e}")

    healthy = checks["database"] and checks["spotify_configured"]
    return {"status": "healthy" if healthy else "degraded", "checks": checks}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5988")),
        reload=DEBUG,
    )
