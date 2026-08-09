"""Tests for the one-time code exchange that replaced tokens-in-the-URL."""

from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.models.requests import SessionExchangeRequest
from app.routers import auth


@pytest.fixture(autouse=True)
def clear_store():
    auth.pending_auths.clear()
    yield
    auth.pending_auths.clear()


TOKEN_INFO = {"access_token": "access-abc", "refresh_token": "refresh-xyz", "expires_in": 3600}
PROFILE = {"id": "matt", "display_name": "Matt O'Neill"}


async def test_code_exchanges_for_tokens():
    code = auth._store_pending_auth(TOKEN_INFO, PROFILE)
    result = await auth.exchange_session(SessionExchangeRequest(code=code))

    assert result.access_token == "access-abc"
    assert result.refresh_token == "refresh-xyz"
    assert result.user["id"] == "matt"


async def test_code_is_single_use():
    code = auth._store_pending_auth(TOKEN_INFO, PROFILE)
    await auth.exchange_session(SessionExchangeRequest(code=code))

    with pytest.raises(HTTPException) as exc:
        await auth.exchange_session(SessionExchangeRequest(code=code))
    assert exc.value.status_code == 400


async def test_unknown_code_is_rejected():
    with pytest.raises(HTTPException) as exc:
        await auth.exchange_session(SessionExchangeRequest(code="never-issued"))
    assert exc.value.status_code == 400


async def test_expired_code_is_rejected():
    code = auth._store_pending_auth(TOKEN_INFO, PROFILE)
    auth.pending_auths[code]["created"] -= auth.AUTH_CODE_TTL + timedelta(seconds=1)

    with pytest.raises(HTTPException) as exc:
        await auth.exchange_session(SessionExchangeRequest(code=code))
    assert exc.value.status_code == 400


async def test_expires_in_counts_down_from_the_callback():
    """The token starts ageing when Spotify issues it, not when it is collected."""
    code = auth._store_pending_auth(TOKEN_INFO, PROFILE)
    auth.pending_auths[code]["created"] -= timedelta(seconds=30)

    result = await auth.exchange_session(SessionExchangeRequest(code=code))
    assert 3565 <= result.expires_in <= 3571


def test_codes_are_unguessable_and_unique():
    codes = {auth._store_pending_auth(TOKEN_INFO, PROFILE) for _ in range(50)}
    assert len(codes) == 50
    assert all(len(c) >= 32 for c in codes)


def test_expired_codes_are_cleaned_up():
    stale = auth._store_pending_auth(TOKEN_INFO, PROFILE)
    fresh = auth._store_pending_auth(TOKEN_INFO, PROFILE)
    auth.pending_auths[stale]["created"] -= auth.AUTH_CODE_TTL + timedelta(seconds=1)

    auth.cleanup_expired_auth_codes()

    assert stale not in auth.pending_auths
    assert fresh in auth.pending_auths


class TestDisplayNameSplitting:
    def test_splits_first_and_last_name(self):
        assert auth._split_display_name("Matt O'Neill") == {
            "first_name": "Matt",
            "last_name": "O'Neill",
        }

    def test_keeps_multi_word_surnames_together(self):
        assert auth._split_display_name("Ada van der Berg")["last_name"] == "van der Berg"

    def test_single_name_has_no_last_name(self):
        assert auth._split_display_name("Bjork") == {"first_name": "Bjork", "last_name": None}

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_missing_display_name_yields_nothing(self, value):
        assert auth._split_display_name(value) == {"first_name": None, "last_name": None}
