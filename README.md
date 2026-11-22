# doc-insight

AI-powered web app that analyses uploaded PDF documents (text and images) and generates key details for each document plus a consolidated summary report across all of them.

## Run

### Prerequisites

Docker with Docker Compose, from either of these:

- **[Docker Desktop](https://docs.docker.com/get-started/get-docker/)**: install it, then open the app so the engine is running. Compose is included.
- **[Colima](https://github.com/abiosoft/colima)** (macOS, free and open source):

  ```bash
  brew install colima docker docker-compose
  mkdir -p ~/.docker
  ```

  Add this to `~/.docker/config.json` so Docker finds the Compose plugin (on Intel Macs, use `/usr/local` instead of `/opt/homebrew`):

  ```json
  "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]
  ```

  Then start the engine with `colima start`. Run it again after a reboot.

Check with `docker compose version`.

Copy the example environment file:

```bash
cp .env.example .env
```

### Start

```bash
docker compose up -d
```

- App: <http://localhost:8080>
- API: <http://localhost:8000> (also served by the app under `/api`)

Stop it with `docker compose down`. For local development without Docker, see [CONTRIBUTING](CONTRIBUTING.md).
