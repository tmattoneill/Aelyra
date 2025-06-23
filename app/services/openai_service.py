import openai
import json
import logging
import os
from typing import List, Dict

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self, api_key: str = None):
        # Use provided API key or fall back to environment variable
        final_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not final_api_key:
            raise ValueError("OpenAI API key not provided and not found in environment variables")
        self.client = openai.OpenAI(api_key=final_api_key)

    async def generate_track_suggestions(self, query: str) -> List[Dict[str, str]]:
        """
        Generate track suggestions based on natural language query
        """
        try:
            prompt = f"""
Based on the user query: "{query}"

Generate a list of 10-15 song suggestions that match this request. 
Return the response as a JSON array with each song having "title" and "artist" fields.
Focus on popular, well-known tracks that are likely to be available on Spotify.

Example format:
[
  {{"title": "Song Name", "artist": "Artist Name"}},
  {{"title": "Another Song", "artist": "Another Artist"}}
]

Query: {query}
"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a music expert who creates curated playlists. Always respond with valid JSON only - no markdown formatting, no backticks, no code blocks. Return raw JSON that can be parsed directly."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            content = response.choices[0].message.content.strip()
            
            # Clean up markdown formatting if present
            if content.startswith('```json'):
                content = content[7:]  # Remove ```json
            elif content.startswith('```'):
                content = content[3:]   # Remove ```
            
            if content.endswith('```'):
                content = content[:-3]  # Remove trailing ```
            
            content = content.strip()

            # Parse JSON response
            try:
                tracks = json.loads(content)
                if not isinstance(tracks, list):
                    raise ValueError("Response is not a list")

                # Validate structure
                for track in tracks:
                    if not isinstance(track, dict) or "title" not in track or "artist" not in track:
                        raise ValueError("Invalid track structure")

                return tracks

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI response as JSON: {content}")
                raise Exception(f"Failed to parse AI response|RAW_RESPONSE:{content}")

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise Exception(f"Failed to generate track suggestions: {str(e)}")

    async def generate_playlist_title(self, query: str) -> str:
        """
        Generate a playlist title based on the user query
        """
        try:
            prompt = f"""
Based on the user query: "{query}"

Generate a creative, catchy playlist title that captures the essence of this request.
The title should be 2-6 words long and engaging.
Return only the title, no additional text or quotes.

Examples:
- For "upbeat songs for morning workout" → "Morning Energy Boost"
- For "chill songs for studying" → "Study Zone Vibes"
- For "romantic dinner music" → "Candlelit Romance"

Query: {query}
"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a creative playlist curator. Generate catchy, short playlist titles."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=50
            )

            title = response.choices[0].message.content.strip()

            # Clean up title (remove quotes if present)
            title = title.strip('"').strip("'")

            return title

        except Exception as e:
            logger.error(f"Failed to generate playlist title: {str(e)}")
            # Fallback to a simple title
            return f"Custom Playlist"