
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from dotenv import load_dotenv

from app.routers import playlist, auth
from app.models.responses import ErrorResponse

load_dotenv()

app = FastAPI(
    title="PlayMaker API",
    description="AI-Powered Spotify Playlist Generator",
    version="1.0.0"
)

# CORS middleware for frontend integration
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(playlist.router, prefix="/api")
app.include_router(auth.router, prefix="/api/spotify")

@app.get("/")
async def root():
    return {"message": "PlayMaker API - AI-Powered Spotify Playlist Generator"}

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
