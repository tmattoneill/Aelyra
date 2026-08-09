"""Tests for model parameter selection and playlist post-processing.

The parameter rules encode behaviour verified against the live OpenAI API:
gpt-5-mini rejects any explicit temperature, and gpt-5.2 rejects temperature
whenever reasoning is switched on.
"""

from app.services.llm_service import (
    MAX_TRACKS_PER_ARTIST,
    LLMService,
    QueryAnalysis,
)


def track(name, artist, year=2020):
    return {"track_name": name, "artist": artist, "album": "An Album", "release_year": year}


class TestModelKwargs:
    def test_temperature_is_dropped_for_models_that_reject_it(self):
        assert "temperature" not in LLMService._model_kwargs("gpt-5-mini", temperature=0.7)

    def test_temperature_is_kept_when_the_model_allows_it(self):
        assert LLMService._model_kwargs("gpt-5.2", temperature=0.7)["temperature"] == 0.7

    def test_reasoning_wins_over_temperature_because_they_conflict(self):
        kwargs = LLMService._model_kwargs("gpt-5.2", temperature=0.7, reasoning_effort="low")
        assert kwargs["reasoning_effort"] == "low"
        assert "temperature" not in kwargs

    def test_temperature_survives_alongside_a_non_reasoning_effort(self):
        kwargs = LLMService._model_kwargs("gpt-5.2", temperature=0.7, reasoning_effort="none")
        assert kwargs["temperature"] == 0.7
        assert kwargs["reasoning_effort"] == "none"

    def test_unsupported_effort_values_are_not_sent(self):
        # gpt-5.2 has no "minimal" level.
        assert "reasoning_effort" not in LLMService._model_kwargs("gpt-5.2", reasoning_effort="minimal")
        # gpt-5-mini has no "none" level.
        assert "reasoning_effort" not in LLMService._model_kwargs("gpt-5-mini", reasoning_effort="none")

    def test_unknown_models_get_nothing_optional(self):
        kwargs = LLMService._model_kwargs("some-future-model", temperature=0.7, reasoning_effort="low")
        assert kwargs == {}


class TestDedupeTracks:
    def test_enforces_the_per_artist_cap(self):
        raw = [track(f"Song {i}", "Beach House") for i in range(5)]
        result = LLMService._dedupe_tracks(raw, [])
        assert len(result) == MAX_TRACKS_PER_ARTIST

    def test_counts_existing_tracks_towards_the_cap(self):
        existing = [{"track_name": "Space Song", "artist": "Beach House"}]
        raw = [track("Myth", "Beach House"), track("PPP", "Beach House")]
        result = LLMService._dedupe_tracks(raw, existing)
        assert len(result) == MAX_TRACKS_PER_ARTIST - 1

    def test_drops_tracks_already_selected(self):
        existing = [{"track_name": "Holocene", "artist": "Bon Iver"}]
        result = LLMService._dedupe_tracks([track("Holocene", "Bon Iver")], existing)
        assert result == []

    def test_rejects_entries_missing_required_fields(self):
        raw = [{"track_name": "No Artist"}, {"artist": "No Title"}, track("Good", "Artist")]
        result = LLMService._dedupe_tracks(raw, [])
        assert len(result) == 1
        assert result[0]["track_name"] == "Good"

    def test_fills_in_missing_optional_fields(self):
        result = LLMService._dedupe_tracks([{"track_name": "A", "artist": "B"}], [])
        assert result[0]["album"] == "Unknown Album"
        assert result[0]["release_year"] == "Unknown"


class TestDiversity:
    analysis = QueryAnalysis(
        genres=["indie"], moods=["chill"], eras=["2010s"], tempo_range="medium",
        reference_artists=[], themes=[], energy_level="medium",
    )

    def test_a_varied_playlist_passes(self):
        service = LLMService.__new__(LLMService)
        tracks = [track("A", "One", 2011), track("B", "Two", 2004), track("C", "Three", 1998)]
        assert service.validate_diversity(tracks, self.analysis).is_valid

    def test_an_over_represented_artist_is_reported(self):
        service = LLMService.__new__(LLMService)
        tracks = [track(f"Song {i}", "Same Artist") for i in range(4)]
        report = service.validate_diversity(tracks, self.analysis)

        assert not report.is_valid
        assert "same artist" in report.artist_violations

    def test_same_title_by_different_artists_is_not_a_duplicate(self):
        """Plenty of distinct songs share a title; only title+artist repeats count."""
        service = LLMService.__new__(LLMService)
        tracks = [track("Crazy", "Gnarls Barkley", 2006), track("Crazy", "Patsy Cline", 1961)]
        report = service.validate_diversity(tracks, self.analysis)

        assert report.duplicate_tracks == []
        assert report.is_valid

    def test_era_clustering_is_flagged_when_specific_eras_were_asked_for(self):
        service = LLMService.__new__(LLMService)
        tracks = [track("A", "One", 2021), track("B", "Two", 2022), track("C", "Three", 2023)]
        report = service.validate_diversity(tracks, self.analysis)

        assert not report.is_valid
        assert any("same decade" in issue for issue in report.issues)

    def test_a_genuine_repeat_is_caught(self):
        service = LLMService.__new__(LLMService)
        tracks = [track("Holocene", "Bon Iver"), track("Holocene", "Bon Iver")]
        assert not service.validate_diversity(tracks, self.analysis).is_valid

    def test_fixes_preserve_order_and_drop_the_excess(self):
        tracks = [
            track("A", "One"),
            track("B", "Two"),
            track("C", "One"),
            track("D", "One"),  # third by One, over the cap
            track("E", "Three"),
        ]
        kept = LLMService.apply_diversity_fixes(tracks)

        assert [t["track_name"] for t in kept] == ["A", "B", "C", "E"]
