"""Tests for the user lookup that broke every signup after the first."""

from app.services.user_service import UNSET, UserService


def test_creates_user_from_spotify_profile(db_session):
    service = UserService(db_session)
    user = service.get_or_create_user(
        spotify_username="matt",
        email="matt@example.com",
        first_name="Matt",
        last_name="O'Neill",
        location="GB",
    )

    assert user.id is not None
    assert user.spotify_username == "matt"
    assert user.email == "matt@example.com"
    assert user.last_name == "O'Neill"


def test_second_user_without_email_does_not_collide(db_session):
    """The original bug.

    Users were looked up by email, which was always empty because the OAuth
    scopes never requested one. The first account claimed the empty string and
    every later signup hit the unique constraint on it.
    """
    service = UserService(db_session)

    first = service.get_or_create_user(spotify_username="user_one", email=None)
    second = service.get_or_create_user(spotify_username="user_two", email=None)

    assert first.id != second.id
    assert first.email is None
    assert second.email is None


def test_empty_email_is_stored_as_null(db_session):
    service = UserService(db_session)
    user = service.get_or_create_user(spotify_username="matt", email="")
    assert user.email is None


def test_returning_user_is_matched_by_spotify_username(db_session):
    service = UserService(db_session)
    created = service.get_or_create_user(spotify_username="matt", email="matt@example.com")
    again = service.get_or_create_user(spotify_username="matt", email="matt@example.com")

    assert created.id == again.id
    assert db_session.query(type(created)).count() == 1


def test_user_edits_survive_a_later_login(db_session):
    """Spotify owns location; the user owns their name and API key."""
    service = UserService(db_session)
    user = service.get_or_create_user(spotify_username="matt", email="matt@example.com", first_name="Matt")

    service.update_user(user, first_name="Matthew", openai_api_key="sk-user-key")
    service.get_or_create_user(spotify_username="matt", email="matt@example.com", first_name="Matt", location="US")

    db_session.refresh(user)
    assert user.first_name == "Matthew"
    assert user.openai_api_key == "sk-user-key"
    assert user.location == "US"


def test_email_is_backfilled_once_the_scope_is_granted(db_session):
    service = UserService(db_session)
    user = service.get_or_create_user(spotify_username="matt", email=None)
    assert user.email is None

    service.get_or_create_user(spotify_username="matt", email="matt@example.com")
    db_session.refresh(user)
    assert user.email == "matt@example.com"


def test_none_leaves_a_field_alone_but_unset_clears_it(db_session):
    service = UserService(db_session)
    user = service.get_or_create_user(spotify_username="matt", openai_api_key="sk-stored")

    service.update_user(user, openai_api_key=None)
    assert user.openai_api_key == "sk-stored"

    service.update_user(user, openai_api_key=UNSET)
    assert user.openai_api_key is None
