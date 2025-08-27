# Bramble - Digital Signage System

A modern Python digital signage system that uses MPV player with IPC control for seamless media playback. Built with `uv` for fast, reliable dependency management. Supports both images and videos with configurable display durations, designed to be prototypeable on workstations and deployable to Raspberry Pi.

## Features

- **MPV with IPC Control**: Gapless media switching using MPV's JSON IPC interface
- **Mixed Media Support**: Images (with configurable duration) and videos
- **Auto-Detection**: Platform-specific MPV configuration (GPU for desktop, DRM for Pi)
- **Playlist Management**: Automatic playlist generation and directory watching
- **CLI Interface**: Simple commands for testing and control
- **Configuration**: YAML config and environment variable support
- **Modern Tooling**: Uses `uv` for fast dependency management
- **Graceful Handling**: Error handling and fallbacks for missing dependencies

## Quick Start

### Prerequisites

1. **UV Package Manager** (recommended):
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv
```

2. **MPV Player** (required):
```bash
# macOS
brew install mpv

# Ubuntu/Debian/Raspberry Pi OS
sudo apt-get install mpv

# Arch Linux
sudo pacman -S mpv
```

### Installation

1. Clone and setup with `uv`:
```bash
git clone <repository-url>
cd bramble

# Initialize and sync dependencies
uv sync

# Or use just
just install
```

2. Create media directory and add content:
```bash
mkdir media
# Copy your images and videos to the media/ directory
```

3. Test in windowed mode:
```bash
uv run python main.py --test-mode

# Or use just
just test-run
```

## Usage

### Keyboard Controls

During playback, MPV provides these keyboard controls:
- **`SPACE`** - Toggle play/pause
- **`q`** - Quit the application
- **`>` or `→`** - Skip to next media file
- **`<` or `←`** - Skip to previous media file
- **`f`** - Toggle fullscreen
- **`m`** - Mute/unmute
- **`9`/`0`** - Volume down/up
- **`s`** - Take screenshot
- **`r`** - Rotate video

### With UV (Recommended)

```bash
# Start signage (fullscreen)
uv run python main.py

# Or use the installed script
uv run bramble

# Start in test mode (windowed)
uv run python main.py --test-mode

# Use custom media directory
uv run python main.py --media-dir /path/to/media

# Show status
uv run python main.py status

# Control playback
uv run python main.py next        # Skip to next
uv run python main.py prev        # Go to previous
uv run python main.py refresh     # Reload playlist

# Manage media files
uv run python main.py list        # List current media
uv run python main.py add /path/to/file.jpg
uv run python main.py remove filename.jpg
```

### Using Just (Convenient Commands)

Install [just](https://github.com/casey/just) for convenient commands:

```bash
# Install dependencies with uv
just install

# Development setup with all extras
just dev

# Run in test mode
just test-run

# Check if MPV is installed
just check-mpv

# Create demo content
just demo

# Run linting and tests
just check

# Deploy to Raspberry Pi
just deploy-pi pi@192.168.1.100

# Update dependencies
just update

# Show dependency tree
just deps
```

### Global Installation

Install as a global command using `uv tool`:

```bash
# Install globally
uv tool install .

# Run from anywhere
bramble --test-mode

# Uninstall
uv tool uninstall bramble
```

## Configuration

Configuration is loaded from (in precedence order):
1. Command line arguments
2. Environment variables
3. `config.yaml` file
4. Defaults

### config.yaml
```yaml
# Media directory
media_directory: "./media"

# Image display duration (seconds)
default_image_duration: 5.0

# MPV settings (null = auto-detect)
video_output: null          # gpu, drm, x11, wayland
hardware_decode: "auto"     # auto, yes, no, vaapi, nvdec

# Display settings
fullscreen: true
test_mode: false

# Directory watching
watch_directory: true

