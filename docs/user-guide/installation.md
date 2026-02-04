# Installation

This guide covers different methods to install AI Issue Agent.

## Installation Methods

=== "pip (Recommended)"
    Install from PyPI (once published):
    
    ```bash
    pip install ai-issue-agent
    ```

=== "pipx (Isolated)"
    Install in an isolated environment:
    
    ```bash
    pipx install ai-issue-agent
    ```

=== "From Source"
    Install from the GitHub repository:
    
    ```bash
    git clone https://github.com/jtdub/ai-issue-agent.git
    cd ai-issue-agent
    pip install -e .
    ```

=== "Docker"
    Run using Docker:
    
    ```bash
    docker pull ghcr.io/jtdub/ai-issue-agent:latest
    docker run -v $(pwd)/config.yaml:/app/config.yaml \
               --env-file .env \
               ghcr.io/jtdub/ai-issue-agent:latest
    ```

## Verify Installation

Check that the installation was successful:

```bash
ai-issue-agent --version
```

Expected output:
```
ai-issue-agent version 0.1.0
```

## Install Dependencies for Development

If you're planning to contribute or modify the code:

```bash
# Clone the repository
git clone https://github.com/jtdub/ai-issue-agent.git
cd ai-issue-agent

# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install with development dependencies
poetry install --with dev

# Install pre-commit hooks
poetry run pre-commit install

# Run tests to verify setup
poetry run pytest
```

## Platform-Specific Instructions

### macOS

Using Homebrew:

```bash
brew install python@3.11
pip3.11 install ai-issue-agent
```

### Linux

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
pip3 install ai-issue-agent
```

#### RHEL/CentOS/Fedora

```bash
sudo dnf install python3.11 python3-pip
pip3 install ai-issue-agent
```

### Windows

Using PowerShell:

```powershell
# Install Python from python.org or Microsoft Store
# Then install the package
pip install ai-issue-agent
```

Or use WSL (Windows Subsystem for Linux):

```bash
wsl --install
# Follow Ubuntu instructions above
```

## Setting Up a Virtual Environment

It's recommended to use a virtual environment:

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate it
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install ai-issue-agent
pip install ai-issue-agent
```

## Installing GitHub CLI

The agent uses GitHub CLI for some operations:

=== "macOS"
    ```bash
    brew install gh
    ```

=== "Ubuntu/Debian"
    ```bash
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
        sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
        https://cli.github.com/packages stable main" | \
        sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt update
    sudo apt install gh
    ```

=== "Windows"
    ```powershell
    winget install GitHub.cli
    ```

Verify GitHub CLI installation:

```bash
gh --version
```

## Next Steps

After installation:

1. [Configure your settings](configuration.md)
2. [Set up integrations](configuration.md#integration-setup)
3. [Start using the agent](usage.md)

## Troubleshooting

### Command not found

If `ai-issue-agent` command is not found after installation:

```bash
# Add to PATH (Linux/macOS)
export PATH="$HOME/.local/bin:$PATH"

# Or use python module syntax
python -m ai_issue_agent --version
```

### Permission errors

If you encounter permission errors during installation:

```bash
# Use --user flag
pip install --user ai-issue-agent

# Or use a virtual environment (recommended)
python -m venv venv
source venv/bin/activate
pip install ai-issue-agent
```

### SSL certificate errors

If you encounter SSL errors:

```bash
# Upgrade pip and certifi
pip install --upgrade pip certifi

# Or specify trusted host (not recommended for production)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org ai-issue-agent
```

For more troubleshooting, see the [Troubleshooting Guide](troubleshooting.md).
