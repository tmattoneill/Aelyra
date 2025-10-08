import re
import logging
from typing import List, Dict, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class M3UParser:
    """
    Parser for M3U playlist files, specifically for Spotify track URLs
    """

    # Regex patterns for Spotify URLs
    SPOTIFY_TRACK_URL_PATTERN = r'https?://open\.spotify\.com/track/([a-zA-Z0-9]+)'
    SPOTIFY_TRACK_URI_PATTERN = r'spotify:track:([a-zA-Z0-9]+)'

    # Maximum number of tracks to prevent abuse
    MAX_TRACKS = 500

    @staticmethod
    def parse(m3u_content: str) -> Dict:
        """
        Parse M3U file content and extract Spotify track IDs

        Args:
            m3u_content: The raw content of the .m3u file

        Returns:
            Dictionary containing:
                - track_ids: List of Spotify track IDs
                - track_info: List of track metadata (if available from EXTINF)
                - warnings: List of parsing warnings

        Raises:
            ValueError: If the file is invalid or contains no valid Spotify tracks
        """
        if not m3u_content or not m3u_content.strip():
            raise ValueError("M3U file is empty")

        lines = m3u_content.strip().split('\n')
        track_ids = []
        track_info = []
        warnings = []
        current_extinf = None

        # Check if it's an extended M3U file
        is_extended = lines[0].strip().upper() == '#EXTM3U'

        for i, line in enumerate(lines):
            line = line.strip()

            # Skip empty lines and comments (except EXTINF)
            if not line or (line.startswith('#') and not line.startswith('#EXTINF')):
                continue

            # Parse EXTINF metadata (optional)
            if line.startswith('#EXTINF'):
                try:
                    # Format: #EXTINF:duration,Artist - Track Title
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        current_extinf = parts[1].strip()
                except Exception as e:
                    logger.warning(f"Failed to parse EXTINF on line {i+1}: {str(e)}")
                continue

            # Try to extract Spotify track ID from URL or URI
            track_id = M3UParser._extract_spotify_track_id(line)

            if track_id:
                # Avoid duplicates
                if track_id not in track_ids:
                    track_ids.append(track_id)

                    # Store metadata if available
                    metadata = {
                        'track_id': track_id,
                        'extinf': current_extinf,
                        'url': line
                    }
                    track_info.append(metadata)

                    # Check max tracks limit
                    if len(track_ids) >= M3UParser.MAX_TRACKS:
                        warnings.append(f"Reached maximum limit of {M3UParser.MAX_TRACKS} tracks. Additional tracks ignored.")
                        break
                else:
                    warnings.append(f"Duplicate track ID found on line {i+1}, skipping")

                # Reset current EXTINF after processing
                current_extinf = None
            elif line.startswith('http') or line.startswith('spotify:'):
                # It's a URL but not a Spotify track URL
                warnings.append(f"Non-Spotify URL on line {i+1}, skipping: {line[:50]}")

        if not track_ids:
            raise ValueError("No valid Spotify track URLs found in M3U file")

        logger.info(f"Parsed M3U file: {len(track_ids)} tracks found, {len(warnings)} warnings")

        return {
            'track_ids': track_ids,
            'track_info': track_info,
            'warnings': warnings,
            'is_extended': is_extended
        }

    @staticmethod
    def _extract_spotify_track_id(line: str) -> str:
        """
        Extract Spotify track ID from a URL or URI

        Args:
            line: A line from the M3U file

        Returns:
            Track ID if found, None otherwise
        """
        # Try URL pattern first (https://open.spotify.com/track/...)
        match = re.search(M3UParser.SPOTIFY_TRACK_URL_PATTERN, line)
        if match:
            return match.group(1)

        # Try URI pattern (spotify:track:...)
        match = re.search(M3UParser.SPOTIFY_TRACK_URI_PATTERN, line)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def validate_file_content(content: str) -> Tuple[bool, str]:
        """
        Quick validation of M3U file content

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not content or not content.strip():
            return False, "File is empty"

        # Check file size (rough estimate: max 100KB for text)
        if len(content) > 100 * 1024:
            return False, "File is too large (max 100KB)"

        lines = content.strip().split('\n')

        # Check if it looks like an M3U file
        has_m3u_header = lines[0].strip().upper() == '#EXTM3U'
        has_spotify_urls = any(
            'spotify.com/track' in line or 'spotify:track:' in line
            for line in lines
        )

        if not has_spotify_urls:
            return False, "No Spotify track URLs found in file"

        return True, ""
