# Visual Workflow Editor

[English](README.md) | [中文](README_zh.md) | [日本語](README_ja.md)

This is a Docker containerized visual workflow editor project that supports cross-platform development and CI/CD deployment.

## Project Description

This project includes:

- Backend service based on FastAPI
- Frontend application based on React
- SQLite database storage

## Development Environment Requirements

- Docker and Docker Compose
- Visual Studio Code (recommended, supports Dev Container)
- Git

No need to install Python, Node.js or any other dependencies, everything runs in Docker containers.

## Development with Dev Container (Recommended)

### 1. Install Necessary Tools

- Install [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Install [Visual Studio Code](https://code.visualstudio.com/)
- Install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension in VSCode

### 2. Clone the Project and Start the Development Container

```bash
git clone https://github.com/your-username/visual_workflow_editor.git
cd visual_workflow_editor
```

Open the project folder in VSCode. When prompted with "Devcontainer configuration detected", click "Reopen in Container". Alternatively, use the command palette (F1) and select "Dev Containers: Open Folder in Container".

When starting for the first time, the Dev Container will automatically build the development environment, install all dependencies, and prepare the frontend and backend services.

### 3. Access the Application

Once the container is running:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Development with Scripts (Alternative Method)

If you're not using VS Code Dev Container, you can also use the scripts provided in the project:

```bash
# Start the development environment
./scripts/dev.sh

# Rebuild containers (when dependencies are updated)
./scripts/rebuild.sh

# Check service status
./scripts/check-status.sh
```

## Project Structure

```
visual_workflow_editor/
├── .devcontainer/       # Dev Container configuration
├── .github/workflows/   # GitHub Actions CI/CD configuration
├── backend/             # Python backend
│   ├── app/             # Application code
│   └── Dockerfile       # Backend Docker configuration
├── config/              # Configuration files directory
│   └── global_variables.json # Global variables configuration
├── deployment/          # Deployment-related configuration
├── dev_docs/            # Development documentation
├── frontend/            # React frontend
│   ├── src/             # Source code
│   └── Dockerfile       # Frontend Docker configuration
├── logs/                # Application logs
├── scripts/             # Development scripts
├── CHANGELOG.md         # Version update log
└── README.md            # Project description
```

## Development Workflow

1. **Using the Terminal**

   ```bash
   # Open terminal in container
   # If using VS Code Dev Container, use the VS Code terminal directly
   ```

2. **Starting Services**

   ```bash
   # In the development container, frontend and backend services start automatically
   # To start manually:
   cd /workspace/frontend && npm start
   cd /workspace/backend && python run_backend.py
   ```

3. **Viewing Logs**

   ```bash
   # Frontend logs
   tail -f /workspace/logs/frontend.log

   # Backend logs
   tail -f /workspace/logs/backend.log
   ```

## CI/CD Deployment

This project has GitHub Actions workflows configured, which automatically:

1. Build and test code
2. Push Docker images to GitHub Container Registry
3. Deploy frontend to GitHub Pages (if applicable)

when pushed to the main or master branch.

## Configuration

- Backend configuration is in the `backend/.env` file
- Global variables are stored in `config/global_variables.json`
- The database uses SQLite, located at `config/flow_editor.db`

## Version Management

The project uses semantic versioning, with the format: `MAJOR.MINOR.PATCH`

- MAJOR: Incremented when making incompatible API changes
- MINOR: Incremented when adding backwards-compatible functionality
- PATCH: Incremented when making backwards-compatible bug fixes

### Version Update Tool

The project provides a version update script that can automatically update the version number, create Git tags, and update the changelog:

```bash
# Update patch version
./scripts/update-version.sh

# Update minor version
./scripts/update-version.sh minor "Add new feature"

# Update major version
./scripts/update-version.sh major "Major update"
```

### Version History

See [CHANGELOG.md](CHANGELOG.md) for complete version history and change notes.
