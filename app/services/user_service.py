from sqlalchemy.orm import Session
from app.models.user import User
from typing import Optional

class UserService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()
    
    def get_user_by_spotify_username(self, spotify_username: str) -> Optional[User]:
        return self.db.query(User).filter(User.spotify_username == spotify_username).first()
    
    def create_user(self, email: str, spotify_username: str, first_name: str = None, 
                   last_name: str = None, location: str = None, openai_api_key: str = None) -> User:
        user = User(
            email=email,
            spotify_username=spotify_username,
            first_name=first_name,
            last_name=last_name,
            location=location,
            openai_api_key=openai_api_key
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def update_user(self, user: User, **kwargs) -> User:
        for key, value in kwargs.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_or_create_user(self, email: str, spotify_username: str, **kwargs) -> User:
        user = self.get_user_by_email(email)
        if not user:
            # New user: set all fields from Spotify profile
            user = self.create_user(email, spotify_username, **kwargs)
        else:
            # Existing user: only update system fields, preserve user-customizable fields
            system_fields = {
                'spotify_username': spotify_username,
                'location': kwargs.get('location')  # Location can change
            }
            user = self.update_user(user, **system_fields)
        return user