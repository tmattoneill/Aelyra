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
        Generate 50 track suggestions in one bulk call for better performance
        """
        try:
            # Build user prompt using system prompt format
            user_prompt = self.system_prompts["track_generation"]["objective"].format(prompt=query)
            
            # Combine role and rules into system message for better context
            system_content = f"""{self.system_prompts["track_generation"]["role"]}

{self.system_prompts["track_generation"]["rules"]["core_directive"]}

Rules:
- {' '.join(self.system_prompts["track_generation"]["rules"]["factuality"])}
- {' '.join(self.system_prompts["track_generation"]["rules"]["recording_type"])}
- {' '.join(self.system_prompts["track_generation"]["rules"]["playlist_diversity"])}

{self.system_prompts["track_generation"]["system_message"]}"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=4000,  # Increased for 50 tracks
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
                    
                    if len(valid_tracks) >= 50:  # Cap at 50 tracks
                        break

                logger.info(f"Generated {len(valid_tracks)} valid tracks from bulk request")
                
                # If we didn't get enough tracks, make additional requests
                if len(valid_tracks) < 30:  # Minimum threshold for decent playlist
                    logger.warning(f"Only got {len(valid_tracks)} tracks, attempting fallback generation")
                    additional_tracks = await self._generate_additional_tracks(query, valid_tracks, 50 - len(valid_tracks))
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
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
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
    
