"""Bronze quarantine skill - Record isolation."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.models.anomaly import Anomaly
from src.lib.constants import SeverityLevel
from src.lib.logger import get_logger


class QuarantineConfig(BaseModel):
    """Configuration for quarantine skill."""

    quarantine_dir: str = Field(
        default="data/quarantine",
        description="Directory for quarantined records",
    )
    preserve_original: bool = Field(
        default=True,
        description="Whether to preserve original record data",
    )


class QuarantineRecord(BaseModel):
    """A quarantined record with metadata."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    batch_id: str
    record_index: int
    record_data: dict[str, Any]
    anomaly_ids: list[str] = Field(default_factory=list)
    failure_codes: list[str] = Field(default_factory=list)
    quarantine_reason: str
    quarantined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QuarantineResult(BaseModel):
    """Result of quarantine operation."""

    quarantined_count: int = 0
    quarantine_ids: list[str] = Field(default_factory=list)
    skipped_count: int = 0


class QuarantineSkill:
    """Bronze skill for isolating invalid records (FR-016, FR-017).

    Quarantines records with CRITICAL severity while preserving originals.
    """

    name: str = "bronze.quarantine"

    def __init__(self, config: QuarantineConfig | None = None):
        """Initialize the quarantine skill.

        Args:
            config: Configuration for quarantine handling.
        """
        self.config = config or QuarantineConfig()
        self._logger = get_logger("bronze.quarantine")

    def quarantine_records(
        self,
        records: list[dict[str, Any]],
        anomalies: list[Anomaly],
        batch_id: str,
    ) -> QuarantineResult:
        """Quarantine records affected by CRITICAL anomalies.

        Args:
            records: All records in the batch.
            anomalies: Detected anomalies.
            batch_id: ID of the batch.

        Returns:
            QuarantineResult with operation outcome.
        """
        # Find records to quarantine (only CRITICAL severity)
        records_to_quarantine: dict[int, list[Anomaly]] = {}

        for anomaly in anomalies:
            if anomaly.severity != SeverityLevel.CRITICAL:
                continue

            for idx in anomaly.affected_records:
                if idx not in records_to_quarantine:
                    records_to_quarantine[idx] = []
                records_to_quarantine[idx].append(anomaly)

        if not records_to_quarantine:
            return QuarantineResult()

        # Create quarantine directory
        quarantine_dir = Path(self.config.quarantine_dir)
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        quarantine_ids: list[str] = []
        skipped = 0

        for idx, anomaly_list in records_to_quarantine.items():
            if idx >= len(records):
                skipped += 1
                continue

            record = records[idx]
            q_record = self._create_quarantine_record(
                batch_id=batch_id,
                record_index=idx,
                record_data=record,
                anomalies=anomaly_list,
            )

            if self._save_quarantine_record(q_record):
                quarantine_ids.append(q_record.id)
                self._logger.info(
                    "record_quarantined",
                    quarantine_id=q_record.id,
                    batch_id=batch_id,
                    record_index=idx,
                    failure_codes=q_record.failure_codes,
                )
            else:
                skipped += 1

        return QuarantineResult(
            quarantined_count=len(quarantine_ids),
            quarantine_ids=quarantine_ids,
            skipped_count=skipped,
        )

    def _create_quarantine_record(
        self,
        batch_id: str,
        record_index: int,
        record_data: dict[str, Any],
        anomalies: list[Anomaly],
    ) -> QuarantineRecord:
        """Create a quarantine record from anomaly data.

        Args:
            batch_id: ID of the batch.
            record_index: Index of the record.
            record_data: The actual record data.
            anomalies: Anomalies affecting this record.

        Returns:
            QuarantineRecord instance.
        """
        failure_codes = list(set(a.failure_code.value for a in anomalies))
        anomaly_ids = [a.id for a in anomalies]
        reasons = [a.root_cause for a in anomalies]

        return QuarantineRecord(
            batch_id=batch_id,
            record_index=record_index,
            record_data=record_data if self.config.preserve_original else {},
            anomaly_ids=anomaly_ids,
            failure_codes=failure_codes,
            quarantine_reason="; ".join(reasons),
        )

    def _save_quarantine_record(self, record: QuarantineRecord) -> bool:
        """Save a quarantine record to disk.

        Args:
            record: QuarantineRecord to save.

        Returns:
            True if save was successful.
        """
        quarantine_dir = Path(self.config.quarantine_dir)
        filepath = quarantine_dir / f"{record.id}.json"

        try:
            data = {
                "id": record.id,
                "batch_id": record.batch_id,
                "record_index": record.record_index,
                "record_data": record.record_data,
                "anomaly_ids": record.anomaly_ids,
                "failure_codes": record.failure_codes,
                "quarantine_reason": record.quarantine_reason,
                "quarantined_at": record.quarantined_at.isoformat(),
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            return True
        except Exception as e:
            self._logger.error("quarantine_save_failed", error=str(e), record_id=record.id)
            return False

    def get_quarantined_record(self, quarantine_id: str) -> QuarantineRecord | None:
        """Retrieve a quarantined record.

        Args:
            quarantine_id: ID of the quarantine record.

        Returns:
            QuarantineRecord or None if not found.
        """
        quarantine_dir = Path(self.config.quarantine_dir)
        filepath = quarantine_dir / f"{quarantine_id}.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            return QuarantineRecord(
                id=data["id"],
                batch_id=data["batch_id"],
                record_index=data["record_index"],
                record_data=data.get("record_data", {}),
                anomaly_ids=data.get("anomaly_ids", []),
                failure_codes=data.get("failure_codes", []),
                quarantine_reason=data.get("quarantine_reason", ""),
                quarantined_at=datetime.fromisoformat(data["quarantined_at"]),
            )
        except Exception:
            return None

    def list_quarantined(
        self,
        batch_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List quarantined records.

        Args:
            batch_id: Optional filter by batch ID.
            limit: Maximum records to return.

        Returns:
            List of quarantine record summaries.
        """
        quarantine_dir = Path(self.config.quarantine_dir)
        if not quarantine_dir.exists():
            return []

        records = []
        for filepath in quarantine_dir.glob("*.json"):
            if len(records) >= limit:
                break

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if batch_id and data.get("batch_id") != batch_id:
                    continue

                records.append({
                    "id": data.get("id"),
                    "batch_id": data.get("batch_id"),
                    "record_index": data.get("record_index"),
                    "failure_codes": data.get("failure_codes", []),
                    "quarantine_reason": data.get("quarantine_reason", ""),
                    "quarantined_at": data.get("quarantined_at"),
                })
            except Exception:
                continue

        # Sort by quarantine time (newest first)
        records.sort(key=lambda x: x.get("quarantined_at", ""), reverse=True)
        return records

    def release_record(self, quarantine_id: str) -> bool:
        """Release a record from quarantine (delete).

        Args:
            quarantine_id: ID of the quarantine record.

        Returns:
            True if release was successful.
        """
        quarantine_dir = Path(self.config.quarantine_dir)
        filepath = quarantine_dir / f"{quarantine_id}.json"

        if filepath.exists():
            try:
                filepath.unlink()
                self._logger.info("record_released", quarantine_id=quarantine_id)
                return True
            except Exception:
                return False
        return False

    def get_quarantine_stats(self) -> dict[str, Any]:
        """Get statistics about quarantined records.

        Returns:
            Dictionary with quarantine statistics.
        """
        quarantine_dir = Path(self.config.quarantine_dir)
        if not quarantine_dir.exists():
            return {"total": 0, "by_failure_code": {}, "by_batch": {}}

        total = 0
        by_failure_code: dict[str, int] = {}
        by_batch: dict[str, int] = {}

        for filepath in quarantine_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                total += 1

                batch_id = data.get("batch_id", "unknown")
                by_batch[batch_id] = by_batch.get(batch_id, 0) + 1

                for code in data.get("failure_codes", []):
                    by_failure_code[code] = by_failure_code.get(code, 0) + 1

            except Exception:
                continue

        return {
            "total": total,
            "by_failure_code": by_failure_code,
            "by_batch": by_batch,
        }