# Logging
log_level: "INFO"
```

### Environment Variables

Prefix all config keys with `SIGNAGE_`:
```bash
export SIGNAGE_MEDIA_DIRECTORY="/home/pi/media"
export SIGNAGE_IMAGE_DURATION="10.0"
export SIGNAGE_FULLSCREEN="true"
export SIGNAGE_TEST_MODE="false"
export SIGNAGE_LOG_LEVEL="DEBUG"
```

## Raspberry Pi Deployment

### Automatic Setup with UV
```bash
# On the Pi
just pi-setup

# Install as systemd service
just install-service
sudo systemctl start signage
```

### Manual Setup
```bash
# Install uv and dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Update system
sudo apt-get update
sudo apt-get install mpv

# Clone and setup
git clone <repository-url> ~/bramble
cd ~/bramble
uv sync

# Create systemd service
sudo tee /etc/systemd/system/signage.service > /dev/null << 'EOF'
[Unit]
Description=Digital Signage System
After=graphical-session.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bramble
ExecStart=/home/pi/.local/bin/uv run python main.py
Restart=always
RestartSec=5
Environment=DISPLAY=:0
Environment="PATH=/home/pi/.cargo/bin:/home/pi/.local/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=graphical-session.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable signage.service
sudo systemctl start signage.service
```

### Remote Deployment
```bash
# Deploy to Pi over SSH
just deploy-pi pi@192.168.1.100

# Check service status
ssh pi@192.168.1.100 'sudo systemctl status signage'

# View logs
ssh pi@192.168.1.100 'journalctl -u signage.service -f'
```

## Supported Media Formats

**Images**: JPG, JPEG, PNG, GIF, BMP, TIFF, WebP, SVG
**Videos**: MP4, AVI, MKV, MOV, WMV, FLV, WebM, M4V, MPG, MPEG

Files are sorted alphabetically and looped continuously.

## Platform-Specific Settings

The system auto-detects the platform and configures MPV accordingly:

**macOS/Linux Desktop**: `--vo=gpu --hwdec=auto`
**Raspberry Pi**: `--vo=drm --hwdec=auto --no-config`

## Development

### Setup Development Environment
```bash
# Install with dev dependencies using uv
uv sync --all-extras

# Or with just
just dev

# Run checks
just lint       # Ruff linting
just typecheck  # MyPy type checking
just test       # Pytest
just check      # All checks
```

### Working with UV

```bash
# Add a new dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Update all dependencies
uv sync --upgrade

# Show dependency tree
uv tree

# Build the package
uv build

# Create a lock file
uv lock
```

### Project Structure
```
bramble/
├── src/signage/
│   ├── __init__.py       # Package initialization
│   ├── player.py         # MPV IPC controller
│   ├── scheduler.py      # Playlist and timing management
│   ├── config.py         # Configuration handling
│   └── cli.py            # CLI interface
├── main.py              # Entry point
├── config.yaml          # Default configuration
├── pyproject.toml       # Project metadata and dependencies
├── uv.lock              # Locked dependencies
├── justfile             # Task runner commands
└── README.md            # This file
```

## Troubleshooting

### MPV Not Found
```
Error: MPV is not installed!
```
Install MPV using your system's package manager (see Prerequisites).

### UV Not Found
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### Permission Issues on Pi
```bash
# Add user to video group
sudo usermod -a -G video pi

# Check DRM permissions
ls -la /dev/dri/
```

### Socket Connection Failed
Check that:
1. MPV started successfully
2. No other instances are running
3. Temp directory is writable

### Service Won't Start
```bash
# Check service status
sudo systemctl status signage.service

# View detailed logs
journalctl -u signage.service -f

# Check MPV on Pi
sudo -u pi mpv --vo=drm --version

# Check uv installation
which uv
uv --version
```

## Why UV?

This project uses `uv` for several advantages:
- **Speed**: 10-100x faster than pip for dependency resolution
- **Reliability**: Deterministic installs with lock files
- **Simplicity**: Single tool for virtual environments and dependencies
- **Compatibility**: Works seamlessly with standard Python packaging
- **Modern**: Built with Rust for performance and reliability

## License

MIT License - see LICENSE file for details.