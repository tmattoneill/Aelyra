import logging
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

# Sentinel so callers can clear a nullable field, which a plain None cannot do
# because None means "leave this alone" in update_user.
UNSET = object()


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        if not email:
            return None
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_spotify_username(self, spotify_username: str) -> Optional[User]:
        return self.db.query(User).filter(User.spotify_username == spotify_username).first()

    def create_user(self, email: Optional[str], spotify_username: str, first_name: str = None,
                    last_name: str = None, location: str = None, openai_api_key: str = None) -> User:
        user = User(
            email=email or None,
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
        """Apply the given fields to a user.

        A value of None means "no change supplied"; pass UNSET to clear a field.
        """
        for key, value in kwargs.items():
            if not hasattr(user, key):
                continue
            if value is UNSET:
                setattr(user, key, None)
            elif value is not None:
                setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_or_create_user(self, spotify_username: str, email: Optional[str] = None, **kwargs) -> User:
        """Look up a user by their Spotify account, creating one if needed.

        Keyed on spotify_username rather than email: it is the stable identifier
        Spotify guarantees, whereas email is absent for accounts that have not
        granted user-read-email and is not unique across Spotify accounts in the
        way the schema previously assumed.
        """
        if not spotify_username:
            raise ValueError("spotify_username is required to identify a user")

        user = self.get_user_by_spotify_username(spotify_username)

        if user is None:
            try:
                return self.create_user(email=email, spotify_username=spotify_username, **kwargs)
            except IntegrityError:
                # Another request created the same user between the lookup and
                # the insert, or the email collides with an existing account.
                self.db.rollback()
                user = self.get_user_by_spotify_username(spotify_username)
                if user is None:
                    raise

        # Existing user: refresh only the fields Spotify owns, leaving anything
        # the user has edited themselves (names, API key) untouched.
        updates = {"location": kwargs.get("location")}
        if email and not user.email:
            updates["email"] = email
        return self.update_user(user, **updates)
