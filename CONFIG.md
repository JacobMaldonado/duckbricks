# DuckBricks Configuration

## Default Data Directory

DuckBricks stores all data in a user-writable directory by default:

**Default location:** `~/.duckbricks/data/`

This includes:
- `metastore.ducklake` — Catalog metadata
- `parquet/` — Data files for tables
- `<catalog_name>.ducklake` — Additional catalog metadata files

## Environment Variables

You can customize the data location using environment variables:

```bash
# Catalog metadata file location
export DUCKBRICKS_CATALOG_PATH="/path/to/metastore.ducklake"

# Data files directory
export DUCKBRICKS_DATA_PATH="/path/to/parquet/"

# Default catalog name
export DUCKBRICKS_DUCKLAKE_NAME="duckbricks"

# Server configuration
export DUCKBRICKS_HOST="0.0.0.0"
export DUCKBRICKS_PORT="8000"
```

## Docker / Production Setup

For Docker or production deployments, mount a volume and set environment variables:

```yaml
services:
  duckbricks:
    image: duckbricks:latest
    volumes:
      - duckbricks-data:/data
    environment:
      - DUCKBRICKS_CATALOG_PATH=/data/metastore.ducklake
      - DUCKBRICKS_DATA_PATH=/data/parquet/
```

## Permissions

The default `~/.duckbricks/data/` directory is automatically created with user permissions. No root access or special permissions needed for local development.

For shared/production deployments using custom paths, ensure the DuckBricks process has:
- **Read/write access** to the catalog path directory
- **Read/write access** to the data path directory

## Verification

On startup, DuckBricks logs the active configuration:

```
📁 DuckBricks data directory: /home/user/.duckbricks/data
   Catalog: /home/user/.duckbricks/data/metastore.ducklake
   Data: /home/user/.duckbricks/data/parquet/
```

Check the console output to verify your configuration is correct.
