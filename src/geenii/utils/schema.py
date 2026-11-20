"""Helpers to write JSON Schemas for tool parameters.

geenii passes a tool's `parameters` to the model unchanged, so each one must be a full object schema.

    params(
        path=string("File to read"),
        max_lines=integer("Lines to return"),
        required=["path"],
    )
"""

from collections.abc import Iterable


def string(description: str, **extra) -> dict:
    return {"type": "string", "description": description, **extra}


def integer(description: str, **extra) -> dict:
    return {"type": "integer", "description": description, **extra}


def number(description: str, **extra) -> dict:
    return {"type": "number", "description": description, **extra}


def boolean(description: str, **extra) -> dict:
    return {"type": "boolean", "description": description, **extra}


def array(items: dict, description: str, **extra) -> dict:
    return {"type": "array", "items": items, "description": description, **extra}


def params(*, required: Iterable[str] = (), **properties: dict) -> dict:
    """An object schema with the given properties. `required` names must be properties."""
    required = list(required)
    unknown = set(required) - properties.keys()
    if unknown:
        raise ValueError(f"Required parameters without a property: {sorted(unknown)}")
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema
