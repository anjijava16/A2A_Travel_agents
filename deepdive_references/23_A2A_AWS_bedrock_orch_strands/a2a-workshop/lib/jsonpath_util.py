#!/usr/bin/env python3
"""
Simple JSONPath Utility for Data Extraction

Supports basic JSONPath syntax for extracting data from nested dictionaries.
Used by workflow executor to map data between stages.

Supported Syntax:
    $.field_name - Access top-level field
    $.field.nested - Access nested field
    $.field[0] - Access array element (not commonly needed)
"""

from typing import Any

from lib.logger import get_logger

# Initialize logger for JSONPath operations
logger = get_logger(context={"component": "JSONPathUtil"})


def extract_jsonpath(data: dict[str, Any], path: str) -> Any:
    """
    Extract value from nested dictionary using JSONPath-like syntax.

    Args:
        data: Dictionary to extract from (typically stage_results)
        path: JSONPath string (e.g., "$.events_call.events")

    Returns:
        Extracted value, or None if path not found

    Examples:
        >>> data = {"events_call": {"events": [1, 2, 3], "count": 3}}
        >>> extract_jsonpath(data, "$.events_call.events")
        [1, 2, 3]
        >>> extract_jsonpath(data, "$.events_call.count")
        3
    """
    # Log extraction attempt with data structure preview
    data_preview = {}
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                data_preview[key] = f"<dict with {len(value)} keys>"
            elif isinstance(value, list):
                data_preview[key] = f"<list with {len(value)} items>"
            else:
                data_preview[key] = f"<{type(value).__name__}>"

    logger.debug(
        "🔍 JSONPath extraction attempt",
        extra={
            "path": path,
            "available_keys": list(data.keys()) if isinstance(data, dict) else "N/A",
            "data_structure": str(data_preview)[:200],
        },
    )

    if not path or not path.startswith("$."):
        logger.warning(
            "Invalid JSONPath syntax",
            extra={"path": path, "reason": "Must start with '$.'"},
        )
        return None

    # Remove leading "$."
    path = path[2:]

    # Split into parts
    parts = path.split(".")

    # Traverse the data structure
    current = data
    for idx, part in enumerate(parts):
        if current is None:
            logger.warning(
                "JSONPath extraction failed: intermediate value is None",
                extra={"path": path, "failed_at_part": part, "part_index": idx},
            )
            return None

        # Handle array indexing (e.g., "field[0]")
        if "[" in part and "]" in part:
            field_name = part[: part.index("[")]
            index_str = part[part.index("[") + 1 : part.index("]")]
            try:
                index = int(index_str)
                current = current.get(field_name, [])[index]
            except (KeyError, IndexError, ValueError) as e:
                logger.warning(
                    "JSONPath array access failed",
                    extra={
                        "path": path,
                        "field": field_name,
                        "index": index_str,
                        "error": str(e),
                    },
                )
                return None
        else:
            # Simple field access
            if isinstance(current, dict):
                if part not in current:
                    # Enhanced error message with suggestions
                    available_keys = list(current.keys())

                    # Find similar keys (simple string matching)
                    suggestions = [
                        k
                        for k in available_keys
                        if part.lower() in k.lower() or k.lower() in part.lower()
                    ]

                    error_extra = {
                        "path": path,
                        "missing_key": part,
                        "available_keys": available_keys,
                        "part_index": idx,
                    }

                    # Add suggestions if found
                    if suggestions:
                        error_extra["suggested_keys"] = suggestions
                        logger.warning(
                            f"JSONPath extraction failed: key '{part}' not found. Did you mean one of these? {suggestions}",
                            extra=error_extra,
                        )
                    else:
                        logger.warning(
                            f"JSONPath extraction failed: key '{part}' not found. Available keys: {available_keys}",
                            extra=error_extra,
                        )

                    return None
                current = current.get(part)
            else:
                logger.warning(
                    "JSONPath extraction failed: expected dict",
                    extra={
                        "path": path,
                        "expected": "dict",
                        "actual": type(current).__name__,
                        "part": part,
                        "part_index": idx,
                    },
                )
                return None

    # Log successful extraction with value preview
    value_preview = None
    if isinstance(current, list):
        value_preview = f"<list with {len(current)} items>"
    elif isinstance(current, dict):
        value_preview = f"<dict with {len(current)} keys>"
    else:
        value_preview = str(current)[:100]

    logger.debug(
        "✓ JSONPath extraction successful",
        extra={
            "path": path,
            "value_type": type(current).__name__,
            "value_preview": value_preview,
        },
    )

    return current


