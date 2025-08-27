# Justfile for digital signage project

# Default recipe lists all available commands
default:
    @just --list

# Build the package
build:
    @uv build && echo "✓ Package built"

# Run all checks (lint, typecheck, test)
check: lint typecheck test

# Check if MPV is installed
check-mpv:
    @which mpv > /dev/null && echo "✓ MPV is installed" || echo "✗ MPV not found - install with: brew install mpv"

# Clean up build artifacts
clean:
    @rm -rf build/ dist/ *.egg-info/ && find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && find . -type f -name "*.pyc" -delete

# Create a simple demo with sample media
demo:
    #!/bin/bash
    mkdir -p media
    echo "Creating demo content..."
    if command -v convert &> /dev/null; then
        convert -size 1920x1080 xc:blue -pointsize 72 -fill white -gravity center -annotate 0 "Demo Slide 1" media/demo1.png
        convert -size 1920x1080 xc:red -pointsize 72 -fill white -gravity center -annotate 0 "Demo Slide 2" media/demo2.png
        convert -size 1920x1080 xc:green -pointsize 72 -fill white -gravity center -annotate 0 "Demo Slide 3" media/demo3.png
        echo "✓ Created demo images in media/ directory"
    else
        echo "Install ImageMagick to create demo content: brew install imagemagick"
        echo "Or manually add images/videos to the media/ directory"
    fi

# Deploy to Raspberry Pi (requires SSH access)
deploy-pi host:
    #!/bin/bash
    echo "Deploying to Raspberry Pi at {{host}}..."
    rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' . {{host}}:~/bramble/
    ssh {{host}} "cd ~/bramble && source \$HOME/.cargo/env && uv sync"
    echo "✓ Deployed to {{host}}"

# Show dependency tree
deps:
    @uv tree

# Create virtual environment and install in development mode
dev:
    @uv sync --all-extras && echo "✓ Development environment ready"

# Format code
format:
    @uv run ruff format src/

# Initialize uv project and sync dependencies
init:
    @uv sync && echo "✓ Project initialized with uv"

# Install dependencies using uv
install:
    @uv sync

# Install the package globally with uv tool
install-global:
    @uv tool install . && echo "✓ Installed globally as 'bramble' command"

# Install and enable systemd service (Pi only)
install-service:
    #!/bin/bash
    echo "Installing systemd service..."
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
    sudo systemctl daemon-reload
    sudo systemctl enable signage.service
    echo "✓ Service installed. Start with: sudo systemctl start signage"

# Run linting
lint:
    @uv run ruff check src/ --fix

# List media files
list-media:
    @uv run python main.py list

# View service logs
logs:
    @journalctl -u signage.service -f

# Skip to next media
next:
    @uv run python main.py next

# Setup for Raspberry Pi (update system and install MPV)
pi-setup:
    #!/bin/bash
    echo "Setting up Raspberry Pi..."
    sudo apt-get update
    sudo apt-get install -y mpv python3-pip curl
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
    uv sync
    echo "✓ Raspberry Pi setup complete"

# Skip to previous media
prev:
    @uv run python main.py prev

# Refresh playlist
refresh:
    @uv run python main.py refresh

# Remove a media file
remove-media name:
    @uv run python main.py remove {{name}}

# Run the signage system
run *args:
    @uv run python main.py {{args}}

# Start systemd service
service-start:
    @sudo systemctl start signage.service

# Show systemd service status
service-status:
    @sudo systemctl status signage.service

# Stop systemd service
service-stop:
    @sudo systemctl stop signage.service

# Create media directory with sample files
setup-media:
    @mkdir -p media && echo "Created media directory. Add your images and videos there."

# Show configuration
show-config:
    @uv run python main.py config-show

# Show current status
status:
    @uv run python main.py status

# Run tests
test:
    @uv run pytest tests/ -v

# Run in test mode (windowed)
test-run *args:
    @uv run python main.py --test-mode {{args}}

# Run type checking
typecheck:
    @uv run mypy src/

# Uninstall global installation
uninstall-global:
    @uv tool uninstall bramble && echo "✓ Uninstalled global command"

# Update all dependencies to latest versions
update:
    @uv sync --upgrade && echo "✓ Dependencies updated"