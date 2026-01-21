"""DataBatch model for DMRG-FTE."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.lib.constants import BatchStatus


class DataBatch(BaseModel):
    """Represents a batch of data records for validation.

    Per spec FR-001: Validates incoming data batches against quality rules.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str = Field(..., description="Source file path or identifier")
    arrival_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the batch arrived for processing",
    )
    record_count: int = Field(ge=0, description="Number of records in the batch")
    status: BatchStatus = Field(
        default=BatchStatus.PENDING,
        description="Current status in the validation pipeline",
    )
    records: list[dict[str, Any]] = Field(
        default_factory=list,
        description="The actual data records",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the batch",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @classmethod
    def from_records(
        cls,
        records: list[dict[str, Any]],
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> "DataBatch":
        """Create a DataBatch from a list of records.

        Args:
            records: List of record dictionaries.
            source: Source identifier (file path).
            metadata: Optional additional metadata.

        Returns:
            New DataBatch instance.
        """
        return cls(
            source=source,
            record_count=len(records),
            records=records,
            metadata=metadata or {},
        )

    def set_status(self, status: BatchStatus) -> None:
        """Update the batch status.

        Args:
            status: New status to set.
        """
        self.status = status

    def mark_validating(self) -> None:
        """Mark batch as currently being validated."""
        self.status = BatchStatus.VALIDATING

    def mark_passed(self) -> None:
        """Mark batch as passed validation."""
        self.status = BatchStatus.PASSED

    def mark_failed(self) -> None:
        """Mark batch as failed validation."""
        self.status = BatchStatus.FAILED

    def mark_error(self) -> None:
        """Mark batch as having an error during validation."""
        self.status = BatchStatus.ERROR

    @property
    def is_empty(self) -> bool:
        """Check if the batch has no records."""
        return self.record_count == 0

    @property
    def is_complete(self) -> bool:
        """Check if validation has completed (pass or fail)."""
        return self.status.is_terminal

    def get_record(self, index: int) -> dict[str, Any] | None:
        """Get a specific record by index.

        Args:
            index: Record index (0-based).

        Returns:
            Record dictionary or None if index is out of bounds.
        """
        if 0 <= index < len(self.records):
            return self.records[index]
        return None

    def iter_records(self):
        """Iterate over records with their indices.

        Yields:
            Tuple of (index, record).
        """
        yield from enumerate(self.records)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode="json")
