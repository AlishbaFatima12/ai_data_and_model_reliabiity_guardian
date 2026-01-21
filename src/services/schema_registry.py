"""Schema Registry service for loading and managing schema contracts.

Provides loading, caching, and versioning of JSON Schema contracts.
"""

import json
from pathlib import Path
from typing import Any

import structlog

from src.models.schema_contract import SchemaContract

logger = structlog.get_logger(__name__)


class SchemaRegistry:
    """Registry for managing schema contracts.

    Loads schemas from config/schemas/ directory and provides
    lookup, versioning, and caching functionality.
    """

    def __init__(self, schema_dir: Path | None = None) -> None:
        """Initialize the schema registry.

        Args:
            schema_dir: Directory containing JSON schema files.
        """
        self.schema_dir = schema_dir or Path("config/schemas")
        self._schemas: dict[str, dict[str, SchemaContract]] = {}  # id -> version -> contract
        self._hashes: dict[str, str] = {}  # contract_id:version -> hash
        self._loaded = False

        logger.info("schema_registry_initialized", schema_dir=str(self.schema_dir))

    def load_schemas(self) -> int:
        """Load all schemas from the schema directory.

        Returns:
            Number of schemas loaded.
        """
        if not self.schema_dir.exists():
            logger.warning("schema_dir_not_found", path=str(self.schema_dir))
            return 0

        count = 0
        for schema_file in self.schema_dir.glob("*.json"):
            try:
                contract = self._load_schema_file(schema_file)
                if contract:
                    self._register_contract(contract)
                    count += 1
            except Exception as e:
                logger.error(
                    "schema_load_error",
                    file=str(schema_file),
                    error=str(e),
                )

        self._loaded = True
        logger.info("schemas_loaded", count=count)
        return count

    def _load_schema_file(self, path: Path) -> SchemaContract | None:
        """Load a schema contract from a JSON file.

        Args:
            path: Path to the JSON schema file.

        Returns:
            SchemaContract or None if loading fails.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extract metadata from file or schema
        contract_id = data.get("x-contract-id", path.stem)
        version = data.get("x-version", "1.0.0")
        source = data.get("x-source", path.stem)

        contract = SchemaContract.from_json_schema(
            schema=data,
            contract_id=contract_id,
            version=version,
            source=source,
        )

        logger.debug(
            "schema_file_loaded",
            file=str(path),
            contract_id=contract.id,
            version=contract.version,
        )

        return contract

    def _register_contract(self, contract: SchemaContract) -> None:
        """Register a contract in the registry.

        Args:
            contract: The contract to register.
        """
        if contract.id not in self._schemas:
            self._schemas[contract.id] = {}

        self._schemas[contract.id][contract.version] = contract
        self._hashes[f"{contract.id}:{contract.version}"] = contract.contract_hash

        logger.debug(
            "contract_registered",
            contract_id=contract.id,
            version=contract.version,
            hash=contract.contract_hash[:16],
        )

    def get_contract(
        self, contract_id: str, version: str | None = None
    ) -> SchemaContract | None:
        """Get a schema contract by ID and optional version.

        Args:
            contract_id: The contract identifier.
            version: Specific version, or None for latest.

        Returns:
            SchemaContract or None if not found.
        """
        if not self._loaded:
            self.load_schemas()

        if contract_id not in self._schemas:
            return None

        versions = self._schemas[contract_id]

        if version:
            return versions.get(version)

        # Return latest version
        if not versions:
            return None

        latest_version = max(versions.keys(), key=self._parse_version)
        return versions[latest_version]

    def get_contract_for_source(self, source: str) -> SchemaContract | None:
        """Get the schema contract for a data source.

        Args:
            source: The data source name.

        Returns:
            SchemaContract or None if not found.
        """
        if not self._loaded:
            self.load_schemas()

        for versions in self._schemas.values():
            for contract in versions.values():
                if contract.source == source:
                    return contract

        return None

    def get_contract_hash(self, contract_id: str, version: str) -> str | None:
        """Get the registered hash for a contract.

        Args:
            contract_id: The contract identifier.
            version: The contract version.

        Returns:
            Hex-encoded hash or None if not found.
        """
        return self._hashes.get(f"{contract_id}:{version}")

    def verify_hash(self, contract_id: str, version: str, hash_to_check: str) -> bool:
        """Verify a contract hash matches the registered hash.

        Args:
            contract_id: The contract identifier.
            version: The contract version.
            hash_to_check: The hash to verify.

        Returns:
            True if hashes match, False otherwise.
        """
        registered_hash = self.get_contract_hash(contract_id, version)
        if registered_hash is None:
            return False
        return registered_hash == hash_to_check

    def list_contracts(self) -> list[tuple[str, str]]:
        """List all registered contracts.

        Returns:
            List of (contract_id, version) tuples.
        """
        if not self._loaded:
            self.load_schemas()

        result = []
        for contract_id, versions in self._schemas.items():
            for version in versions:
                result.append((contract_id, version))
        return result

    def list_versions(self, contract_id: str) -> list[str]:
        """List all versions of a contract.

        Args:
            contract_id: The contract identifier.

        Returns:
            List of version strings, sorted newest first.
        """
        if not self._loaded:
            self.load_schemas()

        if contract_id not in self._schemas:
            return []

        versions = list(self._schemas[contract_id].keys())
        return sorted(versions, key=self._parse_version, reverse=True)

    def register_contract(self, contract: SchemaContract) -> None:
        """Manually register a contract (for testing or dynamic loading).

        Args:
            contract: The contract to register.
        """
        self._register_contract(contract)

    def reload(self) -> int:
        """Reload all schemas from disk.

        Returns:
            Number of schemas loaded.
        """
        self._schemas.clear()
        self._hashes.clear()
        self._loaded = False
        return self.load_schemas()

    @staticmethod
    def _parse_version(version: str) -> tuple[int, ...]:
        """Parse semantic version string to tuple for comparison.

        Args:
            version: Version string like "1.2.3".

        Returns:
            Tuple of integers for comparison.
        """
        try:
            parts = version.split(".")
            return tuple(int(p) for p in parts)
        except (ValueError, AttributeError):
            return (0, 0, 0)
