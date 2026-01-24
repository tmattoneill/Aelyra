import openai
import json
import logging
import os
from typing import List, Dict, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Model constants - tiered for cost optimization
MODEL_FAST = "gpt-5-mini"   # For simple tasks: playlist titles, query analysis
MODEL_KNOWLEDGE = "gpt-5.2"  # For complex tasks requiring broad music knowledge


@dataclass
class QueryAnalysis:
    """Structured analysis of a user's playlist query"""
    genres: List[str]
    moods: List[str]
    eras: List[str]
    tempo_range: str
    reference_artists: List[str]
    themes: List[str]
    energy_level: str
    exclude_artists: List[str] = None

    def __post_init__(self):
        if self.exclude_artists is None:
            self.exclude_artists = []


@dataclass
class DiversityReport:
    """Report on playlist diversity validation"""
    is_valid: bool
    artist_violations: List[str]  # Artists appearing more than 2 times
    duplicate_tracks: List[str]   # Duplicate track names
    era_distribution: Dict[str, int]  # Count of tracks per era
    issues: List[str]  # Human-readable issues
    replacement_count: int  # Number of tracks that need replacement

class OpenAIService:
    def __init__(self, api_key: str = None):
        # Use provided API key or fall back to environment variable
        final_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not final_api_key:
            raise ValueError("OpenAI API key not provided and not found in environment variables")
        # Set longer timeout for reasoning models
        # Use AsyncOpenAI for proper async support
        self.client = openai.AsyncOpenAI(api_key=final_api_key, timeout=120.0)
        
        # Load prompts from config files
        self.config_dir = Path(__file__).parent.parent.parent / ".config"
        self.system_prompts = self._load_config("system_prompt.json")
        self.user_prompts = self._load_config("user_prompt.json")
    
    def _load_config(self, filename: str) -> dict:
        """Load configuration from JSON file"""
        try:
            config_path = self.config_dir / filename
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config {filename}: {str(e)}")
            raise ValueError(f"Failed to load configuration file: {filename}")

    async def generate_track_suggestions(self, query: str, count: int = 35) -> List[Dict[str, str]]:
        """
        Generate track suggestions in one bulk call for better performance
        Reduced default from 50 to 35 for faster initial response
        """
        try:
            # Build user prompt using system prompt format with dynamic count
            user_prompt = self.system_prompts["track_generation"]["objective"].replace("exactly 50 songs", f"exactly {count} songs").format(prompt=query)
            
            # Combine role and rules into system message for better context
            system_content = f"""{self.system_prompts["track_generation"]["role"]}

{self.system_prompts["track_generation"]["rules"]["core_directive"]}

Rules:
- {' '.join(self.system_prompts["track_generation"]["rules"]["factuality"])}
- {' '.join(self.system_prompts["track_generation"]["rules"]["recording_type"])}
- {' '.join(self.system_prompts["track_generation"]["rules"]["playlist_diversity"])}

{self.system_prompts["track_generation"]["system_message"].replace("exactly 50 track objects", f"exactly {count} track objects")}"""

            response = await self.client.chat.completions.create(
                model=MODEL_KNOWLEDGE,  # Needs broad music catalog knowledge
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=int(count * 80),  # Dynamic based on track count
                temperature=0.7
            )

            content = response.choices[0].message.content.strip()
            logger.info(f"Raw bulk response length: {len(content)}")
            
            # Clean up markdown formatting if present
            if content.startswith('```json'):
                content = content[7:]
            elif content.startswith('```'):
                content = content[3:]
            
            if content.endswith('```'):
                content = content[:-3]
            
            content = content.strip()

            # Extract JSON array if needed
            if not content.startswith('['):
                start_idx = content.find('[')
                if start_idx != -1:
                    end_idx = content.rfind(']')
                    if end_idx != -1 and end_idx > start_idx:
                        content = content[start_idx:end_idx + 1]

            if not content:
                raise Exception("Empty response from OpenAI")
            
            # Parse JSON response
            try:
                tracks_raw = json.loads(content)
                
                if not isinstance(tracks_raw, list):
                    raise Exception("Response is not a JSON array")
                
                # Process and validate tracks
                valid_tracks = []
                seen_tracks = set()
                
                for i, track in enumerate(tracks_raw):
                    if not isinstance(track, dict):
                        logger.warning(f"Track {i+1} is not a dict: {track}")
                        continue
                    
                    # Normalize field names
                    if "title" in track and "track_name" not in track:
                        track["track_name"] = track.pop("title")
                    
                    # Validate required fields
                    if not all(field in track for field in ["track_name", "artist"]):
                        logger.warning(f"Track {i+1} missing required fields: {track}")
                        continue
                    
                    # Set defaults for optional fields
                    track.setdefault("album", "Unknown Album")
                    track.setdefault("release_year", "Unknown")
                    
                    # Check for duplicates
                    track_key = f"{track['track_name'].lower()}|{track['artist'].lower()}"
                    if track_key in seen_tracks:
                        logger.info(f"Skipping duplicate: {track['track_name']} by {track['artist']}")
                        continue
                    
                    seen_tracks.add(track_key)
                    valid_tracks.append(track)
                    
                    if len(valid_tracks) >= count:  # Cap at requested count
                        break

                logger.info(f"Generated {len(valid_tracks)} valid tracks from bulk request")
                
                # If we didn't get enough tracks, make additional requests
                min_threshold = max(15, count // 2)  # Dynamic minimum threshold
                if len(valid_tracks) < min_threshold:
                    logger.warning(f"Only got {len(valid_tracks)} tracks, attempting fallback generation")
                    additional_tracks = await self._generate_additional_tracks(query, valid_tracks, count - len(valid_tracks))
                    valid_tracks.extend(additional_tracks)
                
                if not valid_tracks:
                    raise Exception("Failed to generate any valid tracks")
                
                return valid_tracks

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse bulk response: {content[:500]}...")
                raise Exception(f"Invalid JSON response from OpenAI: {str(e)}")

        except Exception as e:
            logger.error(f"OpenAI bulk generation error: {str(e)}")
            raise Exception(f"Failed to generate track suggestions: {str(e)}")

    async def _generate_additional_tracks(self, query: str, existing_tracks: List[Dict], count: int) -> List[Dict[str, str]]:
        """
        Generate additional tracks when bulk generation doesn't return enough
        """
        try:
            # Build list of existing tracks to avoid
            existing_list = ", ".join([f'"{t["track_name"]}" by {t["artist"]}' for t in existing_tracks])
            avoid_text = f"\n\nDo not suggest any of these already selected tracks: {existing_list}"
            
            user_prompt = f"Generate exactly {count} more songs that fit: \"{query}\".{avoid_text}"
            
            response = await self.client.chat.completions.create(
                model=MODEL_KNOWLEDGE,  # Needs broad music catalog knowledge
                messages=[
                    {"role": "system", "content": self.system_prompts["track_generation"]["system_message"]},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=2000,
                temperature=0.8
            )

            content = response.choices[0].message.content.strip()
            
            # Clean and parse (same logic as main method)
            if content.startswith('```json'):
                content = content[7:]
            elif content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()

            if not content.startswith('['):
                start_idx = content.find('[')
                if start_idx != -1:
                    end_idx = content.rfind(']')
                    if end_idx != -1:
                        content = content[start_idx:end_idx + 1]

            additional_tracks = []
            if content:
                try:
                    tracks_raw = json.loads(content)
                    if isinstance(tracks_raw, list):
                        existing_keys = {f"{t['track_name'].lower()}|{t['artist'].lower()}" for t in existing_tracks}
                        
                        for track in tracks_raw:
                            if isinstance(track, dict) and "track_name" in track and "artist" in track:
                                track.setdefault("album", "Unknown Album")
                                track.setdefault("release_year", "Unknown")
                                
                                track_key = f"{track['track_name'].lower()}|{track['artist'].lower()}"
                                if track_key not in existing_keys:
                                    additional_tracks.append(track)
                                    existing_keys.add(track_key)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse additional tracks response")
            
            logger.info(f"Generated {len(additional_tracks)} additional tracks")
            return additional_tracks
            
        except Exception as e:
            logger.error(f"Error generating additional tracks: {str(e)}")
            return []

    async def generate_playlist_title(self, query: str) -> str:
        """
        Generate a playlist title based on the user query
        Now using JSON format for consistency
        """
        try:
            # Build user prompt from config
            user_prompt = self.user_prompts["playlist_title"].format(query=query)

            response = await self.client.chat.completions.create(
                model=MODEL_FAST,  # Simple creative task
                messages=[
                    {"role": "system", "content": self.system_prompts["playlist_title"]["system_message"]},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=100
                # Note: gpt-5-mini only supports default temperature (1)
            )

            content = response.choices[0].message.content.strip()
            logger.info(f"Raw playlist title response: '{content}'")

            # Clean up markdown formatting if present
            if content.startswith('```json'):
                content = content[7:]  # Remove ```json
            elif content.startswith('```'):
                content = content[3:]   # Remove ```
            
            if content.endswith('```'):
                content = content[:-3]  # Remove trailing ```
            
            content = content.strip()

            # Extract JSON object if needed
            if not content.startswith('{'):
                start_idx = content.find('{')
                if start_idx != -1:
                    end_idx = content.rfind('}')
                    if end_idx != -1 and end_idx > start_idx:
                        content = content[start_idx:end_idx + 1]

            # Parse JSON response
            try:
                result = json.loads(content)
                if isinstance(result, dict) and "playlist_name" in result:
                    title = result["playlist_name"].strip()
                    logger.info(f"Extracted playlist title: '{title}'")
                    
                    if title and len(title.strip()) >= 2:
                        return title
                    else:
                        logger.warning(f"Generated title too short: '{title}', using fallback")
                        return "Custom Playlist"
                else:
                    logger.warning(f"Invalid playlist title structure: {result}")
                    return "Custom Playlist"

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse playlist title response: {content}")
                return "Custom Playlist"

        except Exception as e:
            logger.error(f"Failed to generate playlist title: {str(e)}")
            return "Custom Playlist"

    # ==========================================================================
    # MULTI-PASS AGENTIC PLAYLIST GENERATION
    # ==========================================================================

    async def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Pass 1: Analyze the user's query to extract structured information
        about genres, moods, eras, tempo, themes, and reference artists.
        """
        try:
            system_prompt = self.system_prompts.get("query_analysis", {}).get(
                "system_message",
                """You are a music analysis expert. Analyze playlist queries to extract structured information.
                CRITICAL: Your response must be ONLY a valid JSON object. No other text, explanations, or markdown."""
            )

            user_prompt = f"""Analyze this playlist request and extract structured information:

"{query}"

Return a JSON object with these exact fields:
- genres: array of music genres (e.g., ["indie pop", "indie rock"])
- moods: array of mood descriptors (e.g., ["upbeat", "carefree", "nostalgic"])
- eras: array of time periods (e.g., ["2010s", "2020s"])
- tempo_range: string describing tempo (e.g., "medium-fast", "slow", "varied")
- reference_artists: array of any artists mentioned or strongly implied (e.g., ["The 1975", "Vampire Weekend"])
- themes: array of contextual themes (e.g., ["road trip", "summer", "workout"])
- energy_level: string (one of: "low", "medium", "high", "varied")
- exclude_artists: array of artists to NOT include (typically the reference artists themselves)

Be thorough in your analysis. If genres or moods aren't explicit, infer them from context."""

            response = await self.client.chat.completions.create(
                model=MODEL_FAST,  # Simple extraction task
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=500
                # Note: gpt-5-mini only supports default temperature (1)
            )

            content = response.choices[0].message.content.strip()
            content = self._clean_json_response(content)

            try:
                data = json.loads(content)
                return QueryAnalysis(
                    genres=data.get("genres", []),
                    moods=data.get("moods", []),
                    eras=data.get("eras", []),
                    tempo_range=data.get("tempo_range", "varied"),
                    reference_artists=data.get("reference_artists", []),
                    themes=data.get("themes", []),
                    energy_level=data.get("energy_level", "varied"),
                    exclude_artists=data.get("exclude_artists", [])
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse query analysis: {content[:500]}")
                # Return a basic analysis based on the query
                return QueryAnalysis(
                    genres=[],
                    moods=[],
                    eras=[],
                    tempo_range="varied",
                    reference_artists=[],
                    themes=[query],
                    energy_level="varied",
                    exclude_artists=[]
                )

        except Exception as e:
            logger.error(f"Query analysis failed: {str(e)}")
            return QueryAnalysis(
                genres=[],
                moods=[],
                eras=[],
                tempo_range="varied",
                reference_artists=[],
                themes=[query],
                energy_level="varied",
                exclude_artists=[]
            )

    async def generate_tracks_from_analysis(
        self,
        analysis: QueryAnalysis,
        count: int,
        existing_tracks: List[Dict] = None
    ) -> List[Dict[str, str]]:
        """
        Pass 2: Generate track suggestions based on the structured analysis.
        Requests ~30% extra to account for Spotify search failures.
        Enforces max 2 tracks per artist and mix of popular + deep cuts.
        """
        if existing_tracks is None:
            existing_tracks = []

        # Request 30% more to account for Spotify search failures
        request_count = int(count * 1.3) + 5

        try:
            system_prompt = self.system_prompts.get("track_generation_agentic", {}).get(
                "system_message",
                """You are an expert music curator with encyclopedic knowledge of music across all genres and eras.
                CRITICAL: Your response must be ONLY a valid JSON array. No other text, explanations, or markdown."""
            )

            # Build context from analysis
            genres_str = ", ".join(analysis.genres) if analysis.genres else "varied genres"
            moods_str = ", ".join(analysis.moods) if analysis.moods else "varied moods"
            eras_str = ", ".join(analysis.eras) if analysis.eras else "any era"
            themes_str = ", ".join(analysis.themes) if analysis.themes else ""

            exclude_str = ""
            if analysis.exclude_artists:
                exclude_str = f"\n\nDO NOT include any songs by these reference artists (the user wants SIMILAR music, not their actual songs): {', '.join(analysis.exclude_artists)}"

            existing_str = ""
            if existing_tracks:
                existing_list = [f'"{t.get("track_name", t.get("title", ""))}" by {t.get("artist", "")}'
                               for t in existing_tracks[:50]]  # Limit to avoid token overflow
                existing_str = f"\n\nDO NOT suggest these already selected tracks: {', '.join(existing_list)}"

            user_prompt = f"""Generate exactly {request_count} song recommendations based on this analysis:

GENRES: {genres_str}
MOODS: {moods_str}
ERAS: {eras_str}
TEMPO: {analysis.tempo_range}
ENERGY: {analysis.energy_level}
THEMES: {themes_str}
REFERENCE STYLE: Like {', '.join(analysis.reference_artists) if analysis.reference_artists else 'various artists'}

REQUIREMENTS:
1. Maximum 2 songs per artist across all {request_count} tracks
2. Mix of well-known tracks (~60%) and hidden gems/deep cuts (~40%)
3. All tracks must be real, officially released songs
4. Prefer original studio recordings over live versions or remixes
5. Ensure variety within the specified eras
6. Match the mood and energy level accurately{exclude_str}{existing_str}

Return a JSON array of track objects with these fields:
- track_name: string (exact song title)
- artist: string (primary artist name)
- album: string (album name)
- release_year: number (year released)"""

            response = await self.client.chat.completions.create(
                model=MODEL_KNOWLEDGE,  # Needs broad music catalog knowledge
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=int(request_count * 80),
                temperature=0.7
            )

            content = response.choices[0].message.content.strip()
            content = self._clean_json_response(content, array=True)

            try:
                tracks_raw = json.loads(content)
                if not isinstance(tracks_raw, list):
                    raise Exception("Response is not a JSON array")

                # Process and validate tracks
                valid_tracks = []
                seen_tracks = set()
                artist_count = {}

                # Include existing tracks in deduplication
                for track in existing_tracks:
                    track_key = f"{track.get('track_name', track.get('title', '')).lower()}|{track.get('artist', '').lower()}"
                    seen_tracks.add(track_key)
                    artist = track.get('artist', '').lower()
                    artist_count[artist] = artist_count.get(artist, 0) + 1

                for track in tracks_raw:
                    if not isinstance(track, dict):
                        continue

                    # Normalize field names
                    if "title" in track and "track_name" not in track:
                        track["track_name"] = track.pop("title")

                    if not all(field in track for field in ["track_name", "artist"]):
                        continue

                    track.setdefault("album", "Unknown Album")
                    track.setdefault("release_year", "Unknown")

                    # Check for duplicates
                    track_key = f"{track['track_name'].lower()}|{track['artist'].lower()}"
                    if track_key in seen_tracks:
                        continue

                    # Check artist limit (max 2 per artist)
                    artist_lower = track['artist'].lower()
                    if artist_count.get(artist_lower, 0) >= 2:
                        logger.debug(f"Skipping track - artist limit reached: {track['artist']}")
                        continue

                    seen_tracks.add(track_key)
                    artist_count[artist_lower] = artist_count.get(artist_lower, 0) + 1
                    valid_tracks.append(track)

                logger.info(f"Generated {len(valid_tracks)} valid tracks from analysis-based generation")
                return valid_tracks

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse track generation response: {content[:500]}")
                raise Exception(f"Invalid JSON response from AI: {str(e)}")

        except Exception as e:
            logger.error(f"Track generation from analysis failed: {str(e)}")
            raise

    async def validate_diversity(
        self,
        tracks: List[Dict],
        analysis: QueryAnalysis
    ) -> DiversityReport:
        """
        Pass 3: Validate the diversity of the generated playlist.
        Checks artist distribution, duplicates, and era variety.
        """
        issues = []
        artist_count = {}
        track_names = {}
        era_distribution = {}
        artist_violations = []
        duplicate_tracks = []

        for track in tracks:
            # Count artists
            artist = track.get('artist', 'Unknown').lower()
            artist_count[artist] = artist_count.get(artist, 0) + 1

            # Check for duplicate track names
            track_name = track.get('track_name', track.get('title', '')).lower()
            if track_name in track_names:
                duplicate_tracks.append(f"{track.get('track_name')} by {track.get('artist')}")
            else:
                track_names[track_name] = True

            # Track era distribution
            year = track.get('release_year', 'Unknown')
            if isinstance(year, int) or (isinstance(year, str) and year.isdigit()):
                decade = f"{str(year)[:3]}0s"
                era_distribution[decade] = era_distribution.get(decade, 0) + 1

        # Check artist violations (more than 2 tracks per artist)
        for artist, count in artist_count.items():
            if count > 2:
                artist_violations.append(artist)
                issues.append(f"Artist '{artist}' appears {count} times (max 2 allowed)")

        # Check for duplicates
        if duplicate_tracks:
            issues.append(f"Found {len(duplicate_tracks)} duplicate tracks")

        # Check era variety if specific eras were requested
        if analysis.eras and len(era_distribution) == 1:
            issues.append("All tracks are from the same decade - more variety recommended")

        replacement_count = len(duplicate_tracks) + sum(max(0, c - 2) for c in artist_count.values())

        return DiversityReport(
            is_valid=len(issues) == 0,
            artist_violations=artist_violations,
            duplicate_tracks=duplicate_tracks,
            era_distribution=era_distribution,
            issues=issues,
            replacement_count=replacement_count
        )

    async def generate_replacement_tracks(
        self,
        analysis: QueryAnalysis,
        count: int,
        existing_tracks: List[Dict],
        exclude_artists: List[str]
    ) -> List[Dict[str, str]]:
        """
        Generate replacement tracks while avoiding specific artists.
        Used when diversity validation fails.
        """
        # Add excluded artists to the analysis
        extended_exclude = list(set(analysis.exclude_artists + exclude_artists))
        modified_analysis = QueryAnalysis(
            genres=analysis.genres,
            moods=analysis.moods,
            eras=analysis.eras,
            tempo_range=analysis.tempo_range,
            reference_artists=analysis.reference_artists,
            themes=analysis.themes,
            energy_level=analysis.energy_level,
            exclude_artists=extended_exclude
        )

        return await self.generate_tracks_from_analysis(
            modified_analysis,
            count + 5,  # Extra buffer
            existing_tracks
        )

    async def generate_playlist_agentic(
        self,
        query: str,
        track_count: int = 10,
        progress_callback=None
    ) -> tuple[List[Dict[str, str]], QueryAnalysis]:
        """
        Orchestrator method for multi-pass agentic playlist generation.

        Args:
            query: User's natural language playlist request
            track_count: Number of tracks to generate (5-100, default 10)
            progress_callback: Optional async callback for progress updates
                              Signature: async def callback(pass_name: str, message: str)

        Returns:
            Tuple of (tracks list, query analysis)
        """
        async def emit_progress(pass_name: str, message: str):
            if progress_callback:
                await progress_callback(pass_name, message)
            logger.info(f"[{pass_name}] {message}")

        try:
            # PASS 1: Analyze the query
            await emit_progress("analyze", "Analyzing your music preferences...")
            analysis = await self.analyze_query(query)
            genres_str = ', '.join(analysis.genres[:3]) if analysis.genres else 'various genres'
            moods_str = ', '.join(analysis.moods[:3]) if analysis.moods else 'mixed moods'
            await emit_progress("analyze", f"Identified: {genres_str} / {moods_str}")
            logger.info(f"Query analysis complete: {asdict(analysis)}")

            # PASS 2: Generate tracks based on analysis
            await emit_progress("generate", f"Generating {track_count} track recommendations...")
            tracks = await self.generate_tracks_from_analysis(analysis, track_count)
            await emit_progress("generate", f"Generated {len(tracks)} potential tracks")

            # PASS 3: Validate diversity
            await emit_progress("validate", "Validating playlist diversity...")
            diversity_report = await self.validate_diversity(tracks, analysis)

            if not diversity_report.is_valid:
                await emit_progress("validate", f"Found issues: {', '.join(diversity_report.issues)}")

                # Remove problematic tracks
                tracks_to_remove = set()
                artist_seen = {}

                for i, track in enumerate(tracks):
                    artist = track.get('artist', '').lower()
                    if artist_seen.get(artist, 0) >= 2:
                        tracks_to_remove.add(i)
                    else:
                        artist_seen[artist] = artist_seen.get(artist, 0) + 1

                # Also remove duplicates
                seen_names = set()
                for i, track in enumerate(tracks):
                    name = track.get('track_name', '').lower()
                    if name in seen_names:
                        tracks_to_remove.add(i)
                    seen_names.add(name)

                cleaned_tracks = [t for i, t in enumerate(tracks) if i not in tracks_to_remove]

                # Generate replacements if needed
                if len(cleaned_tracks) < track_count:
                    needed = track_count - len(cleaned_tracks)
                    await emit_progress("validate", f"Generating {needed} replacement tracks...")

                    replacements = await self.generate_replacement_tracks(
                        analysis,
                        needed,
                        cleaned_tracks,
                        diversity_report.artist_violations
                    )
                    cleaned_tracks.extend(replacements[:needed])

                tracks = cleaned_tracks

            # Trim to exact count requested
            tracks = tracks[:track_count]

            await emit_progress("complete", f"Playlist ready with {len(tracks)} tracks")
            return tracks, analysis

        except Exception as e:
            logger.error(f"Agentic playlist generation failed: {str(e)}")
            raise

    def _clean_json_response(self, content: str, array: bool = False) -> str:
        """
        Clean up markdown formatting from AI responses.
        """
        # Remove markdown code blocks
        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]

        if content.endswith('```'):
            content = content[:-3]

        content = content.strip()

        # Extract JSON structure if needed
        if array:
            if not content.startswith('['):
                start_idx = content.find('[')
                if start_idx != -1:
                    end_idx = content.rfind(']')
                    if end_idx != -1 and end_idx > start_idx:
                        content = content[start_idx:end_idx + 1]
        else:
            if not content.startswith('{'):
                start_idx = content.find('{')
                if start_idx != -1:
                    end_idx = content.rfind('}')
                    if end_idx != -1 and end_idx > start_idx:
                        content = content[start_idx:end_idx + 1]

        return content
