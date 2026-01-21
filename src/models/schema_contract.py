"""Schema Contract models for Silver Tier.

Defines SchemaContract and ColumnDefinition models for schema validation.
"""

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ColumnCriticality(str, Enum):
    """Column criticality determines severity of violations."""

    REQUIRED = "required"  # Missing/invalid → CRITICAL severity
    OPTIONAL = "optional"  # Missing/invalid → WARNING severity


class ColumnType(str, Enum):
    """Supported column data types."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"
    DATE = "date"
    DATETIME = "datetime"


class ColumnConstraint(BaseModel):
    """Constraints for a column definition."""

    nullable: bool = Field(default=True, description="Whether column can be null")
    unique: bool = Field(default=False, description="Whether values must be unique")
    min_length: int | None = Field(None, ge=0, description="Minimum string length")
    max_length: int | None = Field(None, ge=0, description="Maximum string length")
    minimum: float | None = Field(None, description="Minimum numeric value")
    maximum: float | None = Field(None, description="Maximum numeric value")
    pattern: str | None = Field(None, description="Regex pattern for string values")
    enum_values: list[Any] | None = Field(None, description="Allowed enumeration values")
    precision: int | None = Field(None, ge=0, description="Decimal precision for numbers")
    scale: int | None = Field(None, ge=0, description="Decimal scale for numbers")
    foreign_key: str | None = Field(None, description="Foreign key reference (table.column)")


class ColumnDefinition(BaseModel):
    """Definition of a single column in a schema contract."""

    name: str = Field(..., description="Column name")
    column_type: ColumnType = Field(..., description="Data type")
    criticality: ColumnCriticality = Field(
        default=ColumnCriticality.REQUIRED,
        description="Column criticality (required/optional)",
    )
    description: str = Field(default="", description="Human-readable description")
    constraints: ColumnConstraint = Field(
        default_factory=ColumnConstraint,
        description="Column constraints",
    )
    default_value: Any | None = Field(None, description="Default value if not provided")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @property
    def is_required(self) -> bool:
        """Check if column is required."""
        return self.criticality == ColumnCriticality.REQUIRED

    @property
    def is_nullable(self) -> bool:
        """Check if column allows null values."""
        return self.constraints.nullable


class SchemaContract(BaseModel):
    """Schema contract defining expected data structure.

    Per spec: Contracts define columns, types, constraints, and
    criticality for data validation.
    """

    id: str = Field(..., description="Unique contract identifier")
    name: str = Field(..., description="Human-readable contract name")
    version: str = Field(..., description="Semantic version (e.g., 1.0.0)")
    source: str = Field(..., description="Data source this contract applies to")
    columns: list[ColumnDefinition] = Field(
        default_factory=list,
        description="Column definitions",
    )
    additional_properties: bool = Field(
        default=False,
        description="Whether extra columns are allowed",
    )
    description: str = Field(default="", description="Contract description")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When contract was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When contract was last updated",
    )
    owner: str = Field(default="", description="Team/person responsible")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    # Cached hash (computed on demand)
    _hash: str | None = None

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @property
    def column_names(self) -> list[str]:
        """Get list of all column names."""
        return [col.name for col in self.columns]

    @property
    def required_columns(self) -> list[ColumnDefinition]:
        """Get list of required columns."""
        return [col for col in self.columns if col.is_required]

    @property
    def optional_columns(self) -> list[ColumnDefinition]:
        """Get list of optional columns."""
        return [col for col in self.columns if not col.is_required]

    def get_column(self, name: str) -> ColumnDefinition | None:
        """Get column definition by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def compute_hash(self) -> str:
        """Compute deterministic SHA-256 hash of contract.

        Hash includes: columns, types, constraints, version.
        Excludes: timestamps, metadata, description.

        Returns:
            Hex-encoded SHA-256 hash.
        """
        # Build canonical representation for hashing
        hash_data = {
            "id": self.id,
            "version": self.version,
            "source": self.source,
            "additional_properties": self.additional_properties,
            "columns": [
                {
                    "name": col.name,
                    "column_type": col.column_type.value,
                    "criticality": col.criticality.value,
                    "constraints": col.constraints.model_dump(exclude_none=True),
                }
                for col in sorted(self.columns, key=lambda c: c.name)
            ],
        }

        # Compute SHA-256 hash
        canonical = json.dumps(hash_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def contract_hash(self) -> str:
        """Get contract hash (cached)."""
        if self._hash is None:
            object.__setattr__(self, "_hash", self.compute_hash())
        return self._hash

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema format.

        Returns:
            JSON Schema dictionary compatible with jsonschema library.
        """
        properties: dict[str, Any] = {}
        required: list[str] = []

        for col in self.columns:
            prop: dict[str, Any] = {}

            # Map column type to JSON Schema type
            type_mapping = {
                ColumnType.STRING: "string",
                ColumnType.INTEGER: "integer",
                ColumnType.NUMBER: "number",
                ColumnType.BOOLEAN: "boolean",
                ColumnType.ARRAY: "array",
                ColumnType.OBJECT: "object",
                ColumnType.NULL: "null",
                ColumnType.DATE: "string",
                ColumnType.DATETIME: "string",
            }
            prop["type"] = type_mapping.get(col.column_type, "string")

            # Add format for date/datetime
            if col.column_type == ColumnType.DATE:
                prop["format"] = "date"
            elif col.column_type == ColumnType.DATETIME:
                prop["format"] = "date-time"

            # Add constraints
            constraints = col.constraints
            if constraints.min_length is not None:
                prop["minLength"] = constraints.min_length
            if constraints.max_length is not None:
                prop["maxLength"] = constraints.max_length
            if constraints.minimum is not None:
                prop["minimum"] = constraints.minimum
            if constraints.maximum is not None:
                prop["maximum"] = constraints.maximum
            if constraints.pattern is not None:
                prop["pattern"] = constraints.pattern
            if constraints.enum_values is not None:
                prop["enum"] = constraints.enum_values

            # Add description
            if col.description:
                prop["description"] = col.description

            # Add custom extension for criticality
            prop["x-column-criticality"] = col.criticality.value

            properties[col.name] = prop

            # Track required columns
            if col.is_required and not constraints.nullable:
                required.append(col.name)

        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": self.name,
            "description": self.description,
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": self.additional_properties,
        }

        return schema

    @classmethod
    def from_json_schema(
        cls, schema: dict[str, Any], contract_id: str, version: str, source: str
    ) -> "SchemaContract":
        """Create SchemaContract from JSON Schema.

        Args:
            schema: JSON Schema dictionary.
            contract_id: Unique contract identifier.
            version: Semantic version string.
            source: Data source name.

        Returns:
            New SchemaContract instance.
        """
        columns: list[ColumnDefinition] = []
        properties = schema.get("properties", {})
        required_names = set(schema.get("required", []))

        # Reverse type mapping
        type_mapping = {
            "string": ColumnType.STRING,
            "integer": ColumnType.INTEGER,
            "number": ColumnType.NUMBER,
            "boolean": ColumnType.BOOLEAN,
            "array": ColumnType.ARRAY,
            "object": ColumnType.OBJECT,
            "null": ColumnType.NULL,
        }

        for col_name, col_schema in properties.items():
            col_type_str = col_schema.get("type", "string")
            col_type = type_mapping.get(col_type_str, ColumnType.STRING)

            # Check for date format
            if col_type == ColumnType.STRING:
                format_str = col_schema.get("format", "")
                if format_str == "date":
                    col_type = ColumnType.DATE
                elif format_str == "date-time":
                    col_type = ColumnType.DATETIME

            # Extract criticality from extension or infer from required
            criticality_str = col_schema.get("x-column-criticality", None)
            if criticality_str:
                criticality = ColumnCriticality(criticality_str)
            elif col_name in required_names:
                criticality = ColumnCriticality.REQUIRED
            else:
                criticality = ColumnCriticality.OPTIONAL

            # Build constraints
            constraints = ColumnConstraint(
                nullable=col_name not in required_names,
                min_length=col_schema.get("minLength"),
                max_length=col_schema.get("maxLength"),
                minimum=col_schema.get("minimum"),
                maximum=col_schema.get("maximum"),
                pattern=col_schema.get("pattern"),
                enum_values=col_schema.get("enum"),
            )

            columns.append(
                ColumnDefinition(
                    name=col_name,
                    column_type=col_type,
                    criticality=criticality,
                    description=col_schema.get("description", ""),
                    constraints=constraints,
                )
            )

        return cls(
            id=contract_id,
            name=schema.get("title", contract_id),
            version=version,
            source=source,
            columns=columns,
            additional_properties=schema.get("additionalProperties", False),
            description=schema.get("description", ""),
        )
