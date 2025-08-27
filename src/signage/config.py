"""Configuration management for signage system."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SignageConfig:
    """Configuration for the signage system."""

    media_directory: str = "./media"
    default_image_duration: float = 5.0
    socket_path: str | None = None
    video_output: str | None = None
    hardware_decode: str = "auto"
    fullscreen: bool = True
    test_mode: bool = False
    watch_directory: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SignageConfig":
        """Create config from dictionary."""
        config = cls()

        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                logger.warning(f"Unknown configuration key: {key}")

        return config

    @classmethod
    def from_yaml(cls, config_path: str) -> "SignageConfig":
        """Load configuration from YAML file."""
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {config_path}")
            return cls.from_dict(data)
        except FileNotFoundError:
            logger.info(f"Configuration file not found: {config_path}, using defaults")
            return cls()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            return cls()
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return cls()

    @classmethod
    def from_env(cls) -> "SignageConfig":
        """Load configuration from environment variables."""
        config = cls()

        env_mapping = {
            "SIGNAGE_MEDIA_DIRECTORY": "media_directory",
            "SIGNAGE_IMAGE_DURATION": "default_image_duration",
            "SIGNAGE_SOCKET_PATH": "socket_path",
            "SIGNAGE_VIDEO_OUTPUT": "video_output",
            "SIGNAGE_HARDWARE_DECODE": "hardware_decode",
            "SIGNAGE_FULLSCREEN": "fullscreen",
            "SIGNAGE_TEST_MODE": "test_mode",
            "SIGNAGE_WATCH_DIRECTORY": "watch_directory",
            "SIGNAGE_LOG_LEVEL": "log_level",
        }

        for env_var, attr_name in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    attr_type = type(getattr(config, attr_name))

                    parsed_value: bool | float | int | str
                    if attr_type is bool:
                        parsed_value = env_value.lower() in ("true", "1", "yes", "on")
                    elif attr_type is float:
                        parsed_value = float(env_value)
                    elif attr_type is int:
                        parsed_value = int(env_value)
                    else:
                        parsed_value = env_value

                    setattr(config, attr_name, parsed_value)
                    logger.debug(f"Set {attr_name} from environment: {parsed_value}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid value for {env_var}: {env_value} ({e})")

        return config

    @classmethod
    def load(cls, config_path: str | None = None) -> "SignageConfig":
        """Load configuration with precedence: CLI args > env vars > config file > defaults.

        Args:
            config_path: Path to YAML config file. If None, looks for config.yaml.
        """
        if config_path is None:
            config_path = "config.yaml"
            if not os.path.exists(config_path):
                config_path = str(Path(__file__).parent.parent.parent / "config.yaml")

        config = cls.from_yaml(config_path)

        env_config = cls.from_env()
        for attr_name in config.__dataclass_fields__:
            env_value = getattr(env_config, attr_name)
            default_value = getattr(cls(), attr_name)
            if env_value != default_value:
                setattr(config, attr_name, env_value)

        config.validate()
        return config

    def validate(self) -> None:
        """Validate configuration values."""
        errors = []

        if not self.media_directory:
            errors.append("media_directory cannot be empty")

        if self.default_image_duration <= 0:
            errors.append("default_image_duration must be positive")

        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            errors.append(f"log_level must be one of: {', '.join(valid_log_levels)}")

        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

    def setup_logging(self) -> None:
        """Set up logging based on configuration."""
        log_level = getattr(logging, self.log_level.upper(), logging.INFO)

        logging.basicConfig(
            level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        if self.test_mode:
            logging.getLogger().setLevel(logging.DEBUG)

        logger.info(f"Logging configured at {self.log_level} level")

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {field.name: getattr(self, field.name) for field in self.__dataclass_fields__.values()}

    def save_to_yaml(self, path: str) -> None:
        """Save configuration to YAML file."""
        try:
            with open(path, "w") as f:
                yaml.dump(self.to_dict(), f, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
