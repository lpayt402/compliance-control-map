import json


def _matches(value: object, schema: dict[str, object]) -> bool:
    expected = schema.get("type")
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        if not isinstance(value, list):
            return False
        item_schema = schema.get("items", {})
        return isinstance(item_schema, dict) and all(_matches(item, item_schema) for item in value)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return False


def parse_structured_proposal(
    text: str,
    schema: dict[str, object],
    *,
    allowed_source_references: set[str],
) -> dict[str, object] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict) or schema.get("type") != "object":
        return None
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        return None
    if any(key not in value for key in required if isinstance(key, str)):
        return None
    if schema.get("additionalProperties") is False and set(value) - set(properties):
        return None
    for key, item in value.items():
        item_schema = properties.get(key)
        if not isinstance(item_schema, dict) or not _matches(item, item_schema):
            return None
    source_references = value.get("source_references")
    if not isinstance(source_references, list) or not source_references:
        return None
    if any(
        not isinstance(source_ref, str) or source_ref not in allowed_source_references
        for source_ref in source_references
    ):
        return None
    return value
