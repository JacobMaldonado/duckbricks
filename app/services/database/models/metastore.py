"""SQLAlchemy ORM models for the metastore schema — mirrors DuckLake catalog metadata."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.services.database.base import Base


class CatalogModel(Base):
    """Top-level catalog namespace (mirrors DuckLake catalog)."""

    __tablename__ = "catalogs"
    __table_args__ = {"schema": "metastore"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    schemas: Mapped[list["SchemaModel"]] = relationship(
        "SchemaModel", back_populates="catalog", cascade="all, delete-orphan"
    )


class SchemaModel(Base):
    """Schema namespace within a catalog."""

    __tablename__ = "schemas"
    __table_args__ = {"schema": "metastore"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalog_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("metastore.catalogs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    catalog: Mapped["CatalogModel"] = relationship("CatalogModel", back_populates="schemas")
    tables: Mapped[list["TableModel"]] = relationship(
        "TableModel", back_populates="schema", cascade="all, delete-orphan"
    )


class TableModel(Base):
    """Table or view within a schema."""

    __tablename__ = "tables"
    __table_args__ = {"schema": "metastore"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("metastore.schemas.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_type: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_format: Mapped[str] = mapped_column(String(50), default="parquet")
    location: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    schema: Mapped["SchemaModel"] = relationship("SchemaModel", back_populates="tables")
    columns: Mapped[list["ColumnModel"]] = relationship(
        "ColumnModel", back_populates="table", cascade="all, delete-orphan"
    )
    partitions: Mapped[list["PartitionModel"]] = relationship(
        "PartitionModel", back_populates="table", cascade="all, delete-orphan"
    )


class ColumnModel(Base):
    """Column definition for a table."""

    __tablename__ = "columns"
    __table_args__ = {"schema": "metastore"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("metastore.tables.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    ordinal_position: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    table: Mapped["TableModel"] = relationship("TableModel", back_populates="columns")


class PartitionModel(Base):
    """Partition metadata for a partitioned table."""

    __tablename__ = "partitions"
    __table_args__ = {"schema": "metastore"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("metastore.tables.id", ondelete="CASCADE"), nullable=False
    )
    location: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    table: Mapped["TableModel"] = relationship("TableModel", back_populates="partitions")
