# 🦆 DuckBricks

**A self-hosted data platform built on DuckLake and DuckDB**

DuckBricks is a lightweight, self-hosted data platform that provides Databricks-like functionality using [DuckLake](https://ducklake.select/) as its table format and [DuckDB](https://duckdb.org/) as its query engine. It ships a web UI for browsing the catalog, authoring SQL, orchestrating jobs, and managing a notebook-driven workspace.

## Features

- **Metastore Explorer** — Browse the catalog (catalog → schema → table) and inspect table schemas.
- **Query Editor** — Write and run SQL with CodeMirror syntax highlighting and schema-aware autocompletion.
- **Jobs** — Schedule and run queries and workflows via [Prefect](https://docs.prefect.io/).
- **Workspace** — File tree, [Marimo](https://marimo.io/) notebooks, and Git integration for versioned data work.
- **Settings** — Configure storage backend and connection settings.

## Tech Stack

- **UI:** [NiceGUI](https://nicegui.io/) 2.x (Quasar 2 + Vue)
- **Query Engine:** [DuckDB](https://duckdb.org/)
- **Table Format:** [DuckLake](https://ducklake.select/)
- **Metastore + App DB:** [PostgreSQL](https://www.postgresql.org/)
- **Orchestration:** [Prefect](https://docs.prefect.io/) 3
- **Notebooks:** [Marimo](https://marimo.io/)
- **Deployment:** Docker Compose

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Run

```bash
git clone https://github.com/JacobMaldonado/duckbricks.git
cd duckbricks
cp .env.example .env   # if present; otherwise configure env vars directly
docker compose up -d
```

The web UI is available at `http://localhost:8082`.

### Services

`docker compose up -d` starts:

| Service | Purpose | Port (host) |
|---------|---------|-------------|
| `duckbricks` | NiceGUI web app | `8082` |
| `postgres` | Metastore + application database | `5432` |
| `prefect-server` | Workflow orchestration (UI proxied at `/prefect-ui`) | `4200` |
| `duckbricks-worker` | Prefect work pool worker | — |
| `marimo` | Notebook server (proxied at `/marimo`) | `2718` |

## Pages

| Route | Description |
|-------|-------------|
| `/explorer` | Metastore Explorer (catalog browser) |
| `/query` | Query Editor with SQL autocompletion |
| `/jobs` | Scheduled jobs and executions |
| `/workspace` | File tree, Marimo notebooks, Git integration |
| `/settings` | Storage and connection settings |
| `/prefect-ui` | Proxied Prefect UI |
| `/marimo` | Proxied Marimo notebook server |

## Configuration

Configuration is loaded from environment variables (or a `.env` file). See `app/config.py` for the full list.

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `DUCKBRICKS_HOST` | `0.0.0.0` | Web server host |
| `DUCKBRICKS_PORT` | `8000` | Web server port (inside the container) |
| `DUCKBRICKS_ENV` | `production` | Set to `development` to enable reload |
| `DUCKBRICKS_DATA_PATH` | `/data/parquet/` | Path for Parquet file storage |
| `DUCKBRICKS_DUCKLAKE_NAME` | `duckbricks` | Name of the DuckLake database |
| `DUCKBRICKS_STORAGE_BACKEND` | `local` | Storage backend (`local`, `s3`, `minio`, `r2`, `gcs`, `azure`) |
| `DUCKBRICKS_WORKSPACE_PATH` | `./workspace` | Workspace root for files and notebooks |
| `DATABASE_URL` | `postgresql://duckbricks:duckbricks@localhost:5432/duckbricks` | PostgreSQL connection string |
| `MARIMO_URL` | `/marimo` | Public base path for Marimo |
| `MARIMO_INTERNAL_URL` | `http://localhost:2718` | Internal Marimo server URL |
| `PREFECT_INTERNAL_URL` | `http://localhost:4200` | Internal Prefect server URL |
| `PREFECT_EXTERNAL_URL` | `http://localhost:4200` | External Prefect server URL |

## Development

```bash
poetry install
poetry run pre-commit install
poetry run pytest            # run tests
poetry run python -m app.main  # run the app locally
```

## Architecture

For system design, component responsibilities, and data flow, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). For UI styling conventions, see [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md).

## License

MIT License — see [LICENSE](LICENSE) for details.
