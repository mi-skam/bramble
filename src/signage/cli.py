"""CLI interface for the signage system."""

import logging
import sys
import time
from pathlib import Path

import click

from .config import SignageConfig
from .media_manager import MediaManager
from .player import MPVController
from .scheduler import SignageScheduler
from .setup_manager import SetupManager

logger = logging.getLogger(__name__)


class SignageCLI:
    """CLI controller for the signage system."""

    def __init__(self, config: SignageConfig) -> None:
        """Initialize CLI controller."""
        self.config = config
        self.setup_manager = SetupManager(config)
        self.media_manager: MediaManager | None = None
        self.player: MPVController | None = None
        self.scheduler: SignageScheduler | None = None
        self.running = False

    def initialize(self) -> bool:
        """Initialize the signage system components.

        Returns:
            True if initialization successful.
        """
        # Prepare environment (logging, validation, requirements)
        if not self.setup_manager.prepare_environment():
            return False

        # Initialize media manager
        self.media_manager = MediaManager(
            media_directory=self.config.media_directory,
            default_image_duration=self.config.default_image_duration,
        )

        # Initialize player
        self.player = MPVController(
            socket_path=self.config.socket_path,
            video_output=self.config.video_output,
            hardware_decode=self.config.hardware_decode,
            fullscreen=self.config.fullscreen,
            test_mode=self.config.test_mode,
        )

        # Initialize scheduler
        self.scheduler = SignageScheduler(
            media_manager=self.media_manager,
            player=self.player,
            watch_directory=self.config.watch_directory,
        )

        return True

    def start_signage(self) -> bool:
        """Start the signage system."""
        try:
            if not self.scheduler:
                logger.error("System not initialized")
                return False

            if not self.scheduler.start():
                logger.error("Failed to start scheduler")
                return False

            self.running = True
            logger.info("Signage system started successfully")
            logger.info("Keyboard controls: SPACE=play/pause, q=quit, >=next, <=previous")
            return True

        except Exception as e:
            logger.error(f"Failed to start signage system: {e}")
            return False

    def stop(self) -> None:
        """Stop the signage system."""
        if self.scheduler:
            self.scheduler.stop()
            self.scheduler = None

        self.running = False
        logger.info("Signage system stopped")

    def get_status(self) -> dict:
        """Get current system status."""
        if not self.scheduler:
            return {"status": "not_initialized"}

        return {
            "status": "running" if self.running else "stopped",
            **self.scheduler.get_status(),
        }

    def next_media(self) -> bool:
        """Skip to next media."""
        if not self.scheduler:
            return False

        media = self.scheduler.next_media()
        if media:
            if self.player:
                self.player.next()
            return True
        return False

    def previous_media(self) -> bool:
        """Skip to previous media."""
        if not self.scheduler:
            return False

        media = self.scheduler.previous_media()
        if media:
            if self.player:
                self.player.previous()
            return True
        return False

    def refresh_playlist(self) -> None:
        """Refresh the media playlist."""
        if self.scheduler:
            self.scheduler.refresh_playlist()
            logger.info("Playlist refreshed")

    def add_media_file(self, source_path: str) -> bool:
        """Add a media file to the collection."""
        if not self.media_manager:
            logger.error("Media manager not initialized")
            return False

        return self.media_manager.add_media_file(Path(source_path))

    def remove_media_file(self, filename: str) -> bool:
        """Remove a media file from the collection."""
        if not self.media_manager:
            logger.error("Media manager not initialized")
            return False

        return self.media_manager.remove_media_file(filename)

    def list_media_files(self) -> list[str]:
        """List all media files."""
        if not self.media_manager:
            return []

        return self.media_manager.list_media_files()