def build_mapped_input(
    stage_results: dict[str, Any],
    input_mapping: dict[str, str],
    fallback_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build input data for agent using input_mapping and stage results.

    Args:
        stage_results: Accumulated results from all previous stages
        input_mapping: Dictionary mapping target_field -> JSONPath
        fallback_data: Optional fallback data (e.g., user query) if extraction fails

    Returns:
        Dictionary with mapped fields

    Example:
        >>> stage_results = {
        ...     "events_call": {"events": [{"name": "Event1"}], "count": 1},
        ...     "coords_call": {"latitude": 47.6, "longitude": -122.3}
        ... }
        >>> input_mapping = {
        ...     "locations": "$.events_call.events",
        ...     "center_lat": "$.coords_call.latitude",
        ...     "center_lon": "$.coords_call.longitude"
        ... }
        >>> build_mapped_input(stage_results, input_mapping)
        {'locations': [{'name': 'Event1'}], 'center_lat': 47.6, 'center_lon': -122.3}
    """
    logger.debug(
        "📋 Building mapped input",
        extra={"input_mapping": input_mapping, "num_mappings": len(input_mapping)},
    )

    mapped_data = {}
    success_count = 0
    fallback_count = 0

    for target_field, source_value in input_mapping.items():
        # Check if this is a JSONPath expression or a literal value
        if isinstance(source_value, str) and source_value.startswith("$."):
            # This is a JSONPath expression - extract from stage_results
            value = extract_jsonpath(stage_results, source_value)

            if value is not None:
                mapped_data[target_field] = value
                success_count += 1

                # Log value preview
                if isinstance(value, list):
                    value_preview = f"<list with {len(value)} items>"
                elif isinstance(value, dict):
                    value_preview = f"<dict with {len(value)} keys>"
                else:
                    value_preview = str(value)[:100]

                logger.debug(
                    f"✓ Mapped {target_field}",
                    extra={
                        "source": source_value,
                        "type": "jsonpath",
                        "value_type": type(value).__name__,
                        "value_preview": value_preview,
                    },
                )
            elif fallback_data and target_field in fallback_data:
                # Try fallback if extraction failed
                mapped_data[target_field] = fallback_data[target_field]
                fallback_count += 1
                logger.debug(
                    f"⚠️  Mapped {target_field} using fallback",
                    extra={
                        "source": source_value,
                        "reason": "JSONPath extraction returned None",
                    },
                )
            else:
                logger.warning(
                    f"✗ Failed to map {target_field}",
                    extra={
                        "source": source_value,
                        "reason": "JSONPath extraction returned None and no fallback available",
                    },
                )
        else:
            # This is a LITERAL VALUE
            # Check if it's a JSON-encoded array/object and parse it
            # This handles cases where the LLM generates: "dietary_restrictions": "[\"vegan\"]"
            # instead of: "dietary_restrictions": ["vegan"]
            if isinstance(source_value, str) and (
                source_value.startswith('[') or source_value.startswith('{')
            ):
                try:
                    import json
                    parsed_value = json.loads(source_value)
                    mapped_data[target_field] = parsed_value
                    success_count += 1
                    logger.debug(
                        f"✓ Mapped {target_field} (parsed JSON)",
                        extra={
                            "source": source_value[:100],
                            "type": "literal_json",
                            "parsed_type": type(parsed_value).__name__,
                            "value": str(parsed_value)[:100],
                        },
                    )
                except json.JSONDecodeError:
                    # Not valid JSON, use as plain string (backward compatible)
                    mapped_data[target_field] = source_value
                    success_count += 1
                    logger.debug(
                        f"✓ Mapped {target_field}",
                        extra={
                            "source": source_value,
                            "type": "literal",
                            "value": source_value[:100],
                        },
                    )
            else:
                # Plain string or other literal value
                mapped_data[target_field] = source_value
                success_count += 1
                logger.debug(
                    f"✓ Mapped {target_field}",
                    extra={
                        "source": source_value,
                        "type": "literal",
                        "value": str(source_value)[:100],
                    },
                )

    logger.debug(
        "✓ Mapped input built",
        extra={
            "successful_mappings": success_count,
            "fallback_mappings": fallback_count,
            "failed_mappings": len(input_mapping) - success_count - fallback_count,
            "total_fields": len(mapped_data),
        },
    )

    return mapped_data
