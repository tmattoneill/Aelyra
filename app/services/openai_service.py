import openai
import json
import logging
import os
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self, api_key: str = None):
        # Use provided API key or fall back to environment variable
        final_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not final_api_key:
            raise ValueError("OpenAI API key not provided and not found in environment variables")
        # Set longer timeout for reasoning models
        self.client = openai.OpenAI(api_key=final_api_key, timeout=120.0)
        
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

    async def generate_track_suggestions(self, query: str) -> List[Dict[str, str]]:
        """
        Generate track suggestions based on natural language query
        Now generates tracks one at a time to avoid truncation issues
        """
        try:
            tracks = []
            max_tracks = 10
            
            for i in range(max_tracks):
                # Create avoid duplicates text
                existing_tracks = ", ".join([f'"{t.get("track_name", t.get("title", ""))}" by {t.get("artist", "")}' for t in tracks])
                avoid_duplicates = f"\n\nDo not suggest any of these already selected tracks: {existing_tracks}" if existing_tracks else ""
                
                # Build user prompt from config
                user_prompt = self.user_prompts["track_generation"].format(
                    query=query,
                    avoid_duplicates=avoid_duplicates
                )

                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": self.system_prompts["track_generation"]["system_message"]},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_completion_tokens=300,
                    temperature=0.7
                )

                content = response.choices[0].message.content.strip()
                logger.info(f"Raw track {i+1} response (length: {len(content)}): '{content}'")
                
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

                # Skip empty responses
                if not content:
                    logger.warning(f"Empty response for track {i+1}, skipping")
                    continue
                
                # Parse JSON response
                try:
                    track = json.loads(content)
                    
                    # Validate required fields (supporting both old and new format)
                    required_fields = ["track_name", "artist"]
                    if not isinstance(track, dict) or not all(field in track for field in required_fields):
                        # Try old format for backward compatibility
                        if "title" in track and "artist" in track:
                            track["track_name"] = track.pop("title")
                        else:
                            logger.warning(f"Invalid track structure for track {i+1}: {track}")
                            continue
                    
                    # Ensure all expected fields exist with defaults
                    track.setdefault("album", "Unknown Album")
                    track.setdefault("release_year", "Unknown")
                    
                    # Check for duplicates
                    track_name = track.get("track_name", "").lower()
                    artist = track.get("artist", "").lower()
                    if any(t.get("track_name", t.get("title", "")).lower() == track_name and 
                           t.get("artist", "").lower() == artist for t in tracks):
                        logger.info(f"Skipping duplicate track: {track.get('track_name')} by {track.get('artist')}")
                        continue
                    
                    tracks.append(track)
                    logger.info(f"Added track {len(tracks)}: {track.get('track_name')} by {track.get('artist')}")

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse track {i+1} response: {content}")
                    logger.warning(f"JSON decode error: {str(e)}")
                    continue

            if not tracks:
                raise Exception("Failed to generate any valid tracks")
            
            return tracks

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise Exception(f"Failed to generate track suggestions: {str(e)}")

    async def generate_playlist_title(self, query: str) -> str:
        """
        Generate a playlist title based on the user query
        Now using JSON format for consistency
        """
        try:
            # Build user prompt from config
            user_prompt = self.user_prompts["playlist_title"].format(query=query)

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompts["playlist_title"]["system_message"]},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=100,
                temperature=0.7
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
    
    async def generate_track_alternatives(self, main_track: Dict[str, str], count: int = 4) -> List[Dict[str, str]]:
        """
        Generate alternative tracks based on a main track
        """
        try:
            alternatives = []
            
            for i in range(count):
                # Build avoid duplicates text
                existing_tracks = [main_track] + alternatives
                existing_list = ", ".join([f'"{t.get("track_name", t.get("title", ""))}" by {t.get("artist", "")}' for t in existing_tracks])
                avoid_duplicates = f"\n\nDo not suggest any of these tracks: {existing_list}"
                
                # Build user prompt from config
                user_prompt = self.user_prompts["track_alternatives"].format(
                    track_name=main_track.get("track_name", main_track.get("title", "")),
                    artist=main_track.get("artist", ""),
                    album=main_track.get("album", "Unknown Album"),
                    release_year=main_track.get("release_year", "Unknown"),
                    avoid_duplicates=avoid_duplicates
                )

                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": self.system_prompts["track_generation"]["system_message"]},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_completion_tokens=300,
                    temperature=0.8  # Higher temperature for more variety
                )

                content = response.choices[0].message.content.strip()
                logger.info(f"Raw alternative {i+1} response: '{content}'")
                
                # Clean up and parse (same logic as track generation)
                if content.startswith('```json'):
                    content = content[7:]
                elif content.startswith('```'):
                    content = content[3:]
                
                if content.endswith('```'):
                    content = content[:-3]
                
                content = content.strip()

                if not content.startswith('{'):
                    start_idx = content.find('{')
                    if start_idx != -1:
                        end_idx = content.rfind('}')
                        if end_idx != -1 and end_idx > start_idx:
                            content = content[start_idx:end_idx + 1]

                if not content:
                    logger.warning(f"Empty alternative response {i+1}, skipping")
                    continue
                
                try:
                    alternative = json.loads(content)
                    
                    # Validate and normalize fields
                    if "title" in alternative and "artist" in alternative:
                        alternative["track_name"] = alternative.pop("title")
                    
                    if not isinstance(alternative, dict) or "track_name" not in alternative or "artist" not in alternative:
                        logger.warning(f"Invalid alternative structure {i+1}: {alternative}")
                        continue
                    
                    # Set defaults
                    alternative.setdefault("album", "Unknown Album")
                    alternative.setdefault("release_year", "Unknown")
                    
                    # Check for duplicates
                    alt_name = alternative.get("track_name", "").lower()
                    alt_artist = alternative.get("artist", "").lower()
                    main_name = main_track.get("track_name", main_track.get("title", "")).lower()
                    main_artist = main_track.get("artist", "").lower()
                    
                    # Skip if same as main track or existing alternatives
                    if (alt_name == main_name and alt_artist == main_artist) or \
                       any(t.get("track_name", "").lower() == alt_name and t.get("artist", "").lower() == alt_artist for t in alternatives):
                        logger.info(f"Skipping duplicate alternative: {alternative.get('track_name')} by {alternative.get('artist')}")
                        continue
                    
                    alternatives.append(alternative)
                    logger.info(f"Added alternative {len(alternatives)}: {alternative.get('track_name')} by {alternative.get('artist')}")

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse alternative {i+1} response: {content}")
                    continue
            
            return alternatives

        except Exception as e:
            logger.error(f"Error generating track alternatives: {str(e)}")
            return []