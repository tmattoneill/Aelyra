import pytest

from app.services.m3u_parser import M3UParser

TRACK_A = "4cOdK2wGLETKBW3PvgPWqT"
TRACK_B = "1301WleyT98MSxVHPZCA6M"


def test_parses_urls_and_uris():
    content = f"#EXTM3U\nhttps://open.spotify.com/track/{TRACK_A}\nspotify:track:{TRACK_B}\n"
    result = M3UParser.parse(content)
    assert result["track_ids"] == [TRACK_A, TRACK_B]


def test_parses_plain_m3u_without_a_header():
    result = M3UParser.parse(f"https://open.spotify.com/track/{TRACK_A}\n")
    assert result["track_ids"] == [TRACK_A]
    assert result["is_extended"] is False


def test_url_query_parameters_do_not_break_the_id():
    content = f"https://open.spotify.com/track/{TRACK_A}?si=abc123\n"
    assert M3UParser.parse(content)["track_ids"] == [TRACK_A]


def test_duplicates_are_dropped_with_a_warning():
    content = f"https://open.spotify.com/track/{TRACK_A}\nhttps://open.spotify.com/track/{TRACK_A}\n"
    result = M3UParser.parse(content)
    assert result["track_ids"] == [TRACK_A]
    assert any("Duplicate" in w for w in result["warnings"])


def test_non_spotify_urls_are_reported_not_silently_ignored():
    content = f"https://open.spotify.com/track/{TRACK_A}\nhttps://example.com/song.mp3\n"
    result = M3UParser.parse(content)
    assert result["track_ids"] == [TRACK_A]
    assert any("Non-Spotify" in w for w in result["warnings"])


def test_extinf_titles_containing_commas_are_kept_whole():
    content = (
        "#EXTM3U\n"
        "#EXTINF:210,Artist Name - Song, With Comma\n"
        f"https://open.spotify.com/track/{TRACK_A}\n"
    )
    result = M3UParser.parse(content)
    assert result["track_info"][0]["extinf"] == "Artist Name - Song, With Comma"


def test_file_with_no_spotify_links_is_rejected():
    with pytest.raises(ValueError):
        M3UParser.parse("#EXTM3U\nhttps://example.com/a.mp3\n")


def test_empty_file_is_rejected():
    with pytest.raises(ValueError):
        M3UParser.parse("   ")


def test_track_limit_is_enforced():
    # Ids must be 22 chars, so pad a counter out to that length.
    lines = [f"spotify:track:{str(i).zfill(22)}" for i in range(M3UParser.MAX_TRACKS + 25)]
    result = M3UParser.parse("\n".join(lines))
    assert len(result["track_ids"]) == M3UParser.MAX_TRACKS
    assert any("maximum" in w.lower() for w in result["warnings"])


def test_ids_of_the_wrong_length_are_not_accepted():
    """Spotify ids are always 22 base62 characters."""
    assert M3UParser._extract_spotify_track_id("spotify:track:tooshort") is None


class TestValidateFileContent:
    def test_accepts_a_file_with_spotify_links(self):
        ok, message = M3UParser.validate_file_content(f"spotify:track:{TRACK_A}")
        assert ok and message == ""

    def test_rejects_an_empty_file(self):
        ok, message = M3UParser.validate_file_content("")
        assert not ok and "empty" in message.lower()

    def test_rejects_an_oversized_file(self):
        ok, message = M3UParser.validate_file_content("x" * (100 * 1024 + 1))
        assert not ok and "too large" in message.lower()

    def test_rejects_a_file_with_no_spotify_links(self):
        ok, message = M3UParser.validate_file_content("#EXTM3U\nhttps://example.com/a.mp3")
        assert not ok and "No Spotify" in message
