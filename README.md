# 🧱 DuckBricks

**Open-source data platform built on DuckLake**

DuckBricks is a lightweight, self-hosted data platform that uses [DuckLake](https://ducklake.select/) as its storage layer and [DuckDB](https://duckdb.org/) as its query engine. Deploy it with Docker Compose and start querying in minutes.

## Features

- **Metastore Management** — Initialize and manage your DuckLake metastore
- **Query Engine** — Run SQL queries against DuckLake via a REST API
- **Table Catalog** — Browse tables, schemas, and row counts

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Run

```bash
git clone https://github.com/JacobMaldonado/duckbricks.git
cd duckbricks
docker compose up -d
```

The API will be available at `http://localhost:8000`.

### Initialize the Metastore

```bash
curl -X POST http://localhost:8000/api/metastore/init
```

### Create a Table

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "CREATE TABLE users (id INTEGER, name VARCHAR, email VARCHAR)"}'
```

### Insert Data

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "INSERT INTO users VALUES (1, '\''Alice'\'', '\''alice@example.com'\''), (2, '\''Bob'\'', '\''bob@example.com'\'')"}'
```

### Query Data

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM users"}'
```

### List Tables

```bash
curl http://localhost:8000/api/tables
```

### Get Table Details

```bash
curl http://localhost:8000/api/tables/users
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/metastore/init` | Initialize the DuckLake metastore |
| `GET` | `/api/metastore/status` | Check metastore status |
| `POST` | `/api/query` | Execute a SQL query |
| `GET` | `/api/tables` | List all tables |
| `GET` | `/api/tables/{name}` | Get table details |

### Query Request

```json
{
  "sql": "SELECT * FROM my_table"
}
```

### Query Response

```json
{
  "success": true,
  "columns": ["id", "name", "email"],
  "rows": [[1, "Alice", "alice@example.com"], [2, "Bob", "bob@example.com"]],
  "row_count": 2
}
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DUCKBRICKS_CATALOG_PATH` | `/data/metastore.ducklake` | Path to the DuckLake catalog file |
| `DUCKBRICKS_DATA_PATH` | `/data/parquet/` | Path for Parquet file storage |
| `DUCKBRICKS_DUCKLAKE_NAME` | `duckbricks` | Name of the DuckLake database |
| `DUCKBRICKS_HOST` | `0.0.0.0` | API server host |
| `DUCKBRICKS_PORT` | `8000` | API server port |

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   REST API   │────▶│    DuckDB    │────▶│     DuckLake     │
│  (FastAPI)   │     │  (Engine)    │     │  (Catalog + Data)│
└──────────────┘     └──────────────┘     └──────────────────┘
                                                   │
                                          ┌────────┴────────┐
                                          │                 │
                                    ┌─────┴─────┐   ┌──────┴──────┐
                                    │  Catalog   │   │   Parquet   │
                                    │ (.ducklake)│   │   Files     │
                                    └───────────┘   └─────────────┘
```

## Tech Stack

- **API Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Query Engine:** [DuckDB](https://duckdb.org/)
- **Storage Layer:** [DuckLake](https://ducklake.select/)
- **Deployment:** Docker Compose

## License

MIT License — see [LICENSE](LICENSE) for details.