@click.group(invoke_without_command=True)
@click.option("--config", "-c", help="Configuration file path")
@click.option("--test-mode", "-t", is_flag=True, help="Run in windowed test mode")
@click.option("--media-dir", "-m", help="Media directory path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, config: str | None, test_mode: bool, media_dir: str | None, verbose: bool) -> None:
    """Digital signage system using MPV with IPC control."""
    signage_config = SignageConfig.load(config)

    # Apply CLI overrides
    if test_mode:
        signage_config.test_mode = True
        signage_config.fullscreen = False

    if media_dir:
        signage_config.media_directory = media_dir

    if verbose:
        signage_config.log_level = "DEBUG"

    # Create CLI controller
    ctx.ensure_object(dict)
    ctx.obj["config"] = signage_config
    ctx.obj["cli"] = SignageCLI(signage_config)

    # Run default command if no subcommand specified
    if ctx.invoked_subcommand is None:
        ctx.invoke(run)


@cli.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    """Start the signage system."""
    cli_obj = ctx.obj["cli"]

    logger.info("Starting signage system...")

    # Initialize components
    if not cli_obj.initialize():
        logger.error("Failed to initialize signage system")
        sys.exit(1)

    # Set up signal handlers
    cli_obj.setup_manager.setup_signal_handlers(cli_obj.stop)

    # Start the system
    if not cli_obj.start_signage():
        logger.error("Failed to start signage system")
        sys.exit(1)

    # Main loop
    try:
        while cli_obj.running:
            # Check if scheduler has requested shutdown (e.g., user pressed q in MPV)
            if cli_obj.scheduler and cli_obj.scheduler.stop_event.is_set():
                logger.info("Scheduler requested shutdown")
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        cli_obj.stop()


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current signage status."""
    cli_obj = ctx.obj["cli"]

    # Initialize if needed
    if not cli_obj.media_manager:
        cli_obj.initialize()

    status_info = cli_obj.get_status()

    click.echo("Signage Status:")
    for key, value in status_info.items():
        click.echo(f"  {key}: {value}")


@cli.command(name="next")
@click.pass_context
def next_media(ctx: click.Context) -> None:
    """Skip to next media file."""
    cli_obj = ctx.obj["cli"]

    # Initialize if needed
    if not cli_obj.scheduler and not cli_obj.initialize():
        click.echo("Failed to initialize system")
        return

    if cli_obj.next_media():
        click.echo("Skipped to next media")
    else:
        click.echo("Failed to skip to next media")


@cli.command()
@click.pass_context
def prev(ctx: click.Context) -> None:
    """Skip to previous media file."""
    cli_obj = ctx.obj["cli"]

    # Initialize if needed
    if not cli_obj.scheduler and not cli_obj.initialize():
        click.echo("Failed to initialize system")
        return

    if cli_obj.previous_media():
        click.echo("Skipped to previous media")
    else:
        click.echo("Failed to skip to previous media")


@cli.command()
@click.pass_context
def refresh(ctx: click.Context) -> None:
    """Refresh the media playlist."""
    cli_obj = ctx.obj["cli"]

    # Initialize if needed
    if not cli_obj.scheduler and not cli_obj.initialize():
        click.echo("Failed to initialize system")
        return

    cli_obj.refresh_playlist()
    click.echo("Playlist refreshed")


@cli.command()
@click.argument("media_file", type=click.Path(exists=True))
@click.pass_context
def add(ctx: click.Context, media_file: str) -> None:
    """Add a media file to the media directory."""
    cli_obj = ctx.obj["cli"]

    # Initialize if needed
    if not cli_obj.media_manager and not cli_obj.initialize():
        click.echo("Failed to initialize system")
        return

    if cli_obj.add_media_file(media_file):
        click.echo(f"Added {Path(media_file).name} to media directory")
    else:
        click.echo("Failed to add media file")


@cli.command()
@click.argument("media_name")
@click.pass_context
def remove(ctx: click.Context, media_name: str) -> None:
    """Remove a media file from the media directory."""
    cli_obj = ctx.obj["cli"]

    # Initialize if needed
    if not cli_obj.media_manager and not cli_obj.initialize():
        click.echo("Failed to initialize system")
        return

    if cli_obj.remove_media_file(media_name):
        click.echo(f"Removed {media_name} from media directory")
    else:
        click.echo(f"Failed to remove {media_name}")


@cli.command(name="list")
@click.pass_context
def list_media(ctx: click.Context) -> None:
    """List media files in the directory."""
    cli_obj = ctx.obj["cli"]
    config = ctx.obj["config"]

    # Initialize if needed
    if not cli_obj.media_manager and not cli_obj.initialize():
        click.echo("Failed to initialize system")
        return

    click.echo(f"Media files in {config.media_directory}:")

    files = cli_obj.list_media_files()

    if not files:
        click.echo("  No media files found")
    else:
        for i, file in enumerate(files, 1):
            click.echo(f"  {i}: {file}")


@cli.command()
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show current configuration."""
    config = ctx.obj["config"]
    click.echo("Current Configuration:")

    for key, value in config.to_dict().items():
        click.echo(f"  {key}: {value}")


@cli.command()
@click.pass_context
def system_info(ctx: click.Context) -> None:
    """Show system information."""
    cli_obj = ctx.obj["cli"]

    # Initialize if needed
    if not cli_obj.setup_manager:
        cli_obj.setup_manager = SetupManager(ctx.obj["config"])

    info = cli_obj.setup_manager.get_system_info()

    click.echo("System Information:")
    click.echo(f"  Platform: {info['platform']}")
    click.echo(f"  Python: {info['python_version']}")
    click.echo(f"  Is Raspberry Pi: {info['is_raspberry_pi']}")
    click.echo(f"  Has Display: {info['has_display']}")
    click.echo("\nRequirements:")
    for key, value in info["requirements"].items():
        status = "✓" if value else "✗"
        click.echo(f"  {status} {key}: {value}")
    click.echo("\nConfiguration:")
    for key, value in info["config"].items():
        click.echo(f"  {key}: {value}")


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
