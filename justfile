# Justfile for digital signage project
# Note: uv (Python package manager) is installed via Rust's cargo toolchain,
# hence the ~/.cargo/bin PATH references throughout the Pi deployment targets

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
    
    # Update dependencies (uv installed via rust toolchain)
    ssh {{host}} "cd ~/bramble && export PATH=\$HOME/.cargo/bin:\$PATH && uv sync"
    
    # Restart service if it was installed
    ssh {{host}} "sudo systemctl is-enabled --quiet signage.service && sudo systemctl start signage.service || true"
    
    echo "✓ Deployed to {{host}}"


# Create virtual environment and install in development mode
dev:
    @uv sync --all-extras && echo "✓ Development environment ready"

# Install the package globally with uv tool
install:
    @uv tool install . && echo "✓ Installed globally as 'bramble' command"




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
pi-start host:
    @ssh {{host}} "sudo systemctl start signage.service" && echo "✓ Service started on {{host}}"

pi-stop host:
    @ssh {{host}} "sudo systemctl stop signage.service" && echo "✓ Service stopped on {{host}}"

pi-status host:
    @ssh {{host}} "sudo systemctl status signage.service"

pi-logs host:
    @ssh {{host}} "journalctl -u signage.service -f"

# Complete Pi deployment (setup + deploy + install service)
pi host:
    #!/bin/bash
    echo "🍇 Starting complete Raspberry Pi deployment to {{host}}..."
    
    # Setup Pi (install dependencies)
    echo "📦 Setting up Raspberry Pi dependencies..."
    ssh {{host}} "sudo apt-get update && sudo apt-get install -y mpv python3-pip curl"
    
    # Install uv and ensure it's in PATH
    echo "📦 Installing uv package manager..."
    ssh {{host}} "curl -LsSf https://astral.sh/uv/install.sh | sh"
    ssh {{host}} "echo 'export PATH=\$HOME/.cargo/bin:\$PATH' >> ~/.bashrc"
    
    # Verify uv installation
    ssh {{host}} "export PATH=\$HOME/.cargo/bin:\$PATH && uv --version" || {
        echo "❌ Failed to install uv"
        exit 1
    }
    
    ssh {{host}} "mkdir -p ~/bramble"
    echo "✓ Pi setup complete"
    
    # Deploy code
    echo "🚀 Deploying bramble to {{host}}..."
    @just pi-deploy {{host}}
    
    # Install systemd service
    echo "⚙️ Installing systemd service..."
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
    echo "✓ Service installed and enabled"
    
    echo "🎉 Complete deployment to {{host}} finished! Use 'just pi-service-start {{host}}' to start."

# Connect to Pi and run signage in test mode for debugging  
pi-debug host:
    @ssh {{host}} "cd ~/bramble && export PATH=\$HOME/.cargo/bin:\$PATH && uv run python main.py --test-mode --verbose"

# Install or repair uv on Raspberry Pi
pi-fix-uv host:
    #!/bin/bash
    echo "🔧 Installing/repairing uv on {{host}}..."
    
    # Install uv
    ssh {{host}} "curl -LsSf https://astral.sh/uv/install.sh | sh"
    
    # Add to PATH in bashrc if not already there
    ssh {{host}} "grep -q '.cargo/bin' ~/.bashrc || echo 'export PATH=\$HOME/.cargo/bin:\$PATH' >> ~/.bashrc"
    
    # Verify installation
    if ssh {{host}} "export PATH=\$HOME/.cargo/bin:\$PATH && uv --version"; then
        echo "✓ uv is working on {{host}}"
    else
        echo "❌ Failed to install uv on {{host}}"
        echo "Try manual installation:"
        echo "  1. SSH into the Pi: just ssh {{host}}"
        echo "  2. Run: curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo "  3. Run: source \$HOME/.cargo/env"
        exit 1
    fi

# SSH into Raspberry Pi
ssh host:
    @ssh {{host}}

