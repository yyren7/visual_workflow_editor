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
git clone https://github.com/your-username/visual_workflow_editor.git # Replace with your repository URL
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
# Start the development environment (includes building/rebuilding containers)
./start-dev.sh

# Rebuild containers explicitly (if needed, e.g., Dockerfile changes)
./scripts/rebuild-container.sh

# Check service status
./scripts/check-status.sh
```

## Project Structure

```
visual_workflow_editor/
├── .devcontainer/       # Dev Container configuration
├── .github/workflows/   # GitHub Actions CI/CD configuration
├── backend/             # Python backend (FastAPI)
│   ├── app/             # Application code
│   ├── langchainchat/   # Langchain chat specific code
│   ├── config/          # Backend specific configurations (if any)
│   ├── tests/           # Backend tests
│   ├── scripts/         # Backend specific scripts (if any)
│   ├── requirements.txt # Python dependencies
│   ├── run_backend.py   # Backend start script
│   └── Dockerfile       # Backend Docker configuration
├── database/            # Database files
│   └── flow_editor.db   # SQLite database file
├── frontend/            # React frontend
│   ├── public/          # Public assets
│   ├── src/             # Source code
│   ├── package.json     # Node.js dependencies
│   ├── tsconfig.json    # TypeScript configuration
│   ├── craco.config.js  # Craco configuration override
│   └── Dockerfile       # Frontend Docker configuration
├── logs/                # Application logs
├── scripts/             # General development scripts
│   ├── check-status.sh
│   ├── dev.sh           # (May be legacy or helper script)
│   ├── local-start.sh   # (May be legacy or helper script)
│   ├── post-create-fixed.sh # Dev container setup script
│   ├── rebuild-container.sh
│   ├── rebuild.sh       # (May be legacy or helper script)
│   └── update-version.sh # Version update script
├── .env                 # Environment variables (API Keys, DB path, etc.) - **DO NOT COMMIT SENSITIVE DATA**
├── .gitignore           # Git ignore configuration
├── start-dev.sh         # Main script to start development environment
├── CHANGELOG.md         # Version update log
├── README.md            # Project description (English)
├── README_ja.md         # Project description (Japanese)
└── README_zh.md         # Project description (Chinese)
```

## Development Workflow

1. **Using the Terminal**

   ```bash
   # Open terminal in container
   # If using VS Code Dev Container, use the VS Code terminal directly
   ```

2. **Starting Services (Inside Dev Container)**

   ```bash
   # In the development container, frontend and backend services start automatically via supervisord (check .devcontainer/devcontainer.json and scripts/post-create-fixed.sh)
   # To start manually (if needed for debugging):
   cd /workspace/frontend && npm start
   cd /workspace/backend && python run_backend.py
   ```

3. **Viewing Logs**

   ```bash
   # Inside the container:
   # Check supervisord logs first (configured in .devcontainer/supervisor/supervisord.conf)
   tail -f /var/log/supervisor/frontend-stdout.log
   tail -f /var/log/supervisor/frontend-stderr.log
   tail -f /var/log/supervisor/backend-stdout.log
   tail -f /var/log/supervisor/backend-stderr.log

   # Application specific logs (if configured):
   tail -f /workspace/logs/frontend.log
   tail -f /workspace/logs/backend.log
   ```

## CI/CD Deployment

This project has GitHub Actions workflows configured, which automatically:

1. Build and test code
2. Push Docker images to GitHub Container Registry
3. Deploy frontend to GitHub Pages (if applicable)

when pushed to the main or master branch.

## Configuration

- **Environment Variables**: Main configuration is managed via the `.env` file in the project root. Create this file from `example.env` if it doesn't exist. It includes:
  - `DATABASE_URL`: Path to the SQLite database (default: `sqlite:////workspace/database/flow_editor.db`).
  - `SECRET_KEY`: Secret key for the backend application.
  - API Keys: `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `EMBEDDING_LMSTUDIO_API_KEY` (and related settings). Fill these in if you intend to use the respective services.
  - `CORS_ORIGINS`: Allowed origins for Cross-Origin Resource Sharing.
- **Database**: Uses SQLite, the database file is located at `database/flow_editor.db` by default (path configured in `.env`).

**Important**: Ensure the `.env` file is added to your `.gitignore` to avoid committing sensitive API keys.

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
