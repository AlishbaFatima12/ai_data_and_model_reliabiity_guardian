"""Reference Data Models for Silver Tier Layer 3.

This module defines models for reference data used in referential integrity checks:
- ReferenceDataSet: Represents lookup data loaded from CSV/JSON files
- ReferenceColumn: Column configuration for reference data
- LookupResult: Result of a lookup operation
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ReferenceDataFormat(str, Enum):
    """Supported reference data file formats."""

    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"


class ReferenceColumn(BaseModel):
    """Configuration for a reference data column.

    Attributes:
        name: Column name
        is_key: Whether this is the lookup key column
        data_type: Expected data type
        allow_null: Whether null values are allowed
    """

    name: str = Field(..., description="Column name")
    is_key: bool = Field(default=False, description="Is lookup key column")
    data_type: str = Field(default="string", description="Expected data type")
    allow_null: bool = Field(default=False, description="Allow null values")


class ReferenceDataConfig(BaseModel):
    """Configuration for a reference data set.

    Attributes:
        id: Unique identifier for this reference data
        name: Human-readable name
        description: Description of the data
        file_path: Path to the data file
        format: File format (csv, json, jsonl)
        key_column: Column to use for lookups
        columns: Column configurations
        refresh_interval_seconds: How often to reload data
        active_column: Optional column indicating active/inactive records
        last_loaded: When data was last loaded
    """

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(default="", description="Description")
    file_path: str = Field(..., description="Path to data file")
    format: ReferenceDataFormat = Field(
        default=ReferenceDataFormat.CSV, description="File format"
    )
    key_column: str = Field(..., description="Column for lookups")
    columns: list[ReferenceColumn] = Field(
        default_factory=list, description="Column configurations"
    )
    refresh_interval_seconds: int = Field(
        default=3600, ge=60, description="Refresh interval"
    )
    active_column: str | None = Field(
        None, description="Column indicating active/inactive"
    )
    last_loaded: datetime | None = Field(None, description="Last load time")


class ReferenceDataSet(BaseModel):
    """Represents lookup data loaded from CSV/JSON files.

    Used for referential integrity checks (BL-002) and orphan detection (BL-008).

    Attributes:
        config: Reference data configuration
        data: The actual lookup data (key -> record)
        keys: Set of all valid keys for fast lookup
        record_count: Number of records loaded
        loaded_at: When the data was loaded
        file_hash: Hash of source file for change detection
    """

    config: ReferenceDataConfig = Field(..., description="Configuration")
    data: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Key -> record mapping"
    )
    keys: set[str] = Field(default_factory=set, description="All valid keys")
    record_count: int = Field(default=0, ge=0, description="Record count")
    loaded_at: datetime = Field(
        default_factory=datetime.utcnow, description="Load time"
    )
    file_hash: str = Field(default="", description="Source file hash")

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    def contains(self, key: str) -> bool:
        """Check if key exists in reference data.

        Args:
            key: The key to look up.

        Returns:
            True if key exists.
        """
        return key in self.keys

    def get(self, key: str) -> dict[str, Any] | None:
        """Get record by key.

        Args:
            key: The key to look up.

        Returns:
            Record dict or None if not found.
        """
        return self.data.get(key)

    def get_value(self, key: str, column: str) -> Any | None:
        """Get specific column value for a key.

        Args:
            key: The key to look up.
            column: The column to retrieve.

        Returns:
            Column value or None.
        """
        record = self.data.get(key)
        if record is None:
            return None
        return record.get(column)

    def is_active(self, key: str) -> bool:
        """Check if record is active (not deleted/inactive).

        Args:
            key: The key to check.

        Returns:
            True if record is active or no active_column configured.
        """
        if self.config.active_column is None:
            return key in self.keys

        record = self.data.get(key)
        if record is None:
            return False

        active_value = record.get(self.config.active_column)
        # Truthy check for active status
        if isinstance(active_value, bool):
            return active_value
        if isinstance(active_value, str):
            return active_value.lower() in ("true", "yes", "1", "active")
        return bool(active_value)

    def needs_refresh(self) -> bool:
        """Check if data needs to be refreshed.

        Returns:
            True if refresh interval has passed.
        """
        if self.loaded_at is None:
            return True
        elapsed = (datetime.utcnow() - self.loaded_at).total_seconds()
        return elapsed >= self.config.refresh_interval_seconds

    @classmethod
    def create_empty(cls, config: ReferenceDataConfig) -> "ReferenceDataSet":
        """Create an empty reference data set.

        Args:
            config: The configuration for the data set.

        Returns:
            Empty ReferenceDataSet instance.
        """
        return cls(
            config=config,
            data={},
            keys=set(),
            record_count=0,
        )


class LookupResult(BaseModel):
    """Result of a reference data lookup.

    Attributes:
        found: Whether the key was found
        key: The key that was looked up
        reference_id: ID of the reference data set
        record: The matching record (if found)
        is_active: Whether the record is active
        lookup_time_ms: Time taken for lookup
    """

    found: bool = Field(..., description="Whether key was found")
    key: str = Field(..., description="Looked up key")
    reference_id: str = Field(..., description="Reference data set ID")
    record: dict[str, Any] | None = Field(None, description="Matching record")
    is_active: bool = Field(default=True, description="Whether record is active")
    lookup_time_ms: float = Field(default=0.0, ge=0, description="Lookup time")


class ReferenceIntegrityCheck(BaseModel):
    """Configuration for a referential integrity check.

    Attributes:
        id: Check identifier
        source_field: Field in source data containing FK
        reference_id: ID of reference data set to check against
        check_active: Whether to check active status
        allow_null: Whether null FK values are allowed
        failure_code: BL-002 or BL-008
    """

    id: str = Field(..., description="Check identifier")
    source_field: str = Field(..., description="Source field with FK")
    reference_id: str = Field(..., description="Reference data set ID")
    check_active: bool = Field(default=True, description="Check active status")
    allow_null: bool = Field(default=False, description="Allow null FK")
    failure_code: str = Field(default="BL-002", description="Failure code")
