"""Utility checkpoint skill - State persistence."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.models.checkpoint import Checkpoint


class CheckpointConfig(BaseModel):
    """Configuration for checkpoint management."""

    checkpoint_dir: str = Field(
        default="data/checkpoints",
        description="Directory for checkpoint files",
    )
    max_checkpoints: int = Field(
        default=100,
        ge=1,
        description="Maximum checkpoints to retain",
    )


class CheckpointSkill:
    """Utility skill for saving/restoring validation state (FR-018, FR-019).

    Manages checkpoints for validation state recovery.
    """

    name: str = "util.checkpoint"

    def __init__(self, config: CheckpointConfig | None = None):
        """Initialize the checkpoint skill.

        Args:
            config: Configuration for checkpoint management.
        """
        self.config = config or CheckpointConfig()

    def save(self, checkpoint: Checkpoint) -> str:
        """Save a checkpoint to disk.

        Args:
            checkpoint: Checkpoint to save.

        Returns:
            Path to the saved checkpoint file.
        """
        checkpoint_dir = Path(self.config.checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{checkpoint.id}.json"
        filepath = checkpoint_dir / filename

        data = checkpoint.to_dict()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        # Cleanup old checkpoints
        self._cleanup_old_checkpoints()

        return str(filepath)

    def load(self, checkpoint_id: str) -> Checkpoint | None:
        """Load a checkpoint from disk.

        Args:
            checkpoint_id: ID of the checkpoint to load.

        Returns:
            Loaded Checkpoint or None if not found.
        """
        checkpoint_dir = Path(self.config.checkpoint_dir)
        filepath = checkpoint_dir / f"{checkpoint_id}.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Convert datetime strings
            if "created_at" in data and isinstance(data["created_at"], str):
                data["created_at"] = datetime.fromisoformat(data["created_at"])

            return Checkpoint(**data)
        except Exception:
            return None

    def load_latest_for_batch(self, batch_id: str) -> Checkpoint | None:
        """Load the most recent checkpoint for a batch.

        Args:
            batch_id: ID of the batch.

        Returns:
            Most recent Checkpoint for the batch or None.
        """
        checkpoint_dir = Path(self.config.checkpoint_dir)
        if not checkpoint_dir.exists():
            return None

        latest: Checkpoint | None = None
        latest_time: datetime | None = None

        for filepath in checkpoint_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if data.get("batch_id") != batch_id:
                    continue

                created_at = data.get("created_at")
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)

                if latest_time is None or created_at > latest_time:
                    # Convert datetime strings
                    if "created_at" in data and isinstance(data["created_at"], str):
                        data["created_at"] = datetime.fromisoformat(data["created_at"])

                    latest = Checkpoint(**data)
                    latest_time = created_at

            except Exception:
                continue

        return latest

    def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: ID of the checkpoint to delete.

        Returns:
            True if deletion was successful.
        """
        checkpoint_dir = Path(self.config.checkpoint_dir)
        filepath = checkpoint_dir / f"{checkpoint_id}.json"

        if filepath.exists():
            try:
                filepath.unlink()
                return True
            except Exception:
                return False
        return False

    def delete_for_batch(self, batch_id: str) -> int:
        """Delete all checkpoints for a batch.

        Args:
            batch_id: ID of the batch.

        Returns:
            Number of checkpoints deleted.
        """
        checkpoint_dir = Path(self.config.checkpoint_dir)
        if not checkpoint_dir.exists():
            return 0

        deleted = 0
        for filepath in checkpoint_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if data.get("batch_id") == batch_id:
                    filepath.unlink()
                    deleted += 1

            except Exception:
                continue

        return deleted

    def list_checkpoints(self, batch_id: str | None = None) -> list[dict[str, Any]]:
        """List all checkpoints, optionally filtered by batch.

        Args:
            batch_id: Optional batch ID to filter by.

        Returns:
            List of checkpoint summaries.
        """
        checkpoint_dir = Path(self.config.checkpoint_dir)
        if not checkpoint_dir.exists():
            return []

        checkpoints = []
        for filepath in checkpoint_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if batch_id is not None and data.get("batch_id") != batch_id:
                    continue

                checkpoints.append({
                    "id": data.get("id"),
                    "batch_id": data.get("batch_id"),
                    "position": data.get("position"),
                    "created_at": data.get("created_at"),
                    "filepath": str(filepath),
                })

            except Exception:
                continue

        # Sort by creation time (newest first)
        checkpoints.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return checkpoints

    def create_start_checkpoint(
        self,
        batch_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """Create and save a start checkpoint.

        Args:
            batch_id: ID of the batch.
            metadata: Optional metadata.

        Returns:
            Created Checkpoint.
        """
        checkpoint = Checkpoint.create_start(
            batch_id=batch_id,
            metadata=metadata,
        )
        self.save(checkpoint)
        return checkpoint

    def create_progress_checkpoint(
        self,
        batch_id: str,
        position: int,
        partial_results: dict[str, Any],
        validation_context: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """Create and save a progress checkpoint.

        Args:
            batch_id: ID of the batch.
            position: Current record position.
            partial_results: Partial results collected so far.
            validation_context: Current validation context.
            metadata: Optional metadata.

        Returns:
            Created Checkpoint.
        """
        checkpoint = Checkpoint.create_progress(
            batch_id=batch_id,
            position=position,
            partial_results=partial_results,
            validation_context=validation_context,
            metadata=metadata,
        )
        self.save(checkpoint)
        return checkpoint

    def _cleanup_old_checkpoints(self) -> int:
        """Remove old checkpoints beyond the retention limit.

        Returns:
            Number of checkpoints removed.
        """
        checkpoint_dir = Path(self.config.checkpoint_dir)
        if not checkpoint_dir.exists():
            return 0

        # Get all checkpoint files with their modification times
        checkpoints = []
        for filepath in checkpoint_dir.glob("*.json"):
            try:
                stat = filepath.stat()
                checkpoints.append((filepath, stat.st_mtime))
            except Exception:
                continue

        # Sort by modification time (oldest first)
        checkpoints.sort(key=lambda x: x[1])

        # Remove oldest checkpoints if over limit
        removed = 0
        while len(checkpoints) > self.config.max_checkpoints:
            filepath, _ = checkpoints.pop(0)
            try:
                filepath.unlink()
                removed += 1
            except Exception:
                pass

        return removed
