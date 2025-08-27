"""Scheduler for managing signage playback and timing."""

import logging
import time
from threading import Event, Thread
from typing import TYPE_CHECKING, Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer as WatchdogObserver

if TYPE_CHECKING:
    pass

from .media_manager import MediaManager
from .player import MPVController

logger = logging.getLogger(__name__)


class MediaWatcher(FileSystemEventHandler):
    """Watch media directory for changes."""

    def __init__(self, scheduler: "SignageScheduler") -> None:
        """Initialize media watcher."""
        self.scheduler = scheduler

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation."""
        if not event.is_directory:
            logger.info(f"New media file detected: {event.src_path!r}")
            self.scheduler.refresh_playlist()

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion."""
        if not event.is_directory:
            logger.info(f"Media file deleted: {event.src_path!r}")
            self.scheduler.refresh_playlist()

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification."""
        if not event.is_directory:
            logger.debug(f"Media file modified: {event.src_path!r}")


class SignageScheduler:
    """Manages playlist scheduling and playback coordination."""

    def __init__(
        self,
        media_manager: MediaManager,
        player: MPVController,
        watch_directory: bool = True,
    ) -> None:
        """Initialize scheduler.

        Args:
            media_manager: Media file manager.
            player: MPV player controller.
            watch_directory: Watch directory for changes.
        """
        self.media_manager = media_manager
        self.player = player
        self.watch_directory = watch_directory

        self.running = False
        self.stop_event = Event()
        self.playback_thread: Thread | None = None
        self.observer: Any = None

        # Initialize playlist
        self.media_manager.refresh_playlist()

    def refresh_playlist(self) -> None:
        """Refresh the media playlist."""
        self.media_manager.refresh_playlist()

    def get_status(self) -> dict:
        """Get current scheduler status."""
        playlist_info = self.media_manager.get_playlist_info()

        return {
            "running": self.running,
            "player_active": self.player.is_running(),
            **playlist_info,
        }

    def next_media(self) -> str | None:
        """Skip to next media file."""
        media = self.media_manager.next_media()
        if media:
            logger.info(f"Skipped to next media: {media}")
            return str(media)
        return None

    def previous_media(self) -> str | None:
        """Skip to previous media file."""
        media = self.media_manager.previous_media()
        if media:
            logger.info(f"Skipped to previous media: {media}")
            return str(media)
        return None

    def _playback_loop(self) -> None:
        """Main playback loop running in separate thread."""
        logger.info("Starting playback loop")
        consecutive_failures = 0
        max_failures = 10

        while not self.stop_event.is_set():
            if self.media_manager.is_empty():
                logger.warning("No media files in playlist, waiting...")
                self.stop_event.wait(5.0)
                self.media_manager.refresh_playlist()
                consecutive_failures = 0
                continue

            current_media = self.media_manager.get_current_media()
            if not current_media:
                self.stop_event.wait(1.0)
                continue

            logger.info(f"Playing: {current_media}")

            try:
                if not self.player.load_file(str(current_media.path), current_media.duration):
                    # Check if MPV exited normally (user quit)
                    exit_code = self.player.get_exit_code()
                    if exit_code == 0:
                        logger.info("User quit during file loading, stopping system")
                        self.stop_event.set()
                        break

                    logger.error(f"Failed to load file: {current_media.path}")
                    consecutive_failures += 1

                    # If we have too many consecutive failures, wait longer
                    if consecutive_failures >= max_failures:
                        logger.error(f"Too many consecutive failures ({consecutive_failures}), waiting 30 seconds...")
                        self.stop_event.wait(30.0)
                        consecutive_failures = 0
                    else:
                        # Wait a bit before trying the next file
                        self.stop_event.wait(2.0)

                    self.media_manager.next_media()
                    continue

                # Reset failure counter on successful load
                consecutive_failures = 0

                if current_media.is_video:
                    # Wait for video to finish playing
                    self._wait_for_video_completion()
                else:
                    # Wait for image duration
                    if current_media.duration:
                        self.stop_event.wait(current_media.duration)

            except Exception as e:
                logger.error(f"Error during playback of {current_media.path}: {e}")
                consecutive_failures += 1

                # Wait before trying next media to avoid rapid error loops
                self.stop_event.wait(2.0)

            if not self.stop_event.is_set():
                self.media_manager.next_media()

        logger.info("Playback loop stopped")

    def _wait_for_video_completion(self) -> None:
        """Wait for current video to finish playing."""
        start_time = time.time()
        max_wait_time = 3600  # 1 hour max per video
        video_started = False
        last_position = 0
        stuck_count = 0
        max_stuck_attempts = 10  # If position doesn't change for 5 seconds, assume video ended

        logger.debug("Waiting for video completion...")

        while not self.stop_event.is_set():
            try:
                if not self.player.is_running():
                    exit_code = self.player.get_exit_code()
                    if exit_code == 0:
                        logger.info("MPV exited normally (user pressed q), stopping system")
                        self.stop_event.set()  # Signal the main system to stop
                        return
                    else:
                        logger.warning("MPV process died during video playback")
                        break

                # Get video properties
                duration = self.player.get_property("duration")
                position = self.player.get_property("time-pos")
                paused = self.player.get_property("pause")
                eof_reached = self.player.get_property("eof-reached")

                # If we can't get basic properties, wait and retry
                if paused is None:
                    logger.debug("Properties not available yet, waiting...")
                    self.stop_event.wait(0.5)
                    continue

                # Check if video has started
                if not video_started and position and position > 0:
                    video_started = True
                    logger.info(f"Video started playing, duration: {duration}s")

                # Log progress periodically for debugging
                if duration and position and video_started:
                    elapsed = time.time() - start_time
                    if int(elapsed) % 3 == 0:  # Every 3 seconds
                        logger.debug(f"Video progress: {position:.1f}/{duration:.1f}s (paused={paused})")

                # Check for completion conditions
                if eof_reached:
                    logger.info("EOF reached, video complete")
                    break

                if duration and position and position >= duration - 0.5:
                    logger.info("Video position near end, completing")
                    break

                # Check if video is stuck (position not advancing)
                if video_started and position is not None:
                    if abs(position - last_position) < 0.1:  # Position hasn't advanced much
                        stuck_count += 1
                        if stuck_count >= max_stuck_attempts:
                            logger.warning(f"Video appears stuck at position {position:.1f}, assuming complete")
                            break
                    else:
                        stuck_count = 0  # Reset counter if position advanced
                    last_position = position

                # Fallback: if no duration info after reasonable time, assume short video
                if not video_started and time.time() - start_time > 10:
                    logger.warning("No video progress detected after 10s, assuming very short video or playback issue")
                    break

                # Safety timeout to prevent infinite loops
                if time.time() - start_time > max_wait_time:
                    current_media = self.media_manager.get_current_media()
                    logger.warning(
                        f"Video {current_media.name if current_media else 'unknown'} exceeded max play time, skipping"
                    )
                    break

                self.stop_event.wait(0.5)

            except Exception as e:
                logger.warning(f"Error checking video progress: {e}")
                self.stop_event.wait(1.0)
                # Don't break on error, continue trying

        logger.info("Video completion wait finished")

    def start(self) -> bool:
        """Start the signage scheduler."""
        if self.running:
            logger.warning("Scheduler is already running")
            return True

        if self.media_manager.is_empty():
            logger.warning("No media files in playlist, but starting anyway...")

        if not self.player.start():
            logger.error("Failed to start MPV player")
            return False

        if self.watch_directory:
            try:
                self.observer = WatchdogObserver()
                event_handler = MediaWatcher(self)
                self.observer.schedule(event_handler, str(self.media_manager.media_directory), recursive=False)
                self.observer.start()
                logger.info(f"Started watching directory: {self.media_manager.media_directory}")
            except Exception as e:
                logger.error(f"Failed to start directory watcher: {e}")

        self.running = True
        self.stop_event.clear()
        self.playback_thread = Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()

        logger.info("Signage scheduler started")
        return True

    def stop(self) -> None:
        """Stop the signage scheduler."""
        if not self.running:
            return

        logger.info("Stopping signage scheduler...")
        self.running = False
        self.stop_event.set()

        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=5.0)
            if self.playback_thread.is_alive():
                logger.warning("Playback thread did not stop gracefully")

        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=2.0)
                self.observer = None
            except Exception as e:
                logger.error(f"Error stopping directory observer: {e}")

        self.player.stop()
        logger.info("Signage scheduler stopped")

    def __enter__(self) -> "SignageScheduler":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.stop()
