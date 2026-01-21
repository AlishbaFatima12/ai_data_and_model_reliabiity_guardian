"""Silver Tier Contract Checksum Skill.

Verifies contract integrity via SHA-256 hashing:
- SC-008: Contract hash mismatch
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.schema_contract import SchemaContract
from src.models.silver_anomaly import SchemaAnomaly, ViolationDetail

logger = structlog.get_logger(__name__)


class ContractVerificationResult:
    """Result of contract verification."""

    def __init__(self) -> None:
        self.passed: bool = True
        self.anomalies: list[SchemaAnomaly] = []
        self.computed_hash: str = ""
        self.expected_hash: str = ""

    def add_anomaly(self, anomaly: SchemaAnomaly) -> None:
        """Add an anomaly to the result."""
        self.anomalies.append(anomaly)
        self.passed = False


def compute_contract_hash(contract: SchemaContract) -> str:
    """Compute deterministic SHA-256 hash of a contract.

    Hash includes: id, version, source, columns (names, types, constraints).
    Hash excludes: timestamps, descriptions, metadata.

    Args:
        contract: The schema contract to hash.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    return contract.compute_hash()


def compute_schema_hash(schema: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of a raw JSON schema.

    Args:
        schema: JSON Schema dictionary.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    # Extract only structural elements for hashing
    hash_data = {
        "type": schema.get("type", "object"),
        "properties": {},
        "required": sorted(schema.get("required", [])),
        "additionalProperties": schema.get("additionalProperties", True),
    }

    # Process properties
    for prop_name, prop_schema in schema.get("properties", {}).items():
        hash_data["properties"][prop_name] = {
            "type": prop_schema.get("type"),
            "format": prop_schema.get("format"),
            "minLength": prop_schema.get("minLength"),
            "maxLength": prop_schema.get("maxLength"),
            "minimum": prop_schema.get("minimum"),
            "maximum": prop_schema.get("maximum"),
            "pattern": prop_schema.get("pattern"),
            "enum": prop_schema.get("enum"),
        }
        # Remove None values
        hash_data["properties"][prop_name] = {
            k: v for k, v in hash_data["properties"][prop_name].items() if v is not None
        }

    # Sort properties by name for deterministic hash
    hash_data["properties"] = dict(sorted(hash_data["properties"].items()))

    # Compute hash
    canonical = json.dumps(hash_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_contract_hash(
    data_contract_hash: str,
    registered_hash: str,
    contract_id: str,
    contract_version: str,
    batch_id: str,
) -> ContractVerificationResult:
    """Verify a contract hash matches the registered hash.

    Detects SC-008 (contract hash mismatch).

    Args:
        data_contract_hash: Hash from the incoming data's contract.
        registered_hash: Hash registered in the schema registry.
        contract_id: The contract identifier.
        contract_version: The contract version.
        batch_id: ID of the batch being validated.

    Returns:
        ContractVerificationResult with verification status.
    """
    result = ContractVerificationResult()
    result.computed_hash = data_contract_hash
    result.expected_hash = registered_hash

    if data_contract_hash != registered_hash:
        now = datetime.now(timezone.utc)

        anomaly = SchemaAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.CONTRACT_HASH_MISMATCH,
            severity=SeverityLevel.CRITICAL,
            contract_id=contract_id,
            contract_version=contract_version,
            affected_columns=[],
            violation_details=[
                ViolationDetail(
                    column="__contract_hash__",
                    issue="Contract hash mismatch",
                    expected=registered_hash[:16] + "...",
                    actual=data_contract_hash[:16] + "...",
                )
            ],
            batch_id=batch_id,
            timestamp=now,
            explanation=(
                f"Contract hash mismatch for {contract_id} v{contract_version}. "
                f"Expected {registered_hash[:16]}..., got {data_contract_hash[:16]}..."
            ),
            blocking=True,
        )
        result.add_anomaly(anomaly)

        logger.warning(
            "contract_hash_mismatch",
            contract_id=contract_id,
            contract_version=contract_version,
            expected_hash=registered_hash[:16],
            actual_hash=data_contract_hash[:16],
        )
    else:
        logger.debug(
            "contract_hash_verified",
            contract_id=contract_id,
            contract_version=contract_version,
            hash=data_contract_hash[:16],
        )

    return result


def verify_contract(
    current_contract: SchemaContract,
    registered_contract: SchemaContract,
    batch_id: str,
) -> ContractVerificationResult:
    """Verify a contract against its registered version.

    Args:
        current_contract: The contract to verify.
        registered_contract: The registered reference contract.
        batch_id: ID of the batch being validated.

    Returns:
        ContractVerificationResult with verification status.
    """
    current_hash = current_contract.contract_hash
    registered_hash = registered_contract.contract_hash

    return verify_contract_hash(
        data_contract_hash=current_hash,
        registered_hash=registered_hash,
        contract_id=current_contract.id,
        contract_version=current_contract.version,
        batch_id=batch_id,
    )


class ContractRegistry:
    """Simple in-memory contract registry for hash management.

    Note: For production use, this should be replaced with
    a persistent storage backend (database, file-based, etc.).
    """

    def __init__(self) -> None:
        self._contracts: dict[str, SchemaContract] = {}  # id:version -> contract
        self._hashes: dict[str, str] = {}  # id:version -> hash
        self._history: dict[str, list[str]] = {}  # id -> [versions]

    def register(self, contract: SchemaContract) -> str:
        """Register a contract and return its hash.

        Args:
            contract: The contract to register.

        Returns:
            The contract hash.
        """
        key = f"{contract.id}:{contract.version}"
        contract_hash = contract.contract_hash

        self._contracts[key] = contract
        self._hashes[key] = contract_hash

        # Track version history
        if contract.id not in self._history:
            self._history[contract.id] = []
        if contract.version not in self._history[contract.id]:
            self._history[contract.id].append(contract.version)
            self._history[contract.id].sort(key=_parse_version)

        logger.info(
            "contract_registered",
            contract_id=contract.id,
            version=contract.version,
            hash=contract_hash[:16],
        )

        return contract_hash

    def get(self, contract_id: str, version: str) -> SchemaContract | None:
        """Get a registered contract.

        Args:
            contract_id: The contract identifier.
            version: The contract version.

        Returns:
            The contract or None if not found.
        """
        key = f"{contract_id}:{version}"
        return self._contracts.get(key)

    def get_hash(self, contract_id: str, version: str) -> str | None:
        """Get the registered hash for a contract.

        Args:
            contract_id: The contract identifier.
            version: The contract version.

        Returns:
            The hash or None if not found.
        """
        key = f"{contract_id}:{version}"
        return self._hashes.get(key)

    def get_versions(self, contract_id: str) -> list[str]:
        """Get all versions of a contract.

        Args:
            contract_id: The contract identifier.

        Returns:
            List of version strings.
        """
        return self._history.get(contract_id, [])

    def get_latest(self, contract_id: str) -> SchemaContract | None:
        """Get the latest version of a contract.

        Args:
            contract_id: The contract identifier.

        Returns:
            The latest contract or None if not found.
        """
        versions = self.get_versions(contract_id)
        if not versions:
            return None
        latest_version = versions[-1]
        return self.get(contract_id, latest_version)

    def verify(
        self, contract: SchemaContract, batch_id: str
    ) -> ContractVerificationResult:
        """Verify a contract against the registered version.

        Args:
            contract: The contract to verify.
            batch_id: ID of the batch being validated.

        Returns:
            ContractVerificationResult with verification status.
        """
        registered = self.get(contract.id, contract.version)
        if registered is None:
            # Contract not registered - this is also a problem
            result = ContractVerificationResult()
            result.computed_hash = contract.contract_hash
            result.expected_hash = ""

            anomaly = SchemaAnomaly(
                id=str(uuid4()),
                failure_code=FailureCode.CONTRACT_HASH_MISMATCH,
                severity=SeverityLevel.CRITICAL,
                contract_id=contract.id,
                contract_version=contract.version,
                affected_columns=[],
                violation_details=[
                    ViolationDetail(
                        column="__contract__",
                        issue="Contract not registered",
                        expected="registered",
                        actual="not found",
                    )
                ],
                batch_id=batch_id,
                timestamp=datetime.now(timezone.utc),
                explanation=f"Contract {contract.id} v{contract.version} is not registered",
                blocking=True,
            )
            result.add_anomaly(anomaly)
            return result

        return verify_contract(contract, registered, batch_id)


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse version string for sorting."""
    try:
        return tuple(int(p) for p in version.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)
