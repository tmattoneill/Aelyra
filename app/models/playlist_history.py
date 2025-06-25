from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class PlaylistHistory(Base):
    __tablename__ = "playlist_history"

    id = Column(Integer, primary_key=True, index=True)
    playlist_hash = Column(String(32), unique=True, index=True, nullable=False)  # MD5 hash
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    playlist_name = Column(String(255), nullable=False)
    user_description = Column(Text, nullable=True)  # Original user query
    spotify_playlist_id = Column(String(255), nullable=False)
    spotify_playlist_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    track_count = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="playlists")
    tracks = relationship("PlaylistTrack", back_populates="playlist", cascade="all, delete-orphan")

class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id = Column(Integer, primary_key=True, index=True)
    playlist_history_id = Column(Integer, ForeignKey("playlist_history.id"), nullable=False)
    spotify_track_id = Column(String(255), nullable=False)
    track_name = Column(String(255), nullable=False)
    artist_name = Column(String(255), nullable=False)
    album_name = Column(String(255), nullable=True)
    position = Column(Integer, nullable=False)

    # Relationships
    playlist = relationship("PlaylistHistory", back_populates="tracks")