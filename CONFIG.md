# DuckBricks Configuration

## Environment Variables

DuckBricks can be configured using environment variables. All configuration is optional — sensible defaults are provided.

### Data Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `DUCKBRICKS_CATALOG_PATH` | `~/.duckbricks/data/metastore.ducklake` | Path to the DuckLake metastore catalog file |
| `DUCKBRICKS_DATA_PATH` | `~/.duckbricks/data/parquet` | Path to the directory where Parquet data files are stored |
| `DUCKBRICKS_DUCKLAKE_NAME` | `duckbricks` | Name of the DuckLake catalog |

### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `DUCKBRICKS_HOST` | `0.0.0.0` | Host address to bind the web server |
| `DUCKBRICKS_PORT` | `8000` | Port number for the web server |

## Default Behavior

By default, DuckBricks stores all data in `~/.duckbricks/data/`:
- **Catalog metadata:** `~/.duckbricks/data/metastore.ducklake`
- **Parquet data files:** `~/.duckbricks/data/parquet/`

The data directory is automatically created with user permissions on first run — no sudo or root access required.

## Custom Configuration Example

To use a custom data location, set environment variables before starting DuckBricks:

```bash
export DUCKBRICKS_CATALOG_PATH="/mnt/data/prod/metastore.ducklake"
export DUCKBRICKS_DATA_PATH="/mnt/data/prod/parquet"
python3 -m app.main
```

## Docker / Production Deployment

For production or containerized deployments, mount a persistent volume and set the paths:

```bash
docker run -v /host/data:/data \
  -e DUCKBRICKS_CATALOG_PATH=/data/metastore.ducklake \
  -e DUCKBRICKS_DATA_PATH=/data/parquet \
  -p 8000:8000 \
  duckbricks
```

## Verifying Configuration

On startup, DuckBricks logs the active data directory location:

```
📁 DuckBricks data directory: /home/user/.duckbricks/data
   Catalog: /home/user/.duckbricks/data/metastore.ducklake
   Data path: /home/user/.duckbricks/data/parquet/
```

Check the logs to confirm your configuration is loaded correctly.
