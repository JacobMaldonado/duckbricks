# DuckBricks Architecture

**Version:** 0.3.0
**Last Updated:** 2026-08-24
**Status:** Living Document

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Tech Stack Details](#2-tech-stack-details)
3. [Deployment Architecture](#3-deployment-architecture)
4. [Database Design](#4-database-design)
5. [Swappable Components](#5-swappable-components-critical)
6. [Data Flow](#6-data-flow)
7. [Security & Access Control](#7-security--access-control)
8. [Configuration Management](#8-configuration-management)
9. [Future Considerations](#9-future-considerations)

---

## 1. Architecture Overview

### 1.1 System Vision

DuckBricks is a self-hosted data platform that provides Databricks-like functionality using DuckDB as the query engine and DuckLake as the table format. The platform enables users to manage data catalogs, author SQL queries, orchestrate data pipelines, and analyze results through an intuitive web interface.

### 1.2 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         DuckBricks Platform                      │
│                                                                   │
│  ┌────────────┐         ┌──────────────┐      ┌──────────────┐ │
│  │  NiceGUI   │◄────────│   FastAPI    │      │   Prefect    │ │
│  │  Frontend  │         │   REST API   │      │  Orchestrator│ │
│  │  (Python)  │         │   (Python)   │      │   (Python)   │ │
│  └─────┬──────┘         └──────┬───────┘      └──────┬───────┘ │
│        │                       │                     │          │
│        │         ┌─────────────┴─────────────────────┘          │
│        │         │                                               │
│        └─────────▼──────────────────────┐                       │
│                                          │                       │
│          ┌───────────────────────────────▼─────────────┐        │
│          │       DuckBricks Service Layer              │        │
│          │  (Metastore Manager, Query Engine, Jobs)   │        │
│          └───────────┬──────────────────┬──────────────┘        │
│                      │                  │                        │
│         ┌────────────▼──────┐    ┌──────▼───────────┐          │
│         │     DuckDB        │    │   PostgreSQL     │          │
│         │  Query Engine     │    │  Metastore + App │          │
│         └────────┬──────────┘    └──────────────────┘          │
│                  │                                               │
└──────────────────┼───────────────────────────────────────────────┘
                   │
       ┌───────────▼────────────┐
       │      DuckLake          │
       │  (Open Table Format)   │
       │                        │
       │  ┌──────────────────┐  │
       │  │ Catalog Metadata │  │
       │  │  (PostgreSQL)    │  │
       │  └──────────────────┘  │
       │                        │
       │  ┌──────────────────┐  │
       │  │  Parquet Files   │  │
       │  │ (Local/MinIO/S3) │  │
       │  └──────────────────┘  │
       └────────────────────────┘
```

### 1.3 Architectural Principles

**1. Simplicity First**
Start with the simplest solution that works. Add complexity only when requirements demand it. The current implementation uses one NiceGUI application with in-process DuckDB, PostgreSQL-backed DuckLake metadata, and separate Prefect and Marimo services.

**2. Loose Coupling via Abstraction Layers**
Components communicate through well-defined interfaces, not concrete implementations. Storage, scheduling, and database backends must be swappable via dependency injection and adapter patterns.

**3. Separation of Concerns**
- **Presentation Layer:** NiceGUI (UI components)
- **API Layer:** FastAPI (REST endpoints for external integrations)
- **Service Layer:** Business logic (metastore management, query execution, job orchestration)
- **Data Layer:** DuckDB (query engine), PostgreSQL (metastore + app state), DuckLake (storage format)

**4. Progressive Enhancement**
The architecture supports incremental evolution:
- **Implemented:** NiceGUI, DuckDB, PostgreSQL-backed DuckLake, Prefect 3, Marimo workspaces, Git integration, and configurable local/cloud storage
- **Next:** Expand the FastAPI surface and add production authentication
- **Later:** Multi-tenancy, workspace isolation, RBAC, and multi-node deployment

**5. Container-First Deployment**
All components are containerized and orchestrated via Docker Compose for local/single-node deployments. The architecture must support migration to Kubernetes for production scale-out.

### 1.4 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **NiceGUI Frontend** | Web UI for catalog browsing, query authoring, and results visualization |
| **FastAPI REST API** | Programmatic access for external tools, CLI, and integrations |
| **DuckBricks Service Layer** | Metastore management, query execution, schema discovery, job scheduling |
| **DuckDB Query Engine** | SQL query execution against DuckLake tables |
| **PostgreSQL** | Persistent storage for metastore catalog and application state (users, workspaces, queries, jobs) |
| **DuckLake** | Open table format for data storage (Parquet files + catalog metadata) |
| **Prefect** | Workflow orchestration for scheduled queries, data pipelines, and ETL jobs |
| **MinIO / S3** | Object storage for DuckLake Parquet files (swappable with local filesystem) |

---

## 2. Tech Stack Details

### 2.1 NiceGUI (Frontend)

**Why NiceGUI?**
NiceGUI is a Python-based UI framework that enables rapid development of web interfaces without JavaScript. It's ideal for data tools where Python developers can build full-stack applications without context switching.

**Architecture Integration:**
- **Entry Point:** `app/main.py` defines page routes (`/explorer`, `/query`)
- **Components:** Reusable UI components in `app/ui/components/`
- **Pages:** Full-page views in `app/ui/pages/`
- **State Management:** NiceGUI's reactive state binding for UI updates
- **Layout Patterns:** Splitter-based editor views, a three-pane metastore workbench, and
  lazy-loaded tree views with `ui.tree`

**Current Implementation:**
- Metastore Workbench: catalog hierarchy, schema assets, comments, columns, previews,
  DuckLake history, and physical properties. Quality, usage, tags, and lineage intentionally
  remain unconfigured until DuckBricks has dedicated application services for them.
- Query Workspace: SQL editor with schema browser and results table

**Future Enhancements:**
- Dashboard widgets (query history, job status, data lineage)
- Workspace switcher (multi-tenancy support)
- User preferences and saved queries

### 2.2 FastAPI (REST API)

**Why FastAPI?**
FastAPI provides automatic OpenAPI documentation, data validation via Pydantic, and async support. It complements NiceGUI by exposing programmatic access to DuckBricks functionality.

**When to Use FastAPI vs. NiceGUI:**
- **NiceGUI:** Interactive UI for human users
- **FastAPI:** Programmatic access for CLI tools, CI/CD pipelines, external integrations

**Planned API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/catalogs` | GET | List all catalogs |
| `/api/catalogs/{catalog}/schemas` | GET | List schemas in a catalog |
| `/api/schemas/{catalog}.{schema}/tables` | GET | List tables in a schema |
| `/api/tables/{catalog}.{schema}.{table}` | GET | Get table metadata (schema, stats) |
| `/api/query` | POST | Execute a SQL query |
| `/api/query/{query_id}` | GET | Get query status and results |
| `/api/jobs` | GET | List scheduled jobs |
| `/api/jobs/{job_id}` | POST | Trigger a job execution |

**Integration Pattern:**
Both NiceGUI and FastAPI share the same service layer (`app/services/`). The service layer is framework-agnostic and exposes business logic through plain Python interfaces.

```python
# Shared service layer
from app.services.metastore import MetastoreService

# NiceGUI page
def explorer_page():
    service = MetastoreService()  # Dependency injection
    catalogs = service.list_catalogs()
    ...

# FastAPI endpoint
@app.get("/api/catalogs")
def list_catalogs():
    service = MetastoreService()  # Same service
    return service.list_catalogs()
```

### 2.3 DuckDB (Query Engine)

**Why DuckDB?**
DuckDB is an in-process analytical database optimized for OLAP workloads. It natively supports reading Parquet files, enabling efficient querying of DuckLake tables without data movement.

**Integration Architecture:**
- **Connection Management:** `app/services/metastore/ducklake_manager.py` provides the `MetastoreManager` used by the singleton in `app/services/metastore/__init__.py`
- **Thread Safety:** Uses Python `threading.Lock` to serialize access to the DuckDB connection
- **DuckLake Extension:** `LOAD ducklake` enables DuckLake catalog integration
- **Catalog Attachment:** `ATTACH 'ducklake:postgres:<dsn>' AS <name>` mounts the PostgreSQL-backed DuckLake catalog

**Query Execution Flow:**
1. User submits SQL query via NiceGUI or FastAPI
2. Service layer validates query and checks metastore initialization
3. `DuckLakeManager.execute_query(sql)` acquires lock and executes query via DuckDB
4. Results are fetched as Python lists and returned to caller
5. UI renders results in a table or API serializes to JSON

**Current Limitations:**
- Single in-process connection (no concurrent query execution)
- No query result caching
- Limited query observability (no query plans, execution time tracking)

**Future Enhancements:**
- Connection pooling for concurrent queries
- Query result caching (e.g., using Redis)
- Query history and execution stats stored in PostgreSQL

### 2.4 DuckLake (Open Table Format)

**Why DuckLake?**
DuckLake is an open table format built for DuckDB that provides ACID transactions, time travel, and schema evolution. It's similar to Apache Iceberg but optimized for DuckDB's architecture.

**Storage Structure:**
```
/data/
└── parquet/
    ├── catalog_name/
    │   ├── schema_name/
    │   │   ├── table_name/
    │   │   │   ├── part-00000.parquet
    │   │   │   ├── part-00001.parquet
    │   │   │   └── ...
```

**Catalog Metadata:**
- Stored in PostgreSQL through DuckLake's PostgreSQL catalog integration
- Configured independently from the application SQLAlchemy connection through `DUCKLAKE_PG_*`
- Tracks table schemas, snapshots, partitions, and data-file locations

**Parquet Files:**
- Columnar storage format optimized for analytics
- Compressed (Snappy by default)
- Stored in `DATA_PATH` (configurable via `DUCKBRICKS_DATA_PATH`)

**PostgreSQL integration:**
DuckLake metadata is stored directly in PostgreSQL and remains the source of truth. The SQLAlchemy
`metastore` models exist for future application-level metadata, but no background mirror/sync process
is currently active.

**DuckLake Operations:**
```sql
-- Attach catalog
ATTACH 'ducklake:postgres:host=postgres port=5432 dbname=duckbricks user=duckbricks password=***'
  AS duckbricks (DATA_PATH '/data/parquet/', AUTOMATIC_MIGRATION TRUE);

-- Use catalog
USE duckbricks;

-- Create table (writes metadata to .ducklake + Parquet files to DATA_PATH)
CREATE TABLE users (id INTEGER, name VARCHAR, email VARCHAR);

-- Insert data (appends Parquet files)
INSERT INTO users VALUES (1, 'Alice', 'alice@example.com');

-- Query data (reads Parquet files via catalog)
SELECT * FROM users;
```

### 2.5 PostgreSQL (Metastore & Application Database)

**Why PostgreSQL?**
PostgreSQL provides durable relational storage for both DuckLake catalog metadata and DuckBricks application state.

**Database Roles:**
1. **DuckLake catalog:** DuckLake writes its catalog tables directly through the PostgreSQL catalog adapter.
2. **Application database:** SQLAlchemy stores jobs, tasks, query tabs, Git connections, and Git-folder registrations in the `app` schema.

**Schema Design (see Section 4 for details):**
- DuckLake-managed catalog tables are the source of truth for data metadata.
- `app` schema: DuckBricks-owned application state.
- `metastore` ORM models are reserved for future application metadata; no mirror job currently writes them.

**Integration Pattern:**
- DuckDB attaches DuckLake using the `DUCKLAKE_PG_*` connection settings.
- SQLAlchemy connects using `DATABASE_URL`.
- Both connections point to the Compose PostgreSQL service by default but remain independently configurable.

**Connection Management:**
- SQLAlchemy owns the application engine and session factory.
- Startup creates the required schemas and applies the current additive migrations.
- Alembic is installed but has not yet replaced the startup migration mechanism.

### 2.6 Prefect (Workflow Orchestration)

**Why Prefect?**
Prefect provides Pythonic workflow orchestration with a modern UI, dynamic DAGs, and rich failure handling. It's ideal for scheduled queries, ETL pipelines, and data quality checks.

**Use Cases:**
- **Scheduled Queries:** Run SQL queries on a cron schedule, save results to tables
- **Data Pipelines:** Orchestrate multi-step ETL workflows (extract → transform → load)
- **Data Quality Checks:** Run validation queries and alert on failures

**Integration Architecture:**
- Prefect runs in a separate container (`prefect-server`)
- DuckBricks defines its flow in `app/services/jobs/prefect_flows.py`
- The application creates and updates Prefect deployments through `PrefectApiClient`
- The `duckbricks-worker` executes deployments from the `duckbricks-pool` work pool
- Job definitions are stored in PostgreSQL; run state and logs are read from Prefect

**Example Workflow:**
```python
from prefect import flow, task
from app.services.query import QueryService

@task
def execute_query(sql: str):
    service = QueryService()
    return service.execute(sql)

@flow
def daily_report():
    result = execute_query("SELECT COUNT(*) FROM users WHERE created_at >= CURRENT_DATE")
    # Send notification or save result
```

**Deployment:**
- Prefect server runs via Docker Compose
- Deployments are registered through the Prefect API when jobs are created or updated
- Execution is triggered through the DuckBricks UI, Prefect UI/API, or deployment schedules

---

## 3. Deployment Architecture

### 3.1 Docker Compose Overview

**Current Architecture:**
```yaml
services:
  duckbricks:
    build: .
    ports:
      - "8082:8000"
    volumes:
      - duckbricks-data:/data
    environment:
      DATABASE_URL: postgresql://duckbricks:duckbricks@postgres:5432/duckbricks
      DUCKLAKE_PG_HOST: postgres
      PREFECT_API_URL: http://prefect-server:4200/api
      PREFECT_INTERNAL_URL: http://prefect-server:4200
      MARIMO_INTERNAL_URL: http://marimo:2718
    depends_on:
      postgres:
        condition: service_healthy
      prefect-server:
        condition: service_healthy
      marimo:
        condition: service_healthy

  postgres:
    image: postgres:16-alpine

  prefect-server:
    image: prefecthq/prefect:3-latest

  duckbricks-worker:
    build: .
    command: prefect worker start --pool duckbricks-pool

  marimo:
    image: python:3.12-slim

volumes:
  postgres-data:
  prefect-data:
  duckbricks-data:
```

### 3.2 Container Strategy

| Service | Purpose | Scaling | Data Persistence |
|---------|---------|---------|------------------|
| **duckbricks** | NiceGUI + FastAPI server with an in-process DuckDB connection | Single instance | Shared `duckbricks-data` volume |
| **postgres** | DuckLake catalog + application database | Single instance | Volume: `postgres-data` |
| **prefect-server** | Workflow orchestration | Single instance | Volume: `prefect-data` |
| **duckbricks-worker** | Executes Prefect deployments | One or more workers | Shared `duckbricks-data` volume |
| **marimo** | Notebook editor/server | Single instance | Shared `duckbricks-data` volume |

### 3.3 Network Architecture

**Docker Compose Network:**
- Default bridge network for internal service communication
- Exposed ports: `8082` (web), `5432` (postgres), `4200` (Prefect)
- Marimo is reachable only through the DuckBricks `/marimo` proxy

**Port Mapping:**
- `8082` → NiceGUI UI + FastAPI routes
- `5432` → PostgreSQL (for external admin tools like pgAdmin)
- `4200` → Prefect UI

**Internal DNS:**
Services communicate via Docker Compose service names:
- `duckbricks` / `duckbricks-worker` → `postgres`
- `duckbricks` / `duckbricks-worker` → `prefect-server`
- `duckbricks` → `marimo`

### 3.4 Volume Strategy

**Persistent Volumes:**
1. **postgres-data:** PostgreSQL data directory (`/var/lib/postgresql/data`)
2. **prefect-data:** Prefect local state (`/root/.prefect`)
3. **duckbricks-data:** Workspace files and local DuckLake Parquet data

**Backup Strategy:**
- **PostgreSQL:** Use `pg_dump` for logical backups, WAL archiving for PITR
- **DuckLake:** Back up its PostgreSQL catalog and the configured Parquet/object-storage path together

**Development vs. Production:**
- **Dev:** `docker-compose.override.yml` mounts `./app:/app/app` for hot-reload
- **Prod:** Copy code into image at build time (no mounts)

### 3.5 Environment Configuration

**Configuration File:** `.env` (not committed to Git)

```bash
# Application database
DATABASE_URL=postgresql://duckbricks:duckbricks@postgres:5432/duckbricks

# PostgreSQL-backed DuckLake catalog
DUCKLAKE_PG_HOST=postgres
DUCKLAKE_PG_PORT=5432
DUCKLAKE_PG_DATABASE=duckbricks
DUCKLAKE_PG_USER=duckbricks
DUCKLAKE_PG_PASSWORD=duckbricks
DUCKBRICKS_DATA_PATH=/data/parquet/

# Storage Backend (local | minio | s3 | azure | gcs)
DUCKBRICKS_STORAGE_BACKEND=local

# Internal services
PREFECT_API_URL=http://prefect-server:4200/api
PREFECT_INTERNAL_URL=http://prefect-server:4200
PREFECT_EXTERNAL_URL=http://localhost:4200
MARIMO_INTERNAL_URL=http://marimo:2718

# Application
DUCKBRICKS_WORKSPACE_PATH=/data/workspace
DUCKBRICKS_SECRET_KEY=<generate-fernet-key>
```

**Configuration Loading:**
- `app/config.py` loads `.env`, then reads environment variables into module-level constants
- Docker Compose provides container-aware defaults while allowing `.env` overrides
- `RuntimeConfigurationValidator` fails startup for invalid URLs, ports, database settings, storage backends, or missing backend credentials
- Runtime initialization is retried three times before startup fails

### 3.6 Health and Readiness

- `GET /health/live` confirms that the web process can serve requests and has no dependency checks.
- `GET /health/ready` checks PostgreSQL, DuckLake, Prefect, and Marimo concurrently.
- Readiness returns HTTP `503` with sanitized component states when a dependency is unavailable.
- Compose uses readiness for the DuckBricks container and service-specific health checks for PostgreSQL, Prefect, and Marimo.

---

## 4. Database Design

### 4.1 PostgreSQL Schema Design

**Schema Organization:**
- `metastore` schema: DuckLake metadata mirror
- `app` schema: Application state (users, workspaces, queries, jobs)

### 4.2 Metastore Schema

**Purpose:** Mirror DuckLake catalog metadata for richer querying and workspace-based access control.

```sql
CREATE SCHEMA metastore;

-- Catalogs (top-level namespaces)
CREATE TABLE metastore.catalogs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Schemas (namespaces within catalogs)
CREATE TABLE metastore.schemas (
    id SERIAL PRIMARY KEY,
    catalog_id INTEGER NOT NULL REFERENCES metastore.catalogs(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(catalog_id, name)
);

-- Tables
CREATE TABLE metastore.tables (
    id SERIAL PRIMARY KEY,
    schema_id INTEGER NOT NULL REFERENCES metastore.schemas(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    table_type VARCHAR(50) NOT NULL CHECK (table_type IN ('table', 'view', 'external')),
    storage_format VARCHAR(50) DEFAULT 'parquet',
    location TEXT,  -- Path to Parquet files (e.g., s3://bucket/path/to/table)
    row_count BIGINT,
    size_bytes BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(schema_id, name)
);

-- Columns
CREATE TABLE metastore.columns (
    id SERIAL PRIMARY KEY,
    table_id INTEGER NOT NULL REFERENCES metastore.tables(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    is_nullable BOOLEAN DEFAULT TRUE,
    ordinal_position INTEGER NOT NULL,
    comment TEXT,
    UNIQUE(table_id, name)
);

-- Partitions (for partitioned tables)
CREATE TABLE metastore.partitions (
    id SERIAL PRIMARY KEY,
    table_id INTEGER NOT NULL REFERENCES metastore.tables(id) ON DELETE CASCADE,
    partition_spec JSONB NOT NULL,  -- e.g., {"year": 2024, "month": 3}
    location TEXT NOT NULL,
    row_count BIGINT,
    size_bytes BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast lookup
CREATE INDEX idx_schemas_catalog_id ON metastore.schemas(catalog_id);
CREATE INDEX idx_tables_schema_id ON metastore.tables(schema_id);
CREATE INDEX idx_columns_table_id ON metastore.columns(table_id);
CREATE INDEX idx_partitions_table_id ON metastore.partitions(table_id);

-- Full-text search on table and column names
CREATE INDEX idx_tables_name_gin ON metastore.tables USING gin(to_tsvector('english', name));
CREATE INDEX idx_columns_name_gin ON metastore.columns USING gin(to_tsvector('english', name));
```

### 4.3 Application Schema

**Purpose:** Store user accounts, workspaces, saved queries, job definitions, and execution logs.

```sql
CREATE SCHEMA app;

-- Users
CREATE TABLE app.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Workspaces (multi-tenancy)
CREATE TABLE app.workspaces (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_by INTEGER NOT NULL REFERENCES app.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Workspace Members
CREATE TABLE app.workspace_members (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'editor', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workspace_id, user_id)
);

-- Saved Queries
CREATE TABLE app.queries (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sql_text TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES app.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Query Execution History
CREATE TABLE app.query_executions (
    id SERIAL PRIMARY KEY,
    query_id INTEGER REFERENCES app.queries(id) ON DELETE SET NULL,
    workspace_id INTEGER NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    executed_by INTEGER NOT NULL REFERENCES app.users(id),
    sql_text TEXT NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('running', 'success', 'failed', 'cancelled')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    row_count INTEGER,
    error_message TEXT,
    result_location TEXT  -- Path to cached results (e.g., S3 path)
);

-- Jobs (scheduled queries / workflows)
CREATE TABLE app.jobs (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    job_type VARCHAR(50) NOT NULL CHECK (job_type IN ('query', 'workflow')),
    schedule_cron VARCHAR(100),  -- Cron expression (e.g., "0 0 * * *" for daily at midnight)
    is_enabled BOOLEAN DEFAULT TRUE,
    query_id INTEGER REFERENCES app.queries(id) ON DELETE SET NULL,
    workflow_definition JSONB,  -- For complex workflows
    created_by INTEGER NOT NULL REFERENCES app.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Job Execution History
CREATE TABLE app.job_executions (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES app.jobs(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL CHECK (status IN ('running', 'success', 'failed', 'cancelled')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    error_message TEXT,
    logs_location TEXT  -- Path to execution logs
);

-- Indexes
CREATE INDEX idx_workspace_members_workspace_id ON app.workspace_members(workspace_id);
CREATE INDEX idx_workspace_members_user_id ON app.workspace_members(user_id);
CREATE INDEX idx_queries_workspace_id ON app.queries(workspace_id);
CREATE INDEX idx_query_executions_workspace_id ON app.query_executions(workspace_id);
CREATE INDEX idx_query_executions_executed_by ON app.query_executions(executed_by);
CREATE INDEX idx_query_executions_started_at ON app.query_executions(started_at DESC);
CREATE INDEX idx_jobs_workspace_id ON app.jobs(workspace_id);
CREATE INDEX idx_job_executions_job_id ON app.job_executions(job_id);
CREATE INDEX idx_job_executions_started_at ON app.job_executions(started_at DESC);
```

### 4.4 Migration Strategy

**Tool:** Alembic (SQLAlchemy's migration tool)

**Workflow:**
1. Define schema changes in Alembic migration files (`migrations/versions/`)
2. Run `alembic upgrade head` to apply migrations
3. Migrations run automatically on container startup (via entrypoint script)

**Example Migration:**
```python
"""Create metastore schema

Revision ID: 001_create_metastore
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.execute("CREATE SCHEMA metastore")
    op.create_table(
        'catalogs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(255), unique=True, nullable=False),
        ...
        schema='metastore'
    )

def downgrade():
    op.drop_table('catalogs', schema='metastore')
    op.execute("DROP SCHEMA metastore")
```

### 4.5 Database Abstraction Layer

**Pattern:** Repository Pattern + Dependency Injection

**Why?**
- Decouple business logic from PostgreSQL specifics
- Enable swapping PostgreSQL for another database (e.g., MySQL, SQLite for testing)
- Simplify testing with in-memory repositories

**Architecture:**

```python
# Abstract interface
from abc import ABC, abstractmethod
from typing import List

class MetastoreRepository(ABC):
    @abstractmethod
    def list_catalogs(self) -> List[str]:
        pass

    @abstractmethod
    def list_schemas(self, catalog: str) -> List[str]:
        pass

    @abstractmethod
    def list_tables(self, catalog: str, schema: str) -> List[str]:
        pass

# PostgreSQL implementation
from sqlalchemy.orm import Session

class PostgresMetastoreRepository(MetastoreRepository):
    def __init__(self, session: Session):
        self.session = session

    def list_catalogs(self) -> List[str]:
        return [row.name for row in self.session.query(Catalog).all()]

# In-memory implementation (for tests)
class InMemoryMetastoreRepository(MetastoreRepository):
    def __init__(self):
        self.catalogs = []

    def list_catalogs(self) -> List[str]:
        return self.catalogs
```

**Dependency Injection:**

```python
# Service layer
class MetastoreService:
    def __init__(self, repo: MetastoreRepository):
        self.repo = repo

    def list_catalogs(self) -> List[str]:
        return self.repo.list_catalogs()

# FastAPI dependency
from fastapi import Depends

def get_metastore_repo() -> MetastoreRepository:
    session = get_db_session()  # SQLAlchemy session
    return PostgresMetastoreRepository(session)

@app.get("/api/catalogs")
def list_catalogs(repo: MetastoreRepository = Depends(get_metastore_repo)):
    service = MetastoreService(repo)
    return service.list_catalogs()
```

---

## 5. Swappable Components (Critical)

**Architectural Goal:**
Design for flexibility. Components that may change (storage backend, scheduler, database) must be swappable via configuration without code changes.

### 5.1 Database Backend Abstraction

**Current:** PostgreSQL
**Future Options:** MySQL, CockroachDB, SQLite (for embedded deployments)

**Strategy:** Repository Pattern + SQLAlchemy ORM

**Interface:**
```python
from abc import ABC, abstractmethod
from typing import List, Optional

class MetastoreRepository(ABC):
    @abstractmethod
    def list_catalogs(self) -> List[Catalog]: pass

    @abstractmethod
    def get_catalog(self, name: str) -> Optional[Catalog]: pass

    @abstractmethod
    def create_catalog(self, catalog: Catalog) -> Catalog: pass

class QueryRepository(ABC):
    @abstractmethod
    def list_queries(self, workspace_id: int) -> List[Query]: pass

    @abstractmethod
    def save_query(self, query: Query) -> Query: pass
```

**Configuration-Driven Selection:**
```python
# config.py
DATABASE_BACKEND = os.getenv("DATABASE_BACKEND", "postgresql")

# factory.py
def get_metastore_repo() -> MetastoreRepository:
    if DATABASE_BACKEND == "postgresql":
        return PostgresMetastoreRepository(get_db_session())
    elif DATABASE_BACKEND == "mysql":
        return MySQLMetastoreRepository(get_db_session())
    elif DATABASE_BACKEND == "sqlite":
        return SQLiteMetastoreRepository(get_db_session())
    else:
        raise ValueError(f"Unknown database backend: {DATABASE_BACKEND}")
```

**SQLAlchemy Support:**
SQLAlchemy abstracts most SQL dialects, so switching databases is primarily a connection string change:
```bash
# PostgreSQL
DATABASE_URL=postgresql://user:pass@postgres:5432/db

# MySQL
DATABASE_URL=mysql+pymysql://user:pass@mysql:3306/db

# SQLite
DATABASE_URL=sqlite:///data/duckbricks.db
```

### 5.2 Task Scheduler Abstraction

**Current:** Prefect
**Future Options:** Airflow, Dagster, custom scheduler

**Strategy:** Workflow Interface + Adapter Pattern

**Interface:**
```python
from abc import ABC, abstractmethod
from typing import Callable

class WorkflowScheduler(ABC):
    @abstractmethod
    def register_workflow(self, name: str, schedule: str, fn: Callable): pass

    @abstractmethod
    def trigger_workflow(self, name: str): pass

    @abstractmethod
    def list_workflows(self) -> List[str]: pass

    @abstractmethod
    def get_workflow_status(self, name: str) -> str: pass
```

**Prefect Adapter:**
```python
from prefect import flow
from prefect.deployments import Deployment

class PrefectScheduler(WorkflowScheduler):
    def register_workflow(self, name: str, schedule: str, fn: Callable):
        flow_fn = flow(name=name)(fn)
        deployment = Deployment.build_from_flow(
            flow=flow_fn,
            name=name,
            schedule={"cron": schedule}
        )
        deployment.apply()

    def trigger_workflow(self, name: str):
        # Trigger via Prefect API
        ...
```

**Airflow Adapter:**
```python
from airflow import DAG
from airflow.operators.python import PythonOperator

class AirflowScheduler(WorkflowScheduler):
    def register_workflow(self, name: str, schedule: str, fn: Callable):
        dag = DAG(dag_id=name, schedule_interval=schedule)
        task = PythonOperator(task_id=name, python_callable=fn, dag=dag)
        # Register DAG with Airflow
        ...
```

**Configuration:**
```bash
WORKFLOW_SCHEDULER=prefect  # or airflow, dagster, custom
```

### 5.3 File Storage Abstraction

**Current:** Local filesystem
**Future Options:** MinIO, S3, Azure Blob, GCS

**Strategy:** Storage Interface + Adapter Pattern

**Interface:**
```python
from abc import ABC, abstractmethod
from typing import BinaryIO

class StorageBackend(ABC):
    @abstractmethod
    def write(self, path: str, data: BinaryIO): pass

    @abstractmethod
    def read(self, path: str) -> BinaryIO: pass

    @abstractmethod
    def delete(self, path: str): pass

    @abstractmethod
    def list(self, prefix: str) -> List[str]: pass

    @abstractmethod
    def exists(self, path: str) -> bool: pass
```

**Local Filesystem Adapter:**
```python
import os
import shutil

class LocalStorageBackend(StorageBackend):
    def __init__(self, base_path: str):
        self.base_path = base_path

    def write(self, path: str, data: BinaryIO):
        full_path = os.path.join(self.base_path, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            shutil.copyfileobj(data, f)

    def read(self, path: str) -> BinaryIO:
        full_path = os.path.join(self.base_path, path)
        return open(full_path, 'rb')
```

**S3 Adapter:**
```python
import boto3

class S3StorageBackend(StorageBackend):
    def __init__(self, bucket: str, endpoint_url: str = None):
        self.s3 = boto3.client('s3', endpoint_url=endpoint_url)
        self.bucket = bucket

    def write(self, path: str, data: BinaryIO):
        self.s3.upload_fileobj(data, self.bucket, path)

    def read(self, path: str) -> BinaryIO:
        obj = self.s3.get_object(Bucket=self.bucket, Key=path)
        return obj['Body']
```

**Configuration:**
```bash
STORAGE_BACKEND=s3
S3_BUCKET=duckbricks
S3_ENDPOINT_URL=http://minio:9000  # For MinIO
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=changeme
```

**Factory:**
```python
def get_storage_backend() -> StorageBackend:
    backend = os.getenv("STORAGE_BACKEND", "local")
    if backend == "local":
        return LocalStorageBackend(base_path="/data/parquet")
    elif backend == "s3":
        return S3StorageBackend(
            bucket=os.getenv("S3_BUCKET"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL")
        )
    elif backend == "azure":
        return AzureBlobStorageBackend(...)
    elif backend == "gcs":
        return GCSStorageBackend(...)
    else:
        raise ValueError(f"Unknown storage backend: {backend}")
```

### 5.4 Dependency Injection Strategy

**Why Dependency Injection?**
- Loose coupling: Services depend on interfaces, not concrete implementations
- Testability: Inject mock repositories in tests
- Configuration-driven: Swap implementations via config without code changes

**Pattern:**
```python
# Service layer
class QueryService:
    def __init__(
        self,
        query_repo: QueryRepository,
        storage: StorageBackend,
        scheduler: WorkflowScheduler
    ):
        self.query_repo = query_repo
        self.storage = storage
        self.scheduler = scheduler

    def execute_query(self, sql: str):
        # Uses injected dependencies
        result = self.query_repo.execute(sql)
        self.storage.write("results/query-123.parquet", result)
        return result

# FastAPI dependency
def get_query_service() -> QueryService:
    return QueryService(
        query_repo=get_query_repo(),
        storage=get_storage_backend(),
        scheduler=get_workflow_scheduler()
    )

@app.post("/api/query")
def execute_query(sql: str, service: QueryService = Depends(get_query_service)):
    return service.execute_query(sql)
```

---

## 6. Data Flow

### 6.1 User Request Flow

**NiceGUI Page Load:**
```
User Browser
    │
    ├─► GET /explorer  ────────────────────┐
    │                                       │
    └──────────────────────────────────────▼
                                    NiceGUI Server (app/main.py)
                                            │
                                            ├─► explorer_page()
                                            │       │
                                            │       ├─► MetastoreService.list_catalogs()
                                            │       │       │
                                            │       │       └─► MetastoreRepository (Postgres)
                                            │       │
                                            │       └─► Render UI (ui.tree, ui.splitter)
                                            │
                                            └─► HTML + WebSocket (for reactive updates)
```

**FastAPI Request:**
```
External Client (CLI, CI/CD)
    │
    ├─► POST /api/query
    │   Body: {"sql": "SELECT * FROM users"}
    │
    └──────────────────────────────────────▼
                                    FastAPI Server (app/api/routes.py)
                                            │
                                            ├─► QueryService.execute_query(sql)
                                            │       │
                                            │       ├─► DuckLakeManager.execute_query(sql)
                                            │       │       │
                                            │       │       └─► DuckDB (reads Parquet via DuckLake)
                                            │       │
                                            │       └─► QueryRepository.save_execution(result)
                                            │
                                            └─► JSON Response
                                                    {"rows": [...], "columns": [...]}
```

### 6.2 Query Execution Flow

```
User submits SQL query
    │
    ├─► NiceGUI /query page OR FastAPI POST /api/query
    │
    └──────────────────────────────────────▼
                            QueryService.execute_query(sql)
                                    │
                                    ├─► Validate SQL (basic checks)
                                    │
                                    ├─► DuckLakeManager.execute_query(sql)
                                    │       │
                                    │       ├─► Acquire thread lock
                                    │       │
                                    │       ├─► conn.execute(sql)  [DuckDB]
                                    │       │       │
                                    │       │       └─► DuckLake reads Parquet files
                                    │       │               from StorageBackend
                                    │       │
                                    │       └─► Fetch results (rows, columns)
                                    │
                                    ├─► QueryRepository.save_execution(...)  [Postgres]
                                    │
                                    └─► Return results to user
```

### 6.3 Metastore Update Flow

**Creating a Catalog/Schema/Table:**
```
User creates a catalog via UI or API
    │
    ├─► POST /api/catalogs  {"name": "analytics"}
    │
    └──────────────────────────────────────▼
                            MetastoreService.create_catalog(name)
                                    │
                                    ├─► DuckLakeManager.execute_query("CREATE CATALOG analytics")
                                    │       │
                                    │       └─► DuckLake updates .ducklake catalog file
                                    │
                                    ├─► MetastoreRepository.create_catalog(...)  [Postgres]
                                    │       │
                                    │       └─► INSERT INTO metastore.catalogs (name, ...)
                                    │
                                    └─► Return success response
```

**Sync Flow (Background Job):**
DuckLake is the source of truth. PostgreSQL is synced periodically:
```
Prefect scheduled job (every 5 minutes)
    │
    └─► MetastoreSyncWorkflow.run()
            │
            ├─► DuckLakeManager.list_catalogs()  [DuckLake]
            │
            ├─► MetastoreRepository.list_catalogs()  [Postgres]
            │
            ├─► Diff: Find new/deleted catalogs
            │
            ├─► For each new catalog:
            │   └─► MetastoreRepository.create_catalog(...)
            │
            └─► For each deleted catalog:
                └─► MetastoreRepository.delete_catalog(...)
```

### 6.4 Job Scheduling and Execution Flow

```
User creates a scheduled query
    │
    ├─► POST /api/jobs
    │   Body: {"name": "daily_report", "schedule": "0 0 * * *", "sql": "..."}
    │
    └──────────────────────────────────────▼
                            JobService.create_job(...)
                                    │
                                    ├─► JobRepository.save_job(...)  [Postgres]
                                    │
                                    └─► WorkflowScheduler.register_workflow(...)  [Prefect]
                                            │
                                            └─► Prefect stores workflow definition

Prefect triggers job (cron: 0 0 * * *)
    │
    └─► Prefect calls: JobWorkflow.run(job_id)
            │
            ├─► JobService.execute_job(job_id)
            │       │
            │       ├─► JobRepository.get_job(job_id)  [Postgres]
            │       │
            │       ├─► QueryService.execute_query(sql)  [DuckDB]
            │       │
            │       ├─► StorageBackend.write("results/...", result)  [S3/MinIO]
            │       │
            │       └─► JobRepository.save_execution_log(...)  [Postgres]
            │
            └─► Send notification (email, Slack, etc.)
```

### 6.5 File Upload and Storage Flow

**Uploading a CSV to create a table:**
```
User uploads CSV file via UI
    │
    ├─► POST /api/files  (multipart/form-data)
    │   File: data.csv
    │
    └──────────────────────────────────────▼
                            FileService.ingest_csv(file, table_name)
                                    │
                                    ├─► StorageBackend.write("uploads/data.csv", file)  [S3]
                                    │
                                    ├─► DuckLakeManager.execute_query(
                                    │       "CREATE TABLE users AS
                                    │        SELECT * FROM read_csv('s3://bucket/uploads/data.csv')"
                                    │   )
                                    │       │
                                    │       └─► DuckLake writes Parquet files to DATA_PATH
                                    │
                                    ├─► MetastoreRepository.create_table(...)  [Postgres]
                                    │
                                    └─► Return success response
```

---

## 7. Security & Access Control

### 7.1 Authentication Strategy

**Phase 1 (Current):** No authentication (single-user mode)

**Phase 2:** Session-based authentication for NiceGUI
- Username/password login via NiceGUI form
- Sessions stored in signed cookies (FastAPI `Starlette` sessions)
- Passwords hashed with bcrypt

**Phase 3:** JWT-based authentication for FastAPI
- Token-based auth for API access
- OAuth2 flow for external integrations
- API keys for service-to-service communication

**Implementation:**
```python
# FastAPI auth dependency
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    # Decode JWT, verify signature, load user from DB
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user

@app.get("/api/queries")
def list_queries(user: User = Depends(get_current_user)):
    # User is authenticated
    return query_service.list_queries(user.workspace_id)
```

### 7.2 Authorization Model

**Multi-Tenancy:** Workspace-based isolation

**Role-Based Access Control (RBAC):**
- **Admin:** Full workspace control (manage members, delete queries/tables)
- **Editor:** Create/edit queries, run jobs, create tables
- **Viewer:** Read-only access (view queries, results, metastore)

**Permission Checks:**
```python
def require_role(role: str):
    def decorator(fn):
        def wrapper(user: User = Depends(get_current_user), *args, **kwargs):
            member = workspace_repo.get_member(workspace_id, user.id)
            if member.role not in [role, "admin"]:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            return fn(user, *args, **kwargs)
        return wrapper
    return decorator

@app.delete("/api/queries/{query_id}")
@require_role("editor")
def delete_query(query_id: int, user: User):
    query_service.delete_query(query_id)
```

### 7.3 Workspace Isolation

**Data Isolation:**
- Each workspace has its own catalog in DuckLake (`workspace_<id>`)
- PostgreSQL metastore entries are linked to `workspace_id`
- Query execution context automatically filters by workspace

**Implementation:**
```python
class QueryService:
    def __init__(self, workspace_id: int):
        self.workspace_id = workspace_id

    def execute_query(self, sql: str):
        # Automatically prefix table references with workspace catalog
        scoped_sql = f"USE workspace_{self.workspace_id}; {sql}"
        return ducklake_manager.execute_query(scoped_sql)
```

### 7.4 Secrets Management

**Sensitive Configuration:**
- Database passwords
- Storage credentials (S3 keys, MinIO secrets)
- API keys (Prefect, external integrations)

**Strategy:**
- **Development:** `.env` file (not committed to Git)
- **Production:** Environment variables injected by orchestration platform
- **Kubernetes:** Use Kubernetes Secrets or external secret managers (Vault, AWS Secrets Manager)

**Never log secrets:**
```python
import logging

# BAD: Logs password
logging.info(f"Connecting to {DATABASE_URL}")

# GOOD: Redact password
logging.info(f"Connecting to {redact_url(DATABASE_URL)}")
```

---

## 8. Configuration Management

### 8.1 Environment Variables

**Configuration Hierarchy:**
1. Hardcoded defaults (in `config.py`)
2. `.env` file (development)
3. Environment variables (production)

**Example Configuration:**

```python
from app.config import RuntimeConfiguration, validate_runtime_configuration

configuration = RuntimeConfiguration.current()
validate_runtime_configuration(configuration)
```

The validator checks configuration shape and required backend credentials without placing secret
values in its error messages. Connectivity is verified separately during application startup and
through readiness checks.

### 8.2 Configuration File Strategy

**`.env` File (Development):**
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/duckbricks
DUCKLAKE_PG_HOST=localhost
DUCKBRICKS_STORAGE_BACKEND=local
PREFECT_INTERNAL_URL=http://localhost:4200
MARIMO_INTERNAL_URL=http://localhost:2718
```

**Environment Variables (Production):**
```bash
export DATABASE_URL="postgresql://..."
export DUCKBRICKS_STORAGE_BACKEND="s3"
export DUCKBRICKS_DATA_PATH="s3://duckbricks-prod/data/"
export DUCKBRICKS_SECRET_KEY="<fernet-key>"
```

**Docker Compose:**
```yaml
services:
  duckbricks:
    environment:
      DATABASE_URL: ${DATABASE_URL:-postgresql://duckbricks:duckbricks@postgres/duckbricks}
      DUCKLAKE_PG_HOST: ${DUCKLAKE_PG_HOST:-postgres}
      DUCKBRICKS_STORAGE_BACKEND: ${DUCKBRICKS_STORAGE_BACKEND:-local}
```

### 8.3 Swapping Components via Configuration

**Example: Switch from local storage to S3:**

```bash
# Before (local)
DUCKBRICKS_STORAGE_BACKEND=local
DUCKBRICKS_DATA_PATH=/data/parquet/

# After (S3)
DUCKBRICKS_STORAGE_BACKEND=s3
DUCKBRICKS_DATA_PATH=s3://duckbricks-prod/data/
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

**No code changes required.** `StorageBackendFactory` reads `DUCKBRICKS_STORAGE_BACKEND` and returns the appropriate adapter.

Prefect is currently the only implemented scheduler. A scheduler abstraction remains a future
architectural option rather than a configuration-only switch.

---

## 9. Future Considerations

### 9.1 Scalability Strategy

**Horizontal Scaling:**
- **Current:** Single `duckbricks-web` container
- **Future:** Multiple replicas behind a load balancer (NGINX, HAProxy, ALB)

**Stateless Design:**
- All application state stored in PostgreSQL
- DuckLake catalog is shared across replicas (read-only or with coordination)
- Session data stored in Redis or signed cookies (no in-memory sessions)

**Database Scaling:**
- **PostgreSQL:** Primary-replica replication for read scaling
- **DuckDB:** Each replica has its own in-process connection (reads are parallel)

**Prefect Scaling:**
- Prefect agent pool can be scaled independently
- Workflows execute on worker nodes, not the web server

**Load Balancer Configuration:**
```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - duckbricks-web-1
      - duckbricks-web-2
      - duckbricks-web-3

  duckbricks-web-1:
    <<: *duckbricks-web
  duckbricks-web-2:
    <<: *duckbricks-web
  duckbricks-web-3:
    <<: *duckbricks-web
```

### 9.2 Performance Optimization

**Query Result Caching:**
- Cache results of expensive queries in Redis (TTL-based)
- Cache key: SHA256 hash of SQL query
- Invalidation: Clear cache on table updates

**Connection Pooling:**
- PostgreSQL: Use `pgbouncer` or SQLAlchemy's built-in pool
- DuckDB: Consider connection pool for concurrent queries (if DuckDB adds support)

**Query Optimization:**
- Profile slow queries with `EXPLAIN` in DuckDB
- Index frequently queried columns in DuckLake (Parquet row groups)
- Partition large tables by date/time for faster filtering

**DuckLake Optimizations:**
- Use column pruning (only read needed columns)
- Predicate pushdown (filter at Parquet file level)
- Partition pruning (skip irrelevant partitions)

### 9.3 Observability

**Logging:**
- Structured logging (JSON format) via `structlog`
- Log aggregation with ELK stack (Elasticsearch, Logstash, Kibana) or Loki

**Metrics:**
- Expose Prometheus metrics endpoint (`/metrics`)
- Track: Request latency, query execution time, error rates, active connections
- Dashboards in Grafana

**Tracing:**
- Distributed tracing with OpenTelemetry
- Trace requests across NiceGUI → Service Layer → DuckDB → PostgreSQL
- Visualize traces in Jaeger or Tempo

**Example Prometheus Metrics:**
```python
from prometheus_client import Counter, Histogram

query_counter = Counter('duckbricks_queries_total', 'Total queries executed')
query_duration = Histogram('duckbricks_query_duration_seconds', 'Query execution time')

def execute_query(sql: str):
    query_counter.inc()
    with query_duration.time():
        return ducklake_manager.execute_query(sql)
```

### 9.4 Migration to Kubernetes

**Current:** Docker Compose (single-node)
**Future:** Kubernetes (multi-node, HA)

**Benefits of Kubernetes:**
- Automatic pod restarts on failure
- Horizontal pod autoscaling (HPA)
- Rolling updates with zero downtime
- Persistent volume claims for data storage

**Example Kubernetes Deployment:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: duckbricks-web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: duckbricks
  template:
    metadata:
      labels:
        app: duckbricks
    spec:
      containers:
      - name: duckbricks
        image: duckbricks/web:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: duckbricks-secrets
              key: database-url
        volumeMounts:
        - name: data
          mountPath: /data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: duckbricks-data-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: duckbricks-web
spec:
  selector:
    app: duckbricks
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

**StatefulSets for Stateful Components:**
- PostgreSQL: Use StatefulSet with persistent volumes
- Prefect Server: StatefulSet for consistent pod identity

**Migration Path:**
1. Dockerize all components (already done)
2. Test locally with Docker Compose
3. Create Kubernetes manifests (Deployments, Services, Secrets)
4. Deploy to staging cluster (Minikube or K3s)
5. Load test and tune resource requests/limits
6. Deploy to production cluster (EKS, GKE, AKS)

---

## Appendix: Architectural Decision Records (ADRs)

### ADR-001: Use NiceGUI for Frontend

**Status:** Accepted
**Date:** 2026-03-01

**Context:**
Need a web UI framework for the DuckBricks platform. Options: React/Vue (JavaScript), Streamlit, Dash, NiceGUI.

**Decision:**
Use NiceGUI for the frontend.

**Rationale:**
- Python-only development (no JavaScript context switching)
- Reactive UI updates (WebSocket-based)
- Rapid prototyping and iteration
- Native integration with Python backend logic

**Consequences:**
- Limited ecosystem compared to React/Vue
- Harder to customize complex UI components
- Requires Python runtime on server (no static HTML/JS deployment)

---

### ADR-002: Use PostgreSQL as Metastore Backend

**Status:** Accepted
**Date:** 2026-03-05

**Context:**
DuckLake's `.ducklake` catalog is file-based. Need a richer queryable metastore for workspace isolation, access control, and audit logging.

**Decision:**
Mirror DuckLake metadata in PostgreSQL.

**Rationale:**
- Rich query capabilities (search by column name, filter by workspace)
- Transactional updates (ACID guarantees)
- Mature ecosystem (ORMs, migration tools, backups)
- Supports workspace-based multi-tenancy with foreign keys

**Consequences:**
- Dual source of truth (DuckLake + PostgreSQL must stay in sync)
- Requires background sync jobs
- Adds operational complexity (one more database to manage)

---

### ADR-003: Use Prefect for Workflow Orchestration

**Status:** Accepted
**Date:** 2026-03-08

**Context:**
Need a workflow orchestration tool for scheduled queries, ETL pipelines, and data quality checks. Options: Prefect, Airflow, Dagster.

**Decision:**
Use Prefect for workflow orchestration.

**Rationale:**
- Pythonic API (native Python functions become workflows)
- Modern UI (better than Airflow's)
- Dynamic DAGs (no need to predefine all workflows)
- Strong failure handling and retries

**Consequences:**
- Less mature than Airflow (smaller community, fewer plugins)
- Requires Prefect Cloud or self-hosted server
- Learning curve for team unfamiliar with Prefect

---

## Glossary

| Term | Definition |
|------|------------|
| **DuckLake** | Open table format for DuckDB, similar to Apache Iceberg |
| **Catalog** | Top-level namespace in DuckLake (equivalent to a database) |
| **Schema** | Namespace within a catalog (equivalent to a schema in PostgreSQL) |
| **Table** | Data table stored as Parquet files in DuckLake |
| **Metastore** | Central repository of metadata about catalogs, schemas, and tables |
| **Workspace** | Multi-tenant isolation unit; each workspace has its own catalog |
| **Query Execution** | The process of running a SQL query against DuckLake via DuckDB |
| **Job** | Scheduled workflow (e.g., daily report, ETL pipeline) |
| **Parquet** | Columnar storage format optimized for analytics |
| **Repository Pattern** | Design pattern that abstracts data access behind interfaces |
| **Dependency Injection** | Technique for providing dependencies to functions/classes rather than hardcoding them |

---

## References

- [DuckDB Documentation](https://duckdb.org/docs/)
- [DuckLake Documentation](https://ducklake.select/docs/stable)
- [NiceGUI Documentation](https://nicegui.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Prefect Documentation](https://docs.prefect.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
