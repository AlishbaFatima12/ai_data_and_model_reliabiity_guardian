"""Checkpoint model for DMRG-FTE."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Checkpoint(BaseModel):
    """Checkpoint for validation state recovery.

    Per spec FR-018, FR-019: Save and restore validation state for recovery.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    batch_id: str = Field(..., description="ID of the batch being validated")
    position: int = Field(
        ge=0,
        description="Current record position (0-indexed)",
    )
    partial_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Partial validation results so far",
    )
    validation_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Validation context (skill states, accumulators)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the checkpoint was created",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @classmethod
    def create_start(
        cls,
        batch_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> "Checkpoint":
        """Create a checkpoint at validation start.

        Args:
            batch_id: ID of the batch being validated.
            metadata: Optional metadata.

        Returns:
            New Checkpoint at position 0.
        """
        return cls(
            batch_id=batch_id,
            position=0,
            partial_results={},
            validation_context={},
            metadata=metadata or {},
        )

    @classmethod
    def create_progress(
        cls,
        batch_id: str,
        position: int,
        partial_results: dict[str, Any],
        validation_context: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> "Checkpoint":
        """Create a checkpoint at a specific position.

        Args:
            batch_id: ID of the batch being validated.
            position: Current record position.
            partial_results: Results collected so far.
            validation_context: Current validation context.
            metadata: Optional metadata.

        Returns:
            New Checkpoint at specified position.
        """
        return cls(
            batch_id=batch_id,
            position=position,
            partial_results=partial_results,
            validation_context=validation_context,
            metadata=metadata or {},
        )

    @property
    def is_start(self) -> bool:
        """Check if this is a start checkpoint."""
        return self.position == 0 and not self.partial_results

    @property
    def records_processed(self) -> int:
        """Get number of records processed."""
        return self.position

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode="json")
