"""DuckBricks — API entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.db import manager
from app.config import CATALOG_PATH

import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-initialize metastore on startup if catalog already exists."""
    if os.path.exists(CATALOG_PATH):
        try:
            manager.initialize()
        except Exception as e:
            print(f"Warning: Could not auto-attach existing metastore: {e}")
    yield


app = FastAPI(
    title="DuckBricks",
    description="Open-source data platform built on DuckLake",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Models ---

class QueryRequest(BaseModel):
    sql: str


class QueryResponse(BaseModel):
    success: bool
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0
    message: str | None = None
    error: str | None = None


class MetastoreStatus(BaseModel):
    initialized: bool
    catalog_path: str
    data_path: str
    ducklake_name: str
    catalog_exists: bool


class ColumnSchema(BaseModel):
    column_name: str
    data_type: str
    is_nullable: str | None = None


class TableInfo(BaseModel):
    name: str
    column_count: int
    row_count: int
    columns: list[ColumnSchema]


# --- Health ---

@app.get("/health")
def health():
    return {"status": "ok"}


# --- Metastore ---

@app.post("/api/metastore/init", response_model=MetastoreStatus)
def init_metastore():
    """Initialize or re-attach the DuckLake metastore."""
    try:
        return manager.initialize()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metastore/status", response_model=MetastoreStatus)
def metastore_status():
    """Check metastore status."""
    return manager.status()


# --- Query ---

@app.post("/api/query", response_model=QueryResponse)
def run_query(req: QueryRequest):
    """Execute a SQL query against DuckLake."""
    if not manager.is_initialized:
        raise HTTPException(
            status_code=400,
            detail="Metastore not initialized. Call POST /api/metastore/init first.",
        )
    result = manager.execute_query(req.sql)
    return result


# --- Table Catalog ---

@app.get("/api/tables", response_model=list[TableInfo])
def list_tables():
    """List all tables in the DuckLake catalog."""
    if not manager.is_initialized:
        raise HTTPException(
            status_code=400,
            detail="Metastore not initialized. Call POST /api/metastore/init first.",
        )
    try:
        return manager.list_tables()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tables/{table_name}", response_model=TableInfo)
def get_table(table_name: str):
    """Get detailed info for a specific table."""
    if not manager.is_initialized:
        raise HTTPException(
            status_code=400,
            detail="Metastore not initialized. Call POST /api/metastore/init first.",
        )
    try:
        table = manager.get_table(table_name)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")
        return table
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
