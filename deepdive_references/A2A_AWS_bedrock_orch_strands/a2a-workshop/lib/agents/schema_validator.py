#!/usr/bin/env python3
"""
Schema Validator for Agent Capabilities

Validates that agent capability schemas are complete and correct.
Catches schema issues at agent startup rather than during workflow execution.

Key Validations:
- input_schema has all required fields defined in properties
- output_schema is present and has properties
- Schema structure follows JSON Schema spec
- Field types are valid

Usage:
    from lib.agents.schema_validator import validate_capability_schema
from lib.logger import get_logger


logger = get_logger()

    result = validate_capability_schema(capability)
    if not result.is_valid:
        logger.error(f"Schema validation failed: {result.errors}")
"""

from enum import Enum
from typing import Any, NamedTuple


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""

    ERROR = "error"  # Must fix - will cause runtime failures
    WARNING = "warning"  # Should fix - may cause issues
    INFO = "info"  # Nice to have - best practice


class ValidationIssue(NamedTuple):
    """Represents a single validation issue"""

    severity: ValidationSeverity
    field_path: str
    message: str
    suggestion: str | None = None


class ValidationResult(NamedTuple):
    """Result of schema validation"""

    is_valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    info: list[ValidationIssue]

    @property
    def all_issues(self) -> list[ValidationIssue]:
        """Get all issues sorted by severity"""
        return self.errors + self.warnings + self.info

    def has_errors(self) -> bool:
        """Check if there are any errors"""
        return len(self.errors) > 0

    def summary(self) -> str:
        """Get human-readable summary"""
        if self.is_valid:
            return "✓ Schema validation passed"

        lines = ["✗ Schema validation failed:"]
        for issue in self.all_issues:
            icon = (
                "❌"
                if issue.severity == ValidationSeverity.ERROR
                else "⚠️" if issue.severity == ValidationSeverity.WARNING else "ℹ️"
            )
            lines.append(f"  {icon} {issue.field_path}: {issue.message}")
            if issue.suggestion:
                lines.append(f"      → {issue.suggestion}")
        return "\n".join(lines)


