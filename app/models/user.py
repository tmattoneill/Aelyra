from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Nullable: Spotify omits email for accounts that have not granted
    # user-read-email, and spotify_username is the identity we key on.
    email = Column(String(255), unique=True, index=True, nullable=True)
    spotify_username = Column(String(255), unique=True, index=True, nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    location = Column(String(100), nullable=True)  # Country code (GB, US, FR, ...)
    date_created = Column(DateTime(timezone=True), server_default=func.now())
    openai_api_key = Column(Text, nullable=True)  # Encrypted storage recommended for production

    # Relationships
    playlists = relationship("PlaylistHistory", back_populates="user")
