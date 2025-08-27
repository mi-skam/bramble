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
pi-deploy host:
    #!/bin/bash
    echo "Deploying to Raspberry Pi at {{host}}..."
    
    # Stop service if running
    ssh {{host}} "sudo systemctl is-active --quiet signage.service && sudo systemctl stop signage.service || true"
    
    # Deploy files (exclude media directory to preserve existing media)
    rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' --exclude='media/' . {{host}}:~/bramble/
    
    # Update dependencies
    ssh {{host}} "cd ~/bramble && source \$HOME/.cargo/env && uv sync"
    
    # Restart service if it was installed
    ssh {{host}} "sudo systemctl is-enabled --quiet signage.service && sudo systemctl start signage.service || true"
    
    echo "✓ Deployed to {{host}}"


# Create virtual environment and install in development mode
dev:
    @uv sync --all-extras && echo "✓ Development environment ready"

# Install the package globally with uv tool
install:
    @uv tool install . && echo "✓ Installed globally as 'bramble' command"

# Install and enable systemd service (Pi only)
pi-install-service host:
    #!/bin/bash
    echo "Installing systemd service on {{host}}..."
    ssh {{host}} 'printf "%s\n" \
        "[Unit]" \
        "Description=Digital Signage System" \
        "After=graphical-session.target" \
        "" \
        "[Service]" \
        "Type=simple" \
        "User=pi" \
        "WorkingDirectory=/home/pi/bramble" \
        "ExecStart=/home/pi/.local/bin/uv run python main.py" \
        "Restart=always" \
        "RestartSec=5" \
        "Environment=DISPLAY=:0" \
        "Environment=PATH=/home/pi/.cargo/bin:/home/pi/.local/bin:/usr/local/bin:/usr/bin:/bin" \
        "" \
        "[Install]" \
        "WantedBy=graphical-session.target" \
        | sudo tee /etc/systemd/system/signage.service > /dev/null'
    ssh {{host}} "sudo systemctl daemon-reload && sudo systemctl enable signage.service"
    echo "✓ Service installed on {{host}}. Start with: just pi-service-start {{host}}"



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

# Raspberry Pi service management
pi-service-start host:
    @ssh {{host}} "sudo systemctl start signage.service" && echo "✓ Service started on {{host}}"

pi-service-stop host:
    @ssh {{host}} "sudo systemctl stop signage.service" && echo "✓ Service stopped on {{host}}"

pi-service-status host:
    @ssh {{host}} "sudo systemctl status signage.service"

pi-service-logs host:
    @ssh {{host}} "journalctl -u signage.service -f"

# Complete Pi deployment (setup + deploy + install service)
pi host:
    #!/bin/bash
    echo "🍇 Starting complete Raspberry Pi deployment to {{host}}..."
    
    # Setup Pi (install dependencies)
    echo "📦 Setting up Raspberry Pi dependencies..."
    ssh {{host}} "sudo apt-get update && sudo apt-get install -y mpv python3-pip curl"
    ssh {{host}} "curl -LsSf https://astral.sh/uv/install.sh | sh"
    ssh {{host}} "mkdir -p ~/bramble"
    echo "✓ Pi setup complete"
    
    # Deploy code
    echo "🚀 Deploying bramble to {{host}}..."
    @just pi-deploy {{host}}
    
    # Install service
    echo "⚙️ Installing systemd service..."
    @just pi-install-service {{host}}
    
    echo "🎉 Complete deployment to {{host}} finished!"

# Connect to Pi and run signage in test mode for debugging  
pi-debug host:
    @ssh {{host}} "cd ~/bramble && source ~/.cargo/env && uv run python main.py --test-mode --verbose"

