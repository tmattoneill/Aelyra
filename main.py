
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from dotenv import load_dotenv

from app.routers import playlist, auth
from app.models.responses import ErrorResponse
from app.database import engine, Base

load_dotenv()

app = FastAPI(
    title="Aelyra API",
    description="AI-Powered Spotify Playlist Generator",
    version="1.0.0"
)

# Create database tables
Base.metadata.create_all(bind=engine)

# CORS middleware for frontend integration
# Default to secure origins for production, but allow localhost for development
default_origins = "http://localhost:3000,http://127.0.0.1:3000"
if os.getenv("DEBUG", "True").lower() == "true":
    default_origins += ",*"  # Allow all origins in development mode only

allowed_origins = os.getenv("CORS_ORIGINS", default_origins).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include routers
app.include_router(playlist.router, prefix="/api")
app.include_router(auth.router, prefix="/api/spotify")

@app.get("/")
async def root():
    return {"message": "Aelyra API - AI-Powered Spotify Playlist Generator"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5988"))
    reload = os.getenv("DEBUG", "True").lower() == "true"
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload
    )
