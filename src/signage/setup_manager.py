"""Setup and initialization management."""

import logging
import platform
import shutil
import signal
import sys
from pathlib import Path
from typing import Callable, Optional

from .config import SignageConfig

logger = logging.getLogger(__name__)


class SetupManager:
    """Manages system setup, initialization, and requirements checking."""

    def __init__(self, config: SignageConfig) -> None:
        """Initialize setup manager.
        
        Args:
            config: Application configuration.
        """
        self.config = config
        self.shutdown_handlers: list[Callable] = []

    def check_requirements(self) -> bool:
        """Check if all system requirements are met.
        
        Returns:
            True if all requirements are satisfied.
        """
        all_ok = True
        
        # Check MPV installation
        if not self._check_mpv():
            all_ok = False
        
        # Check media directory
        if not self._check_media_directory():
            all_ok = False
        
        return all_ok

    def _check_mpv(self) -> bool:
        """Check if MPV is installed.
        
        Returns:
            True if MPV is available.
        """
        if not shutil.which("mpv"):
            logger.error("MPV is not installed!")
            logger.error("Installation instructions:")
            logger.error("  macOS: brew install mpv")
            logger.error("  Ubuntu/Debian: sudo apt-get install mpv")
            logger.error("  Arch: sudo pacman -S mpv")
            logger.error("  Raspberry Pi OS: sudo apt-get install mpv")
            return False
        
        logger.debug("MPV is installed")
        return True

    def _check_media_directory(self) -> bool:
        """Check if media directory exists and is accessible.
        
        Returns:
            True if media directory is ready.
        """
        media_path = Path(self.config.media_directory)
        
        if not media_path.exists():
            logger.warning(f"Media directory does not exist: {media_path}")
            try:
                media_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created media directory: {media_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to create media directory: {e}")
                return False
        
        if not media_path.is_dir():
            logger.error(f"Media path is not a directory: {media_path}")
            return False
        
        # Check if we can read the directory
        try:
            list(media_path.iterdir())
            logger.debug(f"Media directory is accessible: {media_path}")
            return True
        except Exception as e:
            logger.error(f"Cannot access media directory: {e}")
            return False

    def detect_platform(self) -> dict:
        """Detect platform and system information.
        
        Returns:
            Dictionary with platform details.
        """
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        is_raspberry_pi = (("arm" in machine or "aarch" in machine) and 
                           system == "linux" and 
                           os.path.exists("/proc/device-tree/model"))
        has_display = bool(sys.stdout.isatty() or platform.system() == "Windows")
        
        info = {
            "system": system,
            "machine": machine,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "is_raspberry_pi": is_raspberry_pi,
            "has_display": has_display,
        }
        
        logger.info(f"Platform detected: {system} on {machine}")
        logger.debug(f"Platform details: {info}")
        
        return info

    def setup_signal_handlers(self, shutdown_callback: Optional[Callable] = None) -> None:
        """Set up signal handlers for graceful shutdown.
        
        Args:
            shutdown_callback: Optional callback to execute on shutdown.
        """
        def signal_handler(signum: int, frame) -> None:
            logger.info(f"Received signal {signum}, initiating shutdown...")
            
            # Call registered shutdown handlers
            for handler in self.shutdown_handlers:
                try:
                    handler()
                except Exception as e:
                    logger.error(f"Error in shutdown handler: {e}")
            
            # Call the main shutdown callback
            if shutdown_callback:
                try:
                    shutdown_callback()
                except Exception as e:
                    logger.error(f"Error in shutdown callback: {e}")
            
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.debug("Signal handlers configured")

    def register_shutdown_handler(self, handler: Callable) -> None:
        """Register a handler to be called on shutdown.
        
        Args:
            handler: Callback function to execute on shutdown.
        """
        self.shutdown_handlers.append(handler)
        logger.debug(f"Registered shutdown handler: {handler.__name__}")

    def initialize_logging(self) -> None:
        """Initialize and configure logging based on configuration."""
        self.config.setup_logging()
        
        # Set specific loggers if in test mode
        if self.config.test_mode:
            logging.getLogger("signage").setLevel(logging.DEBUG)
            logger.info("Test mode enabled - verbose logging active")

    def validate_configuration(self) -> bool:
        """Validate the current configuration.
        
        Returns:
            True if configuration is valid.
        """
        try:
            self.config.validate()
            logger.debug("Configuration validated successfully")
            return True
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

    def get_system_info(self) -> dict:
        """Get comprehensive system information.
        
        Returns:
            Dictionary with system details.
        """
        platform_info = self.detect_platform()
        
        return {
            **platform_info,
            "config": {
                "media_directory": self.config.media_directory,
                "test_mode": self.config.test_mode,
                "fullscreen": self.config.fullscreen,
                "log_level": self.config.log_level,
            },
            "requirements": {
                "mpv_installed": shutil.which("mpv") is not None,
                "media_directory_exists": Path(self.config.media_directory).exists(),
            },
        }

    def prepare_environment(self) -> bool:
        """Prepare the environment for running the signage system.
        
        Returns:
            True if environment is ready.
        """
        logger.info("Preparing environment...")
        
        # Initialize logging first
        self.initialize_logging()
        
        # Validate configuration
        if not self.validate_configuration():
            return False
        
        # Check all requirements
        if not self.check_requirements():
            logger.error("System requirements not met")
            return False
        
        # Log system info
        system_info = self.get_system_info()
        logger.info(f"System: {system_info['system']} on {system_info['machine']}")
        logger.info(f"Media directory: {self.config.media_directory}")
        logger.info(f"Mode: {'Test' if self.config.test_mode else 'Production'}")
        
        return True