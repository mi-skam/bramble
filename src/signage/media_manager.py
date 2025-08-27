"""Media file management and operations."""

import logging
import mimetypes
import shutil
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger(__name__)


class MediaFile:
    """Represents a media file with metadata."""

    VIDEO_EXTENSIONS: ClassVar[set[str]] = {
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        ".m4v",
        ".mpg",
        ".mpeg",
    }
    IMAGE_EXTENSIONS: ClassVar[set[str]] = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".svg"}
    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS

    def __init__(self, path: Path, default_image_duration: float = 5.0) -> None:
        """Initialize media file.

        Args:
            path: Path to the media file.
            default_image_duration: Default duration for image files.
        """
        self.path = path
        self.name = path.name
        self.is_video = self._is_video()
        self.duration = None if self.is_video else default_image_duration

    def _is_video(self) -> bool:
        """Check if file is a video based on MIME type and extension."""
        mime_type, _ = mimetypes.guess_type(str(self.path))
        if mime_type:
            return mime_type.startswith("video/")
        return self.path.suffix.lower() in self.VIDEO_EXTENSIONS

    @classmethod
    def is_supported(cls, path: Path) -> bool:
        """Check if file extension is supported."""
        return path.suffix.lower() in cls.SUPPORTED_EXTENSIONS and not path.name.startswith(".")

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} ({'video' if self.is_video else f'image {self.duration}s'})"

    def __repr__(self) -> str:
        """String representation."""
        return f"MediaFile({self.path}, video={self.is_video}, duration={self.duration})"


class MediaManager:
    """Manages media files and playlists."""

    def __init__(
        self,
        media_directory: str,
        default_image_duration: float = 5.0,
    ) -> None:
        """Initialize media manager.

        Args:
            media_directory: Directory containing media files.
            default_image_duration: Default duration for image files.
        """
        self.media_directory = Path(media_directory)
        self.default_image_duration = default_image_duration
        self.playlist: list[MediaFile] = []
        self.current_index = 0

        if not self.media_directory.exists():
            logger.warning(f"Media directory does not exist: {self.media_directory}")
            self.media_directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created media directory: {self.media_directory}")

    def scan_directory(self) -> list[MediaFile]:
        """Scan media directory for supported files.

        Returns:
            List of MediaFile objects found in the directory.
        """
        media_files = []

        try:
            files = [f for f in self.media_directory.iterdir() if f.is_file() and MediaFile.is_supported(f)]
            files.sort()

            for file_path in files:
                try:
                    media_file = MediaFile(file_path, self.default_image_duration)
                    media_files.append(media_file)
                    logger.debug(f"Found media file: {media_file}")
                except Exception as e:
                    logger.warning(f"Skipping invalid media file {file_path}: {e}")

        except Exception as e:
            logger.error(f"Error scanning media directory: {e}")

        logger.info(f"Found {len(media_files)} media files in {self.media_directory}")
        return media_files

    def refresh_playlist(self) -> None:
        """Refresh the playlist from the media directory."""
        old_count = len(self.playlist)
        old_current = self.get_current_media()

        self.playlist = self.scan_directory()

        # Try to maintain position if same file exists
        if old_current and old_current.path.exists():
            for i, media in enumerate(self.playlist):
                if media.path == old_current.path:
                    self.current_index = i
                    break

        # Reset index if out of bounds
        if self.current_index >= len(self.playlist):
            self.current_index = 0 if self.playlist else -1

        logger.info(f"Playlist updated: {len(self.playlist)} files (was {old_count})")

    def get_current_media(self) -> MediaFile | None:
        """Get currently selected media file."""
        if not self.playlist or self.current_index < 0:
            return None
        return self.playlist[self.current_index]

    def next_media(self) -> MediaFile | None:
        """Move to next media file."""
        if not self.playlist:
            return None

        self.current_index = (self.current_index + 1) % len(self.playlist)
        return self.get_current_media()

    def previous_media(self) -> MediaFile | None:
        """Move to previous media file."""
        if not self.playlist:
            return None

        self.current_index = (self.current_index - 1) % len(self.playlist)
        return self.get_current_media()

    def skip_to(self, index: int) -> MediaFile | None:
        """Skip to specific media file by index."""
        if not self.playlist or index < 0 or index >= len(self.playlist):
            return None

        self.current_index = index
        return self.get_current_media()

    def add_media_file(self, source_path: Path) -> bool:
        """Copy a media file to the media directory.

        Args:
            source_path: Path to the source media file.

        Returns:
            True if file was successfully added.
        """
        if not source_path.exists():
            logger.error(f"Source file does not exist: {source_path}")
            return False

        if not MediaFile.is_supported(source_path):
            logger.error(f"Unsupported file type: {source_path}")
            return False

        dest_path = self.media_directory / source_path.name

        try:
            shutil.copy2(source_path, dest_path)
            logger.info(f"Added media file: {dest_path.name}")
            self.refresh_playlist()
            return True
        except Exception as e:
            logger.error(f"Failed to add media file: {e}")
            return False

    def remove_media_file(self, filename: str) -> bool:
        """Remove a media file from the media directory.

        Args:
            filename: Name of the file to remove.

        Returns:
            True if file was successfully removed.
        """
        file_path = self.media_directory / filename

        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Removed media file: {filename}")
                self.refresh_playlist()
                return True
            else:
                logger.warning(f"Media file not found: {filename}")
                return False
        except Exception as e:
            logger.error(f"Failed to remove media file: {e}")
            return False

    def list_media_files(self) -> list[str]:
        """Get list of media filenames in the directory."""
        return [media.name for media in self.playlist]

    def get_playlist_info(self) -> dict:
        """Get information about current playlist state."""
        current_media = self.get_current_media()
        return {
            "total_files": len(self.playlist),
            "current_index": self.current_index,
            "current_file": str(current_media) if current_media else None,
            "media_directory": str(self.media_directory),
            "has_videos": any(m.is_video for m in self.playlist),
            "has_images": any(not m.is_video for m in self.playlist),
        }

    def is_empty(self) -> bool:
        """Check if playlist is empty."""
        return len(self.playlist) == 0
