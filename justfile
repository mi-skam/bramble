# Justfile for digital signage project

# Default recipe lists all available commands
default:
    @just --list

# Build the package
build:
    @uv build && echo "✓ Package built"

# Run all checks (lint, typecheck, test)
check:
    @uv run mypy src/
    @uv run ruff check src/ --fix
    @uv run ruff format src/
    @just test
    echo "✓ All checks passed"

# Clean up build artifacts
clean:
    @rm -rf build/ dist/ *.egg-info/ && find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && find . -type f -name "*.pyc" -delete

# Deploy to Raspberry Pi (requires SSH access)
deploy-pi host:
    #!/bin/bash
    echo "Deploying to Raspberry Pi at {{host}}..."
    rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' . {{host}}:~/bramble/
    ssh {{host}} "cd ~/bramble && source \$HOME/.cargo/env && uv sync"
    echo "✓ Deployed to {{host}}"


# Create virtual environment and install in development mode
dev:
    @uv sync --all-extras && echo "✓ Development environment ready"

# Install the package globally with uv tool
install:
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

# Run the signage system
run *args:
    @uv run python main.py {{args}}


# Show configuration
show-config:
    @uv run python main.py config-show


# Run tests
test:
    @uv run pytest tests/ -v


# Update all dependencies to latest versions
update:
    @uv sync --upgrade && echo "✓ Dependencies updated"