def validate_capability_schema(
    capability: dict[str, Any], strict: bool = False
) -> ValidationResult:
    """
    Validate agent capability schema.

    Args:
        capability: Agent capability dictionary with input_schema and output_schema
        strict: If True, treat warnings as errors

    Returns:
        ValidationResult with all validation issues

    Example:
        >>> capability = {
        ...     "id": "search-events",
        ...     "name": "Search Events",
        ...     "input_schema": {
        ...         "type": "object",
        ...         "required": ["location"],
        ...         "properties": {"location": {"type": "string"}}
        ...     },
        ...     "output_schema": {
        ...         "type": "object",
        ...         "properties": {"events": {"type": "array"}}
        ...     }
        ... }
        >>> result = validate_capability_schema(capability)
        >>> result.is_valid
        True
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    info: list[ValidationIssue] = []

    capability_id = capability.get("id", "unknown")

    # Check basic structure
    if "parameters" in capability:
        # New structure: schemas nested in parameters
        params = capability["parameters"]
        input_schema = params.get("input_schema")
        output_schema = params.get("output_schema")
    else:
        # Old structure: schemas at top level
        input_schema = capability.get("input_schema")
        output_schema = capability.get("output_schema")

    # Validate input_schema
    if input_schema:
        _validate_input_schema(input_schema, capability_id, errors, warnings, info)
    else:
        warnings.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                field_path=f"{capability_id}.input_schema",
                message="No input_schema defined",
                suggestion="Add input_schema to enable input_mapping for this capability",
            )
        )

    # Validate output_schema
    if output_schema:
        _validate_output_schema(output_schema, capability_id, errors, warnings, info)
    else:
        warnings.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                field_path=f"{capability_id}.output_schema",
                message="No output_schema defined",
                suggestion="Add output_schema so other agents can map data from this capability",
            )
        )

    # Check for common issues
    _check_common_issues(
        capability, input_schema, output_schema, capability_id, errors, warnings, info
    )

    # Determine overall validity
    is_valid = len(errors) == 0 and (not strict or len(warnings) == 0)

    return ValidationResult(
        is_valid=is_valid, errors=errors, warnings=warnings, info=info
    )


def _validate_input_schema(
    input_schema: dict[str, Any],
    capability_id: str,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
    info: list[ValidationIssue],
) -> None:
    """Validate input_schema structure and completeness"""

    # Check basic structure
    if not isinstance(input_schema, dict):
        errors.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                field_path=f"{capability_id}.input_schema",
                message="input_schema must be a dictionary",
                suggestion="Use JSON Schema format: {type: 'object', properties: {...}}",
            )
        )
        return

    # Check type
    schema_type = input_schema.get("type")
    if schema_type != "object":
        warnings.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                field_path=f"{capability_id}.input_schema.type",
                message=f"Expected type='object', got '{schema_type}'",
                suggestion="Most agent inputs are objects with named parameters",
            )
        )

    # Check properties
    properties = input_schema.get("properties", {})
    if not properties:
        warnings.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                field_path=f"{capability_id}.input_schema.properties",
                message="No properties defined",
                suggestion="Define expected input fields in properties",
            )
        )
        return

    # Check required fields
    required = input_schema.get("required", [])
    if not required:
        info.append(
            ValidationIssue(
                severity=ValidationSeverity.INFO,
                field_path=f"{capability_id}.input_schema.required",
                message="No required fields specified",
                suggestion="Specify which fields are required for this capability",
            )
        )
    else:
        # Validate all required fields exist in properties
        for field in required:
            if field not in properties:
                errors.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        field_path=f"{capability_id}.input_schema.required",
                        message=f"Required field '{field}' not defined in properties",
                        suggestion=f"Add '{field}' to properties or remove from required",
                    )
                )

    # Validate property definitions
    for prop_name, prop_def in properties.items():
        _validate_property_definition(
            prop_def,
            f"{capability_id}.input_schema.properties.{prop_name}",
            errors,
            warnings,
            info,
        )


def _validate_output_schema(
    output_schema: dict[str, Any],
    capability_id: str,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
    info: list[ValidationIssue],
) -> None:
    """Validate output_schema structure and completeness"""

    # Check basic structure
    if not isinstance(output_schema, dict):
        errors.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                field_path=f"{capability_id}.output_schema",
                message="output_schema must be a dictionary",
                suggestion="Use JSON Schema format: {type: 'object', properties: {...}}",
            )
        )
        return

    # Check type
    schema_type = output_schema.get("type")
    if schema_type != "object":
        warnings.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                field_path=f"{capability_id}.output_schema.type",
                message=f"Expected type='object', got '{schema_type}'",
                suggestion="Most agent outputs are objects with named fields",
            )
        )

    # Check properties
    properties = output_schema.get("properties", {})
    if not properties:
        warnings.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                field_path=f"{capability_id}.output_schema.properties",
                message="No properties defined",
                suggestion="Define output fields so other agents can map data from this capability",
            )
        )
        return

    # Validate property definitions
    for prop_name, prop_def in properties.items():
        _validate_property_definition(
            prop_def,
            f"{capability_id}.output_schema.properties.{prop_name}",
            errors,
            warnings,
            info,
        )


def _validate_property_definition(
    prop_def: dict[str, Any],
    field_path: str,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
    info: list[ValidationIssue],
) -> None:
    """Validate individual property definition"""

    if not isinstance(prop_def, dict):
        errors.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                field_path=field_path,
                message="Property definition must be a dictionary",
                suggestion="Use JSON Schema format: {type: 'string', description: '...'}",
            )
        )
        return

    # Check type field
    prop_type = prop_def.get("type")
    if not prop_type:
        warnings.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                field_path=f"{field_path}.type",
                message="Property has no type specified",
                suggestion="Add 'type' field (string, number, boolean, array, object)",
            )
        )
    else:
        valid_types = [
            "string",
            "number",
            "integer",
            "boolean",
            "array",
            "object",
            "null",
        ]
        if prop_type not in valid_types:
            errors.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field_path=f"{field_path}.type",
                    message=f"Invalid type '{prop_type}'",
                    suggestion=f"Use one of: {', '.join(valid_types)}",
                )
            )

    # Check description (best practice)
    if not prop_def.get("description"):
        info.append(
            ValidationIssue(
                severity=ValidationSeverity.INFO,
                field_path=f"{field_path}.description",
                message="No description provided",
                suggestion="Add description to help with mapping and documentation",
            )
        )

    # Validate array items
    if prop_type == "array":
        items = prop_def.get("items")
        if not items:
            warnings.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    field_path=f"{field_path}.items",
                    message="Array has no items definition",
                    suggestion="Define 'items' to specify array element structure",
                )
            )
        elif isinstance(items, dict):
            # Recursively validate nested structure
            _validate_property_definition(
                items, f"{field_path}.items", errors, warnings, info
            )

    # Validate object properties
    if prop_type == "object":
        nested_props = prop_def.get("properties")
        if not nested_props:
            info.append(
                ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    field_path=f"{field_path}.properties",
                    message="Object has no properties defined",
                    suggestion="Define 'properties' to specify object structure",
                )
            )
        elif isinstance(nested_props, dict):
            # Recursively validate nested properties
            for nested_name, nested_def in nested_props.items():
                _validate_property_definition(
                    nested_def,
                    f"{field_path}.properties.{nested_name}",
                    errors,
                    warnings,
                    info,
                )


def _check_common_issues(
    capability: dict[str, Any],
    input_schema: dict[str, Any] | None,
    output_schema: dict[str, Any] | None,
    capability_id: str,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
    info: list[ValidationIssue],
) -> None:
    """Check for common schema issues and anti-patterns"""

    # Check if capability can be used in input_mapping
    if output_schema:
        props = output_schema.get("properties", {})
        if props:
            # Check for generic field names (potential issues)
            generic_names = ["data", "result", "output", "response"]
            for name in generic_names:
                if name in props:
                    info.append(
                        ValidationIssue(
                            severity=ValidationSeverity.INFO,
                            field_path=f"{capability_id}.output_schema.properties.{name}",
                            message=f"Generic field name '{name}' found",
                            suggestion="Consider more descriptive name (e.g., 'events', 'locations', 'weather_data')",
                        )
                    )

            # Check for location data completeness
            has_lat = any("lat" in k.lower() for k in props.keys())
            has_lon = any("lon" in k.lower() for k in props.keys())
            if has_lat != has_lon:
                warnings.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        field_path=f"{capability_id}.output_schema.properties",
                        message="Incomplete location data (has lat but not lon, or vice versa)",
                        suggestion="Include both latitude and longitude for location-based data",
                    )
                )


def validate_agent_capabilities(
    capabilities: list[dict[str, Any]],
    agent_name: str = "unknown",
    strict: bool = False,
) -> dict[str, ValidationResult]:
    """
    Validate all capabilities for an agent.

    Args:
        capabilities: List of capability dictionaries
        agent_name: Name of agent (for logging)
        strict: If True, treat warnings as errors

    Returns:
        Dictionary mapping capability_id -> ValidationResult

    Example:
        >>> capabilities = [
        ...     {"id": "cap1", "input_schema": {...}, "output_schema": {...}},
        ...     {"id": "cap2", "input_schema": {...}, "output_schema": {...}}
        ... ]
        >>> results = validate_agent_capabilities(capabilities, "test-agent")
        >>> all(r.is_valid for r in results.values())
        True
    """
    results = {}

    for capability in capabilities:
        cap_id = capability.get("id", capability.get("name", "unknown"))
        result = validate_capability_schema(capability, strict=strict)
        results[cap_id] = result

    return results


def print_validation_results(
    results: dict[str, ValidationResult], agent_name: str = "unknown"
) -> None:
    """
    Print validation results in human-readable format.

    Args:
        results: Dictionary of capability_id -> ValidationResult
        agent_name: Name of agent being validated
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"Schema Validation Report: {agent_name}")
    logger.info(f"{'='*70}\n")

    total_caps = len(results)
    valid_caps = sum(1 for r in results.values() if r.is_valid)

    logger.info(f"Total Capabilities: {total_caps}")
    logger.info(f"Valid: {valid_caps}")
    logger.info(f"Invalid: {total_caps - valid_caps}\n")

    for cap_id, result in results.items():
        logger.info(f"\n{cap_id}:")
        logger.info(result.summary())

    logger.info(f"\n{'='*70}\n")


if __name__ == "__main__":
    # Example usage and testing
    logger.info("Schema Validator - Example Usage\n")

    # Example 1: Valid schema
    valid_capability = {
        "id": "search-events",
        "name": "Search Events",
        "parameters": {
            "input_schema": {
                "type": "object",
                "required": ["location"],
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                    "max_results": {"type": "number", "description": "Max results"},
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "latitude": {"type": "number"},
                                "longitude": {"type": "number"},
                            },
                        },
                    },
                    "total_count": {"type": "number"},
                },
            },
        },
    }

    result = validate_capability_schema(valid_capability)
    logger.info("Example 1: Valid Schema")
    logger.info(result.summary())
    logger.info()

    # Example 2: Invalid schema (missing required field in properties)
    invalid_capability = {
        "id": "bad-search",
        "parameters": {
            "input_schema": {
                "type": "object",
                "required": [
                    "location",
                    "missing_field",
                ],  # missing_field not in properties!
                "properties": {"location": {"type": "string"}},
            }
        },
    }

    result = validate_capability_schema(invalid_capability)
    logger.info("Example 2: Invalid Schema")
    logger.info(result.summary())
